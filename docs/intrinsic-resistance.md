# Intrinsic resistance (`R*`)

Some organisms are resistant to some antibiotics by nature — a chromosomal enzyme,
an impermeable outer membrane, the absence of the drug's target. CLSI and EUCAST
publish these **expected resistant phenotypes**. AMRIE applies them before
breakpoints: when an isolate/drug pair is covered, the result is **`R*`** whatever
the measurement says.

- [Why it matters](#why-it-matters)
- [Examples](#examples)
- [How a rule is matched](#how-a-rule-is-matched)
- [ATC-class rules](#atc-class-rules)
- [Exceptions](#exceptions)
- [The rule table](#the-rule-table)
- [Switching it off](#switching-it-off)
- [Looking rules up](#looking-rules-up)

---

## Why it matters

A *Klebsiella pneumoniae* can produce a 25 mm ampicillin zone in vitro, which the
Enterobacterales breakpoint (S ≥ 17 mm) would call susceptible. Reporting "S" would
be dangerous: *K. pneumoniae* carries SHV-1 β-lactamase and does not respond to
ampicillin. Intrinsic-resistance rules prevent such false-susceptible reports and
flag tests that should not be reported at all.

```text
eco AMP_ND10 25 → S      E. coli: breakpoint decides
kpn AMP_ND10 25 → R*     K. pneumoniae: intrinsic rule decides
```

---

## Examples

All with the sample configuration (CLSI and EUCAST columns as named):

| Isolate | Test | Value | Result | Rule (reference table) |
|---|---|---|---|---|
| *K. pneumoniae* `kpn` | `AMP_ND10` | 25 | `R*` | CLSI Enterobacterales |
| *K. pneumoniae* `kpn` | `AMP_NM` | 2 | `R*` | CLSI Enterobacterales |
| *P. aeruginosa* `pae` | `CTX_ND30` | 30 | `R*` | CLSI non-fermenters |
| *P. aeruginosa* `pae` | `CTX_ED30` | 30 | `R*` | EUCAST |
| *E. faecalis* `efa` | `CTX_ND30` | 30 | `R*` | enterococci × cephalosporins |
| *E. faecalis* `efa` | `GEN_ND10` | 20 | `R*` | enterococci × aminoglycosides (ATC `J01G`) |
| *E. faecalis* `efa` | `GEH_ND120` | 20 | `S` | high-level gentamicin screen is an **exception** |
| *S. aureus* `sau` | `ATM_ND30` | 30 | `R*` | Gram-positives × aztreonam |
| *S. aureus* `sau` | `COL_NM` | 1 | `R*` | Gram-positives × colistin |
| *L. monocytogenes* `lmo` | `CFR_NM` | 1 | `R*` | 1st-generation cephalosporins (ATC `J01DB`) |
| *P. mirabilis* `pmi` | `TCY_ND30` | 25 | `R*` | tetracyclines (ATC `J01AA`) |
| *P. mirabilis* `pmi` | `NIT_ND300` | 20 | `R*` | nitrofurantoin |
| *E. coli* `eco` | `AZM_ND15` | 20 | `R*` | Enterobacterales × azithromycin |
| *Salmonella* Abortusovis `aov` | `AZM_ND15` | 20 | *(blank)* | *Salmonella* is an **exception** to that rule |
| non-haemolytic streptococcus `sgm` | `GEN_ED10` | 20 | `R*` | EUCAST streptococci × low-level gentamicin |
| viridans streptococcus `svi` | `GEN_ED10` | 20 | *(blank)* | `SVI` is an exception |

---

## How a rule is matched

For each measurement the engine asks: *is there an expected-resistance rule for this
organism, this guideline and this drug?* A rule applies when:

1. **Guideline** — the rule's `GUIDELINE` equals the test column's guideline (a
   CLSI column `…_N…` only uses CLSI rules, an EUCAST column only EUCAST rules).
2. **Organism** — the rule's `ORGANISM_CODE` / `ORGANISM_CODE_TYPE` covers the
   organism at some taxonomy level (`WHONET_ORG_CODE`, `SPECIES_GROUP`,
   `GENUS_CODE`, `GENUS_GROUP`, `FAMILY_CODE`, `SUBKINGDOM_CODE`, `ANAEROBE`, or
   `ALL`), the same levels as breakpoints.
3. **Not an exception organism** — the organism is not covered by
   `EXCEPTION_ORGANISM_CODE` / `EXCEPTION_ORGANISM_CODE_TYPE`.
4. **Drug** — `ABX_CODE` equals the drug code (`ABX_CODE_TYPE = WHONET_ABX_CODE`),
   or the drug's ATC code starts with `ABX_CODE` (`ABX_CODE_TYPE = ATC_CODE`).
5. **Not an exception drug** — the drug is not listed in `ANTIBIOTIC_EXCEPTIONS`.

If several rules match the same guideline and drug, the most specific one is kept.
The result is cached per organism, guideline and drug, so the lookup happens once
per process.

Intrinsic rules are checked **before** breakpoints and do not need a breakpoint to
exist: a drug with no breakpoint for the organism still returns `R*` if a rule
covers it. They do need a valid measurement — an empty cell is not interpreted.

---

## ATC-class rules

106 of the 1,024 rules name a drug **class** by ATC prefix rather than a single drug:

| ATC prefix | Class | Example rule |
|---|---|---|
| `J01AA` | tetracyclines | *Proteus*, *Providencia*, *Morganella* (CLSI) |
| `J01DB` | 1st-generation cephalosporins | *Listeria monocytogenes* (CLSI) |
| `J01G` | aminoglycosides | *Enterococcus faecalis/faecium/gallinarum* (CLSI) |

Every antibiotic whose `ATC_CODE` in `Antibiotics.txt` starts with the prefix is
covered — cefadroxil (`CFR`, J01DB05) for *Listeria*, gentamicin (`GEN`, J01GB03) for
enterococci.

### Load-time code-type correction

Three rules in the upstream table had the wrong `ABX_CODE_TYPE`. On load, each rule's
type is checked against the antibiotic table: if the declared type does not match but
the other does, the other is used; if neither or both match ambiguously, loading
fails.

| Rule | Declared | Used | Effect |
|---|---|---|---|
| CLSI `lmo` × `J01DB` | `WHONET_ABX_CODE` | `ATC_CODE` | *Listeria* × 1st-gen cephalosporins now fires (`lmo CFR_NM` → `R*`) |
| EUCAST `STR` × `GEN` (except `SVI`) | `ATC_CODE` | `WHONET_ABX_CODE` | streptococci × gentamicin now fires (`sgm GEN_ED10` → `R*`) |
| EUCAST `STR` × `GEH` (except `SVI`) | `ATC_CODE` | `WHONET_ABX_CODE` | same, high-level gentamicin code |

On the 622-isolate sample file re-coded to EUCAST, the second and third fixes change
8 results (streptococci on `GEN_ED10`, blank → `R*`).

---

## Exceptions

**Organism exceptions** exclude part of the organism group:

| Rule | Exception | Meaning |
|---|---|---|
| Enterobacterales (`EBC`) × azithromycin | `SAL`, `SHI` (genus) | *Salmonella* and *Shigella* are not intrinsically resistant |
| Non-fermenters (`NFR`) × penicillin, cephalothin (EUCAST) | `MO-` (genus) | *Moraxella* excluded |
| Streptococci (`STR`) × gentamicin (EUCAST) | `SVI` | viridans group excluded |

**Antibiotic exceptions** exclude drugs from a class rule. Enterococci are
intrinsically resistant to aminoglycosides (`J01G`) **except** the high-level
screening tests `KAH` (kanamycin high), `GEH` (gentamicin high) and `STH`
(streptomycin high) — those are reported normally because they detect acquired
high-level resistance, which matters for synergy.

---

## The rule table

`src/amrie/resources/ExpectedResistancePhenotypes.txt` — 1,024 rules.

| | CLSI | EUCAST |
|---|---:|---:|
| rules | 474 | 550 |

| `ORGANISM_CODE_TYPE` | Rules | | `ABX_CODE_TYPE` | Rules |
|---|---:|---|---|---:|
| `WHONET_ORG_CODE` | 801 | | `WHONET_ABX_CODE` | 918 |
| `SPECIES_GROUP` | 90 | | `ATC_CODE` | 106 |
| `GENUS_CODE` | 79 | | | |
| `FAMILY_CODE` | 28 | | | |
| `GENUS_GROUP` | 16 | | | |
| `SUBKINGDOM_CODE` | 5 | | | |
| `ANAEROBE` | 5 | | | |

Columns: `GUIDELINE`, `REFERENCE_TABLE` (the guideline table it comes from, e.g.
`Enterobacterales`), `ORGANISM_CODE`, `ORGANISM_CODE_TYPE`,
`EXCEPTION_ORGANISM_CODE`, `EXCEPTION_ORGANISM_CODE_TYPE`, `ABX_CODE`,
`ABX_CODE_TYPE`, `ANTIBIOTIC_EXCEPTIONS`, `DATE_ENTERED`, `DATE_MODIFIED`,
`COMMENTS`.

---

## Switching it off

```json
{ "UseIntrinsicResistanceRules": false }
```

```python
import dataclasses
from amrie import interpret_single
from amrie.config import read_configuration

config = read_configuration("src/amrie/resources/SampleConfig.json")
no_intrinsic = dataclasses.replace(config, use_intrinsic_resistance_rules=False)
interpret_single(no_intrinsic, "kpn", "AMP_ND10", "25")   # 'S'  (breakpoint only)
interpret_single(no_intrinsic, "kpn", "AMP_ND10", "10")   # 'R'
```

When off, rules are not even looked up. Useful for method-comparison studies or to
see what the breakpoint alone says; keep it on for reporting.

`R*` appears in file output only with `IncludeInterpretationComments: true`;
otherwise it is written as `R`.

---

## Looking rules up

**Python**

```python
from amrie.expected_resistance import get_applicable_expected_resistance_rules as rules

sorted({r.ABX_CODE for r in rules("kpn", ["CLSI"])})
# ['AMP', 'AZM', 'CLI', 'CLR', 'DAP', 'ERY', 'FUS', 'LNZ', 'ORI', 'QDA', 'RIF',
#  'TEC', 'TIC', 'TLV', 'TZD', 'VAN']

len(rules("efa", ["CLSI"]))        # 89 drug-level entries (class rules expanded)
rules("eco", ["CLSI"], ["AMP"])    # []  E. coli is not intrinsically resistant to ampicillin
```

**REST**

```bash
curl -s -X POST http://localhost:8080/api/intrinsic-rules \
  -H "Content-Type: application/json" \
  -d '{"organism_code": "kpn", "restrict_guidelines": true, "guidelines": ["CLSI"]}'
```

```json
{"rules": [
  {"GUIDELINE": "CLSI", "REFERENCE_TABLE": "Enterobacterales", "ORGANISM_CODE": "kpn",
   "ORGANISM_CODE_TYPE": "WHONET_ORG_CODE", "ABX_CODE": "AMP", "ABX_CODE_TYPE": "WHONET_ABX_CODE",
   "ANTIBIOTIC_EXCEPTIONS": "", "COMMENTS": ""},
  …16 rules
]}
```

**Web UI** — on the single tab, choose the organism and press **Applicable
intrinsic rules**.
