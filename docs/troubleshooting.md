# Troubleshooting and FAQ

Start with the symptom.

- [The result is blank](#the-result-is-blank)
- [The output file has no `_INTERP` columns / every result is blank](#the-output-file-has-no-_interp-columns--every-result-is-blank)
- [Some rows are missing from the output](#some-rows-are-missing-from-the-output)
- [I expected `S` but got `R` (or `R*`, `R!`)](#i-expected-s-but-got-r-or-r-r)
- [I expected `R*` / `R!` but got `R`](#i-expected-r--r-but-got-r)
- [`S?`, `R?`, `NS` — why not a plain category?](#s-r-ns--why-not-a-plain-category)
- [The E-test result differs from the broth MIC result](#the-e-test-result-differs-from-the-broth-mic-result)
- [My user-defined breakpoints are ignored](#my-user-defined-breakpoints-are-ignored)
- [My site-of-infection setting has no effect](#my-site-of-infection-setting-has-no-effect)
- [Expert rules do not fire / fire too often](#expert-rules-do-not-fire--fire-too-often)
- [EUCAST results are blank for some organisms](#eucast-results-are-blank-for-some-organisms)
- [Errors and tracebacks](#errors-and-tracebacks)
- [Performance](#performance)
- [FAQ](#faq)

---

## The result is blank

A blank interpretation means *no applicable breakpoint or rule*. Check, in order:

| Cause | How to check | Fix |
|---|---|---|
| Unknown organism code | `"zzz" in amrie.organism.CURRENT_ORGANISMS` | use the WHONET code (`eco`, not `E. coli` or `ECO`) |
| No breakpoint for that guideline and year | `get_applicable_breakpoints(org, [], ["CLSI"], [2026], None, None, ["AMP_ND10"])` is empty | use another year, guideline or a user-defined breakpoint |
| Breakpoint type excluded | your config has `["Human"]` and the drug is veterinary (`ENR`) | add `"Animal"` |
| Wrong potency | `AMP_ND2` vs `AMP_ND10` are different tests | use the potency the guideline publishes |
| Not a number | `"abc"`, `"+"`, `"pos"` | — |
| Disk value outside 6–80 mm | `5`, `81` | check the units |
| A user-defined drug without breakpoints | `X_3_NM` | add a user-defined breakpoint row |
| A EUCAST 2022+ PK/PD-only combination | see [below](#eucast-results-are-blank-for-some-organisms) | |

Ask the engine directly:

```python
from amrie.antibiotic_rules import AntibioticSpecificInterpretationRules as Rules
r = Rules("eco", "PEN_EM", "0.5", [], guideline_year=2026)
r.most_applicable_breakpoint, r.most_applicable_intrinsic     # (None, None) → nothing applies
```

---

## The output file has no `_INTERP` columns / every result is blank

1. **Wrong delimiter.** Passing `-d ";"` for a pipe file is not an error — each line
   becomes one column and nothing is recognised as an antibiotic. Check the first line
   of your file and pass the delimiter it uses.
2. **The header is not `ORGANISM`.** The column must be named exactly `ORGANISM`
   (upper case). `organism` or `Organism` → no interpretations.
3. **Columns are not WHONET test codes.** `Ampicillin` or `AMP` alone is not a test
   column; use `AMP_ND10`, `AMP_NM`, … ([Data formats](data-formats.md#whonet-antibiotic-column-names)).
4. **Leading BOM in an old version.** Since November 2026 a UTF-8 BOM is ignored; with
   older versions, re-save the file as UTF-8 without BOM.

---

## Some rows are missing from the output

Rows with **fewer fields than the header** are skipped (same as the C# engine). This
usually happens when a spreadsheet drops trailing empty cells:

```text
ORGANISM|AMP_ND10|CTX_ND30
eco|19|20        ← kept
eco|19           ← skipped: 2 fields, header has 3
eco|19|          ← kept: trailing empty field present
```

Blank lines are skipped too. Pad short rows with delimiters, or load the file with
pandas and write it back out (pandas always writes every column).

Multi-line quoted values (a comment containing a line break) are not supported;
remove line breaks inside cells.

---

## I expected `S` but got `R` (or `R*`, `R!`)

| Result | Meaning | Where to look |
|---|---|---|
| `R*` | an intrinsic resistance rule covers this organism + drug | [Intrinsic resistance](intrinsic-resistance.md) — e.g. *Klebsiella* × ampicillin |
| `R!` | an expert rule fired from another result on the isolate | [Expert rules](expert-rules.md) — e.g. MRS turns all β-lactams `R!` |
| `R` | the breakpoint says R | check which breakpoint was used (recipe below) — a site of infection, breakpoint year or rounding may explain it |

```python
r = Rules("spn", "PEN_NM", "0.12", [], guideline_year=2026,
          prioritized_sites_of_infection=["Meningitis", "Non-meningitis"])
r.get_interpretation(), r.most_applicable_breakpoint.SITE_OF_INFECTION    # ('R', 'Meningitis')
```

In file output without comments, `R*` and `R!` are written as `R` — turn on
`IncludeInterpretationComments` to see which kind it is.

---

## I expected `R*` / `R!` but got `R`

The suffixes are stripped from `amrie single`, `amrie file`, `interpret_file` and the
web/REST output unless `"IncludeInterpretationComments": true` (REST:
`"include_comments": true`). The Python function `interpret_single` always keeps them.

---

## `S?`, `R?`, `NS` — why not a plain category?

The measurement was censored (`<=`, `>`), so the true MIC could fall in more than one
category. `NS` = "not susceptible, I or R"; `S?` = "probably S but could be higher".
Ask the laboratory for the full dilution range or retest. Details:
[Concepts → censored MIC values](concepts.md#censored-mic-values).

---

## The E-test result differs from the broth MIC result

It should not for the same value — both are rounded the same way. If you compare an
unrounded broth value with a rounded E-test value, set `RoundHalfDilutions`
consistently. `0.75` is compared as `1` when rounding is on, for both `CIP_NM` and
`CIP_EM`.

---

## My user-defined breakpoints are ignored

```python
from amrie.config import read_configuration
len(read_configuration("my-config.json").user_defined_breakpoints)     # 0 → not loaded
```

| Cause | Fix |
|---|---|
| Relative path | relative paths are resolved against `src/amrie/` (the package), not your working directory — use an absolute path |
| Wrong case on Linux/macOS | the bundled folder is `resources`, not `Resources` |
| File does not exist | missing files are ignored silently (as in C#) — check the path |
| Key commented out | `DISABLED_UserDefinedBreakpointsFile` is ignored by design |
| Rows misaligned | every row needs the same number of tab-separated fields as the header; `YEAR` must be a number |
| Organism not covered | the row's `ORGANISM_CODE`/`ORGANISM_CODE_TYPE` must match your isolate (`EBC`/`FAMILY_CODE` for Enterobacterales) |
| Column mismatch | `WHONET_TEST` must equal the column (`X_1_NM`); E-test columns use the `…M` row |

---

## My site-of-infection setting has no effect

- Site names are **case-sensitive** and must match exactly: `Meningitis`, not
  `meningitis` or `CSF`. Unknown names are dropped silently.
- An empty list `[]` means "default order".
- Organism specificity ranks before site: a species-level breakpoint for another site
  beats a genus breakpoint for your site ([Breakpoint selection](breakpoint-selection.md#step-2-sort)).
- The drug may simply not have site-specific breakpoints.

Check what loaded: `read_configuration(...).prioritized_sites_of_infection[:3]`.

---

## Expert rules do not fire / fire too often

**Not firing**

- The rule is not enabled. In JSON, `[]` means *all* rules; `["MRS"]` means only MRS.
- The trigger column is missing or uses another value: `ESBL` must be `+`, `X_BLEE`
  must be `p`, `BETA_LACT` must be `-`.
- The organism is outside the rule's scope (MRS: *Staphylococcus*; ESBL:
  Enterobacterales; BLNAR: *H. influenzae*; ICR: staphylococci and streptococci).
- `interpret_single` sees one drug only; most rules need the whole isolate
  (`amrie file` or `IsolateInterpretation`).

**Firing unexpectedly**

- All rules are on when the key is absent or `[]`. List the ones you want, or
  `["NONE"]` for none.
- MRS row 2 fires on oxacillin **or** cefoxitin being NS — an `I` is enough.

**ESBL only changed a few drugs** — by design of the upstream rule data, the ESBL rules
affect only `MOX`, `CID`, `MAN` and `CFP` ([Expert rules](expert-rules.md#the-five-rules-at-a-glance)).

---

## EUCAST results are blank for some organisms

From 2022, EUCAST's general PK/PD breakpoints are stored as
`ORGANISM_CODE_TYPE=ALL`, `ORGANISM_CODE=Gen`. The C# engine (and therefore this port)
only uses `ALL`/`ALL` rows, which exist for EUCAST 2013–2020 and SFM 2020. So an
organism without a species-specific EUCAST 2022+ breakpoint is blank for drugs that
only have a PK/PD breakpoint:

```text
eco PEN_EM 0.5   GuidelineYear 2026 → (blank)
eco IMR_EM 1     GuidelineYear 2020 → S       (ALL/ALL PK/PD row)
```

Workaround: add the PK/PD rows you need as user-defined breakpoints with
`ORGANISM_CODE=ALL` and `ORGANISM_CODE_TYPE=ALL`.

---

## Errors and tracebacks

| Message | Cause | Fix |
|---|---|---|
| `Invalid value for '--delimiter' / '-d': Unsupported delimiter token…` | delimiter not TAB / `,` / `;` / `|` | pass one of those (quote `|` and `;` in the shell) |
| `HTTP 400 {"detail": "Unsupported delimiter token…"}` | same, REST | |
| `Missing option '--measurement' / '-m'` | CLI usage | see `amrie <command> --help` |
| `FileNotFoundError` | config or input path wrong | |
| `orjson.JSONDecodeError` | the config is not valid JSON (comments and trailing commas *are* allowed) | check quotes and commas |
| `KeyError: 'X_0_NM'` from `amrie single` | invalid test code (`X_0`, `X_01`, `X_100`, `PEN`) | use `X_1`–`X_99`, 3-letter drug codes, a guideline letter and a method |
| `ValueError: Invalid user-defined antibiotic test code …` | the same, from `AntibioticComponents` | |
| `ValueError: The antibiotic key '…' … cannot be resolved uniquely` | a modified `ExpectedResistancePhenotypes.txt` has an ambiguous `ABX_CODE` | fix that row's `ABX_CODE_TYPE` |
| `ValueError: invalid literal for int()` when loading breakpoints | a user-defined row has too many/few fields or a non-numeric `YEAR` | align the columns |

---

## Performance

| Situation | Expect |
|---|---|
| `import amrie` | ~1 s (loads ~80,000 reference rows) |
| one `amrie` CLI call | ~1 s, mostly the import |
| `amrie file` on the 622-isolate sample | a few seconds |
| repeated calls in one process | milliseconds (cached) |

Tips: keep one process alive (Python API or the web server) instead of calling the CLI
per result; load the configuration once; pass a loaded configuration rather than a
path to `interpret_single`.

---

## FAQ

**Is this a medical device?** No. It is for research, surveillance and informational
use. Verify against the official guideline documents before reporting patient results.

**Does it match the C# AMRIE exactly?** It is a port of upstream `99acabc` with the same
tables and algorithm; [upstream-sync.md](upstream-sync.md) lists the sync history and
the few deliberate differences (case-insensitive `TAB`, QC command, line-based input
reading).

**Which guideline year should I use?** The year your laboratory follows — usually the
current one (2026). Use older years only to reproduce historic reports.

**Can I get both CLSI and EUCAST results?** Yes — add columns for both
(`AMP_ND10` and `AMP_ED10`), or see [recipe 8](use-cases.md#8-compare-clsi-and-eucast-on-the-same-isolates).

**Where do the organism codes come from?** WHONET's `Organisms.txt`. Look them up with
`GET /api/organisms` or `amrie.organism.CURRENT_ORGANISMS`.

**How do I add a new year's breakpoints?** Take the new `Breakpoints.txt` from upstream
and follow [Development → updating resource files](development.md#updating-resource-tables).
