# Expert interpretation rules (`R!`)

Expert rules infer resistance from **other results on the same isolate**. A
cefoxitin-resistant *S. aureus* is MRSA, so it must be reported resistant to the
β-lactams on its panel even if their zones look susceptible. AMRIE evaluates the
rules per isolate and marks every affected result **`R!`**.

- [The five rules at a glance](#the-five-rules-at-a-glance)
- [How rules are evaluated](#how-rules-are-evaluated)
- [MRS — methicillin-resistant *Staphylococcus*](#mrs--methicillin-resistant-staphylococcus)
- [ESBL-CONFIRMED](#esbl-confirmed)
- [ESBL-AMPC-PROBABLE](#esbl-ampc-probable)
- [BLNAR-HFLU](#blnar-hflu)
- [ICR — inducible clindamycin resistance](#icr--inducible-clindamycin-resistance)
- [Enabling and disabling rules](#enabling-and-disabling-rules)
- [Input requirements](#input-requirements)
- [Reading the output](#reading-the-output)
- [Looking rules up](#looking-rules-up)

---

## The five rules at a glance

Exactly as they are in `src/amrie/resources/ExpertInterpretationRules.txt`:

| Code | Organisms | Fires when | Marks `R!` |
|---|---|---|---|
| `MRS` | *Staphylococcus* (`STA`, genus) | `MECA_PCR=+` **or** `MRSA=+` **or** `OXA_SCREEN=+` **or** `MRSA_SCRN=+` **or** `PBP2A_AGGL=+` | 140 β-lactams (penicillins, cephems, monobactams, penems, β-lactam/inhibitor combinations), **except** ceftaroline `CPT` and ceftobiprole `BPR` |
| `MRS` (2nd row) | *Staphylococcus* | oxacillin `OXA` **or** cefoxitin `FOX` is **NS** (I or R) | same 140 |
| `ESBL-CONFIRMED` | Enterobacterales (`EBC`, family) | `ESBL=+` **or** `X_BLEE=p` | `MOX`, `CID`, `MAN`, `CFP` |
| `ESBL-AMPC-PROBABLE` | Enterobacterales | any 3rd-generation cephalosporin (`CEPH3`) is **R** | `MOX`, `CID`, `MAN`, `CFP` |
| `BLNAR-HFLU` | *H. influenzae* (`HIN`, serovar group) | `BETA_LACT=-` **and** ampicillin `AMP` is **NS** | `AMC`, `SAM`, `CEC`, `CAT`, `CID`, `CPR`, `CXM`, `CXA`, `TZP` |
| `ICR` | *Staphylococcus* and *Streptococcus* (`STA`, `STR`) | `INDUC_CLI=+` **or** `MLS_DTEST=+` **or** `X_MLS=p` **or** `X_MLS_IND=p` | 33 macrolides, lincosamides and streptogramins |

Drug codes: `MOX` latamoxef (moxalactam), `CID` cefonicid, `MAN` cefamandole, `CFP`
cefoperazone, `AMC` amoxicillin/clavulanate, `SAM` ampicillin/sulbactam, `CEC`
cefaclor, `CXM` cefuroxime, `TZP` piperacillin/tazobactam.

> The ESBL rules in the upstream data affect only the four cephalosporins listed —
> not all β-lactams. A confirmed ESBL *E. coli* with cefotaxime 30 mm stays `S` for
> cefotaxime. Check this against your laboratory's reporting policy.

---

## How rules are evaluated

For each isolate row:

1. **Find candidate rules** — enabled rules whose organism scope covers the isolate
   and whose criteria mention at least one test present in the row.
2. **Make sure the drugs in the criteria are interpreted** — e.g. for MRS row 2,
   `OXA_*` and `FOX_*` columns are interpreted first (breakpoints + intrinsic rules).
   Drug criteria are matched by exact drug code (`FOX` matches `FOX_ND30`,
   `FOX_NM`…, never `OXA_SCREEN` or `X_12` for `X_1`).
3. **Evaluate the criteria**:
   - a drug criterion `= R` is met if one of that drug's results is `R`;
   - a drug criterion `= NS` is met if one is `R` or `I`;
   - `CEPH3 = R` is met if any 3rd-generation cephalosporin result is `R`;
   - a test criterion (`ESBL=+`) is met if the column's value is exactly `+`;
   - criteria are combined with the rule's `AND` / `OR`.
4. **Apply** — every affected drug **present in the row** gets `R!`, overriding its
   own result, including `S`. Drugs not tested are not added.
5. Remaining drugs are interpreted normally.

Rules only run within one isolate (one row). In `interpret_single` there is only one
drug, so a rule fires only if that drug is both a trigger and affected (cefoxitin for
MRS) — use a full row (`IsolateInterpretation`, `amrie file`) to see a rule's full
effect.

---

## MRS — methicillin-resistant *Staphylococcus*

Two rows, both affecting the same β-lactam list.

**By phenotype** — cefoxitin disk 15 mm (*S. aureus* R ≤ 21):

```text
Input   ORGANISM=sau  FOX_ND30=15  PEN_ND10=35  VAN_NM=1
Output  FOX_ND30 R!   PEN_ND10 R!   VAN_NM S
```

Penicillin at 35 mm would be `S` on its own; vancomycin is not a β-lactam and keeps
its own result.

**By genotype / screen** — `MECA_PCR=+`, even with nothing else resistant:

```text
Input   ORGANISM=sau  MECA_PCR=+  PEN_ND10=35  CPT_ND30=25  VAN_NM=1
Output  PEN_ND10 R!   CPT_ND30 S   VAN_NM S
```

Ceftaroline (`CPT`) keeps its own result: it is active against MRSA, which is why the
rule excludes it (and ceftobiprole `BPR`).

**Without MRS enabled** the same first row gives `FOX_ND30 R`, `PEN_ND10 S`.

---

## ESBL-CONFIRMED

Use when the laboratory has confirmed ESBL production (phenotypic confirmation test or
genotype) and records `+` in `ESBL` (or `p` in `X_BLEE`).

```text
Input   ORGANISM=eco  ESBL=+  CTX_ND30=30  MAN_ND30=25  AMP_ND10=19  CIP_ND5=30
Output  MAN_ND30 R!   CTX_ND30 S   AMP_ND10 S   CIP_ND5 S

Input   ORGANISM=eco  ESBL=-  CTX_ND30=30  MAN_ND30=25
Output  CTX_ND30 S    MAN_ND30 S
```

---

## ESBL-AMPC-PROBABLE

Infers probable ESBL/AmpC production when **any 3rd-generation cephalosporin** is
resistant — no confirmatory test needed. The 3rd-generation cephalosporins are the
antibiotics with `PROF_CLASS = CEPH3` in `Antibiotics.txt` (`amrie.antibiotic.CEPH3_ANTIBIOTIC_CODES`).

```text
Input   ORGANISM=eco  CTX_ND30=20  MAN_ND30=25  CFP_ND75=30
Output  CTX_ND30 R    MAN_ND30 R!  CFP_ND75 R!
```

Cefotaxime 20 mm is resistant (CLSI R ≤ 22 for Enterobacterales), which triggers the
rule.

---

## BLNAR-HFLU

β-lactamase-negative, ampicillin-resistant *Haemophilus influenzae*: resistance comes
from altered PBP3, which also reduces activity of amoxicillin/clavulanate and several
cephalosporins.

```text
Input   ORGANISM=hin  BETA_LACT=-  AMP_ND10=15  AMC_ND20=25  CXM_ND30=25
Output  AMP_ND10 R    AMC_ND20 R!  CXM_ND30 R!

Input   ORGANISM=hin  BETA_LACT=+  AMP_ND10=15  AMC_ND20=25
Output  AMP_ND10 R    AMC_ND20 (blank)          ← β-lactamase positive: rule does not fire
```

Both `BETA_LACT` and an ampicillin result are required (`AND`).

---

## ICR — inducible clindamycin resistance

A positive D-test (erythromycin-induced clindamycin resistance) means clindamycin can
fail in therapy even though it tests susceptible. Record the D-test in `INDUC_CLI` or
`MLS_DTEST` (`+`) or `X_MLS` / `X_MLS_IND` (`p`).

```text
Input   ORGANISM=sau  INDUC_CLI=+  ERY_ND15=25  CLI_ND2=25  VAN_NM=1
Output  ERY_ND15 R!   CLI_ND2 R!   VAN_NM S

Same input, ICR disabled:
Output  ERY_ND15 S    CLI_ND2 S
```

The rule is triggered by the D-test field, not by the erythromycin/clindamycin
pattern. It applies to staphylococci and streptococci.

---

## Enabling and disabling rules

| JSON `EnabledExpertInterpretationRules` | Effect |
|---|---|
| key absent, `null` or `[]` | **all** rules |
| `["MRS", "ICR"]` | only these |
| `["NONE"]` (any non-rule value) | no rules |

```json
{ "EnabledExpertInterpretationRules": ["MRS", "ICR", "BLNAR-HFLU"] }
```

Python:

```python
from amrie.config import InterpretationConfiguration
from amrie.expert_rule import RuleCodes

InterpretationConfiguration(enabled_expert_interpretation_rules=[RuleCodes.MRSTAPH, RuleCodes.ICR])
InterpretationConfiguration(enabled_expert_interpretation_rules=None)   # all rules
InterpretationConfiguration(enabled_expert_interpretation_rules=[])     # no rules (Python only)
```

`RuleCodes`: `ESBL_CONFIRMED`, `ESBL_PROBABLE`, `BLNAR`, `MRSTAPH`, `ICR`, `ALL`.

The sample configuration enables `BLNAR-HFLU`, `MRS` and `ICR` and leaves the two
ESBL rules off.

---

## Input requirements

| Rule | Needs in the row |
|---|---|
| `MRS` | `ORGANISM` (a staphylococcus) + one of `MECA_PCR`, `MRSA`, `OXA_SCREEN`, `MRSA_SCRN`, `PBP2A_AGGL`, an `OXA_…` or a `FOX_…` column |
| `ESBL-CONFIRMED` | `ORGANISM` (Enterobacterales) + `ESBL` or `X_BLEE` |
| `ESBL-AMPC-PROBABLE` | `ORGANISM` (Enterobacterales) + at least one 3rd-generation cephalosporin column (`CTX_…`, `CRO_…`, `CAZ_…`, …) |
| `BLNAR-HFLU` | `ORGANISM` (*H. influenzae*) + `BETA_LACT` + an `AMP_…` column |
| `ICR` | `ORGANISM` (staphylococcus or streptococcus) + `INDUC_CLI`, `MLS_DTEST`, `X_MLS` or `X_MLS_IND` |

Values are compared exactly: use `+`, `-` and `p` as shown.

---

## Reading the output

| Where | `IncludeInterpretationComments: false` | `true` |
|---|---|---|
| file output, `amrie single`, REST | `R` | `R!` |
| `interpret_single`, `IsolateInterpretation` (Python) | `R!` | `R!` |

The `!` tells you the result was inferred, not measured — keep it on while reviewing
data, and strip it for systems that only accept S/I/R.

---

## Looking rules up

```python
from amrie.expert_rule import EXPERT_INTERPRETATION_RULES, get_applicable_expert_rules

for r in EXPERT_INTERPRETATION_RULES:
    print(r.RULE_CODE, r.ORGANISM_CODE, r.CriteriaOperator,
          [(c.test_name, c.test_result) for c in r.RULE_CRITERIA], len(r.AFFECTED_ANTIBIOTICS))
# ESBL-CONFIRMED EBC OR [('ESBL', '+'), ('X_BLEE', 'p')] 4
# ESBL-AMPC-PROBABLE EBC AND [('CEPH3', 'R')] 4
# BLNAR-HFLU HIN AND [('BETA_LACT', '-'), ('AMP', 'NS')] 9
# MRS STA OR [('MECA_PCR', '+'), ('MRSA', '+'), ('OXA_SCREEN', '+'), ('MRSA_SCRN', '+'), ('PBP2A_AGGL', '+')] 140
# MRS STA OR [('OXA', 'NS'), ('FOX', 'NS')] 140
# ICR STA OR [('INDUC_CLI', '+'), ('MLS_DTEST', '+'), ('X_MLS', 'p'), ('X_MLS_IND', 'p')] 33
# ICR STR OR [('INDUC_CLI', '+'), ('MLS_DTEST', '+'), ('X_MLS', 'p'), ('X_MLS_IND', 'p')] 33

[r.RULE_CODE for r in get_applicable_expert_rules("sau", ["FOX_ND30", "PEN_ND10"], ["OXA_SCREEN"], None)]
# ['MRS', 'MRS']
```

REST: `POST /api/expert-rules` with `{"organism_code": "sau", "full_test_codes":
["FOX_ND30", "PEN_ND10", "OXA_SCREEN"]}` returns both MRS rows with their criteria and
affected drugs ([Web](web.md#post-apiexpert-rules)).
