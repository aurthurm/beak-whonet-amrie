# Getting started

This tutorial takes you from a fresh clone to interpreting a laboratory file,
explaining each result along the way. It takes about fifteen minutes.

- [1. Install](#1-install)
- [2. Your first interpretation](#2-your-first-interpretation)
- [3. Change the measurement, watch the category change](#3-change-the-measurement-watch-the-category-change)
- [4. MICs and censored values](#4-mics-and-censored-values)
- [5. When the organism decides: intrinsic resistance](#5-when-the-organism-decides-intrinsic-resistance)
- [6. When another test decides: expert rules](#6-when-another-test-decides-expert-rules)
- [7. Interpret a whole file](#7-interpret-a-whole-file)
- [8. Write your own configuration](#8-write-your-own-configuration)
- [9. Do the same from Python](#9-do-the-same-from-python)
- [10. Try the web UI](#10-try-the-web-ui)
- [Where next](#where-next)

---

## 1. Install

```bash
git clone https://github.com/aurthurm/beak-whonet-amrie.git
cd beak-whonet-amrie
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
amrie --help
```

```text
 Usage: amrie [OPTIONS] COMMAND [ARGS]...

 AMRIE antimicrobial susceptibility interpretation engine

╭─ Commands ───────────────────────────────────────────────────────────────╮
│ file     Interpret an entire input file (FILE mode).                     │
│ qc       Evaluate a QC measurement against reference strain ranges.      │
│ single   Interpret a single organism/antibiotic/measurement              │
│          (SINGLE_INTERPRETATION mode).                                   │
╰──────────────────────────────────────────────────────────────────────────╯
```

Make a tutorial copy of the sample configuration that keeps the explanatory
suffixes (`*`, `!`) in results, and put it in a variable:

```bash
sed 's/"IncludeInterpretationComments": false/"IncludeInterpretationComments": true/' \
    src/amrie/resources/SampleConfig.json > tutorial.json
CFG=tutorial.json
```

(The sample itself has `IncludeInterpretationComments: false`, which strips `*` and
`!` from CLI and file output — you will see the difference in step 7.)

---

## 2. Your first interpretation

*E. coli* (`eco`), ampicillin 10 µg disk tested by CLSI (`AMP_ND10`), zone 19 mm:

```bash
amrie single -c $CFG --organism eco --antibiotic AMP_ND10 -m 19 -o result.json
```

```text
S
```

`result.json` records what was asked and the answer:

```json
{
  "OrganismCode": "eco",
  "AntibioticCode": "AMP_ND10",
  "Measurement": "19",
  "Interpretation": "S"
}
```

What the engine did:

1. Read `AMP_ND10` as **AMP** (ampicillin), **N** (CLSI), **D** (disk), **10** (µg).
2. Took the guideline year from the config (2026).
3. Searched the CLSI 2026 disk breakpoints for ampicillin and found the most
   specific one that covers *E. coli*: the **Enterobacterales** (`EBC`, family
   level) breakpoint **S ≥ 17 mm, I 14–16 mm, R ≤ 13 mm**.
4. 19 ≥ 17 → **S**.

---

## 3. Change the measurement, watch the category change

```bash
for mm in 19 17 15 14 13 6; do
  printf "%3s mm → " $mm; amrie single -c $CFG --organism eco --antibiotic AMP_ND10 -m $mm -o /dev/null
done
```

```text
 19 mm → S
 17 mm → S
 15 mm → I
 14 mm → I
 13 mm → R
  6 mm → R
```

For disks, **bigger zones mean more susceptible**: `≥ S` is susceptible, `≤ R` is
resistant, anything in between is intermediate.

---

## 4. MICs and censored values

The same drug by broth microdilution MIC (`AMP_NM`, mg/L). For MICs, **smaller is
more susceptible**: CLSI 2026 for Enterobacterales is S ≤ 8, R ≥ 32.

| Measurement | Result | Why |
|---|---|---|
| `8` | `S` | 8 ≤ 8 |
| `32` | `R` | 32 ≥ 32 |
| `<=2` | `S` | at most 2, certainly ≤ 8 |
| `<2` | `S` | read as `<=1` (one dilution lower), still S |
| `≤2` | `S` | the Unicode symbol is accepted and normalised |
| `<=16` | `S?` | could be 8 (S) or 16 (I) — the `?` flags the uncertainty |
| `>8` | `NS` | above 8 but could be 16 (I) or ≥ 32 (R) — "non-susceptible" |
| `>16` | `R` | above 16 means at least 32 → R |

```bash
amrie single -c $CFG --organism eco --antibiotic AMP_NM -m "<=16" -o /dev/null   # S?
```

Results with a `<` / `>` modifier are called **censored**. AMRIE never invents a
category it cannot justify: it returns the safe answer (`NS`) or marks the
uncertainty (`?`). See [Concepts → censored MICs](concepts.md#censored-mic-values).

---

## 5. When the organism decides: intrinsic resistance

*Klebsiella pneumoniae* (`kpn`) has a chromosomal β-lactamase, so it is always
resistant to ampicillin, whatever the zone says:

```bash
amrie single -c $CFG --organism kpn --antibiotic AMP_ND10 -m 25 -o /dev/null
```

```text
R*
```

The `*` means "**intrinsic** (expected) resistance rule". A 25 mm zone would be
"S" for *E. coli*; for *Klebsiella* the CLSI expected-resistance table overrides it.
Details: [Intrinsic resistance](intrinsic-resistance.md).

---

## 6. When another test decides: expert rules

A *Staphylococcus aureus* (`sau`) with a cefoxitin 30 µg zone of 15 mm:

```bash
amrie single -c $CFG --organism sau --antibiotic FOX_ND30 -m 15 -o /dev/null
```

```text
R!
```

Cefoxitin resistance is the surrogate test for MRSA, so the **MRS** expert rule
fires (`!` = expert rule). In a full isolate record, MRS also marks every other
β-lactam resistant — you will see that in the next step. Details:
[Expert rules](expert-rules.md).

---

## 7. Interpret a whole file

Create `isolates.txt` — one row per isolate, one column per test, `|`-delimited:

```text
ORGANISM|SPEC_TYPE|AMP_ND10|CTX_ND30|CIP_NM|FOX_ND30|PEN_ND10
eco|ur|19|20|0.5||
kpn|bl|25|30|<=0.25||
sau|wd|||1|15|35
```

Use the **unchanged** sample configuration this time:

```bash
amrie file -c src/amrie/resources/SampleConfig.json -d "|" -i isolates.txt -o results.txt
```

```text
Wrote interpretations to /…/results.txt
```

`results.txt` (tab-delimited, columns aligned here for reading):

```text
ORGANISM SPEC_TYPE AMP_ND10 AMP_ND10_INTERP CTX_ND30 CTX_ND30_INTERP CIP_NM CIP_NM_INTERP FOX_ND30 FOX_ND30_INTERP PEN_ND10 PEN_ND10_INTERP
eco      ur        19       S               20       R               0.5    I
kpn      bl        25       R               30       S               <=0.25 S
sau      wd                                                          1      S             15       R               35       R
```

Notice:

- Every column you did not recognise as an antibiotic (`SPEC_TYPE`) is copied through.
- Each antibiotic column gets an `_INTERP` column right after it.
- `kpn` ampicillin is `R` (intrinsic), and `sau` penicillin at 35 mm is `R` because
  the MRS rule fired on cefoxitin.
- The suffixes `*` and `!` are **stripped** because the sample config has
  `"IncludeInterpretationComments": false`. Run the same command with
  `-c $CFG` (your `tutorial.json`) and you get `R*` and `R!` instead. A `?` suffix is
  never stripped.

---

## 8. Write your own configuration

Copy the sample and change what you need. `my-config.json`:

```json
{
  "GuidelineYear": 2026,
  "PrioritizedBreakpointTypes": ["Human"],
  "EnabledExpertInterpretationRules": ["MRS", "ICR", "BLNAR-HFLU"],
  "IncludeInterpretationComments": true,
  "HorizontalAntibioticResults": false
}
```

```bash
amrie file -c my-config.json -d "|" -i isolates.txt -o long.txt
```

`long.txt` now has one row per measurement, with the suffixes kept:

```text
ORGANISM SPEC_TYPE ANTIBIOTIC_CODE ANTIBIOTIC_MEASUREMENT ANTIBIOTIC_INTERPRETATION
eco      ur        AMP_ND10        19                     S
eco      ur        CTX_ND30        20                     R
eco      ur        CIP_NM          0.5                    I
kpn      bl        AMP_ND10        25                     R*
kpn      bl        CTX_ND30        30                     S
kpn      bl        CIP_NM          <=0.25                 S
sau      wd        CIP_NM          1                      S
sau      wd        FOX_ND30        15                     R!
sau      wd        PEN_ND10        35                     R!
```

Keys you leave out take their defaults. All options: [Configuration](configuration.md).

---

## 9. Do the same from Python

```python
from amrie import interpret_single, interpret_file
from amrie.config import read_configuration

config = read_configuration("src/amrie/resources/SampleConfig.json")

print(interpret_single(config, "eco", "AMP_ND10", "19"))   # S
print(interpret_single(config, "kpn", "AMP_ND10", "25"))   # R*
print(interpret_single(config, "sau", "FOX_ND30", "15"))   # R!

interpret_file(config, "isolates.txt", "results.txt", delimiter="|")
```

Interpret a record you already have in memory — no files at all:

```python
from amrie.isolate import IsolateInterpretation

row = {"ORGANISM": "sau", "FOX_ND30": "15", "PEN_ND10": "35", "VAN_NM": "1"}
result = IsolateInterpretation(
    row, list(row), config.enabled_expert_interpretation_rules, [], guideline_year=2026
).get_all_interpretations()
print(result)   # {'FOX_ND30': 'R!', 'PEN_ND10': 'R!', 'VAN_NM': 'S'}
```

Everything else: [Python API](python-api.md).

---

## 10. Try the web UI

```bash
pip install -e ".[web]"
amrie-web
```

Open <http://localhost:8080>. Pick an organism and an antibiotic, choose disk or
MIC, type a measurement and press **Get interpretations**. The **File** tab does
the same job as `amrie file`, and the **QC** tab checks reference strains. The REST
API is documented live at <http://localhost:8080/docs>. Guide: [Web](web.md).

---

## Where next

- Why that breakpoint? → [Breakpoint selection](breakpoint-selection.md)
- Your result is blank or surprising → [Troubleshooting](troubleshooting.md)
- Ready-made solutions → [Use cases](use-cases.md)
