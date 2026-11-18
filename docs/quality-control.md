# Quality control

Every AST run includes **reference strains** with known, published acceptable
ranges. If a reference strain's result falls outside its range, the run's patient
results cannot be trusted. AMRIE checks a strain/test/measurement against the
bundled QC table and returns `IN`, `OUT` or blank.

> QC evaluation is a Python-port extension: the C# engine ships `QC_Ranges.txt`
> and the range model, and this port adds the `amrie qc` command, the Python helpers,
> a web page and a REST endpoint on top of them.

- [Quick examples](#quick-examples)
- [How a range is chosen](#how-a-range-is-chosen)
- [Reference strains in the table](#reference-strains-in-the-table)
- [MIC and E-test QC](#mic-and-e-test-qc)
- [Command line](#command-line)
- [Python](#python)
- [Web and REST](#web-and-rest)
- [Batch QC from a file](#batch-qc-from-a-file)

---

## Quick examples

| Strain | Test | Value | Range | Result |
|---|---|---|---|---|
| `atcc25922` *E. coli* | `AMP_ND10` | 18 | 15–22 mm (CLSI 2026) | `IN` |
| `atcc25922` | `AMP_ND10` | 10 | 15–22 mm | `OUT` |
| `atcc25922` | `AMP_ND10` | `x` | — | *(blank)* |
| `atcc25922` | `CIP_NM` | 0.008 | 0.004–0.016 mg/L | `IN` |
| `atcc25922` | `CIP_NM` | 0.03 | 0.004–0.016 mg/L | `OUT` |
| `atcc25923` *S. aureus* | `FOX_ND30` | — | 23–29 mm | |
| `atcc27853` *P. aeruginosa* | `MEM_NM` | — | 0.12–1 mg/L | |
| `atcc29212` *E. faecalis* | `VAN_NM` | — | 1–4 mg/L | |
| `atcc29212` | `VAN_NE` | 3 | 1–4 mg/L | `IN` |

---

## How a range is chosen

For `(strain, test column)` the engine:

1. parses the test column into drug, guideline and method (`AMP_ND10` → AMP, CLSI, disk);
2. keeps the QC rows with the same **strain**, **drug code**, **guideline** and
   **method** (disk vs MIC; E-test counts as MIC) — matched case-insensitively;
3. takes the **newest year** among them (there is no year option);
4. returns `IN` if `MINIMUM ≤ value ≤ MAXIMUM`, otherwise `OUT`.

Things to know:

- **The disk potency is not part of the match.** `AMP_ND10` and `AMP_ND2` find the
  same rows; make sure the potency you tested is the one the range was published for
  (see `ABX_TEST` in the table).
- The guideline comes from the column: use `…_N…` for CLSI ranges, `…_E…` for EUCAST.
- A strain with no range for that drug/guideline/method gives a blank result, as does
  a non-numeric value or a disk value outside 6–80 mm.

```python
from amrie.qc import get_applicable_quality_control_range as qc_range
r = qc_range("atcc25922", "AMP_ND10")
(r.GUIDELINE, r.YEAR, r.ABX_TEST, r.METHOD, r.MEDIUM, r.MINIMUM, r.MAXIMUM, r.REFERENCE_TABLE)
# ('CLSI', 2026, 'AMP_ND10', 'Disk', 'MH', Decimal('15'), Decimal('22'), 'Table 4A-1')
```

---

## Reference strains in the table

`QC_Ranges.txt` has 23,136 ranges for 57 strains, 2000–2026:

| Guideline | Ranges |
|---|---:|
| CLSI | 17,552 |
| EUCAST | 5,442 |
| DIN | 85 |
| BSAC | 34 |
| SFM | 23 |

The ten strains with most ranges:

| Strain code | Organism | Ranges |
|---|---|---:|
| `atcc25922` | *Escherichia coli* ATCC 25922 | 4,359 |
| `atcc49619` | *Streptococcus pneumoniae* ATCC 49619 | 2,707 |
| `atcc29213` | *Staphylococcus aureus* ATCC 29213 (MIC) | 2,647 |
| `atcc27853` | *Pseudomonas aeruginosa* ATCC 27853 | 2,209 |
| `atcc29212` | *Enterococcus faecalis* ATCC 29212 | 1,641 |
| `atcc25923` | *Staphylococcus aureus* ATCC 25923 (disk) | 1,582 |
| `atcc49247` | *Haemophilus influenzae* ATCC 49247 | 1,260 |
| `atcc49766` | *Haemophilus influenzae* ATCC 49766 | 904 |
| `atcc49226` | *Neisseria gonorrhoeae* ATCC 49226 | 688 |
| `atcc25285` | *Bacteroides fragilis* ATCC 25285 | 522 |

List them all:

```python
from collections import Counter
from amrie.qc import QUALITY_CONTROL_RANGES
Counter((q.STRAIN, q.WHONET_ORG_CODE) for q in QUALITY_CONTROL_RANGES).most_common()
```

---

## MIC and E-test QC

MIC ranges are compared after the same optional half-dilution rounding as patient
results (`round_half_dilutions=True` by default; `--no-round-half-dilutions` on the
CLI). An E-test reading of 3 mg/L for vancomycin on *E. faecalis* ATCC 29212 is
compared as 4 (rounded) or 3 (unrounded) — both inside 1–4 → `IN`.

---

## Command line

```bash
amrie qc --organism atcc25922 --antibiotic AMP_ND10 -m 18                 # IN
amrie qc --organism atcc25922 --antibiotic CIP_NM   -m 0.03               # OUT
amrie qc --organism atcc29212 --antibiotic VAN_NE   -m 3 --no-round-half-dilutions   # IN
amrie qc --organism atcc25922 --antibiotic AMP_ND10 -m 18 -o qc.json
```

`qc.json`:

```json
{
  "ReferenceStrain": "atcc25922",
  "AntibioticCode": "AMP_ND10",
  "Measurement": "18",
  "Interpretation": "IN"
}
```

---

## Python

```python
from amrie import interpret_qc_single

interpret_qc_single("atcc25922", "AMP_ND10", "18")      # 'IN'
interpret_qc_single("atcc25922", "AMP_ND10", "10")      # 'OUT'
interpret_qc_single("atcc25922", "CIP_NM", "0.008")     # 'IN'
interpret_qc_single("atcc29212", "VAN_NE", "3", round_half_dilutions=False)   # 'IN'
```

---

## Web and REST

The **QC** page (`/qc`) takes a strain, a full test code and a value.

```bash
curl -s -X POST http://localhost:8080/api/qc \
  -H "Content-Type: application/json" \
  -d '{"strain": "atcc25922", "antibiotic": "AMP_ND10", "measurement": "18"}'
```

```json
{"result":"IN"}
```

`round_half_dilutions` (default `true`) can be added to the body.

---

## Batch QC from a file

There is no file mode for QC; a few lines of Python cover it. `qc_log.csv`:

```text
date,strain,test,value
2026-11-01,atcc25922,AMP_ND10,18
2026-11-01,atcc25922,CIP_NM,0.03
2026-11-01,atcc27853,MEM_NM,0.5
```

```python
import csv
from amrie import interpret_qc_single
from amrie.qc import get_applicable_quality_control_range

with open("qc_log.csv", newline="") as f:
    for row in csv.DictReader(f):
        result = interpret_qc_single(row["strain"], row["test"], row["value"])
        r = get_applicable_quality_control_range(row["strain"], row["test"])
        span = f"{r.MINIMUM}–{r.MAXIMUM}" if r else "no range"
        print(row["date"], row["strain"], row["test"], row["value"], span, result or "?")
```

```text
2026-11-01 atcc25922 AMP_ND10 18 15–22 IN
2026-11-01 atcc25922 CIP_NM 0.03 0.004–0.016 OUT
2026-11-01 atcc27853 MEM_NM 0.5 0.12–1 IN
```
