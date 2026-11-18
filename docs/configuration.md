# Configuration reference

A configuration decides **which breakpoints and rules** the engine uses and **how
results are written**. It is a JSON file (CLI, web file mode, `read_configuration`)
or an `InterpretationConfiguration` object (Python).

- [The sample configuration](#the-sample-configuration)
- [How the file is read](#how-the-file-is-read)
- [Options](#options)
  - [`GuidelineYear`](#guidelineyear)
  - [`PrioritizedBreakpointTypes`](#prioritizedbreakpointtypes)
  - [`PrioritizedSitesOfInfection`](#prioritizedsitesofinfection)
  - [`DisabledSitesOfInfection`](#disabledsitesofinfection)
  - [`EnabledExpertInterpretationRules`](#enabledexpertinterpretationrules)
  - [`UseIntrinsicResistanceRules`](#useintrinsicresistancerules)
  - [`RoundHalfDilutions`](#roundhalfdilutions)
  - [`IncludeInterpretationComments`](#includeinterpretationcomments)
  - [`HorizontalAntibioticResults`](#horizontalantibioticresults)
  - [`UserDefinedBreakpointsFile`](#userdefinedbreakpointsfile)
- [Ready-made configurations](#ready-made-configurations)
- [Building a configuration in Python](#building-a-configuration-in-python)
- [JSON Schema](#json-schema)

---

## The sample configuration

[`src/amrie/resources/SampleConfig.json`](../src/amrie/resources/SampleConfig.json):

```json
{
	"$schema": "../../../docs/reference/amrie-config.schema.json",
	"RoundHalfDilutions": true,
	"IncludeInterpretationComments": false,
	"EnabledExpertInterpretationRules": [
		"BLNAR-HFLU",
		"MRS",
		"ICR"
	],
	"_Comment_IgnoredExpertInterpretationRules": [
		"ESBL-CONFIRMED",
		"ESBL-AMPC-PROBABLE"
	],
	"GuidelineYear": 2026,
	"PrioritizedBreakpointTypes": [ "Human", "Animal", "ECOFF" ],
	"PrioritizedSitesOfInfection": [],
	"DisabledSitesOfInfection": [],
	"HorizontalAntibioticResults": true,
	"DISABLED_UserDefinedBreakpointsFile": "Resources\\SampleUserDefinedBreakpoints.txt"
}
```

In words: 2026 breakpoints; human first, then veterinary, then ECOFF; default site
order; MRS, BLNAR and ICR rules on (the two ESBL rules parked in a comment key);
intrinsic resistance on (default); E-test rounding on; suffixes stripped from
output; horizontal layout; no user-defined breakpoints.

---

## How the file is read

| Rule | Example |
|---|---|
| Any key you omit takes its default | `{}` is a valid configuration |
| Key names are **case-insensitive**; snake_case also works | `"guidelineyear"`, `"GUIDELINEYEAR"`, `"guideline_year"` |
| Keys starting with `_Comment` are ignored | `"_Comment_Year": "2026 = CLSI M100-Ed36"` |
| Keys starting with `DISABLED_` are ignored | `"DISABLED_UserDefinedBreakpointsFile": "…"` |
| `$schema` and any unknown key are ignored | `"$schema": "…"`, `"Notes": "…"` |
| `//` and `/* … */` comments are allowed (not inside strings) | `"GuidelineYear": 2026, // M100 ed. 36` |
| Trailing commas are allowed | `["MRS", "ICR",]` |
| A UTF-8 BOM is allowed | files saved by Windows Notepad |
| An empty list (`[]`) for a list option means "not set" | `"PrioritizedSitesOfInfection": []` = default order |

So this is a valid configuration:

```jsonc
{
  // CSF isolates from the 2024 survey
  "guidelineYear": 2024,
  "PrioritizedSitesOfInfection": ["Meningitis",],   /* meningitis breakpoints first */
  "_Comment_Rules": "MRS only for this project",
  "EnabledExpertInterpretationRules": ["MRS"],
}
```

Invalid JSON (e.g. a missing value) raises `orjson.JSONDecodeError`; a missing file
raises `FileNotFoundError`.

---

## Options

### `GuidelineYear`

| Type | Default | Python field |
|---|---|---|
| integer | `2026` (`constants.BREAKPOINT_TABLE_REVISION_YEAR`) | `guideline_year` |

Only breakpoints of this year are used (user-defined breakpoints are always used).
The table holds 1998–2026; the guideline itself comes from each test column
(`_N…` CLSI, `_E…` EUCAST, …).

```json
"GuidelineYear": 2020
```

```text
eco IMR_EM 1   (EUCAST, GuidelineYear 2020) → S    general PK/PD breakpoint S ≤ 2, R > 4
eco IMR_EM 16  (EUCAST, GuidelineYear 2020) → R
```

If the guideline has no breakpoints in that year for the organism/test, the result
is blank — breakpoints are **not** borrowed from other years.

---

### `PrioritizedBreakpointTypes`

| Type | Default | Python field | Values |
|---|---|---|---|
| array of strings | not set → all types | `prioritized_breakpoint_types` | `"Human"`, `"Animal"`, `"ECOFF"` |

Which breakpoint types may be used, in priority order. When not set, all types are
allowed with Human ahead of Animal ahead of ECOFF.

| Setting | Effect |
|---|---|
| `["Human"]` | clinical human breakpoints only — veterinary-only drugs stay blank |
| `["Human", "Animal", "ECOFF"]` | human, else veterinary, else ECOFF |
| `["ECOFF"]` | epidemiological cut-offs only → `WT` / `NWT` |
| `["Animal", "Human"]` | veterinary laboratories |

Enrofloxacin is a veterinary drug with no human breakpoint:

| `eco ENR_ND5` | `["Human", "Animal", "ECOFF"]` | `["Human"]` |
|---|---|---|
| 25 mm | `S` | *(blank)* |
| 20 mm | `I` | *(blank)* |
| 14 mm | `R` | *(blank)* |

And ECOFF-only surveillance:

| `eco AMP_NM` | default | `["ECOFF"]` |
|---|---|---|
| 8 | `S` | `WT` |
| 32 | `R` | `NWT` |

---

### `PrioritizedSitesOfInfection`

| Type | Default | Python field |
|---|---|---|
| array of strings | not set → built-in order | `prioritized_sites_of_infection` |

The order in which site-specific breakpoints are preferred. Names must match the
built-in site names **exactly, including case** — `"meningitis"` is silently dropped,
`"Meningitis"` works; any unknown name is dropped without an error. After
loading, every built-in site you did not list is **appended** in the default order
(unless disabled), so nothing is lost — your list only moves sites to the front.

The built-in order (31 sites):

```text
Non-meningitis, Non-endocarditis, Parenteral, (Blank),
Uncomplicated urinary tract infection, Infections originating from the urinary tract,
Meningitis, Endocarditis, Endocarditis with combination treatment, Intravenous, Oral,
Inhaled, Investigational agent, Extraintestinal, Abscesses, Genital, Intestinal,
Liposomal, Mammary gland, Mastitis, Metritis, Non-pneumonia, Other infections,
Other indications, Pneumonia, Prophylaxis, Respiratory, Screen, Skin, Soft tissue, Wounds
```

`(Blank)` is the breakpoint with no site — the general one.

**Example — CSF isolates.** CLSI 2026 penicillin MIC for *S. pneumoniae* has three
breakpoints: non-meningitis (S ≤ 2, R ≥ 8), meningitis (S ≤ 0.06, R ≥ 0.12) and
oral (S ≤ 0.06, R ≥ 2).

```json
"PrioritizedSitesOfInfection": ["Meningitis"]
```

| `spn PEN_NM` | default order | `["Meningitis"]` first |
|---|---|---|
| 0.06 | `S` | `S` |
| 0.12 | `S` | `R` |
| 1 | `S` | `R` |
| 4 | `I` | `R` |

Use a separate configuration for CSF specimens, or the web/single API's site filter.

---

### `DisabledSitesOfInfection`

| Type | Default | Python field |
|---|---|---|
| array of strings | not set | `disabled_sites_of_infection` |

Sites never to use. They are removed from the priority list after it is completed.

```json
"DisabledSitesOfInfection": ["Mastitis", "Metritis", "Mammary gland"]
```

A typical use is to exclude veterinary-only sites in a human laboratory, or `Oral`
when only parenteral therapy is relevant.

---

### `EnabledExpertInterpretationRules`

| Type | Default | Python field | Values |
|---|---|---|---|
| array of strings | not set → **all** rules | `enabled_expert_interpretation_rules` | `ESBL-CONFIRMED`, `ESBL-AMPC-PROBABLE`, `BLNAR-HFLU`, `MRS`, `ICR` |

| Setting | Effect |
|---|---|
| key absent or `null` | all five rules run |
| `[]` | **all five rules run** (an empty list means "not set") |
| `["MRS", "ICR"]` | only those rules |

To switch every rule off in JSON, list a value that is not a rule code, e.g.
`["NONE"]`; in Python use `enabled_expert_interpretation_rules=[]` directly (an empty
list on the dataclass does disable all rules).

```json
"EnabledExpertInterpretationRules": ["MRS", "ICR", "BLNAR-HFLU"]
```

Effect of `MRS` on a *S. aureus* with cefoxitin 15 mm:

| Test | without MRS | with MRS |
|---|---|---|
| `FOX_ND30 15` | `R` | `R!` |
| `PEN_ND10 35` | `S` | `R!` |

Details of every rule: [Expert rules](expert-rules.md).

---

### `UseIntrinsicResistanceRules`

| Type | Default | Python field |
|---|---|---|
| boolean | `true` | `use_intrinsic_resistance_rules` |

When `false`, expected-resistance rules are skipped and the breakpoint decides.

| `kpn AMP_ND10` | `true` | `false` |
|---|---|---|
| 25 mm | `R*` | `S` |
| 10 mm | `R*` | `R` |

Turn it off for method studies or when you need the raw breakpoint category; keep it
on for reporting. Details: [Intrinsic resistance](intrinsic-resistance.md).

---

### `RoundHalfDilutions`

| Type | Default | Python field |
|---|---|---|
| boolean | `true` | `round_half_dilutions` |

Round MIC and E-test values that fall between standard dilutions **up** to the next
dilution before comparison (0.75 → 1, 1.5 → 2, 3 → 4, 6 → 8).

| `eco CIP_EM` | `true` | `false` |
|---|---|---|
| 0.75 | `R` (as 1) | `I` |

See [Concepts → E-test half dilutions](concepts.md#e-test-half-dilutions).

---

### `IncludeInterpretationComments`

| Type | Default | Python field |
|---|---|---|
| boolean | `false` | `include_interpretation_comments` |

Keep the `*` (intrinsic) and `!` (expert rule) suffixes in output. Affects
`amrie file`, `amrie single`, `interpret_file`, and the web/REST interfaces. The
Python functions `interpret_single` and `IsolateInterpretation` always return the
suffixes. `?` is never removed.

| Isolate / test | `false` | `true` |
|---|---|---|
| `kpn AMP_ND10 25` | `R` | `R*` |
| `sau FOX_ND30 15` (MRS) | `R` | `R!` |
| `eco AMP_NM <=16` | `S?` | `S?` |

Turn it on when reviewing results or auditing rules; leave it off when the output
feeds systems that only understand S/I/R.

---

### `HorizontalAntibioticResults`

| Type | Default | Python field |
|---|---|---|
| boolean | `true` | `horizontal_antibiotic_results` |

- `true` — one row per isolate; an `_INTERP` column follows each antibiotic column.
- `false` — one row per measurement; antibiotic columns are replaced by
  `ANTIBIOTIC_CODE`, `ANTIBIOTIC_MEASUREMENT`, `ANTIBIOTIC_INTERPRETATION` (the
  "long" format most statistics tools prefer).

Examples of both: [Data formats → output files](data-formats.md#output-files).

---

### `UserDefinedBreakpointsFile`

| Type | Default | Python field |
|---|---|---|
| string (path) | `""` | `user_defined_breakpoints_file` (loaded into `user_defined_breakpoints`) |

A tab-delimited file in the `Breakpoints.txt` format with your own breakpoints —
local validation studies, new drugs, or organisms the guidelines do not cover.
User-defined breakpoints:

- are used **in preference to** built-in breakpoints for the same organism and test;
- ignore `GuidelineYear` (they apply to every year);
- are matched to organisms exactly like built-in ones (use `ORGANISM_CODE_TYPE`
  `WHONET_ORG_CODE`, `GENUS_CODE`, …).

**Path resolution.** Absolute paths are used as-is. Relative paths are resolved
against the **package directory** (`src/amrie/`), not the working directory — so the
bundled sample is `resources/SampleUserDefinedBreakpoints.txt`. Backslashes are
converted to `/`. **A file that does not exist is silently ignored**, exactly as in
the C# engine. On Linux/macOS the sample's commented-out value
`Resources\\SampleUserDefinedBreakpoints.txt` does not load because the folder is
`resources` (lower-case) — prefer absolute paths.

```json
"UserDefinedBreakpointsFile": "/srv/amrie/local-breakpoints.txt"
```

The bundled sample defines a penicillin disk breakpoint for acid-fast bacilli
(`afb`): R ≤ 20, S ≥ 28, no I range.

| `afb PEN_ND10` | without | with the sample file |
|---|---|---|
| 30 mm | *(blank)* | `S` |
| 25 mm | *(blank)* | `SDD` (between R and S, no I range) |
| 18 mm | *(blank)* | `R` |

Check that the file actually loaded:

```python
from amrie.config import read_configuration
cfg = read_configuration("my-config.json")
len(cfg.user_defined_breakpoints)        # 0 means the path did not resolve
```

File format: [Data formats → user-defined breakpoints](data-formats.md#user-defined-breakpoints-file).

---

## Ready-made configurations

**Clinical laboratory, CLSI/EUCAST human reporting**

```json
{
  "GuidelineYear": 2026,
  "PrioritizedBreakpointTypes": ["Human"],
  "EnabledExpertInterpretationRules": ["MRS", "ICR", "BLNAR-HFLU", "ESBL-CONFIRMED"],
  "UseIntrinsicResistanceRules": true,
  "IncludeInterpretationComments": false
}
```

**Rule review / audit** — keep the suffixes so every inferred result is visible

```json
{
  "PrioritizedBreakpointTypes": ["Human"],
  "IncludeInterpretationComments": true,
  "HorizontalAntibioticResults": false
}
```

**Surveillance with ECOFFs (WT/NWT)**

```json
{
  "PrioritizedBreakpointTypes": ["ECOFF"],
  "UseIntrinsicResistanceRules": false,
  "EnabledExpertInterpretationRules": ["NONE"],
  "HorizontalAntibioticResults": false
}
```

**Veterinary laboratory**

```json
{
  "PrioritizedBreakpointTypes": ["Animal", "Human", "ECOFF"],
  "EnabledExpertInterpretationRules": ["MRS"]
}
```

**CSF / meningitis specimens**

```json
{
  "PrioritizedBreakpointTypes": ["Human"],
  "PrioritizedSitesOfInfection": ["Meningitis"]
}
```

**Uncomplicated UTI specimens**

```json
{
  "PrioritizedBreakpointTypes": ["Human"],
  "PrioritizedSitesOfInfection": ["Uncomplicated urinary tract infection", "Infections originating from the urinary tract"]
}
```

**Historic data (re-interpret 2019 results with 2019 breakpoints)**

```json
{
  "GuidelineYear": 2019,
  "PrioritizedBreakpointTypes": ["Human"]
}
```

---

## Building a configuration in Python

```python
from amrie.config import InterpretationConfiguration, default_configuration, read_configuration
from amrie.breakpoint import BreakpointTypes, load_breakpoints
from amrie.expert_rule import RuleCodes
from amrie import constants as C
import dataclasses

# Minimal: everything else defaults
config = InterpretationConfiguration(prioritized_breakpoint_types=[BreakpointTypes.HUMAN])

# Everything explicit
config = InterpretationConfiguration(
    guideline_year=2026,
    prioritized_breakpoint_types=[BreakpointTypes.HUMAN, BreakpointTypes.ECOFF],
    prioritized_sites_of_infection=[C.SitesOfInfection.MENINGITIS],
    disabled_sites_of_infection=None,
    enabled_expert_interpretation_rules=[RuleCodes.MRSTAPH, RuleCodes.ICR],
    use_intrinsic_resistance_rules=True,
    round_half_dilutions=True,
    include_interpretation_comments=True,
    horizontal_antibiotic_results=False,
)
config.update_sites_of_infection()       # complete the site list, as read_configuration does

# User-defined breakpoints without a file path in the config
config.user_defined_breakpoints = load_breakpoints(
    "src/amrie/resources/SampleUserDefinedBreakpoints.txt", user_defined=True
)

# Variants of a loaded file
base = read_configuration("src/amrie/resources/SampleConfig.json")
csf = dataclasses.replace(base, prioritized_sites_of_infection=["Meningitis"])
csf.update_sites_of_infection()

# Opinionated preset: Human only, MRS + BLNAR + ICR, comments on, full site order
preset = default_configuration()
```

Note the difference between JSON and Python for empty lists: in JSON `[]` means
"not set"; on the dataclass `enabled_expert_interpretation_rules=[]` means "no rules".

---

## JSON Schema

[`docs/reference/amrie-config.schema.json`](reference/amrie-config.schema.json) (from
upstream) describes every key, its type and allowed values. Point your editor at it
with a `$schema` key — VS Code and JetBrains IDEs then offer completion and
validation:

```json
{
  "$schema": "https://raw.githubusercontent.com/aurthurm/beak-whonet-amrie/main/docs/reference/amrie-config.schema.json",
  "GuidelineYear": 2026
}
```

The engine ignores `$schema`.
