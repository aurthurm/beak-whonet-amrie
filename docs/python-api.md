# Python API reference

Everything you can call from Python, from the three one-line entry points down to
the lookup functions the engine itself uses. All examples run against the bundled
data; results are for guideline year 2026.

- [Quick reference](#quick-reference)
- [Top-level functions (`amrie`)](#top-level-functions-amrie)
- [Configuration (`amrie.config`)](#configuration-amrieconfig)
- [Interpreting isolates (`amrie.isolate`)](#interpreting-isolates-amrieisolate)
- [One measurement in detail (`amrie.antibiotic_rules`)](#one-measurement-in-detail-amrieantibiotic_rules)
- [Batch files (`amrie.io_library`)](#batch-files-amrieio_library)
- [Breakpoints (`amrie.breakpoint`)](#breakpoints-amriebreakpoint)
- [Intrinsic resistance (`amrie.expected_resistance`)](#intrinsic-resistance-amrieexpected_resistance)
- [Expert rules (`amrie.expert_rule`)](#expert-rules-amrieexpert_rule)
- [Quality control (`amrie.qc`)](#quality-control-amrieqc)
- [Reference tables (`amrie.organism`, `amrie.antibiotic`)](#reference-tables-amrieorganism-amrieantibiotic)
- [Parsing helpers (`amrie.parsing`, `amrie.io_utils`)](#parsing-helpers-amrieparsing-amrieio_utils)
- [Constants (`amrie.constants`)](#constants-amrieconstants)
- [Caches (`amrie.antibiotic_rules`, `amrie.bounded_cache`)](#caches)
- [Thread safety and performance](#thread-safety-and-performance)
- [Errors](#errors)

---

## Quick reference

```python
from amrie import interpret_single, interpret_file, interpret_qc_single, InterpretationConfig
from amrie.config import read_configuration, default_configuration

config = read_configuration("src/amrie/resources/SampleConfig.json")

interpret_single(config, "eco", "AMP_ND10", "19")          # 'S'
interpret_file(config, "in.txt", "out.txt", delimiter="|")  # writes out.txt
interpret_qc_single("atcc25922", "AMP_ND10", "18")         # 'IN'
```

| You have… | Use |
|---|---|
| one organism + one test + one value | `interpret_single` |
| a delimited file on disk | `interpret_file` |
| rows already in memory (DataFrame, DB, HL7…) | `IsolateInterpretation` or `interpret_isolates` |
| a QC strain result | `interpret_qc_single` |
| a question like "which breakpoint would apply?" | `get_applicable_breakpoints` |
| "is this organism intrinsically resistant to X?" | `get_applicable_expected_resistance_rules` |
| "which expert rules could apply to this isolate?" | `get_applicable_expert_rules` |

Importing `amrie` loads all resource tables once (about one second); afterwards
every call is in-memory.

---

## Top-level functions (`amrie`)

### `interpret_single(config, organism, antibiotic, measurement) -> str`

Interpret one measurement for one organism and one antibiotic test column.

| Parameter | Type | Description |
|---|---|---|
| `config` | `InterpretationConfiguration` \| `str` \| `Path` | a configuration object, or a path to a JSON config file |
| `organism` | `str` | WHONET organism code, e.g. `"eco"` |
| `antibiotic` | `str` | full WHONET test column, e.g. `"AMP_ND10"`, `"CIP_EM"`, `"X_3_NM"` |
| `measurement` | `str` | raw value: `"19"`, `"0.25"`, `"<=2"`, `">16"`, `"≤2"` |

Returns the interpretation **with** suffixes (`*`, `!`, `?`) — see
[Concepts](concepts.md#interpretation-categories). The config's guideline year is
used. Expert rules can fire from the single drug (e.g. MRS from cefoxitin).

```python
from amrie import interpret_single
from amrie.config import read_configuration

config = read_configuration("src/amrie/resources/SampleConfig.json")

interpret_single(config, "eco", "AMP_ND10", "19")     # 'S'
interpret_single(config, "eco", "AMP_ND10", "15")     # 'I'
interpret_single(config, "eco", "AMP_ND10", "12")     # 'R'
interpret_single(config, "eco", "AMP_NM",   "32")     # 'R'
interpret_single(config, "eco", "AMP_NM",   "<=16")   # 'S?'
interpret_single(config, "eco", "AMP_NM",   ">8")     # 'NS'
interpret_single(config, "kpn", "AMP_ND10", "25")     # 'R*'  intrinsic
interpret_single(config, "sau", "FOX_ND30", "15")     # 'R!'  MRS
interpret_single(config, "sau", "CPT_ND30", "22")     # 'SDD'
interpret_single(config, "nme", "PEN_EM",   "0.25")   # 'S'   EUCAST, N. meningitidis
interpret_single(config, "zzz", "AMP_ND10", "19")     # ''    unknown organism
interpret_single(config, "eco", "AMP_ND10", "abc")    # ''    not a number

# A path works too (the file is read on every call — prefer a loaded config in loops):
interpret_single("src/amrie/resources/SampleConfig.json", "ent", "PEN_ND10", "19")  # 'S'
```

### `interpret_file(config, input_file, output_file, delimiter="\t", guideline_year=-1) -> None`

Read a delimited input file, interpret every isolate (in parallel), write the
output file.

| Parameter | Default | Description |
|---|---|---|
| `config` | — | configuration object or path to a JSON file |
| `input_file` | — | path to the input file (UTF-8; a BOM is ignored) |
| `output_file` | — | path of the output file (created or overwritten; always tab-delimited) |
| `delimiter` | `"\t"` | input field separator: `"\t"`, `","`, `";"` or `"|"` |
| `guideline_year` | `-1` | override the config's `GuidelineYear`; `-1` keeps the config value |

```python
from amrie import interpret_file

interpret_file(config, "isolates.txt", "results.txt", delimiter="|")
interpret_file(config, "lab_2019.csv", "lab_2019_out.txt", delimiter=",", guideline_year=2019)
interpret_file("my-config.json", "isolates.tsv", "results.txt")      # TAB input
```

The output format is described in [Data formats](data-formats.md#output-files).

### `interpret_qc_single(organism, antibiotic, measurement, round_half_dilutions=True) -> str`

Evaluate a QC reference-strain result. Returns `"IN"`, `"OUT"` or `""`.

```python
from amrie import interpret_qc_single

interpret_qc_single("atcc25922", "AMP_ND10", "18")   # 'IN'   range 15–22 mm
interpret_qc_single("atcc25922", "AMP_ND10", "10")   # 'OUT'
interpret_qc_single("atcc25922", "AMP_ND10", "x")    # ''
```

See [Quality control](quality-control.md).

### `InterpretationConfig`

An alias of `amrie.config.InterpretationConfiguration`, exported for convenience.

### `__version__`

```python
import amrie
amrie.__version__        # '1.0.0'
```

---

## Configuration (`amrie.config`)

### `InterpretationConfiguration`

A dataclass. Every field has a default, so `InterpretationConfiguration()` is valid.

| Field | Type | Default | JSON key |
|---|---|---|---|
| `round_half_dilutions` | `bool` | `True` | `RoundHalfDilutions` |
| `include_interpretation_comments` | `bool` | `False` | `IncludeInterpretationComments` |
| `use_intrinsic_resistance_rules` | `bool` | `True` | `UseIntrinsicResistanceRules` |
| `enabled_expert_interpretation_rules` | `list[str] \| None` | `None` (all rules) | `EnabledExpertInterpretationRules` |
| `guideline_year` | `int` | `2026` | `GuidelineYear` |
| `prioritized_breakpoint_types` | `list[str] \| None` | `None` (all types) | `PrioritizedBreakpointTypes` |
| `prioritized_sites_of_infection` | `list[str] \| None` | `None` (default order) | `PrioritizedSitesOfInfection` |
| `disabled_sites_of_infection` | `list[str] \| None` | `None` | `DisabledSitesOfInfection` |
| `horizontal_antibiotic_results` | `bool` | `True` | `HorizontalAntibioticResults` |
| `user_defined_breakpoints_file` | `str` | `""` | `UserDefinedBreakpointsFile` |
| `user_defined_breakpoints` | `list[Breakpoint]` | `[]` | — (loaded from the file) |

```python
from amrie.config import InterpretationConfiguration
from amrie.breakpoint import BreakpointTypes
from amrie.expert_rule import RuleCodes

config = InterpretationConfiguration(
    guideline_year=2026,
    prioritized_breakpoint_types=[BreakpointTypes.HUMAN],
    enabled_expert_interpretation_rules=[RuleCodes.MRSTAPH, RuleCodes.ICR],
    include_interpretation_comments=True,
)
```

Change one field without mutating the original:

```python
import dataclasses

strict_human = dataclasses.replace(config, prioritized_breakpoint_types=["Human"])
year_2020 = dataclasses.replace(config, guideline_year=2020)
```

Method **`update_sites_of_infection()`** reconciles the site lists with the
canonical order (drops unknown names, appends missing sites unless disabled). It is
called by `read_configuration`; call it yourself after building a config that sets
`prioritized_sites_of_infection` or `disabled_sites_of_infection`:

```python
cfg = InterpretationConfiguration(prioritized_sites_of_infection=["Meningitis"],
                                  disabled_sites_of_infection=["Oral"])
cfg.update_sites_of_infection()
cfg.prioritized_sites_of_infection[:3]      # ['Meningitis', 'Non-meningitis', 'Non-endocarditis']
"Oral" in cfg.prioritized_sites_of_infection   # False
```

### `read_configuration(config_file) -> InterpretationConfiguration`

Load a JSON configuration file. Tolerant by design:

- key names are case-insensitive (`GuidelineYear`, `guidelineyear` and `guideline_year` all work);
- `$schema`, unknown keys, and keys starting with `_Comment` or `DISABLED_` are ignored;
- `//` and `/* … */` comments and trailing commas are accepted; a UTF-8 BOM is accepted;
- empty lists for the four list settings mean "not set" (`None`);
- `UserDefinedBreakpointsFile` is loaded into `user_defined_breakpoints` (relative
  paths are resolved against the package directory `src/amrie/`; a missing file is
  silently ignored, as in the C# engine).

```python
from amrie.config import read_configuration
config = read_configuration("src/amrie/resources/SampleConfig.json")
config.guideline_year, config.enabled_expert_interpretation_rules
# (2026, ['BLNAR-HFLU', 'MRS', 'ICR'])
```

### `default_configuration() -> InterpretationConfiguration`

An opinionated, ready-to-use configuration — note it differs from the dataclass
defaults:

| Field | `default_configuration()` |
|---|---|
| `include_interpretation_comments` | `True` |
| `enabled_expert_interpretation_rules` | `["MRS", "BLNAR-HFLU", "ICR"]` |
| `prioritized_breakpoint_types` | `["Human"]` |
| `prioritized_sites_of_infection` | the full default order (31 sites) |
| everything else | dataclass defaults |

---

## Interpreting isolates (`amrie.isolate`)

### `IsolateInterpretation`

Interprets **one isolate record** — all of its antibiotic columns together, which
is what lets expert rules see the whole panel.

```text
IsolateInterpretation(
    data_row_values: dict[str, str],          # {"ORGANISM": "sau", "FOX_ND30": "15", ...}
    column_names: list[str],                  # order of the columns (used for output order)
    enabled_expert_interpretation_rules: list[str] | None,
    user_defined_breakpoints: list[Breakpoint],
    guideline_year: int = -1,                 # pass a real year; -1 matches no breakpoints
    use_intrinsic_resistance_rules: bool = True,
    prioritized_breakpoint_types: list[str] | None = None,
    prioritized_sites_of_infection: list[str] | None = None,
    round_half_dilutions: bool = True,
)
```

- **`get_all_interpretations() -> dict[str, str]`** — `{test_column: interpretation}`
  for every antibiotic column in the row (suffixes included).
- **`IsolateInterpretation.get_single_interpretation(config, organism, antibiotic, measurement) -> str`**
  — static helper used by `interpret_single`.

Non-antibiotic columns (`ORGANISM`, `ESBL`, `BETA_LACT`, `INDUC_CLI`, …) are read
by expert rules but not interpreted. Blank values are skipped.

```python
from amrie.isolate import IsolateInterpretation

row = {"ORGANISM": "sau", "FOX_ND30": "15", "PEN_ND10": "35", "VAN_NM": "1"}
IsolateInterpretation(row, list(row), ["MRS"], [], guideline_year=2026).get_all_interpretations()
# {'FOX_ND30': 'R!', 'PEN_ND10': 'R!', 'VAN_NM': 'S'}

row = {"ORGANISM": "eco", "CTX_ND30": "20", "MAN_ND30": "25", "CFP_ND75": "30"}
IsolateInterpretation(row, list(row), ["ESBL-AMPC-PROBABLE"], [], guideline_year=2026).get_all_interpretations()
# {'CTX_ND30': 'R', 'MAN_ND30': 'R!', 'CFP_ND75': 'R!'}
```

Interpreting a pandas DataFrame:

```python
import pandas as pd
from amrie.isolate import IsolateInterpretation

df = pd.DataFrame([
    {"ORGANISM": "eco", "AMP_ND10": "19", "CTX_ND30": "20"},
    {"ORGANISM": "kpn", "AMP_ND10": "25", "CTX_ND30": "30"},
])

def interpret(row):
    values = {k: str(v) for k, v in row.items() if pd.notna(v) and str(v).strip()}
    return pd.Series(IsolateInterpretation(values, list(df.columns), None, [],
                                           guideline_year=2026).get_all_interpretations())

df.join(df.apply(interpret, axis=1).add_suffix("_INTERP"))
#   ORGANISM AMP_ND10 CTX_ND30 CTX_ND30_INTERP AMP_ND10_INTERP
# 0      eco       19       20               R               S
# 1      kpn       25       30               S              R*
```

---

## One measurement in detail (`amrie.antibiotic_rules`)

### `AntibioticSpecificInterpretationRules`

The unit the engine evaluates: one organism, one test column, one value. Useful
when you want to see *which* breakpoint or rule produced a result.

```python
from amrie.antibiotic_rules import AntibioticSpecificInterpretationRules

r = AntibioticSpecificInterpretationRules("eco", "AMP_ND10", "19", [], guideline_year=2026)
r.get_interpretation()                    # 'S'
bp = r.most_applicable_breakpoint
bp.GUIDELINES, bp.ORGANISM_CODE, bp.ORGANISM_CODE_TYPE, bp.R, bp.I, bp.S
# ('CLSI', 'EBC', 'FAMILY_CODE', Decimal('13'), '14-16', Decimal('17'))
r.most_applicable_intrinsic               # None

k = AntibioticSpecificInterpretationRules("kpn", "AMP_ND10", "25", [], guideline_year=2026)
k.get_interpretation()                    # 'R*'
k.most_applicable_intrinsic.REFERENCE_TABLE   # 'Enterobacterales'
```

Constructor keywords: `guideline_year`, `round_half_dilutions`,
`use_intrinsic_resistance_rules`, `prioritized_breakpoint_types`,
`prioritized_sites_of_infection`. Expert rules are **not** applied here — they need
the whole isolate (`IsolateInterpretation`).

### `preheat_breakpoint_cache(user_defined_breakpoints, guideline_year, prioritized_breakpoint_types, prioritized_sites_of_infection, distinct_interpretation_keys, max_workers=None)`

Resolve the breakpoints for many `(organism, guideline, test_column)` keys in
parallel before a batch run. `interpret_isolates` calls it for you.

---

## Batch files (`amrie.io_library`)

The building blocks behind `interpret_file`, for custom pipelines.

| Function | Purpose |
|---|---|
| `load_input_file(input_file, delimiter) -> (columns, rows)` | Parse a file into the header list and one `dict` per non-blank row (blank fields omitted) |
| `interpret_isolates(config, columns, rows, guideline_year=-1, parallel=True) -> [(row, interpretations)]` | Interpret all rows, in input order; pre-heats the cache; parallel with threads |
| `generate_output_file(output_file, config, columns, results) -> None` | Write the horizontal or vertical output file |
| `FileInterpretationParameters(input_file, delimiter, guideline_year, config_file, output_file)` | Arguments bundle used by the CLI |
| `interpret_data_file(params) -> None` | Load config + file, interpret, write — what `amrie file` runs |

```python
from amrie.config import read_configuration
from amrie.io_library import load_input_file, interpret_isolates, generate_output_file

config = read_configuration("src/amrie/resources/SampleConfig.json")
columns, rows = load_input_file("isolates.txt", "|")
results = interpret_isolates(config, columns, rows)          # [(row, {"AMP_ND10": "S", ...}), ...]

resistant = [row for row, interp in results if any(v.startswith("R") for v in interp.values())]
generate_output_file("results.txt", config, columns, results)
```

Rows with fewer fields than the header are skipped (as upstream). See
[Data formats](data-formats.md#input-files).

---

## Breakpoints (`amrie.breakpoint`)

### `BREAKPOINTS: list[Breakpoint]`

All 51,001 built-in breakpoints. Each `Breakpoint` is a dataclass with the columns of
`Breakpoints.txt`: `GUIDELINES`, `YEAR`, `TEST_METHOD`, `POTENCY`, `ORGANISM_CODE`,
`ORGANISM_CODE_TYPE`, `BREAKPOINT_TYPE`, `HOST`, `SITE_OF_INFECTION`,
`SITES_OF_INFECTION` (tuple), `REFERENCE_TABLE`, `REFERENCE_SEQUENCE`,
`WHONET_ABX_CODE`, `WHONET_TEST`, `R` (Decimal), `I` (str range), `SDD` (str),
`S` (Decimal), `ECV_ECOFF` (Decimal), `ECV_ECOFF_TENTATIVE`, `DATE_ENTERED`,
`DATE_MODIFIED`, `COMMENTS`.

```python
from collections import Counter
from amrie.breakpoint import BREAKPOINTS

Counter(b.GUIDELINES for b in BREAKPOINTS).most_common(3)
# [('CLSI', 27017), ('EUCAST', 22360), ('SFM', 1034)]
```

### `get_applicable_breakpoints(...) -> list[Breakpoint]`

```text
get_applicable_breakpoints(
    whonet_organism_code: str,
    user_defined_breakpoints: list[Breakpoint],
    prioritized_guidelines: list[str] | None = None,
    prioritized_guideline_years: list[int] | None = None,
    prioritized_breakpoint_types: list[str] | None = None,
    prioritized_sites_of_infection: list[str] | None = None,
    prioritized_whonet_abx_full_drug_codes: list[str] | None = None,
    return_first_breakpoint_only: bool = False,
)
```

Returns the applicable breakpoints, most applicable first (see
[Breakpoint selection](breakpoint-selection.md)). `None` for a filter means "any".

```python
from amrie.breakpoint import get_applicable_breakpoints

for b in get_applicable_breakpoints("eco", [], prioritized_guidelines=["CLSI"],
                                    prioritized_guideline_years=[2026],
                                    prioritized_whonet_abx_full_drug_codes=["AMP_ND10"]):
    print(b.BREAKPOINT_TYPE, b.ORGANISM_CODE, b.ORGANISM_CODE_TYPE, repr(b.SITE_OF_INFECTION), b.R, b.I, b.S, b.ECV_ECOFF)
# Human  EBC FAMILY_CODE   ''                                      13 14-16 17 0
# Animal ECO SEROVAR_GROUP 'Uncomplicated urinary tract infection'  0       17 0
# Animal ECO SEROVAR_GROUP 'Uncomplicated urinary tract infection'  0       17 0
# ECOFF  ECO SEROVAR_GROUP ''                                       0        0 13
```

(The two Animal rows are for different hosts.) Pass
`return_first_breakpoint_only=True` with exactly one drug code to get just the
breakpoint the engine would use.

### `load_breakpoints(path, user_defined=False) -> list[Breakpoint]`

Load a breakpoint file in the `Breakpoints.txt` format. With `user_defined=True`
every row's `GUIDELINES` becomes `"UserDefined"` (`GuidelineNames.USER_DEFINED`),
which makes it sort ahead of built-in rows and ignore the year filter.

### `BreakpointTypes`

`BreakpointTypes.HUMAN == "Human"`, `ANIMAL == "Animal"`, `ECOFF == "ECOFF"`.

---

## Intrinsic resistance (`amrie.expected_resistance`)

### `EXPECTED_RESISTANCE_PHENOTYPE_RULES`

All 1,024 rules (CLSI 474, EUCAST 550). Fields: `GUIDELINE`, `REFERENCE_TABLE`,
`ORGANISM_CODE`, `ORGANISM_CODE_TYPE`, `EXCEPTION_ORGANISM_CODE`,
`EXCEPTION_ORGANISM_CODE_TYPE`, `ABX_CODE`, `ABX_CODE_TYPE` (`WHONET_ABX_CODE` or
`ATC_CODE`), `ANTIBIOTIC_EXCEPTIONS`, `DATE_ENTERED`, `DATE_MODIFIED`, `COMMENTS`.

### `get_applicable_expected_resistance_rules(organism, prioritized_guidelines=None, antimicrobial_codes=None)`

Rules that apply to an organism, optionally restricted to guidelines and drug codes.
ATC-class rules are expanded to concrete drugs.

```python
from amrie.expected_resistance import get_applicable_expected_resistance_rules as rules

sorted({r.ABX_CODE for r in rules("kpn", ["CLSI"])})
# ['AMP', 'AZM', 'CLI', 'CLR', 'DAP', 'ERY', 'FUS', 'LNZ', 'ORI', 'QDA', 'RIF',
#  'TEC', 'TIC', 'TLV', 'TZD', 'VAN']

[r.ABX_CODE for r in rules("lmo", ["CLSI"], ["CFR"])]   # ['CFR']  via ATC class J01DB
rules("eco", ["CLSI"], ["AMP"])                         # []      not intrinsic
```

### `resolve_antibiotic_code_type(code, declared_type, antibiotics=None) -> str`

The load-time fix-up for mislabelled rules (ported from upstream): keeps the
declared type when it matches the antibiotic table, otherwise switches to the type
that does match, and raises `ValueError` when neither or both match.

---

## Expert rules (`amrie.expert_rule`)

### `EXPERT_INTERPRETATION_RULES`

The 7 rule rows. Fields: `RULE_CODE`, `DESCRIPTION`, `ORGANISM_CODE`,
`ORGANISM_CODE_TYPE`, `RULE_CRITERIA` (list of `ExpertRuleCriterion(test_name,
test_result)`), `CriteriaOperator` (`"AND"` / `"OR"`), `AFFECTED_ANTIBIOTICS`
(expanded drug codes), `ANTIBIOTIC_EXCEPTIONS`.

### `get_applicable_expert_rules(organism, antimicrobial_codes, other_tests, enabled_expert_interpretation_rules)`

Rules whose organism scope matches and whose criteria reference at least one of the
tests present.

```python
from amrie.expert_rule import get_applicable_expert_rules

[r.DESCRIPTION for r in get_applicable_expert_rules("sau", ["FOX_ND30", "PEN_ND10"], ["OXA_SCREEN"], None)]
# ['Methicillin-resistant Staphylococcus:  MRS = Positive',
#  'Methicillin-resistant Staphylococcus:  Oxacillin or cefoxitin = Non-susceptible']

get_applicable_expert_rules("sau", ["PEN_ND10"], [], None)   # []  nothing to trigger on
```

### `RuleCodes`, `PROF_CLASS`, `RuleOperators`

```python
from amrie.expert_rule import RuleCodes, PROF_CLASS

RuleCodes.ESBL_CONFIRMED  # 'ESBL-CONFIRMED'
RuleCodes.ESBL_PROBABLE   # 'ESBL-AMPC-PROBABLE'
RuleCodes.BLNAR           # 'BLNAR-HFLU'
RuleCodes.MRSTAPH         # 'MRS'
RuleCodes.ICR             # 'ICR'
RuleCodes.ALL             # all five
PROF_CLASS.CEPH3          # 'CEPH3' — "any 3rd-generation cephalosporin" in criteria
```

See [Expert rules](expert-rules.md).

---

## Quality control (`amrie.qc`)

| Name | Purpose |
|---|---|
| `QUALITY_CONTROL_RANGES` | all 23,136 ranges (fields `GUIDELINE`, `YEAR`, `STRAIN`, `REFERENCE_TABLE`, `WHONET_ORG_CODE`, `ANTIBIOTIC`, `ABX_TEST`, `WHONET_ABX_CODE`, `METHOD`, `MEDIUM`, `MINIMUM`, `MAXIMUM`, …) |
| `get_applicable_quality_control_range(strain, test_column, qc_ranges=None)` | the range that applies, or `None` |
| `get_quality_control_interpretation(strain, test_column, measurement, round_half_dilutions=True)` | `"IN"` / `"OUT"` / `""` |
| `load_quality_control_ranges(path=None)` | load a QC table file |

```python
from amrie.qc import get_applicable_quality_control_range
r = get_applicable_quality_control_range("atcc25922", "AMP_ND10")
r.GUIDELINE, r.YEAR, r.MINIMUM, r.MAXIMUM, r.REFERENCE_TABLE
# ('CLSI', 2026, Decimal('15'), Decimal('22'), 'Table 4A-1')
```

---

## Reference tables (`amrie.organism`, `amrie.antibiotic`)

| Name | Contents |
|---|---|
| `amrie.organism.ALL_ORGANISMS` | every row of `Organisms.txt` (2,980), including renamed/obsolete entries |
| `amrie.organism.CURRENT_ORGANISMS` | `dict[code, Organism]` of current organisms (2,351) |
| `amrie.organism.MERGED_ORGANISMS` | `dict[old_code, new_code]` for merged codes (17), e.g. `'csl' → 'cal'` |
| `amrie.antibiotic.ALL_ANTIBIOTICS` | every row of `Antibiotics.txt` (565) |
| `amrie.antibiotic.CEPH3_ANTIBIOTIC_CODES` | 3rd-generation cephalosporin codes (for the `CEPH3` criterion) |
| `amrie.antibiotic.MRS_ANTIBIOTICS_EXCEPT_CPT_BPR` / `ICR_ANTIBIOTICS` | drug lists used by the MRS and ICR rules |

```python
from amrie.organism import CURRENT_ORGANISMS
o = CURRENT_ORGANISMS["eco"]
o.ORGANISM, o.SEROVAR_GROUP, o.GENUS_CODE, o.FAMILY_CODE      # ('Escherichia coli', 'ECO', 'ESC', 'EBC')

# Find organism codes by name
[c for c, o in CURRENT_ORGANISMS.items() if o.ORGANISM.startswith("Klebsiella pneumoniae")][:3]
# ['koz', 'kpn', 'krn']

from amrie.antibiotic import ALL_ANTIBIOTICS
amp = next(a for a in ALL_ANTIBIOTICS if a.WHONET_ABX_CODE == "AMP")
amp.ANTIBIOTIC, amp.CLASS, amp.ATC_CODE                        # ('Ampicillin', 'Penicillins', 'J01CA01')
```

---

## Parsing helpers (`amrie.parsing`, `amrie.io_utils`)

### `AntibioticComponents(test_column)`

Splits a test column into `code`, `guideline` and `test_method`; raises `ValueError`
for malformed codes.

```python
from amrie.parsing import AntibioticComponents as A

a = A("AMP_ND10"); a.code, a.guideline, a.test_method     # ('AMP', 'CLSI', 'DISK')
a = A("CIP_EM");   a.code, a.guideline, a.test_method     # ('CIP', 'EUCAST', 'MIC')
a = A("X_12_NM");  a.code, a.guideline, a.test_method     # ('X_12', 'CLSI', 'MIC')

A("X_0_NM")    # ValueError: Invalid user-defined antibiotic test code 'X_0_NM'. User-defined
               #             antibiotics must follow the pattern X_# or X_## (e.g., X_1 or X_12).
A("X_01_NM")   # ValueError (leading zero)
A("PEN")       # ValueError: Invalid antibiotic test code format 'PEN'.
```

`x_1_ED30` (lower-case `x`) is accepted, but the code keeps its case (`'x_1'`), so
use upper-case `X_` in data to match breakpoints and rules.

### `parse_result(test_method, raw) -> (ok, value, modifier)`

```python
from amrie.parsing import parse_result
parse_result("MIC", "<4")     # (True, Decimal('2'), '<=')   '<4' means at most one dilution lower
parse_result("MIC", ">=8")    # (True, Decimal('4'), '>')
parse_result("MIC", "≤2")     # (True, Decimal('2'), '<=')
parse_result("MIC", "=<2")    # (True, Decimal('2'), '<=')   swapped symbols are fixed
parse_result("DISK", "19")    # (True, Decimal('19'), None)
```

### `round_etest_half_dilutions_up(value) -> Decimal`

```python
from decimal import Decimal
from amrie.parsing import round_etest_half_dilutions_up as up
[str(up(Decimal(x))) for x in ("0.19", "0.75", "1.5", "2", "3", "6")]
# ['0.25', '1', '2', '2', '4', '8']
```

### Regular expressions

| Name | Matches |
|---|---|
| `VALID_ANTIBIOTIC_FIELD_NAME_REGEX` | a full test column: `AMP_ND10`, `X_12_NM` (not `X_01_NM`, not `OXA_SCREEN`) |
| `VALID_ANTIBIOTIC_CODE_REGEX` | just the drug part: `AMP`, `X_12` |
| `NUMERIC_ANTIBIOTIC_RESULT_REGEX` | a numeric measurement with optional `<`, `>`, `=` |

### `amrie.antibiotic.short_code(test_column) -> str`

`short_code("AMP_ND10") == "AMP"`, `short_code("X_12_NM") == "X_12"`.

### `amrie.io_utils`

| Function | Purpose |
|---|---|
| `split_line(record, delimiter) -> list[str]` | split one delimited line, honouring `"…"` quoting and `""` escapes; unquoted fields are trimmed |
| `to_line(values, delimiter) -> str` | join fields, quoting any that contain the delimiter, a quote, a line break, or leading/trailing whitespace |
| `get_resource_headers(headers) -> dict[str, int]` | header name → column index |

```python
from amrie.io_utils import split_line, to_line
split_line('eco,"Smith, J",19', ",")          # ['eco', 'Smith, J', '19']
split_line('a,"say ""hi""",c', ",")          # ['a', 'say "hi"', 'c']
to_line(["eco", "Smith, J", " padded"], ",")  # 'eco,"Smith, J"," padded"'
```

---

## Constants (`amrie.constants`)

```python
from amrie import constants as C

C.BREAKPOINT_TABLE_REVISION_YEAR           # 2026
C.InterpretationCodes.SUSCEPTIBLE          # 'S'   also INTERMEDIATE, RESISTANT, NON_SUSCEPTIBLE,
                                           #       SUSCEPTIBLE_DOSE_DEPENDENT, WILD_TYPE, NON_WILD_TYPE,
                                           #       IN_RANGE ('IN'), OUT_OF_RANGE ('OUT'), UNINTERPRETABLE ('')
C.InterpretationCodes.ASTERISK             # '*'   EXCLAMATION_POINT '!', QUESTION_MARK '?'
C.SitesOfInfection.DEFAULT_ORDER           # list of the 31 sites, highest priority first
C.SitesOfInfection.MENINGITIS              # 'Meningitis'
C.Delimiters.SUPPORTED_FILE_DELIMITERS     # ('\t', ',', ';', '|')
C.Delimiters.parse_file_delimiter_token("TAB")   # '\t'
C.Delimiters.parse_file_delimiter_token("pipe")  # ValueError: Unsupported delimiter token…
C.OrganismGroups.ANAEROBES                 # 'ANA'
```

---

## Caches

The engine memoises two lookups per process:

| Cache | Key | Limits |
|---|---|---|
| breakpoint | organism, guideline, year, test column, breakpoint types, sites, user-defined breakpoints | 262,144 entries / 16,777,216 key characters |
| intrinsic rule | organism, guideline, drug code | 131,072 entries / 4,194,304 key characters |

Both are FIFO `BoundedCache`s (oldest entry evicted first); eviction never changes
a result, only whether it is recomputed.

```python
from amrie.antibiotic_rules import cache_statistics, clear_breakpoints

breakpoints, intrinsic = cache_statistics()
breakpoints     # BoundedCacheStatistics(entries=…, key_characters=…, evictions=…, uncached_keys=…)
clear_breakpoints()   # empty both caches (e.g. after swapping resource tables in tests)
```

`amrie.bounded_cache.BoundedCache(max_entries, max_key_characters)` is reusable:
`get(key)` returns the `MISSING` sentinel on a miss, `add(key, value)` stores
first-writer-wins and returns the cached value.

---

## Thread safety and performance

- Reference tables are immutable after import; the caches are internally locked.
  You can call `interpret_single` / `IsolateInterpretation` from many threads.
- `interpret_isolates(parallel=True)` (and therefore `interpret_file` and
  `amrie file`) pre-heats the breakpoint cache for every distinct
  organism/guideline/test in the file, then interprets rows on a thread pool, and
  returns results in input order. `parallel=False` gives identical results.
- Import cost: ~1 s to load 80,000 reference rows. Keep the process alive (or use
  the web server) when interpreting many small requests.
- Load the configuration once; passing a path to `interpret_single` re-reads it.

---

## Errors

| Situation | What happens |
|---|---|
| Unknown organism code | `""` (uninterpretable) |
| No breakpoint for the guideline / year / type | `""` |
| Measurement not a number, or disk outside 6–80 mm | `""` |
| Malformed test column (`"PEN"`, `"X_0_NM"`) | `ValueError` from `AntibioticComponents` (in `interpret_single` this can surface as a `KeyError`) |
| Unsupported delimiter | `ValueError` (`typer.BadParameter` in the CLI, HTTP 400 in the API) |
| Missing config file | `FileNotFoundError` |
| Invalid JSON in config | `orjson.JSONDecodeError` |
| `UserDefinedBreakpointsFile` does not exist | ignored silently (no user-defined breakpoints) |
