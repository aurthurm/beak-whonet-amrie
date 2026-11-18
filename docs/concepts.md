# Concepts

The background you need to use AMRIE confidently: what the engine is deciding,
what the categories mean, and how WHONET encodes organisms, drugs and tests.

- [What AMRIE does](#what-amrie-does)
- [Test methods](#test-methods)
- [Breakpoints](#breakpoints)
- [Interpretation categories](#interpretation-categories)
- [Censored MIC values](#censored-mic-values)
- [E-test half dilutions](#e-test-half-dilutions)
- [Guidelines and years](#guidelines-and-years)
- [Breakpoint types: Human, Animal, ECOFF](#breakpoint-types-human-animal-ecoff)
- [Sites of infection](#sites-of-infection)
- [Organism taxonomy and specificity](#organism-taxonomy-and-specificity)
- [Intrinsic resistance](#intrinsic-resistance)
- [Expert interpretation rules](#expert-interpretation-rules)
- [Quality control](#quality-control)
- [WHONET codes](#whonet-codes)
- [Glossary](#glossary)

---

## What AMRIE does

A susceptibility test measures how an organism responds to an antibiotic in the
laboratory. The number on its own — "19 mm", "0.5 mg/L" — is not a clinical
answer. Guideline bodies (CLSI, EUCAST, …) publish **breakpoints** that convert
the number into a category that predicts treatment outcome.

AMRIE automates that conversion, consistently and at scale:

```text
  organism  +  antibiotic test  +  measurement  +  configuration
     eco         AMP_ND10            19           year 2026, Human
                              │
                              ▼
          S  /  I  /  SDD  /  R  /  NS  /  WT  /  NWT  /  (blank)
          optionally marked  *  (intrinsic)  !  (expert rule)  ?  (uncertain)
```

---

## Test methods

| Method | Code | Measures | Direction |
|---|---|---|---|
| **Disk diffusion** | `D` | Diameter (mm) of the zone where growth is inhibited around an antibiotic disk | **Bigger zone = more susceptible** |
| **MIC** (broth/agar dilution) | `M` | Minimum inhibitory concentration (mg/L) — lowest concentration that stops growth | **Lower MIC = more susceptible** |
| **E-test** (gradient strip) | `E` | An MIC read from a gradient strip; may fall *between* standard dilutions | Same as MIC |

Disk tests also carry a **potency** — the amount of drug on the disk (ampicillin
`10` µg, cefotaxime `30` µg, trimethoprim/sulfamethoxazole `1_2` = 1.25/23.75 µg).
Breakpoints are potency-specific, which is why the potency is part of the column
name (`AMP_ND10`).

Disk zones must be **6–80 mm** (a 6 mm zone is the disk itself, i.e. no
inhibition); values outside that range are uninterpretable (`eco AMP_ND10 5` → blank).
Leading zeros are fine (`06` = 6 mm). MIC values are not range-checked.

---

## Breakpoints

A breakpoint row says, for one guideline, year, organism group, drug test and
context, where the category boundaries are. For example, CLSI 2026,
Enterobacterales, ampicillin 10 µg disk:

| | R | I | S |
|---|---|---|---|
| zone (mm) | ≤ 13 | 14–16 | ≥ 17 |

And for ampicillin MIC (mg/L):

| | S | I | R |
|---|---|---|---|
| MIC (mg/L) | ≤ 8 | 16 | ≥ 32 |

How the values are compared:

| Method | Susceptible | Resistant | Between |
|---|---|---|---|
| Disk | zone **≥ S** | zone **≤ R** | `I` if an I range exists, else `SDD` (if R > 0), else `NS` |
| MIC | MIC **≤ S** | MIC **≥ R** | `I` if an I range exists, else `SDD`; MIC ≥ R with no R value → `NS` |
| ECOFF | MIC **≤ ECV** (disk **≥ ECV**) → `WT` | otherwise `NWT` | — |

EUCAST publishes MIC breakpoints as "S ≤ x, R > y". The table stores them in the
same `S` / `I` / `R` form as CLSI, with `R` set to the next dilution above *y*: EUCAST
2026 ciprofloxacin for Enterobacterales ("S ≤ 0.25, R > 0.5") is stored as
`S=0.25, I=0.5, R=1`. You never need to convert anything yourself.

The bundled table has **51,001** breakpoints — CLSI, EUCAST, SFM, SRGA, BSAC, NEO,
AFA and DIN; 1998–2026; human, veterinary and ECOFF. Choosing the right one is the
hard part; see [Breakpoint selection](breakpoint-selection.md).

---

## Interpretation categories

| Code | Name | Meaning | Example |
|---|---|---|---|
| `S` | Susceptible | Likely to respond to standard dosing | `eco AMP_ND10 19` |
| `I` | Intermediate (CLSI) / "Susceptible, increased exposure" (EUCAST) | May respond at higher dose or where the drug concentrates | `eco AMP_ND10 15` |
| `SDD` | Susceptible-dose dependent | Susceptible only with a dosing regimen above the standard one | `sau CPT_ND30 22` (ceftaroline) |
| `R` | Resistant | Unlikely to respond | `eco AMP_ND10 12` |
| `NS` | Non-susceptible | Not susceptible, but cannot be split into I vs R — the breakpoint has no R value, or the result is censored | `eco AMP_NM >8` |
| `WT` | Wild type | At or below the epidemiological cut-off: no acquired resistance mechanism | `eco AMP_NM 8` with ECOFF breakpoints |
| `NWT` | Non-wild type | Above the cut-off: an acquired resistance mechanism is likely | `eco AMP_NM 32` with ECOFF breakpoints |
| *(empty)* | Uninterpretable | No breakpoint for this organism/drug/guideline/year, unknown organism, or not a number | `eco AMP_ND10 abc` |

### Suffixes

| Suffix | Set by | Example |
|---|---|---|
| `*` | an [intrinsic resistance](intrinsic-resistance.md) rule — the organism is expected to be resistant regardless of the measurement | `kpn AMP_ND10 25` → `R*` |
| `!` | an [expert rule](expert-rules.md) — resistance inferred from another test on the same isolate | `sau FOX_ND30 15` → `R!` (MRS) |
| `?` | a censored measurement whose category is not certain | `eco AMP_NM <=16` → `S?`, `eco AMP_NM >=8` → `R?` |

The Python API (`interpret_single`, `IsolateInterpretation`) always returns the
suffixes. `amrie single`, `amrie file`, `interpret_file` and the REST API keep `*`
and `!` only when `IncludeInterpretationComments` is `true`; `?` is always kept.

---

## Censored MIC values

Dilution series stop at a top and bottom concentration, so a result can be "at
most" or "more than" a value. AMRIE understands:

| Raw | Normalised to | Meaning |
|---|---|---|
| `2`, `0.25` | value | exact |
| `<=2`, `=<2`, `≤2` | `<= 2` | at most 2 |
| `<2` | `<= 1` | strictly less than 2, i.e. at most one dilution lower |
| `>16`, `>=16`, `=>16`, `≥16` | `> 16` / `> 8` | more than … (`>=16` becomes `> 8`) |

Then, against the breakpoint:

- **`<=`** — if the value is ≤ S, the isolate is certainly **S**. Otherwise the
  true MIC might still be ≤ S, so the result is **`S?`** (or `I?`/`SDD?` when the
  breakpoint has no S range).
- **`>`** — the engine doubles the value (the true MIC is at least the next
  dilution). If that is ≥ R the result is **R**; if it is above S but below R it
  could be I or R, so the result is **NS**; otherwise **`R?`**.

Examples with *E. coli* ampicillin MIC (S ≤ 8, R ≥ 32):

| Raw | Result | Reasoning |
|---|---|---|
| `<=8` | `S` | ≤ 8 is ≤ S |
| `<=16` | `S?` | could be 8 (S) or 16 (I) |
| `>8` | `NS` | at least 16: I or R |
| `>16` | `R` | at least 32 ≥ R |
| `>=8` | `R?` | `>= 8` is read as `> 4`; doubled to 8, not above S, so the category is uncertain |

---

## E-test half dilutions

Standard MIC dilutions are powers of two (…, 0.25, 0.5, 1, 2, 4, …). E-test strips
— and some automated systems — report values *between* them (0.75, 1.5, 3, 6, …).
When `RoundHalfDilutions` is `true` (the default and standard practice), **every
MIC-type result** (`…M` and `…E` columns) is rounded **up** to the next standard
dilution before it is compared with the breakpoint. Values already on a standard
dilution are unchanged.

| Reading | Compared as |
|---|---|
| 0.19 | 0.25 |
| 0.75 | 1 |
| 1.5 | 2 |
| 2 | 2 |
| 3 | 4 |
| 6 | 8 |

```text
eco CIP_EM 0.75                            → R   (0.75 rounds up to 1; stored R = 1)
eco CIP_EM 0.75   RoundHalfDilutions=false → I   (0.75 is above S = 0.25, below R = 1)
eco CIP_NM 0.75                            → R   (broth MIC columns are rounded too)
```

Rounding up is the conservative choice: a strip read at 0.75 has a true MIC of at
least 0.75, and the next concentration a dilution series would have tested is 1.
Disk zones are never rounded.

---

## Guidelines and years

The guideline is encoded in the test column; the year comes from the configuration
(`GuidelineYear`, default 2026). Breakpoints change most years — that is why AMRIE
keeps every year and lets you choose.

| Code | Guideline | Breakpoints in table |
|---|---|---:|
| `N` | CLSI (Clinical and Laboratory Standards Institute, USA) | 27,017 |
| `E` | EUCAST (European Committee on Antimicrobial Susceptibility Testing) | 22,360 |
| `F` | SFM / CA-SFM (Société Française de Microbiologie) | 1,034 |
| `S` | SRGA (Sweden) | 289 |
| `B` | BSAC (UK) | 170 |
| `T` | NEO (Neo-Sensitabs) | 97 |
| `A` | AFA | 28 |
| `D` | DIN (Germany) | 6 |

To interpret historic data with the breakpoints in force at the time, set
`GuidelineYear` to that year, or pass `--year`-style overrides through the API
(`interpret_file(..., guideline_year=2019)`). See
[Use cases → re-interpret historic data](use-cases.md#6-re-interpret-historic-data-with-a-different-year).

---

## Breakpoint types: Human, Animal, ECOFF

| Type | Purpose | Rows |
|---|---|---:|
| `Human` | Clinical breakpoints for human patients | 38,153 |
| `Animal` | Veterinary clinical breakpoints (host-specific: dog, cattle, …) | 2,880 |
| `ECOFF` | Epidemiological cut-offs (wild type vs non-wild type), used for surveillance | 9,968 |

`PrioritizedBreakpointTypes` selects which types may be used and in which order. With
`["Human", "Animal", "ECOFF"]` (the sample config), AMRIE uses a human breakpoint if
there is one, otherwise a veterinary one, otherwise an ECOFF. With `["Human"]`,
anything without a human breakpoint stays blank.

---

## Sites of infection

Some drugs have different breakpoints depending on where the infection is —
penicillin for *S. pneumoniae* is far stricter for **meningitis** than for
pneumonia; nitrofurantoin only has **urinary** breakpoints. Each breakpoint row may
list one or more sites; AMRIE ranks them by a priority list. The default order
starts with the general, non-site-specific breakpoints:

```text
Non-meningitis → Non-endocarditis → Parenteral → (Blank) →
Uncomplicated urinary tract infection → Infections originating from the urinary tract →
Meningitis → Endocarditis → … (31 sites in total)
```

Put a site first (`"PrioritizedSitesOfInfection": ["Meningitis"]`) to interpret
CSF isolates, or remove sites with `DisabledSitesOfInfection`. See
[Configuration](configuration.md#prioritizedsitesofinfection) and
[Breakpoint selection](breakpoint-selection.md#site-of-infection-priority).

---

## Organism taxonomy and specificity

Breakpoints are rarely written for a single species. A breakpoint row targets an
organism *at some level of the taxonomy*, named by `ORGANISM_CODE_TYPE`:

| Level (most → least specific) | Example code | Covers |
|---|---|---|
| `SEROVAR_GROUP` | `ECO`, `NME`, `HIN` | a species including its serovars (*E. coli*, *N. meningitidis*, *H. influenzae*) |
| `WHONET_ORG_CODE` | `sau`, `efm` | one organism code |
| `SPECIES_GROUP` | `BS-` | a group of species (e.g. β-haemolytic streptococci) |
| `GENUS_CODE` | `STA`, `STR` | a genus (*Staphylococcus*, *Streptococcus*) |
| `GENUS_GROUP` | | a group of genera |
| `FAMILY_CODE` | `EBC` | a family / order (*Enterobacterales*) |
| `ANAEROBE+SUBKINGDOM_CODE` | `AN+`, `AN-` | Gram-positive / Gram-negative anaerobes |
| `ANAEROBE` | `ANA` | all anaerobes |
| `ALL` | `ALL` | every organism (non-species-related PK/PD breakpoints) |

When several levels match, the **most specific wins**: a species-specific
breakpoint beats a genus breakpoint, which beats a family breakpoint. The organism
table (`Organisms.txt`) holds each organism's codes at every level, so `eco` knows
it belongs to `ECO` (serovar group), *Escherichia* and `EBC`.

Organisms that were renamed or merged keep their old codes; AMRIE remaps 17 merged
codes to their current successors automatically.

---

## Intrinsic resistance

Some organisms are resistant to some drugs by nature — *Klebsiella* to ampicillin,
*Pseudomonas aeruginosa* to many oral cephalosporins, enterococci to
cephalosporins. CLSI and EUCAST publish these "expected resistant phenotypes".
When an isolate/drug pair matches one, AMRIE returns **`R*`** without looking at
the measurement. Disable with `UseIntrinsicResistanceRules: false`.
→ [Intrinsic resistance](intrinsic-resistance.md)

## Expert interpretation rules

Some results imply others. A cefoxitin-resistant *S. aureus* is MRSA and should be
reported resistant to (almost) all β-lactams; a positive D-test means clindamycin
should be reported resistant. AMRIE's expert rules apply these inferences across
the isolate and mark affected results **`R!`**.
→ [Expert rules](expert-rules.md)

## Quality control

Laboratories test reference strains (e.g. *E. coli* ATCC 25922) alongside patient
isolates. If a reference strain's result falls outside its published range, the
run is not reliable. AMRIE returns `IN` / `OUT` for a strain, test and measurement.
→ [Quality control](quality-control.md)

---

## WHONET codes

### Organism codes

Lower-case, usually three letters: `eco` *Escherichia coli*, `kpn` *Klebsiella
pneumoniae*, `pae` *Pseudomonas aeruginosa*, `sau` *Staphylococcus aureus*, `spn`
*Streptococcus pneumoniae*, `hin` *Haemophilus influenzae*, `nme` *Neisseria
meningitidis*, `efa` *Enterococcus faecalis*, `efm` *E. faecium*, `ent`
*Enterococcus* sp., `lmo` *Listeria monocytogenes*. The full list (2,980 rows,
2,351 current) is in `src/amrie/resources/Organisms.txt`.

Look one up:

```python
from amrie.organism import CURRENT_ORGANISMS
o = CURRENT_ORGANISMS["eco"]
o.ORGANISM, o.SEROVAR_GROUP, o.GENUS_CODE, o.FAMILY_CODE
# ('Escherichia coli', 'ECO', 'ESC', 'EBC')
```

### Antibiotic test columns

```text
<DRUG>_<GUIDELINE><METHOD>[<POTENCY>]
```

| Example | Drug | Guideline | Method | Potency |
|---|---|---|---|---|
| `AMP_ND10` | ampicillin | CLSI | disk | 10 µg |
| `AMP_NM` | ampicillin | CLSI | MIC | — |
| `AMP_EE` | ampicillin | EUCAST | E-test | — |
| `CIP_ED5` | ciprofloxacin | EUCAST | disk | 5 µg |
| `SXT_ND1_2` | trimethoprim/sulfamethoxazole | CLSI | disk | 1.25/23.75 µg |
| `X_12_NM` | user-defined drug 12 | CLSI | MIC | — |

User-defined drugs are `X_1` to `X_99` without leading zeros (`X_01`, `X_0`, `X_100`
are rejected). Full rules: [Data formats](data-formats.md#whonet-antibiotic-column-names).

---

## Glossary

| Term | Meaning |
|---|---|
| **AST** | Antimicrobial susceptibility testing |
| **Breakpoint** | Measurement threshold separating interpretation categories |
| **CLSI M100** | CLSI's annual breakpoint tables |
| **ECOFF / ECV** | Epidemiological cut-off value: upper limit of the wild-type MIC distribution |
| **ESBL** | Extended-spectrum β-lactamase |
| **AmpC** | A class of β-lactamases that hydrolyse cephamycins and 3rd-generation cephalosporins |
| **MRS / MRSA** | Methicillin-resistant *Staphylococcus* (*aureus*) |
| **BLNAR** | β-lactamase-negative, ampicillin-resistant (*H. influenzae*) |
| **ICR / D-test** | Inducible clindamycin resistance and the disk test that detects it |
| **PK/PD breakpoint** | A non-species-related breakpoint derived from pharmacokinetics/pharmacodynamics |
| **ATC code** | WHO Anatomical Therapeutic Chemical classification (e.g. `J01DB` = 1st-gen cephalosporins) |
| **WHONET** | WHO's free software for laboratory AMR surveillance; source of the codes used here |
| **Censored value** | A measurement given as `<x` or `>x` rather than exactly |
| **QC strain** | A reference strain with known expected results, tested to validate a run |
