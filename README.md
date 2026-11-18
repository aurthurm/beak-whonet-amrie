# AMRIE-py

**Antimicrobial Resistance Interpretation Engine — Python port**

AMRIE-py turns raw antimicrobial susceptibility test (AST) measurements — disk
diffusion zone diameters, MIC values and E-test strips — into clinical
categories (**S**, **I**, **SDD**, **R**, **NS**) and epidemiological categories
(**WT** / **NWT**), using the published breakpoints of **CLSI, EUCAST, SFM** and
other guidelines. On top of breakpoints it applies **intrinsic resistance rules**
("*Klebsiella* is always resistant to ampicillin") and **expert interpretation
rules** (MRSA, ESBL, BLNAR, inducible clindamycin resistance), and it can check
**QC reference-strain** results against acceptable ranges.

It is a faithful port of the WHONET team's C# engine
[**WHONET-Development/AMRIE**](https://github.com/WHONET-Development/AMRIE), kept
in sync commit by commit (currently upstream `99acabc`, see
[`docs/upstream-sync.md`](docs/upstream-sync.md)). Same resource tables, same
breakpoint-selection algorithm, same results — plus a Python API, a
cross-platform CLI, a web UI and a REST API.

```text
         eco   AMP_ND10   "19"           ─►  S      E. coli, ampicillin 10 µg disk, 19 mm
         kpn   AMP_ND10   "25"           ─►  R*     K. pneumoniae is intrinsically resistant
         sau   FOX_ND30   "15"  + MRS    ─►  R!     cefoxitin-resistant S. aureus ⇒ MRSA rule
         sau   CPT_ND30   "22"           ─►  SDD    ceftaroline, susceptible dose-dependent
         eco   AMP_NM     "<=16"         ─►  S?     censored MIC, category uncertain
  atcc25922   AMP_ND10   "18"   (QC)     ─►  IN     QC strain within acceptable range
```

> **Not a medical device.** AMRIE-py is provided for research, surveillance and
> informational use. Laboratories must verify breakpoints and rules against the
> current official CLSI / EUCAST / SFM documents before reporting patient results.

---

## Table of contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Five-minute tour](#five-minute-tour)
  - [1. One measurement from the command line](#1-one-measurement-from-the-command-line)
  - [2. A whole laboratory file](#2-a-whole-laboratory-file)
  - [3. From Python](#3-from-python)
  - [4. QC reference strains](#4-qc-reference-strains)
  - [5. Web UI and REST API](#5-web-ui-and-rest-api)
- [Reading the results](#reading-the-results)
- [WHONET codes in one minute](#whonet-codes-in-one-minute)
- [Configuration at a glance](#configuration-at-a-glance)
- [How an interpretation is made](#how-an-interpretation-is-made)
- [Bundled reference data](#bundled-reference-data)
- [Known limitations](#known-limitations)
- [Project layout](#project-layout)
- [Running the tests](#running-the-tests)
- [Documentation map](#documentation-map)
- [Keeping up with upstream](#keeping-up-with-upstream)
- [License and attribution](#license-and-attribution)

---

## Features

| Area | What you get |
|---|---|
| **Guidelines** | CLSI (27,017 breakpoints), EUCAST (22,360), SFM / CA-SFM (1,034), SRGA, BSAC, NEO, AFA and DIN; every year in the table (1998–2026) |
| **Test methods** | Disk diffusion (`D`), MIC (`M`), E-test (`E`, treated as MIC with optional half-dilution rounding) |
| **Breakpoint types** | Human, Animal (veterinary) and ECOFF (epidemiological cut-off) with configurable priority |
| **Sites of infection** | 31 sites (meningitis, UTI, endocarditis, oral, …) with a configurable priority order |
| **Intrinsic resistance** | 1,024 CLSI and EUCAST expected-resistance rules, including ATC-class rules (e.g. "all 1st-gen cephalosporins") |
| **Expert rules** | `MRS`, `ESBL-CONFIRMED`, `ESBL-AMPC-PROBABLE`, `BLNAR-HFLU`, `ICR` |
| **QC** | 23,136 CLSI / EUCAST QC ranges for reference strains such as *E. coli* ATCC 25922 |
| **Custom breakpoints** | User-defined breakpoint files and user-defined drug columns `X_1` … `X_99` |
| **Interfaces** | Python API, `amrie` CLI, NiceGUI web app and a FastAPI REST API with OpenAPI docs |
| **File handling** | TAB, `,`, `;` and `|` delimited input; RFC-style quoting; horizontal or vertical (long) output |
| **Performance** | Resource tables load in under a second; breakpoint lookups are cached (bounded FIFO caches) and pre-heated in parallel for batch files |

---

## Requirements

- **Python 3.10 or newer** (developed and tested on 3.13; the Docker image uses 3.11)
- Core dependencies, installed automatically: `pandas>=2.0`, `typer>=0.9`, `orjson>=3.9`
- Optional: `nicegui>=2.0` and `httpx>=0.27` for the web UI / REST API (`[web]` extra)
- Optional: `pytest>=7.0` for the test suite (`[dev]` extra)

No database, network access or .NET runtime is needed: all reference tables ship
inside the package (`src/amrie/resources/`).

---

## Installation

```bash
git clone https://github.com/aurthurm/beak-whonet-amrie.git
cd beak-whonet-amrie

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"            # engine + CLI + tests (editable)
pip install -e ".[dev,web]"        # …plus the web UI and REST API
pip install .                      # plain, non-editable install
```

Check that it works:

```bash
amrie --help
python -c "import amrie; print(amrie.__version__)"      # 1.0.0
```

Two console scripts are installed: **`amrie`** (CLI) and **`amrie-web`** (web server).

---

## Five-minute tour

All examples below use the bundled sample configuration
[`src/amrie/resources/SampleConfig.json`](src/amrie/resources/SampleConfig.json)
(guideline year 2026; Human → Animal → ECOFF breakpoints; MRS, BLNAR and ICR expert
rules enabled). Every result shown is real output and is checked by
[`tests/test_doc_examples.py`](tests/test_doc_examples.py).

### 1. One measurement from the command line

```bash
amrie single \
  --config src/amrie/resources/SampleConfig.json \
  --organism spn \
  --antibiotic AMC_NM \
  --measurement 2 \
  --output result.json
```

stdout:

```text
S
```

`result.json`:

```json
{
  "OrganismCode": "spn",
  "AntibioticCode": "AMC_NM",
  "Measurement": "2",
  "Interpretation": "S"
}
```

*Streptococcus pneumoniae*, amoxicillin/clavulanate, CLSI MIC of 2 mg/L → susceptible.

### 2. A whole laboratory file

`isolates.txt` (pipe-delimited — one row per isolate, one column per test):

```text
ORGANISM|SPEC_TYPE|AMP_ND10|CTX_ND30|CIP_NM|FOX_ND30|PEN_ND10
eco|ur|19|20|0.5||
kpn|bl|25|30|<=0.25||
sau|wd|||1|15|35
```

```bash
amrie file -c src/amrie/resources/SampleConfig.json -d "|" -i isolates.txt -o results.txt
```

`results.txt` (always **tab**-delimited; every antibiotic column gets an `_INTERP` partner):

```text
ORGANISM  SPEC_TYPE  AMP_ND10  AMP_ND10_INTERP  CTX_ND30  CTX_ND30_INTERP  CIP_NM  CIP_NM_INTERP  FOX_ND30  FOX_ND30_INTERP  PEN_ND10  PEN_ND10_INTERP
eco       ur         19        S                20        R                0.5     I
kpn       bl         25        R                30        S                <=0.25  S
sau       wd                                                               1       S              15        R                35        R
```

What happened, row by row:

- **eco** — straightforward CLSI 2026 breakpoints: ampicillin 19 mm ≥ 17 → `S`;
  cefotaxime 20 mm → `R`; ciprofloxacin 0.5 mg/L → `I`.
- **kpn** — ampicillin 25 mm would be "S" by the zone alone, but *K. pneumoniae* is
  **intrinsically resistant** to ampicillin, so it is `R` (`R*` internally).
- **sau** — cefoxitin 15 mm is resistant, which triggers the **MRS** expert rule
  (methicillin-resistant *Staphylococcus*): every β-lactam on the panel, including
  penicillin at 35 mm, becomes `R` (`R!` internally).

Set `"IncludeInterpretationComments": true` in the config to keep the suffixes that
explain *why*:

```text
kpn  …  AMP_ND10  25  R*  …
sau  …  FOX_ND30  15  R!  PEN_ND10  35  R!
```

Or set `"HorizontalAntibioticResults": false` for one row per measurement:

```text
ORGANISM  SPEC_TYPE  ANTIBIOTIC_CODE  ANTIBIOTIC_MEASUREMENT  ANTIBIOTIC_INTERPRETATION
eco       ur         AMP_ND10         19                      S
eco       ur         CTX_ND30         20                      R
eco       ur         CIP_NM           0.5                     I
kpn       bl         AMP_ND10         25                      R*
…
```

### 3. From Python

```python
from amrie import interpret_single, interpret_file, interpret_qc_single
from amrie.config import read_configuration

config = read_configuration("src/amrie/resources/SampleConfig.json")

interpret_single(config, "eco", "AMP_ND10", "19")    # 'S'   E. coli, ampicillin disk
interpret_single(config, "eco", "AMP_ND10", "15")    # 'I'
interpret_single(config, "eco", "AMP_ND10", "12")    # 'R'
interpret_single(config, "eco", "AMP_NM",  "<=2")    # 'S'   MIC with a modifier
interpret_single(config, "kpn", "AMP_ND10", "25")    # 'R*'  intrinsic resistance
interpret_single(config, "sau", "FOX_ND30", "15")    # 'R!'  MRS expert rule
interpret_single(config, "sau", "CPT_ND30", "22")    # 'SDD' susceptible dose-dependent
interpret_single(config, "eco", "AMP_ND10", "abc")   # ''    not a measurement

# The config can also be a path:
interpret_single("src/amrie/resources/SampleConfig.json", "ent", "PEN_ND10", "19")  # 'S'

# Whole files
interpret_file(config, "isolates.txt", "results.txt", delimiter="|")
```

Change behaviour per call with `dataclasses.replace` — the configuration is a
plain dataclass:

```python
import dataclasses

no_rounding = dataclasses.replace(config, round_half_dilutions=False)
interpret_single(config,      "eco", "CIP_EM", "0.75")   # 'R'  0.75 rounds up to 1 mg/L
interpret_single(no_rounding, "eco", "CIP_EM", "0.75")   # 'I'  0.75 compared as-is

no_intrinsic = dataclasses.replace(config, use_intrinsic_resistance_rules=False)
interpret_single(no_intrinsic, "kpn", "AMP_ND10", "25")  # 'S'  breakpoint only

ecoff_only = dataclasses.replace(config, prioritized_breakpoint_types=["ECOFF"])
interpret_single(ecoff_only, "eco", "AMP_NM", "8")       # 'WT'
interpret_single(ecoff_only, "eco", "AMP_NM", "32")      # 'NWT'
```

Full API: [`docs/python-api.md`](docs/python-api.md).

### 4. QC reference strains

```bash
amrie qc --organism atcc25922 --antibiotic AMP_ND10 --measurement 18
# IN
```

```python
from amrie import interpret_qc_single
interpret_qc_single("atcc25922", "AMP_ND10", "18")   # 'IN'   acceptable range 15–22 mm
interpret_qc_single("atcc25922", "AMP_ND10", "10")   # 'OUT'
interpret_qc_single("atcc25922", "AMP_ND10", "x")    # ''     not interpretable
```

Guide: [`docs/quality-control.md`](docs/quality-control.md).

### 5. Web UI and REST API

```bash
pip install -e ".[web]"
amrie-web                       # serves http://localhost:8080  (OpenAPI docs at /docs)
```

```bash
curl -s -X POST http://localhost:8080/api/interpret/single \
  -H "Content-Type: application/json" \
  -d '{"organism_code": "eco", "whonet_abx_code": "AMP", "measurement": "8",
       "guidelines": ["CLSI", "EUCAST"], "test_method": "mic", "guideline_year": 2026}'
```

```json
{"results":[{"whonet_test":"AMP_NM","interpretation":"S"},{"whonet_test":"AMP_EM","interpretation":"S"}]}
```

Batch files over HTTP:

```bash
curl -s -X POST http://localhost:8080/api/interpret/file \
  -F data_file=@isolates.txt \
  -F config_file=@src/amrie/resources/SampleConfig.json \
  -F delimiter='|' -F guideline_year=2026 -o results.txt
```

Docker: `docker compose up --build`. Guide: [`docs/web.md`](docs/web.md).

---

## Reading the results

| Code | Meaning | Example (SampleConfig, 2026) |
|---|---|---|
| `S` | **Susceptible** — standard dosing is likely to work | `eco AMP_ND10 19` |
| `I` | **Intermediate** / "susceptible, increased exposure" | `eco AMP_ND10 15` |
| `SDD` | **Susceptible-dose dependent** — S only at higher/more frequent dosing | `sau CPT_ND30 22` |
| `R` | **Resistant** | `eco AMP_ND10 12` |
| `NS` | **Non-susceptible** — above the S breakpoint where no R breakpoint exists, or a censored `>` MIC that could be I or R | `eco AMP_NM >8` |
| `WT` | **Wild type** — at or below the ECOFF (no acquired resistance) | `eco AMP_NM 8` (ECOFF only) |
| `NWT` | **Non-wild type** — above the ECOFF | `eco AMP_NM 32` (ECOFF only) |
| *(blank)* | **Uninterpretable** — no breakpoint for this organism/drug/year, unknown organism, or not a number | `eco AMP_ND10 abc` |

Suffixes. The Python API always returns them. The CLI (`amrie single`, `amrie file`)
and the file API keep `*` and `!` only when `IncludeInterpretationComments` is `true`;
`?` is always kept:

| Suffix | Meaning | Example |
|---|---|---|
| `*` | Set by an **intrinsic resistance** rule — the organism is expected to be resistant | `kpn AMP_ND10 25` → `R*` |
| `!` | Set by an **expert interpretation** rule — inferred from another result | `sau FOX_ND30 15` (MRS) → `R!` |
| `?` | **Uncertain** — a censored value (`<`, `>`) cannot be placed in a single category | `eco AMP_NM <=16` → `S?` |

Full explanation, including how censored MICs are handled:
[`docs/concepts.md`](docs/concepts.md#interpretation-categories).

---

## WHONET codes in one minute

AMRIE uses WHONET's coding conventions everywhere.

**Organisms** are lower-case 3-letter codes: `eco` *E. coli*, `kpn` *K. pneumoniae*,
`sau` *S. aureus*, `pae` *P. aeruginosa*, `spn` *S. pneumoniae*, `hin`
*H. influenzae*, `ent` *Enterococcus* sp., `nme` *N. meningitidis* … (2,980 in
`Organisms.txt`; list them with `GET /api/organisms` or
`amrie.organism.CURRENT_ORGANISMS`).

**Antibiotic test columns** encode *drug*, *guideline*, *method* and *potency*:

```text
 AMP _ N D 10            CIP _ E M             X_12 _ N D 30
 │     │ │ └─ potency     │     │ └─ MIC         │      │ │ └─ potency
 │     │ └─── Disk        │     └─── EUCAST      │      │ └─── Disk
 │     └───── CLSI        └───────── ciprofloxacin│      └───── CLSI
 └─────────── ampicillin                         └──────────── user-defined drug 12
```

| Position | Values |
|---|---|
| Drug | 3 capital letters (`AMP`, `CIP`, `FOX`, …) or user-defined `X_1` … `X_99` (no leading zero) |
| Guideline | `N` CLSI · `E` EUCAST · `F` SFM · `S` SRGA · `B` BSAC · `D` DIN · `T` NEO · `A` AFA |
| Method | `D` disk (followed by potency, e.g. `D10`, `D30`, `D1_2`) · `M` MIC · `E` E-test |

Details: [`docs/data-formats.md`](docs/data-formats.md#whonet-antibiotic-column-names).

---

## Configuration at a glance

```json
{
  "$schema": "../../../docs/reference/amrie-config.schema.json",
  "GuidelineYear": 2026,
  "PrioritizedBreakpointTypes": ["Human", "Animal", "ECOFF"],
  "PrioritizedSitesOfInfection": [],
  "DisabledSitesOfInfection": [],
  "EnabledExpertInterpretationRules": ["BLNAR-HFLU", "MRS", "ICR"],
  "UseIntrinsicResistanceRules": true,
  "RoundHalfDilutions": true,
  "IncludeInterpretationComments": false,
  "HorizontalAntibioticResults": true,
  "UserDefinedBreakpointsFile": ""
}
```

| Key | Default | What it controls |
|---|---|---|
| `GuidelineYear` | `2026` | Which year's breakpoint table is used |
| `PrioritizedBreakpointTypes` | all types | Which of `Human`, `Animal`, `ECOFF` are allowed, in priority order |
| `PrioritizedSitesOfInfection` | built-in order | Site-of-infection priority (e.g. put `Meningitis` first for CSF isolates) |
| `DisabledSitesOfInfection` | `[]` | Sites never to use |
| `EnabledExpertInterpretationRules` | all rules | Which expert rules run (`[]` = none) |
| `UseIntrinsicResistanceRules` | `true` | Apply expected-resistance (`R*`) rules |
| `RoundHalfDilutions` | `true` | Round MIC / E-test values between dilutions up (0.75 → 1) before comparison |
| `IncludeInterpretationComments` | `false` | Keep `*` / `!` suffixes in file output |
| `HorizontalAntibioticResults` | `true` | `_INTERP` columns (`true`) or one row per test (`false`) |
| `UserDefinedBreakpointsFile` | `""` | Extra breakpoints that take priority over the built-in table |

The loader is forgiving: key names are case-insensitive; `$schema`, unknown keys,
`_Comment…` and `DISABLED_…` keys are ignored; `//` and `/* */` comments and
trailing commas are accepted. A JSON Schema for editor auto-completion lives at
[`docs/reference/amrie-config.schema.json`](docs/reference/amrie-config.schema.json).

Every option with examples: [`docs/configuration.md`](docs/configuration.md).

---

## How an interpretation is made

```text
measurement ──► parse  ("<=2" → 2, "<="; "≤2" and "=<2" are normalised too)
                  │
                  ▼
   intrinsic rule for organism + drug?  ── yes ──►  R*
                  │ no
                  ▼
   find the most applicable breakpoint
   (guideline from the column, year from the config,
    organism matched at serovar → species → genus → family → … level,
    then breakpoint type, host and site-of-infection priority)
                  │
                  ▼
   compare: disk zone ≥ S → S, ≤ R → R, between → I/SDD
            MIC ≤ S → S, ≥ R → R, between → I/SDD   (ECOFF: ≤ ECV → WT)
                  │
                  ▼
   expert rules for the isolate (MRS, ESBL, BLNAR, ICR) may override ──► R!
```

- Breakpoint selection in depth: [`docs/breakpoint-selection.md`](docs/breakpoint-selection.md)
- Intrinsic resistance: [`docs/intrinsic-resistance.md`](docs/intrinsic-resistance.md)
- Expert rules: [`docs/expert-rules.md`](docs/expert-rules.md)

---

## Bundled reference data

| File | Rows | Contents |
|---|---:|---|
| `Breakpoints.txt` | 51,001 | Human (38,153), ECOFF (9,968) and Animal (2,880) breakpoints for 8 guidelines, 1998–2026 |
| `Organisms.txt` | 2,980 | WHONET organism codes with taxonomy (2,351 current, 17 merged codes) |
| `Antibiotics.txt` | 565 | Drug codes, classes, ATC codes, potencies per guideline |
| `ExpectedResistancePhenotypes.txt` | 1,024 | CLSI (474) and EUCAST (550) intrinsic resistance rules |
| `ExpertInterpretationRules.txt` | 7 | MRS (2 rows), ESBL ×2, BLNAR, ICR (2 rows) |
| `QC_Ranges.txt` | 23,136 | QC acceptable ranges for reference strains |

These are the upstream tables, byte-for-byte (except a three-row organism update
from upstream). See [`docs/data-formats.md`](docs/data-formats.md#bundled-resource-tables).

---

## Known limitations

- **EUCAST 2022–2026 general PK/PD breakpoints are not used.** In the upstream data
  these 195 rows are coded `ORGANISM_CODE_TYPE=ALL`, `ORGANISM_CODE=Gen`, and the
  upstream C# engine only matches `ALL`/`ALL` rows (EUCAST 2013–2020 and SFM 2020).
  This port deliberately matches upstream; organisms without species-specific
  EUCAST 2022+ breakpoints therefore stay uninterpretable for those drugs.
  See [`docs/breakpoint-selection.md`](docs/breakpoint-selection.md#all-organism-pkpd-breakpoints).
- File output is always **tab-delimited**, whatever the input delimiter.
- An invalid antibiotic code passed to `amrie single` (e.g. `X_0_NM`) currently
  ends with a Python traceback instead of a friendly message.
- `GET /api/antibiotics` returns one entry per antibiotic *row*, so a drug present
  in several guideline rows (e.g. `AMP`) appears more than once.
- Results are only as current as the bundled tables (breakpoint revision 2026.1).

More in [`docs/troubleshooting.md`](docs/troubleshooting.md).

---

## Project layout

```text
beak-whonet-amrie/
├── src/amrie/                 the engine (pure Python, no web dependencies)
│   ├── __init__.py            public API: interpret_single / interpret_file / interpret_qc_single
│   ├── cli.py                 `amrie` command (Typer)
│   ├── config.py              InterpretationConfiguration + tolerant JSON loader
│   ├── isolate.py             one isolate row: intrinsic → breakpoints → expert rules
│   ├── antibiotic_rules.py    one measurement vs one breakpoint; bounded caches
│   ├── breakpoint.py          breakpoint table + most-applicable-breakpoint search
│   ├── expected_resistance.py intrinsic resistance rules
│   ├── expert_rule.py         expert interpretation rules
│   ├── qc.py                  QC ranges
│   ├── organism.py / antibiotic.py   reference tables
│   ├── parsing.py / io_utils.py      column-name & measurement parsing, delimited text
│   ├── io_library.py          batch file reading, parallel interpretation, output writing
│   ├── bounded_cache.py       FIFO cache with size limits
│   └── resources/             bundled tables + SampleConfig.json + sample input
├── web/                       NiceGUI pages + FastAPI endpoints
├── tests/                     pytest suite (unit, parity, golden file, doc examples)
└── docs/                      user and developer documentation
```

Module-by-module walkthrough: [`docs/architecture.md`](docs/architecture.md).

---

## Running the tests

```bash
pytest                                   # whole suite
pytest -q tests/test_parity.py           # parity + golden-file regression
pytest -q tests/test_doc_examples.py     # every result quoted in the docs
pytest -k "mrs or intrinsic" -v          # by keyword
```

The suite covers single and batch interpretation, the golden output file, CLI and
web-free API entry points, parallel-vs-sequential parity, QC, user-defined drugs
and breakpoints, every upstream fix (`tests/test_sync_*.py`), the bounded caches,
and the examples in this README. See [`docs/development.md`](docs/development.md).

---

## Documentation map

| If you want to… | Read |
|---|---|
| get going step by step | [`docs/getting-started.md`](docs/getting-started.md) |
| understand S/I/R, breakpoints, ECOFFs, WHONET codes | [`docs/concepts.md`](docs/concepts.md) |
| call the engine from Python | [`docs/python-api.md`](docs/python-api.md) |
| use the command line | [`docs/cli-reference.md`](docs/cli-reference.md) |
| write a configuration file | [`docs/configuration.md`](docs/configuration.md) |
| prepare input files / read output files | [`docs/data-formats.md`](docs/data-formats.md) |
| know why a breakpoint was chosen | [`docs/breakpoint-selection.md`](docs/breakpoint-selection.md) |
| understand `R*` results | [`docs/intrinsic-resistance.md`](docs/intrinsic-resistance.md) |
| understand `R!` results | [`docs/expert-rules.md`](docs/expert-rules.md) |
| check QC strains | [`docs/quality-control.md`](docs/quality-control.md) |
| run the web UI or REST API | [`docs/web.md`](docs/web.md) |
| copy a recipe | [`docs/use-cases.md`](docs/use-cases.md) |
| fix a surprising result | [`docs/troubleshooting.md`](docs/troubleshooting.md) |
| learn the internals | [`docs/architecture.md`](docs/architecture.md) |
| contribute | [`docs/development.md`](docs/development.md) |
| port new upstream changes | [`docs/upstream-sync.md`](docs/upstream-sync.md) |

All of these are indexed in [`docs/index.md`](docs/index.md).

---

## Keeping up with upstream

The C# project evolves (new breakpoint years, rule fixes, data corrections). This
port records the last upstream commit it matches and a log of every sync in
[`docs/upstream-sync.md`](docs/upstream-sync.md), including the exact `git`
commands to list new upstream changes and a checklist for porting them.

---

## License and attribution

- **Engine and data origin.** AMRIE was created by the WHONET team at the WHO
  Collaborating Centre for Surveillance of Antimicrobial Resistance, Brigham and
  Women's Hospital / Mass General Brigham, Boston. This repository is a Python port
  of [WHONET-Development/AMRIE](https://github.com/WHONET-Development/AMRIE).
- **Upstream licence changed.** Upstream was GPL-3.0 at the original port point
  (`69de201`). It is now distributed under the **MGB Open Access License 1.0**,
  which limits use to non-commercial, academic and public-health purposes, requires
  modifications to be shared back via the upstream repository when distributed, and
  requires notices to be preserved. This repository does not yet contain its own
  `LICENSE` file; until one is added, consult the upstream
  [`License.md`](https://github.com/WHONET-Development/AMRIE/blob/main/License.md)
  for the terms that apply to the bundled data and derived code.
- **Clinical content.** Breakpoints, intrinsic resistance tables and QC ranges are
  derived from publications of **CLSI** (M100, M45, VET01S, M23), **EUCAST**
  (breakpoint tables, expected resistant phenotypes, QC tables, ECOFFs) and
  **CA-SFM**; organism, antibiotic, ATC, AWaRe, LOINC and SNOMED CT codes come from
  **WHONET / WHO**. Consult the official documents for full footnotes, dosing and
  testing conditions.
