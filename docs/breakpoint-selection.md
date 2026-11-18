# Breakpoint selection

For a single measurement there can be dozens of candidate breakpoints — different
organism levels, breakpoint types, hosts and sites of infection. This page explains
exactly how AMRIE narrows 51,001 rows down to the one it uses, so you can predict
and explain every result.

The algorithm is `get_applicable_breakpoints()` in
[`src/amrie/breakpoint.py`](../src/amrie/breakpoint.py), a line-by-line port of
`Breakpoint.GetApplicableBreakpoints` in the C# engine.

- [The three steps](#the-three-steps)
- [Step 0: inputs](#step-0-inputs)
- [Step 1: filter](#step-1-filter)
- [Step 2: sort](#step-2-sort)
- [Step 3: select](#step-3-select)
- [Organism matching in detail](#organism-matching-in-detail)
- [ALL-organism (PK/PD) breakpoints](#all-organism-pkpd-breakpoints)
- [Site of infection priority](#site-of-infection-priority)
- [User-defined breakpoints](#user-defined-breakpoints)
- [Worked examples](#worked-examples)
- [Inspecting the choice yourself](#inspecting-the-choice-yourself)

---

## The three steps

```text
 51,001 built-in rows + user-defined rows
        │
        ▼  1. FILTER   guideline · year · breakpoint type · site · test column · organism
        │
        ▼  2. SORT     drug · user-defined first · guideline · year · method ·
        │              breakpoint type · host · organism specificity · site priority
        │
        ▼  3. SELECT   the first row  (interpretation)
                       or one row per group plus its site variants (lookups)
```

---

## Step 0: inputs

When interpreting `eco AMP_ND10 19`, the engine calls the search with:

| Input | Value | From |
|---|---|---|
| organism | `eco` | the row's `ORGANISM` |
| guideline | `CLSI` | `N` in the column name |
| year | `2026` | `GuidelineYear` (or the API override) |
| test column | `AMP_ND10` | the column name; E-test `…E` is recoded to `…M` |
| breakpoint types | e.g. `["Human", "Animal", "ECOFF"]` | `PrioritizedBreakpointTypes` |
| sites of infection | full ordered list | `PrioritizedSitesOfInfection` / `DisabledSitesOfInfection` |
| user-defined breakpoints | list | `UserDefinedBreakpointsFile` |
| "first only" | `True` | the engine needs one breakpoint |

If the organism code is not current, it is looked up in the **merged organisms**
map (e.g. `csl` → `cal`); an unknown code returns no breakpoints → blank result.

---

## Step 1: filter

A row is kept only if **every** condition holds:

| # | Condition | Detail |
|---|---|---|
| 1 | Year | `YEAR` is the requested year — or the row is user-defined |
| 2 | Guideline | `GUIDELINES` is the requested guideline — or the row is user-defined |
| 3 | Breakpoint type | `BREAKPOINT_TYPE` is in the allowed list (any type when the list is not set) |
| 4 | Site of infection | at least one of the row's sites is in the site list; an empty site matches `(Blank)` |
| 5 | Test column | `WHONET_TEST` equals the (recoded) column |
| 6 | Organism | the row targets the organism at some taxonomy level — [details](#organism-matching-in-detail) |

Note what is **not** filtered: host. Veterinary rows for every host survive; the
sort decides between them.

---

## Step 2: sort

Survivors are sorted ascending by this key; the first row wins.

| Priority | Key | Order |
|---|---|---|
| 1 | Test column | position in the requested list |
| 2 | User-defined | user-defined rows first |
| 3 | Guideline | position in the requested list |
| 4 | Year | position in the requested list (newest first when no list) |
| 5 | Test method | alphabetical |
| 6 | **Breakpoint type** | position in `PrioritizedBreakpointTypes` (default Human → Animal → ECOFF → other) |
| 7 | **Host** | alphabetical (`Cats` < `Dogs` < `Human` < `Poultry` …) |
| 8 | **Organism specificity** | serovar group 1 · organism code 2 · species group 3 · genus 4 · genus group 5 · family 6 · anaerobe + Gram 7 · anaerobe 8 · `ALL` and anything else 9 |
| 9 | **Site of infection** | lowest position of any of the row's sites in the site list |

Consequences worth knowing:

- **Breakpoint type beats specificity.** A Human family-level breakpoint is chosen
  over an Animal serovar-level one when Human comes first in your list.
- **Specificity beats site.** A species-specific breakpoint for a lower-priority
  site wins over a genus breakpoint for your first site.
- **Host is alphabetical**, and there is no host setting. Among veterinary
  breakpoints the alphabetically first host wins — for `eco ENR_ND5` (enrofloxacin)
  the *Cats* (Enterobacterales, skin/soft tissue) row is chosen over the more
  specific *Poultry* (*E. coli*) row. This matches the C# engine. Use a
  user-defined breakpoint if you need a specific host.

---

## Step 3: select

### First only (`return_first_breakpoint_only=True`) — interpretation

The engine takes the first sorted row. That row is cached for the organism,
guideline, year, test column and selection settings.

### All applicable (`return_first_breakpoint_only=False`) — lookups

Used by the web "Applicable breakpoints" dialog and `/api/breakpoints`. Rows are
grouped by `(guideline, year, breakpoint type, host, test column)`; from each group
the engine returns the first row **plus** any other rows in the group with the
**same organism code and level** (they differ only by site of infection). Less
specific rows in the group are dropped.

```text
eco, CLSI 2026, AMP_ND10 →
  Human   EBC FAMILY_CODE    (Blank)                                R≤13  I 14-16  S≥17
  Animal  ECO SEROVAR_GROUP  Uncomplicated urinary tract infection         S≥17     (host 1)
  Animal  ECO SEROVAR_GROUP  Uncomplicated urinary tract infection         S≥17     (host 2)
  ECOFF   ECO SEROVAR_GROUP  (Blank)                                       ECV 13
```

---

## Organism matching in detail

A row matches organism *o* if any of these is true:

| `ORGANISM_CODE_TYPE` | Matches when |
|---|---|
| `SEROVAR_GROUP` | *o* has a serovar group equal to `ORGANISM_CODE` |
| `WHONET_ORG_CODE` | *o*'s code equals `ORGANISM_CODE` |
| `SPECIES_GROUP` | *o*'s species group equals `ORGANISM_CODE` |
| `GENUS_CODE` | *o*'s genus code equals `ORGANISM_CODE` |
| `GENUS_GROUP` | *o*'s genus group equals `ORGANISM_CODE` |
| `FAMILY_CODE` | *o*'s family code equals `ORGANISM_CODE` |
| `ANAEROBE+SUBKINGDOM_CODE` | *o* is anaerobic and `ORGANISM_CODE` is `AN+` (Gram-positive) or `AN-` (Gram-negative) to match its Gram reaction |
| `ANAEROBE` | *o* is anaerobic and `ORGANISM_CODE` is `ANA` |
| `ALL` | `ORGANISM_CODE` is also `ALL` — every organism |

*E. coli* (`eco`) has serovar group `ECO`, genus `ESC` and family `EBC`, so CLSI
rows coded `ECO`/`SEROVAR_GROUP`, `ESC`/`GENUS_CODE` and `EBC`/`FAMILY_CODE` all
apply, in that order of preference.

### Load-time code-type correction

Some rows in the upstream table carry the wrong `ORGANISM_CODE_TYPE`. When the
tables load, the engine checks each built-in row: if no current organism matches the
declared type but exactly **one** other type does, it uses that type. 181 rows are
corrected:

| Code | Declared | Used | Rows | Effect |
|---|---|---|---:|---|
| `BS-` | `GENUS_CODE` | `SPECIES_GROUP` | 104 | β-haemolytic streptococcus breakpoints now apply |
| `NME` | `WHONET_ORG_CODE` | `SEROVAR_GROUP` | 77 | *N. meningitidis* breakpoints now apply (`nme PEN_EM 0.25` → `S`) |

User-defined rows are never corrected.

---

## ALL-organism (PK/PD) breakpoints

EUCAST publishes "non-species related" PK/PD breakpoints for use when no species
breakpoint exists. In the table, 515 rows have `ORGANISM_CODE_TYPE = ALL`:

| `ORGANISM_CODE` | Rows | Guidelines / years | Used? |
|---|---:|---|---|
| `ALL` | 320 | EUCAST 2013–2020, SFM 2020 | **yes** — match every organism, lowest specificity |
| `Gen` | 195 | EUCAST 2022–2026 | **no** — the C# engine matches only `ALL`/`ALL`; this port matches upstream |

Example (EUCAST 2020, imipenem/relebactam, general PK/PD S ≤ 2, R > 4):

```text
eco IMR_EM 1   GuidelineYear 2020 → S
eco IMR_EM 16  GuidelineYear 2020 → R
```

Because they rank 9 for specificity, an organism-specific breakpoint always wins
when one exists. For 2022+ EUCAST data, organisms without a species breakpoint stay
uninterpretable for those drugs (`eco PEN_EM 0.5` → blank). If you need the 2022+
PK/PD rows, add them as user-defined breakpoints with
`ORGANISM_CODE = ALL`, `ORGANISM_CODE_TYPE = ALL`.

---

## Site of infection priority

The site list is your `PrioritizedSitesOfInfection` followed by every other site in
the built-in order, minus `DisabledSitesOfInfection`. With nothing configured:

```text
 1 Non-meningitis        9 Endocarditis with combination treatment   17 Intestinal   25 Pneumonia
 2 Non-endocarditis     10 Intravenous                               18 Liposomal    26 Prophylaxis
 3 Parenteral           11 Oral                                      19 Mammary gland 27 Respiratory
 4 (Blank)              12 Inhaled                                   20 Mastitis     28 Screen
 5 Uncomplicated UTI    13 Investigational agent                     21 Metritis     29 Skin
 6 Infections orig. UT  14 Extraintestinal                           22 Non-pneumonia 30 Soft tissue
 7 Meningitis           15 Abscesses                                 23 Other infections 31 Wounds
 8 Endocarditis         16 Genital                                   24 Other indications
```

A row listing several sites (`"Skin, soft tissue"`) sorts at its best site.

**Example.** *S. pneumoniae* penicillin MIC, CLSI 2026:

| Row | Site | S | I | R |
|---|---|---|---|---|
| 1 | Non-meningitis | ≤ 2 | 4 | ≥ 8 |
| 2 | Meningitis | ≤ 0.06 | — | ≥ 0.12 |
| 3 | Oral | ≤ 0.06 | 0.12–1 | ≥ 2 |

(CLSI's 0.06 is stored as `0.064`, the exact two-fold dilution, as the
`get_applicable_breakpoints` output below shows.)

Default order → row 1. `PrioritizedSitesOfInfection: ["Meningitis"]` → row 2:

| `spn PEN_NM` | default | meningitis first |
|---|---|---|
| 0.06 | S | S |
| 0.12 | S | R |
| 1 | S | R |
| 4 | I | R |

Disabling a site removes the rows that *only* have that site.

---

## User-defined breakpoints

- Always pass the year and guideline filters.
- Sort **ahead** of built-in rows (priority 2), so a user-defined row matching the
  organism and test always wins — even if it is less specific than a built-in row.
- Match organisms, types and sites like built-in rows; their `ORGANISM_CODE_TYPE` is
  used as written.

Example: the bundled sample defines `afb PEN_ND10` R ≤ 20, S ≥ 28 → `afb PEN_ND10 25`
is `SDD`, blank without it. See [Configuration](configuration.md#userdefinedbreakpointsfile).

---

## Worked examples

### *E. coli*, ampicillin disk, 19 mm

1. Filter: CLSI, 2026, `AMP_ND10`, types Human/Animal/ECOFF, organism `eco` → 4 rows
   (Human `EBC`, 2 × Animal `ECO`, ECOFF `ECO`).
2. Sort: breakpoint type first → the Human `EBC`/`FAMILY_CODE` row leads, although
   the Animal and ECOFF rows are more specific.
3. Select: R ≤ 13, I 14–16, S ≥ 17 → 19 mm is **S**.

With `PrioritizedBreakpointTypes: ["ECOFF"]` the ECOFF row (ECV 13 mm) is chosen
instead and 19 mm is `WT`.

### *K. pneumoniae*, ampicillin disk, 25 mm

Breakpoint selection would give the `EBC` row (25 ≥ 17 → S), but the intrinsic
resistance rule for *Klebsiella* × ampicillin is checked first → **`R*`**. See
[Intrinsic resistance](intrinsic-resistance.md).

### *N. meningitidis*, penicillin MIC (EUCAST), 0.25 mg/L

The `NME` rows are declared `WHONET_ORG_CODE` in the table but `NME` is a serovar
group; the load-time correction makes them match `nme` → **S**. Before the
November 2026 upstream sync, the result was blank.

### *E. coli*, enrofloxacin disk (veterinary drug), 20 mm

No Human row exists. With `["Human", "Animal", "ECOFF"]` the Animal rows remain;
host sorts alphabetically, so the *Cats* row (S ≥ 23, R ≤ 16) is used → **I**. With
`["Human"]` there is no breakpoint → blank.

---

## Inspecting the choice yourself

```python
from amrie.antibiotic_rules import AntibioticSpecificInterpretationRules

r = AntibioticSpecificInterpretationRules(
    "eco", "ENR_ND5", "20", [], guideline_year=2026,
    prioritized_breakpoint_types=["Human", "Animal", "ECOFF"],
)
b = r.most_applicable_breakpoint
r.get_interpretation(), b.BREAKPOINT_TYPE, b.HOST, b.ORGANISM_CODE, b.ORGANISM_CODE_TYPE, b.SITE_OF_INFECTION
# ('I', 'Animal', 'Cats', 'EBC', 'FAMILY_CODE', 'Skin, soft tissue')
```

```python
from amrie.breakpoint import get_applicable_breakpoints

for b in get_applicable_breakpoints("spn", [], prioritized_guidelines=["CLSI"],
                                    prioritized_guideline_years=[2026],
                                    prioritized_breakpoint_types=["Human"],
                                    prioritized_whonet_abx_full_drug_codes=["PEN_NM"]):
    print(repr(b.SITE_OF_INFECTION), b.S, b.I, b.R)
# 'Non-meningitis' 2 4 8
# 'Meningitis' 0.064  0.12
# 'Oral' 0.064 0.12-1 2
```

In the web UI, **Applicable breakpoints** on the single tab shows the same list;
over HTTP use `POST /api/breakpoints` ([Web](web.md#post-apibreakpoints)).
