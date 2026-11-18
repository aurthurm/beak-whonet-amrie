# Development guide

- [Setup](#setup)
- [Running the tests](#running-the-tests)
- [The test suite](#the-test-suite)
- [Golden file](#golden-file)
- [Documentation examples are tests](#documentation-examples-are-tests)
- [Project layout](#project-layout)
- [Updating resource tables](#updating-resource-tables)
- [Porting an upstream change](#porting-an-upstream-change)
- [Checking parity against the C# engine](#checking-parity-against-the-c-engine)
- [Caches in tests](#caches-in-tests)
- [Coding conventions](#coding-conventions)
- [Dependencies](#dependencies)

---

## Setup

```bash
git clone https://github.com/aurthurm/beak-whonet-amrie.git
cd beak-whonet-amrie
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # engine, CLI, pytest
pip install -e ".[dev,web]"      # + NiceGUI web app
```

Without installing: prefix commands with `PYTHONPATH=src` (and `PYTHONPATH=src:.` for
the web package).

---

## Running the tests

```bash
pytest                                          # everything
pytest -q                                       # quiet
pytest -x                                       # stop at first failure
pytest tests/test_doc_examples.py -v            # one file
pytest tests/test_parity.py::TestGoldenFile     # one class
pytest -k "intrinsic or mrs"                    # by keyword
```

The whole suite takes under a minute.

---

## The test suite

| File | Covers |
|---|---|
| `test_parity.py` | hand-checked single interpretations, file mode, **golden file**, CLI, public API, vertical output, user-defined breakpoints, parallel vs sequential, intrinsic flag, expert rules, input validation |
| `test_qc.py` | QC range lookup, IN/OUT/blank, CLI `qc` |
| `test_doc_examples.py` | every result quoted in the README and `docs/` |
| `test_sync_breakpoint.py` | `ALL`-organism breakpoints, organism-code-type resolution (upstream `d752848`) |
| `test_sync_expected_resistance.py` | antibiotic-code-type resolution |
| `test_sync_rules.py` | cache keyed on the full selection, `RoundHalfDilutions` wiring, thread safety |
| `test_sync_user_defined.py` | `X_1`–`X_99` rules, `short_code`, `AntibioticComponents` (ported `UserDefinedAntibioticTests.cs`) |
| `test_sync_config.py` | `$schema`, comments, trailing commas, case-insensitive keys |
| `test_sync_io.py` | `split_line` / `to_line` edge cases, delimiter validation |
| `test_isolate_short_code.py` | expert-rule drug matching by exact short code (`OXA_SCREEN` regression) |
| `test_bounded_cache.py` | FIFO eviction, limits, statistics, concurrency |
| `test_web_helpers.py` | web display helper honours `include_comments` (skipped without the `[web]` extra) |

Fixtures in `tests/fixtures/`: `golden_sample_output.txt`, `esbl_config.json`,
`vertical_config.json`, `vertical_udb_config.json`.

---

## Golden file

`tests/fixtures/golden_sample_output.txt` is the output of
`resources/SampleInputFile.txt` (622 isolates) with `resources/SampleConfig.json`. Any
change to it means interpretations changed — intended or not.

To regenerate after a deliberate change:

```bash
rm tests/fixtures/golden_sample_output.txt
pytest tests/test_parity.py::TestGoldenFile      # creates the file and skips
pytest tests/test_parity.py::TestGoldenFile      # must pass
git diff --stat tests/fixtures/golden_sample_output.txt
```

Review the diff before committing: for each changed cell, you should be able to say
which upstream change caused it. Note the sample only has **CLSI** columns; changes to
EUCAST/SFM logic do not show up here — test them separately (see
[Checking parity](#checking-parity-against-the-c-engine) and the EUCAST re-coding trick
in [use cases](use-cases.md#8-compare-clsi-and-eucast-on-the-same-isolates)).

---

## Documentation examples are tests

`tests/test_doc_examples.py` asserts the results quoted in the docs (single results,
option effects, QC, expert-rule walkthroughs, file outputs). When you change a quoted
example in the docs, change the test, and vice versa. When a resource-table update
changes a result, the test tells you which page to update.

To execute every Python block in the docs as a smoke test:

```python
import pathlib, re
fence = "`" * 3
pattern = re.compile(fence + r"python\n(.*?)" + fence, re.S)
for md in pathlib.Path("docs").glob("*.md"):
    for block in pattern.findall(md.read_text(encoding="utf-8")):
        ...  # exec(block) in a scratch directory containing the sample files
```

---

## Project layout

```text
beak-whonet-amrie/
├── README.md
├── pyproject.toml              package metadata, `amrie` and `amrie-web` scripts
├── Dockerfile, docker-compose.yml
├── src/amrie/                  engine — see architecture.md
│   └── resources/              bundled tables (shipped as package data)
├── web/                        NiceGUI pages + FastAPI endpoints
├── tests/                      pytest suite + fixtures
└── docs/
    ├── index.md                documentation map
    ├── getting-started.md · concepts.md · use-cases.md · troubleshooting.md
    ├── python-api.md · cli-reference.md · configuration.md · data-formats.md · web.md
    ├── breakpoint-selection.md · intrinsic-resistance.md · expert-rules.md · quality-control.md
    ├── architecture.md · development.md · upstream-sync.md
    └── reference/amrie-config.schema.json
```

---

## Updating resource tables

The tables are upstream's `AMRIE.Library/Resources/*.txt`. To take a new version:

1. **Copy the file** from the upstream clone. Upstream files use **CRLF** line endings;
   keep them CRLF so `git diff` shows only real changes. If `git diff --stat` reports
   every line changed, the line endings differ.
2. **Check the header** — if columns were added or renamed, update the loader:

   | File | Loader |
   |---|---|
   | `Breakpoints.txt` | `breakpoint.load_breakpoints` |
   | `Organisms.txt` | `organism._load_all_organisms`, `_load_merged_organisms` |
   | `Antibiotics.txt` | `antibiotic._load_antibiotics` |
   | `ExpectedResistancePhenotypes.txt` | `expected_resistance._load_rules` |
   | `ExpertInterpretationRules.txt` | `expert_rule._load_expert_rules` |
   | `QC_Ranges.txt` | `qc.load_quality_control_ranges` |

3. **New breakpoint year?** Update `BREAKPOINT_TABLE_REVISION_YEAR` (and
   `BREAKPOINT_TABLE_REVISION_MINOR_CHANGE_NUMBER`) in `constants.py`, and the year in
   `SampleConfig.json` if upstream changed it.
4. **Check that load-time resolution still holds** — the sync tests assert the number of
   rows corrected (`test_sync_breakpoint.py`, `test_sync_expected_resistance.py`);
   new mislabelled rows change those counts. An ambiguous antibiotic code now raises at
   import — fix the row or report it upstream.
5. **Run the suite**, regenerate the golden file if needed, and update
   `test_doc_examples.py` and the docs for any example whose result changed.
6. **Record the sync** in [upstream-sync.md](upstream-sync.md).

---

## Porting an upstream change

1. List new upstream commits ([upstream-sync.md](upstream-sync.md#how-to-check-for-upstream-changes)).
2. Diff with rename detection and whitespace ignored — upstream often reformats:
   `git diff -M -w --ignore-cr-at-eol <last>..HEAD -- AMRIE.Library/`.
3. Find the Python module in the [mapping](architecture.md#c--python-mapping).
4. Port the change; keep names and structure close to the C# so the next diff is easy.
5. Port any new upstream tests (`AMRIE.Library.Tests/`) into `tests/test_sync_*.py`.
6. Measure the data impact (how many rows/results change) and write it in the sync log.

---

## Checking parity against the C# engine

Upstream targets plain `net10.0`, so its CLI builds and runs on Linux, macOS and
Windows with the .NET 10 SDK:

```bash
cd /path/to/AMRIE
dotnet build AMRIE.CLI/AMRIE.CLI.csproj -c Release -p:RunPostBuildEvent=Never
dotnet AMRIE.CLI/bin/Release/net10.0/AMRIE.CLI.dll FILE /path/SampleConfig.json "|" \
       /path/SampleInputFile.txt /tmp/csharp_out.txt
```

(`RunPostBuildEvent=Never` skips the Windows-only code-signing step.) Then run the same
input through `amrie file` and compare the interpretation columns. Upstream's
`AMRIE.Library.DataGenerator` produces an input file that exercises every breakpoint
and rule — the strongest parity fixture available.

---

## Caches in tests

The breakpoint and intrinsic caches live for the whole process. Because their keys
include every selection input, tests with different configurations do not interfere.
Clear them when you swap resource data at runtime:

```python
from amrie.antibiotic_rules import clear_breakpoints, cache_statistics
clear_breakpoints()          # empties both caches
cache_statistics()           # (breakpoint stats, intrinsic stats)
```

---

## Coding conventions

- Mirror the C# names in comments/docstrings ("Port of `Breakpoint.GetApplicableBreakpoints`").
- `from __future__ import annotations` at the top of every module; type hints
  everywhere (`str | None`, `list[str]`).
- Reference tables are module-level constants, built once and never mutated.
- Decimal arithmetic (`decimal.Decimal`) for measurements and breakpoints — never floats.
- Behaviour that intentionally differs from C# must be listed in
  [architecture.md → deliberate differences](architecture.md#deliberate-differences-from-c).
- Linting: `ruff check src tests web`.

---

## Dependencies

| Package | Why | Minimum |
|---|---|---|
| `pandas` | reading the resource tables | 2.0 |
| `typer` | CLI | 0.9 |
| `orjson` | JSON config parsing and JSON output | 3.9 |
| `nicegui` *(web)* | web UI + embedded FastAPI | 2.0 |
| `httpx` *(web)* | HTTP client | 0.27 |
| `pytest` *(dev)* | tests | 7.0 |

Python ≥ 3.10 (union types `X | Y`, built-in generics).
