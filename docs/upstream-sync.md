# Upstream C# Sync Tracker

This file records which commit of the upstream C# AMRIE project was used as the
basis for each change to this Python port. When the C# project is updated, start
your diff from the **"Last synced commit"** below to find only the new changes.

**Upstream repository:** https://github.com/WHONET-Development/AMRIE
(formerly `AClark-WHONET/AMRIE`; GitHub redirects the old URL)

**This port:** https://github.com/aurthurm/beak-whonet-amrie

---

## Current sync state

| Field | Value |
|---|---|
| **Last synced commit** | `99acabc2251c6f5c2a13f9ec285814a59913b81a` |
| **Short hash** | `99acabc` |
| **Date** | 2026-11-18 |
| **Author** | WHONET-Development |
| **Commit message** | Relative paths used instead of absolute. |
| **Synced on** | 2026-11-18 |
| **Synced by** | Upstream sync `69de201..99acabc` |

---

## How to check for upstream changes

```bash
# In the cloned C# repo:
cd /path/to/AMRIE

# Show everything after the last synced commit
git log 99acabc..HEAD --oneline

# Show only changes to source files (ignore installer / CI / docs)
git log 99acabc..HEAD --oneline -- \
  "AMRIE.Library/" \
  "AMRIE.CLI/" \
  "AMRIE.Library.Tests/"

# Full diff of interpretation logic since last sync
# Use -M to follow the 2026-11 folder renames and -w to skip syntax-only churn
git diff -M -w --ignore-cr-at-eol 99acabc..HEAD -- \
  "AMRIE.Library/" \
  "AMRIE.CLI/" \
  "AMRIE.Library.Tests/"
```

---

## Sync log

Each entry records what changed in the C# project and what was done in this port.

| Date | C# commit range | Summary | Python files changed |
|---|---|---|---|
| 2026-05-30 | — (initial port) | Full 1:1 port of the C# engine at `69de201` | All `src/amrie/*.py` files |
| 2026-11-18 | `69de201..99acabc` | Ported `d752848` engine-correctness fixes: `ALL`-organism breakpoints (515 EUCAST/SFM PK-PD rows) now match; breakpoint `ORGANISM_CODE_TYPE` resolved at load (104 `BS-`, 77 `NME` rows); expected-resistance `ABX_CODE_TYPE` resolved at load (J01DB, GEN, GEH); breakpoint cache keyed on full selection (types/sites/user BPs); `RoundHalfDilutions` honoured in batch + single; user-defined antibiotics restricted to `X_1`–`X_99` with C# `ShortCode`; expert-rule drug matching by short code; RFC-style `split_line`/`to_line`; delimiters limited to TAB `,` `;` `\|`; config JSON accepts `$schema`, comments, trailing commas, case-insensitive keys. Data: `Organisms.txt` (*Candidozyma*). Bug already fixed in port: AFA column. Not ported: GUIs, data generator, perf `BoundedCache`. | `breakpoint.py`, `expected_resistance.py`, `antibiotic_rules.py`, `isolate.py`, `io_library.py`, `parsing.py`, `antibiotic.py`, `expert_rule.py`, `config.py`, `io_utils.py`, `constants.py`, `cli.py`, `web/api/interpret.py`, `resources/Organisms.txt`, `resources/SampleConfig.json`, `docs/reference/amrie-config.schema.json`, `tests/test_sync_*.py` |

---

## Sync procedure

When upstream commits are detected, follow these steps:

### 1. Identify the relevant commits

```bash
git log 99acabc..HEAD --oneline -- "AMRIE.Library/" "AMRIE.CLI/" "AMRIE.Library.Tests/"
```

Focus on files that map to Python logic (see
[C# → Python mapping](architecture.md#c--python-mapping)). Ignore:

- `AMRIE.WinForms*/`, `AMRIE.WinUI*/`, `AMRIE.Desktop/` — GUIs and installers, not ported
- `AMRIE.Library.DataGenerator/` — useful for parity fixtures, not ported
- `.agent-index/`, `.agents/`, `docs/`, `licenses/` — upstream tooling and docs
- `.github/`, `*.yml` — CI/packaging, not ported

> **Folder rename (Nov 2026):** `Interpretation Engine/` → `AMRIE.Library/`,
> `Interpretation CLI/` → `AMRIE.CLI/`, namespace `AMR_Engine` → `AMRIE.Library`.
> Resource files under `Resources/` use CRLF line endings — keep ours CRLF when copying.

### 2. Apply the change

Translate the C# diff into the corresponding Python module. The
[architecture doc](architecture.md#c--python-mapping) lists which C# file maps
to which Python module.

Key things to check:

| C# change type | Python impact |
|---|---|
| New/changed breakpoint data (`Breakpoints.txt`) | Replace resource file; update `BREAKPOINT_TABLE_REVISION_YEAR` in `constants.py` |
| Organism data change (`Organisms.txt`) | Replace resource file |
| New intrinsic resistance rule | Replace `ExpectedResistancePhenotypes.txt` |
| New expert rule | Replace `ExpertInterpretationRules.txt`; may need logic change in `expert_rule.py` |
| Interpretation logic change | Update the corresponding module |
| New QC ranges | Replace `QC_Ranges.txt` |

### 3. Update tests

- Add or update test cases in `tests/test_parity.py` or `tests/test_qc.py`.
- For breakpoint data changes, regenerate the golden file:

  ```bash
  rm tests/fixtures/golden_sample_output.txt
  pytest tests/test_parity.py::TestGoldenFile -v   # creates the file
  pytest tests/test_parity.py::TestGoldenFile -v   # must pass now
  ```

### 4. Update this file

Update the **Current sync state** table at the top of this document with the new commit hash, date, and summary. Append a row to the **Sync log** table.

```markdown
| 2026-XX-XX | 99acabc..NEWHASH | Brief description | e.g. breakpoint.py, constants.py |
```
