# Use cases and recipes

Working solutions for common tasks. Each recipe is self-contained; results shown are
real output with the bundled data.

| # | Recipe |
|---|---|
| 1 | [Interpret one result](#1-interpret-one-result) |
| 2 | [Interpret a WHONET export](#2-interpret-a-whonet-export) |
| 3 | [Excel / CSV files](#3-excel--csv-files) |
| 4 | [Interpret records already in memory (pandas, databases, HL7)](#4-interpret-records-already-in-memory) |
| 5 | [Resistance rates per organism and drug](#5-resistance-rates-per-organism-and-drug) |
| 6 | [Re-interpret historic data with a different year](#6-re-interpret-historic-data-with-a-different-year) |
| 7 | [See what changed between breakpoint years](#7-see-what-changed-between-breakpoint-years) |
| 8 | [Compare CLSI and EUCAST on the same isolates](#8-compare-clsi-and-eucast-on-the-same-isolates) |
| 9 | [CSF / meningitis specimens](#9-csf--meningitis-specimens) |
| 10 | [Veterinary laboratory](#10-veterinary-laboratory) |
| 11 | [Surveillance with ECOFFs](#11-surveillance-with-ecoffs) |
| 12 | [Local breakpoints for a new drug (`X_1`)](#12-local-breakpoints-for-a-new-drug-x_1) |
| 13 | [Override a guideline breakpoint locally](#13-override-a-guideline-breakpoint-locally) |
| 14 | [Audit which rule or breakpoint produced each result](#14-audit-which-rule-or-breakpoint-produced-each-result) |
| 15 | [Method comparison without intrinsic rules](#15-method-comparison-without-intrinsic-rules) |
| 16 | [QC log checks](#16-qc-log-checks) |
| 17 | [Call AMRIE from another language](#17-call-amrie-from-another-language) |
| 18 | [A long-running interpretation service](#18-a-long-running-interpretation-service) |

All Python snippets assume:

```python
from amrie import interpret_single, interpret_file
from amrie.config import read_configuration
config = read_configuration("src/amrie/resources/SampleConfig.json")
```

---

## 1. Interpret one result

```bash
amrie single -c src/amrie/resources/SampleConfig.json --organism eco --antibiotic AMP_ND10 -m 19 -o r.json
# S
```

```python
interpret_single(config, "eco", "AMP_ND10", "19")    # 'S'
interpret_single(config, "eco", "AMP_NM", "<=16")    # 'S?'
interpret_single(config, "kpn", "AMP_ND10", "25")    # 'R*'
```

---

## 2. Interpret a WHONET export

WHONET exports are pipe-delimited with one column per test:

```bash
amrie file -c src/amrie/resources/SampleConfig.json -d "|" \
           -i src/amrie/resources/SampleInputFile.txt -o sample_out.txt
```

All 71 input columns are kept; each of the 43 antibiotic columns gets an `_INTERP`
partner. Use `"HorizontalAntibioticResults": false` for one row per result.

---

## 3. Excel / CSV files

Excel "CSV UTF-8" files start with a byte-order mark and use `,` — or `;` in many
European locales. Both work:

```bash
amrie file -c my-config.json -d "," -i export.csv -o results.txt
amrie file -c my-config.json -d ";" -i export.csv -o results.txt
```

Make sure the header says `ORGANISM` (upper case) and that test columns use WHONET
names (`AMP_ND10`, not "Ampicillin"). Rename columns once in Excel, or in Python:

```python
import pandas as pd
df = pd.read_csv("export.csv", dtype=str, keep_default_na=False)
df = df.rename(columns={"Organism": "ORGANISM", "Ampicillin (mm)": "AMP_ND10", "Cefotaxime (mm)": "CTX_ND30"})
df.to_csv("export_whonet.txt", sep="|", index=False)
```

The output is always tab-delimited; open it in Excel with *Data → From Text*.

---

## 4. Interpret records already in memory

No files needed — give `IsolateInterpretation` a dict per isolate:

```python
from amrie.isolate import IsolateInterpretation

def interpret_record(record: dict, year: int = 2026) -> dict:
    values = {k: str(v) for k, v in record.items() if v not in (None, "")}
    return IsolateInterpretation(values, list(values), config.enabled_expert_interpretation_rules,
                                 config.user_defined_breakpoints, guideline_year=year,
                                 prioritized_breakpoint_types=config.prioritized_breakpoint_types
                                 ).get_all_interpretations()

interpret_record({"ORGANISM": "sau", "FOX_ND30": 15, "PEN_ND10": 35, "VAN_NM": 1})
# {'FOX_ND30': 'R!', 'PEN_ND10': 'R!', 'VAN_NM': 'S'}
```

With pandas:

```python
import pandas as pd
df = pd.DataFrame([
    {"ORGANISM": "eco", "AMP_ND10": "19", "CTX_ND30": "20"},
    {"ORGANISM": "kpn", "AMP_ND10": "25", "CTX_ND30": "30"},
])
interp = pd.DataFrame([interpret_record(r) for r in df.to_dict("records")]).add_suffix("_INTERP")
df.join(interp)
#   ORGANISM AMP_ND10 CTX_ND30 CTX_ND30_INTERP AMP_ND10_INTERP
# 0      eco       19       20               R               S
# 1      kpn       25       30               S              R*
```

For many rows at once (parallel, cache pre-heated), use `interpret_isolates`:

```python
from amrie.io_library import interpret_isolates
rows = df.to_dict("records")
results = interpret_isolates(config, list(df.columns), rows)   # [(row, interpretations), …]
```

---

## 5. Resistance rates per organism and drug

```python
from collections import Counter, defaultdict
from amrie.io_library import load_input_file, interpret_isolates

columns, rows = load_input_file("src/amrie/resources/SampleInputFile.txt", "|")
results = interpret_isolates(config, columns, rows)

tally = defaultdict(Counter)
for row, interp in results:
    for test, value in interp.items():
        if value:
            tally[(row["ORGANISM"], test)][value.rstrip("*!?")] += 1

for (org, test), counts in sorted(tally.items(), key=lambda kv: -sum(kv[1].values()))[:6]:
    n = sum(counts.values())
    print(f"{org} {test:9} n={n} %R={100 * counts['R'] / n:.1f}")
```

```text
scn GEN_ND10  n=105 %R=18.1
scn CIP_ND5   n=105 %R=33.3
scn ERY_ND15  n=105 %R=51.4
scn SXT_ND1_2 n=105 %R=35.2
scn CLI_ND2   n=105 %R=26.7
scn PEN_ND10  n=105 %R=76.2
```

(`scn` = coagulase-negative staphylococci, the most frequent organism in the sample.)
For surveillance reporting, de-duplicate to the first isolate per patient first, as
CLSI M39 recommends.

---

## 6. Re-interpret historic data with a different year

The breakpoints in force when the data were produced:

```python
interpret_file(config, "lab_2019.txt", "lab_2019_out.txt", delimiter="|", guideline_year=2019)
```

or a config with `"GuidelineYear": 2019`. Or re-interpret old data with **current**
breakpoints (the default, 2026) to make a time series comparable.

---

## 7. See what changed between breakpoint years

```python
import dataclasses
from collections import Counter
from amrie.io_library import load_input_file, interpret_isolates

columns, rows = load_input_file("src/amrie/resources/SampleInputFile.txt", "|")
new = interpret_isolates(config, columns, rows)                                        # 2026
old = interpret_isolates(dataclasses.replace(config, guideline_year=2020), columns, rows)

changes = Counter(
    (row["ORGANISM"], test, before[test], after.get(test))
    for (row, before), (_, after) in zip(old, new)
    for test in before if before[test] != after.get(test)
)
sum(changes.values())        # 181
changes.most_common(4)
# [(('eco', 'PIP_ND100', 'S', ''), 24), (('hin', 'AMC_ND20', 'S', ''), 23),
#  (('pmi', 'PIP_ND100', 'S', ''), 13), (('kpn', 'PIP_ND100', 'S', ''), 10)]
```

181 results differ between the 2020 and 2026 CLSI tables for the sample — most because
breakpoints for those disk tests are no longer published (`S` → blank).

---

## 8. Compare CLSI and EUCAST on the same isolates

The guideline is part of the column name, so re-code the columns:

```python
def to_eucast(name: str) -> str:
    return name[:4] + "E" + name[5:] if len(name) > 5 and name[3] == "_" and name[4] == "N" else name

e_columns = [to_eucast(c) for c in columns]
e_rows = [{to_eucast(k): v for k, v in r.items()} for r in rows]
eucast = interpret_isolates(config, e_columns, e_rows)

disagree = Counter(
    (test[:3], clsi, e[to_eucast(test)])
    for (_, c), (_, e) in zip(new, eucast)
    for test, clsi in c.items()
    if clsi and e.get(to_eucast(test)) and clsi != e[to_eucast(test)]
)
sum(disagree.values())       # 506
disagree.most_common(3)      # [(('CIP', 'S', 'I'), 157), (('IPM', 'S', 'I'), 47), (('ATM', 'S', 'I'), 41)]
```

Disk potencies differ between guidelines for some drugs; only tests with the same
potency in both can be compared this way.

---

## 9. CSF / meningitis specimens

```json
{ "PrioritizedBreakpointTypes": ["Human"], "PrioritizedSitesOfInfection": ["Meningitis"] }
```

| `spn PEN_NM` | general config | meningitis config |
|---|---|---|
| 0.06 | S | S |
| 0.12 | S | **R** |
| 4 | I | **R** |

Split files by specimen type and run each with its own config, or in Python:

```python
import dataclasses
csf = dataclasses.replace(config, prioritized_sites_of_infection=["Meningitis"])
csf.update_sites_of_infection()
CSF_CODES = {"sf"}            # your laboratory's specimen code(s) for CSF
spec_config = lambda row: csf if row.get("SPEC_TYPE") in CSF_CODES else config
```

---

## 10. Veterinary laboratory

```json
{ "PrioritizedBreakpointTypes": ["Animal", "Human", "ECOFF"] }
```

Enrofloxacin has no human breakpoint: `eco ENR_ND5 20` → `I` with Animal allowed,
blank with `["Human"]`. AMRIE has no host setting — among veterinary breakpoints the
alphabetically first host is used (*Cats* before *Poultry*), see
[Breakpoint selection](breakpoint-selection.md#step-2-sort). For a specific species,
add user-defined breakpoints (recipe 13).

---

## 11. Surveillance with ECOFFs

```json
{
  "PrioritizedBreakpointTypes": ["ECOFF"],
  "UseIntrinsicResistanceRules": false,
  "EnabledExpertInterpretationRules": ["NONE"],
  "HorizontalAntibioticResults": false
}
```

```python
ecoff = dataclasses.replace(config, prioritized_breakpoint_types=["ECOFF"])
interpret_single(ecoff, "eco", "AMP_NM", "8")     # 'WT'
interpret_single(ecoff, "eco", "AMP_NM", "32")    # 'NWT'
```

---

## 12. Local breakpoints for a new drug (`X_1`)

Call the new drug `X_1` in your data (`X_1_NM` for a CLSI-style MIC column) and give
it breakpoints. `local-breakpoints.txt` (tab-delimited, 21 columns):

```text
GUIDELINES	YEAR	TEST_METHOD	POTENCY	ORGANISM_CODE	ORGANISM_CODE_TYPE	BREAKPOINT_TYPE	HOST	SITE_OF_INFECTION	REFERENCE_TABLE	REFERENCE_SEQUENCE	WHONET_ABX_CODE	WHONET_TEST	R	I	SDD	S	ECV_ECOFF	DATE_ENTERED	DATE_MODIFIED	COMMENTS
User-defined	2026	MIC		EBC	FAMILY_CODE	Human	Human		Local study	1	X_1	X_1_NM	8	4		2		2026-11-18		Local validation 2026
```

(Enterobacterales, S ≤ 2, I 4, R ≥ 8.)

```json
{ "UserDefinedBreakpointsFile": "/srv/amrie/local-breakpoints.txt" }
```

| `X_1_NM` for `eco` | 1 | 2 | 4 | 8 | 16 | `<=2` | `>8` |
|---|---|---|---|---|---|---|---|
| result | S | S | I | R | R | S | R |

The breakpoint applies to every Enterobacterales and every guideline year; *S. aureus*
stays blank. Python, without a config file:

```python
from amrie.breakpoint import load_breakpoints
config.user_defined_breakpoints = load_breakpoints("local-breakpoints.txt", user_defined=True)
```

---

## 13. Override a guideline breakpoint locally

A user-defined row for an existing test **wins over** the built-in breakpoint for the
organisms it covers. To use, say, a local ampicillin disk breakpoint for
Enterobacterales, add a row with `WHONET_TEST = AMP_ND10`, `ORGANISM_CODE = EBC`,
`ORGANISM_CODE_TYPE = FAMILY_CODE` and your R/I/S. Because user-defined rows ignore
the year, the override applies to every `GuidelineYear`; keep separate files per
validation period if needed.

---

## 14. Audit which rule or breakpoint produced each result

Turn comments on and use the long layout, then filter:

```json
{ "IncludeInterpretationComments": true, "HorizontalAntibioticResults": false }
```

```bash
awk -F'\t' 'NR==1 || $NF ~ /[*!]$/' results.txt     # only inferred results
```

For the exact breakpoint behind a result:

```python
from amrie.antibiotic_rules import AntibioticSpecificInterpretationRules as Rules

r = Rules("eco", "AMP_ND10", "19", [], guideline_year=2026)
b = r.most_applicable_breakpoint
f"{r.get_interpretation()} via {b.GUIDELINES} {b.YEAR} {b.REFERENCE_TABLE} {b.ORGANISM_CODE}/{b.ORGANISM_CODE_TYPE} S>={b.S} R<={b.R}"
```

---

## 15. Method comparison without intrinsic rules

```python
raw = dataclasses.replace(config, use_intrinsic_resistance_rules=False, enabled_expert_interpretation_rules=[])
interpret_single(raw, "kpn", "AMP_ND10", "25")    # 'S'   breakpoint only (normally R*)
interpret_single(raw, "sau", "FOX_ND30", "15")    # 'R'   no MRS (normally R!)
```

---

## 16. QC log checks

See [Quality control → batch QC](quality-control.md#batch-qc-from-a-file).

---

## 17. Call AMRIE from another language

Run `amrie-web` and use the REST API.

**JavaScript**

```javascript
const res = await fetch("http://localhost:8080/api/interpret/single", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    organism_code: "eco", whonet_abx_code: "AMP", measurement: "19",
    guidelines: ["CLSI"], test_method: "disk", potency: "10", guideline_year: 2026,
  }),
});
console.log((await res.json()).results);   // [{ whonet_test: "AMP_ND10", interpretation: "S" }]
```

**R**

```r
library(httr2)
request("http://localhost:8080/api/interpret/single") |>
  req_body_json(list(organism_code = "eco", whonet_abx_code = "AMP", measurement = "19",
                     guidelines = list("CLSI"), test_method = "disk", potency = "10",
                     guideline_year = 2026)) |>
  req_perform() |> resp_body_json()
```

Or shell out to the CLI (`amrie file …`) for batch work.

---

## 18. A long-running interpretation service

Importing `amrie` costs about a second; after that, lookups are cached. In a service:

- import once at start-up and load configurations once;
- share them across threads — the engine is thread-safe;
- the breakpoint cache is bounded (262,144 entries) and keyed on every setting, so
  serving many different configurations is safe;
- monitor it with `amrie.antibiotic_rules.cache_statistics()`.

```python
from concurrent.futures import ThreadPoolExecutor
from amrie.isolate import IsolateInterpretation

def job(record):
    return IsolateInterpretation(record, list(record), None, [], guideline_year=2026).get_all_interpretations()

records = [{"ORGANISM": "eco", "AMP_ND10": "19"}, {"ORGANISM": "kpn", "AMP_ND10": "25"}]
with ThreadPoolExecutor() as pool:
    results = list(pool.map(job, records))      # [{'AMP_ND10': 'S'}, {'AMP_ND10': 'R*'}]
```
