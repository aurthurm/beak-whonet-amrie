# Data formats

How to name antibiotic columns, what an input file must look like, what the output
looks like, and what is in the bundled reference tables.

- [WHONET antibiotic column names](#whonet-antibiotic-column-names)
- [Input files](#input-files)
- [Measurement values](#measurement-values)
- [Non-antibiotic test columns](#non-antibiotic-test-columns)
- [Output files](#output-files)
- [JSON outputs](#json-outputs)
- [User-defined breakpoints file](#user-defined-breakpoints-file)
- [Bundled resource tables](#bundled-resource-tables)

---

## WHONET antibiotic column names

Every antibiotic result lives in a column whose **name** tells AMRIE the drug, the
guideline, the test method and (for disks) the potency:

```text
<DRUG>_<GUIDELINE><METHOD>[<POTENCY>]
```

| Part | Format | Examples |
|---|---|---|
| `DRUG` | 3 upper-case letters (WHONET antibiotic code), or `X_1` … `X_99` | `AMP`, `CTX`, `VAN`, `X_7` |
| `GUIDELINE` | one letter | `N`, `E`, `F`, `S`, `B`, `D`, `T`, `A` |
| `METHOD` | `D` disk, `M` MIC, `E` E-test | |
| `POTENCY` | disk only; digits, `_` for a combination | `10`, `30`, `1_2`, `2_5`, `1mg` |

### Guideline codes

| Code | Guideline |
|---|---|
| `N` | CLSI |
| `E` | EUCAST |
| `F` | SFM (CA-SFM, France) |
| `S` | SRGA (Sweden) |
| `B` | BSAC (UK) |
| `D` | DIN (Germany) |
| `T` | NEO (Neo-Sensitabs) |
| `A` | AFA |

### Examples

| Column | Meaning |
|---|---|
| `AMP_ND10` | ampicillin · CLSI · disk · 10 µg |
| `AMP_NM` | ampicillin · CLSI · MIC |
| `AMP_NE` | ampicillin · CLSI · E-test (uses the `AMP_NM` breakpoints) |
| `AMP_ED2` | ampicillin · EUCAST · disk · 2 µg |
| `CIP_EM` | ciprofloxacin · EUCAST · MIC |
| `CTX_ND30` | cefotaxime · CLSI · disk · 30 µg |
| `SXT_ND1_2` | trimethoprim/sulfamethoxazole · CLSI · disk · 1.25/23.75 µg |
| `NIT_ND300` | nitrofurantoin · CLSI · disk · 300 µg |
| `PEN_ND10` | penicillin · CLSI · disk · 10 units |
| `PEN_FD1` | penicillin · SFM · disk · 1 unit |
| `X_12_ND30` | user-defined drug 12 · CLSI · disk · 30 µg |

Potencies seen in the breakpoint table, most common first: `30`, `10`, `5`, `15`,
`1_2`, `2`, `1`, `100`, `20`, `200`, `75`, `300`, `25`, `60`, `120`, `500`, `2_5`,
`1mg`, `40`, `80`, `29`, `50`. A disk column only matches breakpoints with the same
potency — `AMP_ND10` and `AMP_ND2` are different tests.

### E-test columns

E-test columns (`…E`) are interpreted with the **MIC** breakpoints of the same
drug and guideline: `AMP_NE` is looked up as `AMP_NM`, `CIP_EE` as `CIP_EM`. They
are rounded to standard dilutions when `RoundHalfDilutions` is on (as are MIC
columns).

### User-defined drugs

For drugs that have no WHONET code yet, use `X_<n>`:

```text
X_<1-99>_<GUIDELINE><METHOD>[<POTENCY>]
```

| Valid | Invalid | Why |
|---|---|---|
| `X_1_NM`, `X_9_ND10`, `X_12_ED30`, `X_99_NM` | `X_0_NM` | numbering starts at 1 |
| | `X_01_NM`, `X_07_ND10` | no leading zeros |
| | `X_100_NM` | at most two digits |
| | `X_1` | guideline and method missing |

Use upper-case `X`: a lower-case `x_1_NM` is parsed, but the drug code stays `x_1`,
which will not match user-defined breakpoints written as `X_1`. User-defined drugs
only have interpretations if you supply breakpoints for them in a
[user-defined breakpoints file](#user-defined-breakpoints-file).

### Columns that look like antibiotics but are not

A column is treated as an antibiotic only if its whole name matches the pattern
above. `OXA_SCREEN`, `MRSA_SCRN`, `ESBL`, `BETA_LACT`, `SPEC_TYPE` are ordinary
columns (some are read by [expert rules](#non-antibiotic-test-columns)). Before the
November 2026 upstream sync, a column such as `OXA_SCREEN` could be mistaken for an
oxacillin result by the MRS rule — that is fixed.

---

## Input files

```text
ORGANISM|SPEC_TYPE|AMP_ND10|CTX_ND30|CIP_NM|FOX_ND30|PEN_ND10
eco|ur|19|20|0.5||
kpn|bl|25|30|<=0.25||
sau|wd|||1|15|35
```

| Rule | Detail |
|---|---|
| Encoding | UTF-8. A leading byte-order mark (Excel "CSV UTF-8") is ignored. |
| Delimiter | one of TAB, `,`, `;`, `|` — chosen with `-d` / `delimiter=` |
| Header | the **first non-blank line** is the header |
| `ORGANISM` column | required for interpretation; the name is **upper-case and case-sensitive** (`organism` is not recognised) |
| Antibiotic columns | any number, any order, named as [above](#whonet-antibiotic-column-names) |
| Other columns | copied to the output unchanged; some are read by expert rules |
| Empty values | ignored (no interpretation, blank `_INTERP`) |
| Blank lines | skipped |
| Short rows | a row with **fewer fields than the header is skipped** (same as upstream). Keep trailing delimiters: `kpn|bl|25|30|<=0.25||` |
| Quoting | `"…"` protects the delimiter: `eco,"Smith, J",19`; `""` inside quotes is a literal quote |
| Multi-line values | not supported — each record must be on one line |
| Line endings | LF or CRLF |

An unknown organism code, or a row without `ORGANISM`, is kept in the output with
blank interpretations.

### Sample input

`src/amrie/resources/SampleInputFile.txt` is a 622-isolate, pipe-delimited WHONET
export with 71 columns (patient and specimen details plus 43 CLSI antibiotic columns). It is the
input of the golden-file regression test.

```bash
amrie file -c src/amrie/resources/SampleConfig.json -d "|" \
           -i src/amrie/resources/SampleInputFile.txt -o sample_out.txt
```

---

## Measurement values

### Disk zones (mm)

| Raw | Read as | Note |
|---|---|---|
| `19` | 19 | |
| `06` | 6 | leading zeros are fine; 6 mm = no zone (disk diameter) |
| `5`, `81` | — | outside 6–80 mm → uninterpretable |

### MIC and E-test (mg/L)

| Raw | Read as | Note |
|---|---|---|
| `4`, `0.25`, `.5` | value | |
| `<=4`, `=<4`, `≤4` | `<= 4` | the three spellings are equivalent |
| `<4` | `<= 2` | "below 4" means at most the next lower dilution |
| `>16` | `> 16` | |
| `>=16`, `=>16`, `≥16` | `> 8` | "at least 16" means above the next lower dilution |
| `=4` | 4 | |
| `abc`, `+`, empty | — | uninterpretable |

How censored values become categories: [Concepts → censored MIC values](concepts.md#censored-mic-values).

---

## Non-antibiotic test columns

Expert rules read these columns. Use exactly these names and values:

| Column | Value that triggers | Rule |
|---|---|---|
| `ESBL` | `+` | `ESBL-CONFIRMED` |
| `X_BLEE` | `p` | `ESBL-CONFIRMED` |
| `BETA_LACT` | `-` (together with ampicillin NS) | `BLNAR-HFLU` |
| `MECA_PCR` | `+` | `MRS` |
| `MRSA` | `+` | `MRS` |
| `OXA_SCREEN` | `+` | `MRS` |
| `MRSA_SCRN` | `+` | `MRS` |
| `PBP2A_AGGL` | `+` | `MRS` |
| `INDUC_CLI` | `+` | `ICR` |
| `MLS_DTEST` | `+` | `ICR` |
| `X_MLS` | `p` | `ICR` |
| `X_MLS_IND` | `p` | `ICR` |

Values are compared exactly (`+` is not `pos`, `p` is not `P`). See
[Expert rules](expert-rules.md).

---

## Output files

Output files are **always tab-delimited**, UTF-8 without BOM, LF line endings, with
a header row. Values are quoted only when they contain a tab, a quote, a line break
or leading/trailing spaces.

### Horizontal layout (`HorizontalAntibioticResults: true`, default)

All input columns in their original order; each antibiotic column is followed by
`<column>_INTERP`.

```text
ORGANISM  SPEC_TYPE  AMP_ND10  AMP_ND10_INTERP  CTX_ND30  CTX_ND30_INTERP  CIP_NM  CIP_NM_INTERP  FOX_ND30  FOX_ND30_INTERP  PEN_ND10  PEN_ND10_INTERP
eco       ur         19        S                20        R                0.5     I
kpn       bl         25        R                30        S                <=0.25  S
sau       wd                                                               1       S              15        R                35        R
```

With `IncludeInterpretationComments: true`:

```text
kpn       bl         25        R*               30        S                <=0.25  S
sau       wd                                                               1       S              15        R!               35        R!
```

### Vertical layout (`HorizontalAntibioticResults: false`)

Non-antibiotic columns are repeated; antibiotic columns are replaced by three
columns; one row per measurement present.

```text
ORGANISM  SPEC_TYPE  ANTIBIOTIC_CODE  ANTIBIOTIC_MEASUREMENT  ANTIBIOTIC_INTERPRETATION
eco       ur         AMP_ND10         19                      S
eco       ur         CTX_ND30         20                      R
eco       ur         CIP_NM           0.5                     I
kpn       bl         AMP_ND10         25                      R*
kpn       bl         CTX_ND30         30                      S
kpn       bl         CIP_NM           <=0.25                  S
sau       wd         CIP_NM           1                       S
sau       wd         FOX_ND30         15                      R!
sau       wd         PEN_ND10         35                      R!
```

(shown with `IncludeInterpretationComments: true`). An isolate with no antibiotic
values still gets one row, with the three antibiotic columns empty, so isolate
counts are preserved:

```text
ORGANISM  WARD   ANTIBIOTIC_CODE  ANTIBIOTIC_MEASUREMENT  ANTIBIOTIC_INTERPRETATION
eco       icu    AMP_ND10         19                      S
eco       icu    CTX_ND30         20                      R
kpn       ward2
```

### Suffixes in output

| Engine result | `IncludeInterpretationComments: false` | `true` |
|---|---|---|
| `R*` | `R` | `R*` |
| `R!` | `R` | `R!` |
| `S?` / `R?` / `NWT?` | `S?` / `R?` / `NWT?` | same |

---

## JSON outputs

`amrie single -o result.json`:

```json
{
  "OrganismCode": "eco",
  "AntibioticCode": "AMP_ND10",
  "Measurement": "19",
  "Interpretation": "S"
}
```

`amrie qc -o qc.json`:

```json
{
  "ReferenceStrain": "atcc25922",
  "AntibioticCode": "AMP_ND10",
  "Measurement": "18",
  "Interpretation": "IN"
}
```

---

## User-defined breakpoints file

Same tab-delimited format as `Breakpoints.txt`. These 21 columns are required, in
any order (columns are found by header name):

```text
GUIDELINES  YEAR  TEST_METHOD  POTENCY  ORGANISM_CODE  ORGANISM_CODE_TYPE  BREAKPOINT_TYPE  HOST
SITE_OF_INFECTION  REFERENCE_TABLE  REFERENCE_SEQUENCE  WHONET_ABX_CODE  WHONET_TEST
R  I  SDD  S  ECV_ECOFF  DATE_ENTERED  DATE_MODIFIED  COMMENTS
```

`ECV_ECOFF_TENTATIVE` (`X` = tentative ECOFF) is optional. Every data row must have
exactly as many fields as the header — count the tabs, including empty fields — and
`YEAR` must be a number.

The bundled example
[`SampleUserDefinedBreakpoints.txt`](../src/amrie/resources/SampleUserDefinedBreakpoints.txt)
(one row, shown vertically):

| Column | Value | Meaning |
|---|---|---|
| `GUIDELINES` | `User-defined` | replaced with `UserDefined` on load |
| `YEAR` | `2022` | informational — user-defined rows apply to every year |
| `TEST_METHOD` | `DISK` | `DISK` or `MIC` |
| `POTENCY` | *(empty)* | |
| `ORGANISM_CODE` | `afb` | acid-fast bacilli |
| `ORGANISM_CODE_TYPE` | `WHONET_ORG_CODE` | taxonomy level of `ORGANISM_CODE` |
| `BREAKPOINT_TYPE` | `Human` | `Human`, `Animal` or `ECOFF` |
| `HOST` | `Human` | |
| `SITE_OF_INFECTION` | *(empty)* | empty = general; comma-separate several sites |
| `WHONET_ABX_CODE` | `PEN` | |
| `WHONET_TEST` | `PEN_ND10` | must equal the input column (E-test columns use the `…M` row) |
| `R` | `20` | disk: R if zone ≤ 20 · MIC: R if MIC ≥ R |
| `I` | *(empty)* | intermediate range text (`21-27`); empty = no I category |
| `SDD` | *(empty)* | SDD range text, if any |
| `S` | `28` | disk: S if zone ≥ 28 · MIC: S if MIC ≤ S |
| `ECV_ECOFF` | *(empty)* | the ECOFF, for `ECOFF` rows |
| `DATE_ENTERED` | `2022-05-20` | ISO date |

Results with this file (`afb PEN_ND10`): 30 → `S`, 25 → `SDD` (between R and S with
no I range), 18 → `R`; without the file, all blank.

Rules:

- `R` and `S` must be numbers (use `0` when absent); `I` and `SDD` are text ranges.
  If `I` is empty, values between R and S are `SDD`.
- User-defined rows are preferred over built-in rows that match the same isolate and
  test, and apply regardless of `GuidelineYear`.
- Organism, type, site and host matching are identical to built-in breakpoints.

---

## Bundled resource tables

All in `src/amrie/resources/`, tab-delimited UTF-8, identical to upstream
`AMRIE.Library/Resources/` (see [upstream sync](upstream-sync.md)).

| File | Rows | Key columns |
|---|---:|---|
| `Breakpoints.txt` | 51,001 | `GUIDELINES, YEAR, TEST_METHOD, POTENCY, ORGANISM_CODE, ORGANISM_CODE_TYPE, BREAKPOINT_TYPE, HOST, SITE_OF_INFECTION, REFERENCE_TABLE, REFERENCE_SEQUENCE, WHONET_ABX_CODE, WHONET_TEST, R, I, SDD, S, ECV_ECOFF, ECV_ECOFF_TENTATIVE, DATE_ENTERED, DATE_MODIFIED, COMMENTS` |
| `Organisms.txt` | 2,980 | `WHONET_ORG_CODE, REPLACED_BY, ORGANISM, TAXONOMIC_STATUS, COMMON, COMMON_COMMENSAL, ORGANISM_TYPE, ANAEROBE, MORPHOLOGY, SUBKINGDOM_CODE, FAMILY_CODE, GENUS_GROUP, GENUS_CODE, SPECIES_GROUP, SEROVAR_GROUP, MSF_GRP_CLIN, SCT_CODE, SCT_TEXT, GBIF_*, KINGDOM … GENUS` |
| `Antibiotics.txt` | 565 | `WHONET_ABX_CODE, ANTIBIOTIC, GUIDELINES, CLSI … AFA, POTENCY, ATC_CODE, CLASS, SUBCLASS, PROF_CLASS, WHO_AWARE, CIA_CATEGORY, HUMAN, VETERINARY, LOINC*` |
| `ExpectedResistancePhenotypes.txt` | 1,024 | `GUIDELINE, REFERENCE_TABLE, ORGANISM_CODE, ORGANISM_CODE_TYPE, EXCEPTION_ORGANISM_CODE, EXCEPTION_ORGANISM_CODE_TYPE, ABX_CODE, ABX_CODE_TYPE, ANTIBIOTIC_EXCEPTIONS` |
| `ExpertInterpretationRules.txt` | 7 | `RULE_CODE, DESCRIPTION, ORGANISM_CODE, ORGANISM_CODE_TYPE, RULE_CRITERIA, AFFECTED_ANTIBIOTICS, ANTIBIOTIC_EXCEPTIONS` |
| `QC_Ranges.txt` | 23,136 | `GUIDELINE, YEAR, STRAIN, REFERENCE_TABLE, WHONET_ORG_CODE, ANTIBIOTIC, ABX_TEST, WHONET_ABX_CODE, METHOD, MEDIUM, MINIMUM, MAXIMUM` |

### Breakpoints at a glance

| By guideline | Rows | By type | Rows |
|---|---:|---|---:|
| CLSI | 27,017 | Human | 38,153 |
| EUCAST | 22,360 | ECOFF | 9,968 |
| SFM | 1,034 | Animal | 2,880 |
| SRGA | 289 | | |
| BSAC | 170 | | |
| NEO | 97 | | |
| AFA | 28 | | |
| DIN | 6 | | |

### Load-time corrections

The engine fixes a few mislabelled rows as it loads the tables (ported from upstream
C#; the files themselves are not changed):

| Table | Correction | Rows affected |
|---|---|---:|
| `Breakpoints.txt` | `ORGANISM_CODE_TYPE` re-derived when the declared type matches no organism but exactly one other type does | 104 (`BS-` → `SPECIES_GROUP`), 77 (`NME` → `SEROVAR_GROUP`) |
| `ExpectedResistancePhenotypes.txt` | `ABX_CODE_TYPE` re-derived when the code is a WHONET code but labelled ATC, or vice versa | 3 (`J01DB`, `GEN`, `GEH`) |

### Inspecting the tables

```python
import pandas as pd
bp = pd.read_csv("src/amrie/resources/Breakpoints.txt", sep="\t", dtype=str, keep_default_na=False)
bp[(bp.GUIDELINES == "CLSI") & (bp.YEAR == "2026") & (bp.WHONET_TEST == "AMP_ND10")][
    ["ORGANISM_CODE", "ORGANISM_CODE_TYPE", "BREAKPOINT_TYPE", "SITE_OF_INFECTION", "R", "I", "S"]
]
```

Or use the engine's typed objects (`amrie.breakpoint.BREAKPOINTS`, …) — see the
[Python API](python-api.md#breakpoints-amriebreakpoint).
