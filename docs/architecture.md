# Architecture

AMRIE-py is a port of the C# engine
[WHONET-Development/AMRIE](https://github.com/WHONET-Development/AMRIE). The code
deliberately mirrors the C# structure file-for-file, so an upstream change can be
located and ported without re-architecting anything (see
[upstream sync](upstream-sync.md)).

- [Module map](#module-map)
- [Layers](#layers)
- [Start-up: loading the reference tables](#start-up-loading-the-reference-tables)
- [Interpreting one isolate](#interpreting-one-isolate)
- [Interpreting one measurement](#interpreting-one-measurement)
- [Batch pipeline](#batch-pipeline)
- [Caches](#caches)
- [Concurrency](#concurrency)
- [Text I/O](#text-io)
- [C# → Python mapping](#c--python-mapping)
- [Deliberate differences from C#](#deliberate-differences-from-c)
- [Web layer](#web-layer)

---

## Module map

```text
src/amrie/
├── __init__.py              public API: interpret_single · interpret_file · interpret_qc_single
├── cli.py                   `amrie` (Typer): file · single · qc
│
├── constants.py             interpretation codes, modifiers, delimiters, sites, organism groups
├── messages.py              user-facing strings (English)
├── paths.py                 resource directory resolution (C# SystemRootPath)
│
├── organism.py              Organisms.txt → ALL_ORGANISMS, CURRENT_ORGANISMS, MERGED_ORGANISMS
├── antibiotic.py            Antibiotics.txt → ALL_ANTIBIOTICS, CEPH3/MRS/ICR drug lists, short_code()
├── breakpoint.py            Breakpoints.txt → BREAKPOINTS; organism-code-type resolution;
│                            get_applicable_breakpoints()
├── expected_resistance.py   intrinsic rules; antibiotic-code-type resolution
├── expert_rule.py           expert rules; criteria evaluation
├── qc.py                    QC ranges and evaluation
│
├── parsing.py               AntibioticComponents, parse_result(), E-test rounding, column regexes
├── io_utils.py              split_line() / to_line() — quote-aware delimited text
├── bounded_cache.py         thread-safe FIFO cache with entry and key-size limits
├── antibiotic_rules.py      one measurement: intrinsic → breakpoint → category; the two caches
├── isolate.py               one isolate row: expert rules + every measurement
├── config.py                InterpretationConfiguration; tolerant JSON loader
├── io_library.py            batch: load_input_file → interpret_isolates → generate_output_file
│
└── resources/               the six reference tables + SampleConfig.json + samples
```

---

## Layers

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Entry points   amrie (__init__) · cli.py · web/ (NiceGUI + FastAPI)    │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│ Batch          io_library.py  load → preheat → interpret (threads) → write │
└───────────────┬──────────────────────────────────────────────────────┘
                │ one row
┌───────────────▼──────────────────────────────────────────────────────┐
│ Isolate        isolate.py  expert rules over the whole row             │
└───────┬───────────────────────────────┬──────────────────────────────┘
        │ one column                    │ rule lookup
┌───────▼──────────────────┐   ┌────────▼─────────────────────────────┐
│ Measurement               │   │ expert_rule.py                        │
│ antibiotic_rules.py       │   └──────────────────────────────────────┘
│  intrinsic → breakpoint   │
│  [bounded caches]         │
└───────┬──────────────────┘
        │
┌───────▼──────────────────────────────────────────────────────────────┐
│ Reference data (immutable, loaded at import)                          │
│ organism · antibiotic · breakpoint · expected_resistance · expert_rule · qc │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Start-up: loading the reference tables

Importing `amrie` loads every table once, at module import time, into immutable lists
and dicts (about one second in total):

| Order | Module | Table | Rows | Extra work |
|---|---|---|---:|---|
| 1 | `organism` | `Organisms.txt` | 2,980 | current-organism map (2,351), merged-code map (17) |
| 2 | `antibiotic` | `Antibiotics.txt` | 565 | CEPH3, MRS and ICR drug lists |
| 3 | `breakpoint` | `Breakpoints.txt` | 51,001 | organism-code-type resolution (index of codes per taxonomy level, memoised per code/type pair) |
| 4 | `expected_resistance` | `ExpectedResistancePhenotypes.txt` | 1,024 | antibiotic-code-type resolution |
| 5 | `expert_rule` | `ExpertInterpretationRules.txt` | 7 | criteria parsed, affected classes expanded to drug codes |
| 6 | `qc` | `QC_Ranges.txt` | 23,136 | |

Each loader reads with pandas (`dtype=str`, no NA conversion) and iterates rows as
plain tuples (`itertuples(name=None)`), indexing columns through a header map so the
column order in the file does not matter.

---

## Interpreting one isolate

`IsolateInterpretation(row, columns, enabled_rules, user_breakpoints, …)`:

```text
1. Antibiotic columns = columns matching VALID_ANTIBIOTIC_FIELD_NAME_REGEX that have a value.
   For each, create an AntibioticSpecificInterpretationRules (lazy).
2. Expert rules applicable to the organism and to the columns present
   (get_applicable_expert_rules, filtered by EnabledExpertInterpretationRules).
3. For each applicable rule:
     a. interpret the drugs its criteria name (exact short-code match; CEPH3 → any
        3rd-generation cephalosporin present);
     b. evaluate the criteria against those results and the non-antibiotic columns;
     c. if satisfied, every affected drug present in the row becomes "R!".
4. get_all_interpretations(): every remaining column is interpreted on its own.
```

---

## Interpreting one measurement

`AntibioticSpecificInterpretationRules(organism, test_column, raw, user_breakpoints, …)`:

```text
AntibioticComponents(test_column)        → drug code, guideline, method
parse_result(method, raw)                → (ok, value, modifier)   "≤2" → (2, "<=")
intrinsic cache (organism, guideline, drug) → ExpectedResistancePhenotypeRule | None
    (skipped when use_intrinsic_resistance_rules is False)
breakpoint cache (organism, guideline, year, selection key) → Breakpoint | None
    (only when the value parsed)

get_interpretation():
    intrinsic rule?      → "R*"
    no breakpoint?       → ""
    ECOFF breakpoint     → WT / NWT (/ "?")
    Human / Animal       → disk: compare zone with S/R
                           MIC:  optional rounding, then S/I/SDD/R/NS (/ "?")
```

---

## Batch pipeline

```text
load_input_file(path, delimiter)
    first non-blank line = header; rows split with split_line(); short rows skipped
        │
        ▼
_collect_distinct_interpretation_keys(rows)        {(organism, guideline, test column)}
        │
        ▼
preheat_breakpoint_cache(...)                      ThreadPoolExecutor
        │
        ▼
interpret_isolates(config, columns, rows)          ThreadPoolExecutor, results kept in input order
    IsolateInterpretation(row).get_all_interpretations()
        │
        ▼
generate_output_file(path, config, columns, results)
    horizontal: <col>, <col>_INTERP …   |   vertical: one row per measurement
    suffixes * and ! stripped unless IncludeInterpretationComments
```

`interpret_data_file(params)` (the CLI) wraps the four calls and reads the
configuration.

---

## Caches

Both caches live in `antibiotic_rules.py` and are
[`BoundedCache`](../src/amrie/bounded_cache.py) instances — a port of upstream
`BoundedCache.cs`.

| | Breakpoint cache | Intrinsic cache |
|---|---|---|
| Key | `(organism, guideline, year, (test column, breakpoint types, sites, user-defined breakpoint fingerprints))` | `(organism, guideline, drug code)` |
| Value | `Breakpoint` or `None` ("nothing applies" is cached too) | `ExpectedResistancePhenotypeRule` or `None` |
| Max entries | 262,144 | 131,072 |
| Max key characters | 16,777,216 | 4,194,304 |

Design points:

- **The key covers every input that changes the answer.** Two calls that differ only
  in breakpoint types, site order or user-defined breakpoints never share an entry,
  which matters for the web API, where every request may bring its own configuration.
  `None` and an empty list are distinct key values.
- **FIFO eviction** (oldest first), as in C#. Eviction only causes a recomputation;
  results never change. A key larger than the whole character budget is computed and
  returned without being stored (`uncached_keys`).
- **Compute outside the lock, store first-writer-wins.** C#'s `GetOrAdd` computes while
  holding the lock; the port looks up (`get`), computes without the lock, then `add`s.
  Parallel preheat threads therefore do not serialise on the slow part. If two threads
  compute the same key, both results are identical and the first one is kept.
- Statistics: `cache_statistics()`; reset: `clear_breakpoints()` (clears both).

---

## Concurrency

| Where | Mechanism |
|---|---|
| `preheat_breakpoint_cache` | `ThreadPoolExecutor`, `min(32, cpu + 4, keys)` workers |
| `interpret_isolates` | `ThreadPoolExecutor`; `parallel=False` for a sequential run (same results) |
| caches | one `threading.Lock` per `BoundedCache` |
| reference tables | immutable after import — no locking |
| web | engine work runs in `asyncio.to_thread` |

Threads (not processes) are used because the work is short lookups over shared
in-memory tables; process pools would have to copy the tables into each worker.

---

## Text I/O

- **Resource tables** — pandas `read_csv(sep="\t", dtype=str)`; headers mapped by name.
- **Input files** — read as UTF-8 with BOM stripping (`utf-8-sig`), split into lines,
  each line split by `split_line()` (port of the new C# `SplitLine`: `"…"` quoting,
  `""` escapes, whitespace after a closing quote ignored, unquoted fields trimmed).
  Lines are the record boundary, so a quoted value cannot contain a line break (the C#
  CsvReader allows it).
- **Output files** — UTF-8 without BOM, `\t`-separated, `\n` line ends, fields joined by
  `to_line()`, which quotes values containing the delimiter, a quote, CR/LF or
  leading/trailing whitespace.
- **Delimiters** — `Delimiters.parse_file_delimiter_token` / `validate_file_delimiter`
  accept TAB, `,`, `;`, `|` (port of C# `ParseFileDelimiterToken`).
- **Configuration** — a string-aware pre-processor strips `//` and `/* */` comments
  and trailing commas, then orjson parses; keys are matched case-insensitively.

---

## C# → Python mapping

Upstream paths are relative to the repository root at `99acabc`.

| C# (`AMRIE.Library/…`) | Python (`src/amrie/…`) |
|---|---|
| `Constants.cs` | `constants.py`, `paths.py` |
| `Antibiotic.cs` | `antibiotic.py` |
| `AntibioticComponents.cs` | `parsing.py` (`AntibioticComponents`) |
| `InterpretationLibrary.cs` | `parsing.py` (`parse_result`, rounding, regexes) |
| `Organism.cs` | `organism.py` |
| `Breakpoint.cs` | `breakpoint.py` |
| `ExpectedResistancePhenotypeRule.cs` | `expected_resistance.py` |
| `ExpertInterpretationRule.cs`, `ExpertRuleCriterion.cs` | `expert_rule.py` |
| `QualityControlRange.cs` | `qc.py` |
| `AntibioticSpecificInterpretationRules.cs` | `antibiotic_rules.py` |
| `BoundedCache.cs` | `bounded_cache.py` |
| `IsolateInterpretation.cs`, `SingleInterpretation.cs` | `isolate.py` |
| `InterpretationConfiguration.cs` | `config.py` |
| `IO_Library.cs` | `io_library.py`, `io_utils.py` |
| `FileInterpretationParameters.cs` | `io_library.py` (`FileInterpretationParameters`) |
| `Translations/Resources*.resx` | `messages.py` (English only) |
| `AMRIE.CLI/Program.cs` | `cli.py` |
| `AMRIE.Library.Tests/*` | `tests/test_sync_*.py` (ported assertions) |
| `Resources/*` | `resources/*` (identical content) |

Not ported: `AMRIE.WinForms`, `AMRIE.WinUI`, `AMRIE.Desktop` (GUIs — replaced by
`web/`), installers, `AMRIE.Library.DataGenerator`.

---

## Deliberate differences from C#

| Area | C# | Python port |
|---|---|---|
| `TAB` delimiter token | exact `TAB` | case-insensitive (`tab` works) |
| QC | range model only | `amrie qc`, `interpret_qc_single`, web page, REST |
| Input reader | CsvReader, quoted line breaks allowed | line-based `split_line`, no multi-line values |
| Cache fill | compute inside the lock | compute outside, first writer wins |
| File processing | bounded batches staged to temp files | whole file in memory |
| Messages | English, Spanish, French, Chinese | English |

Everything else — tables, selection algorithm, rule semantics, category logic — is
intended to be identical, and every upstream engine fix is ported (see
[upstream-sync.md](upstream-sync.md)).

---

## Web layer

`web/` is an independent package that only calls the engine:

```text
browser / HTTP ─► web/pages/* , web/api/* ─► web/helpers.py ─► amrie.*
```

See [web.md](web.md#architecture).
