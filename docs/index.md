# AMRIE-py documentation

AMRIE-py interprets antimicrobial susceptibility test results (disk zones, MICs,
E-tests) against CLSI, EUCAST, SFM and other guideline breakpoints, applies
intrinsic-resistance and expert rules, and evaluates QC strains. It is a Python
port of [WHONET-Development/AMRIE](https://github.com/WHONET-Development/AMRIE).

Start with the [README](../README.md) for a five-minute tour.

---

## Learn

| Document | Read it when you want to… |
|---|---|
| [Getting started](getting-started.md) | install, run your first interpretation, then a whole file, step by step |
| [Concepts](concepts.md) | understand S/I/R/SDD/NS/WT/NWT, breakpoints, ECOFFs, guidelines, censored MICs and WHONET codes |
| [Use cases & recipes](use-cases.md) | copy a working solution for a common task |

## Use

| Document | Covers |
|---|---|
| [Python API](python-api.md) | every public function and class, with signatures and examples |
| [CLI reference](cli-reference.md) | `amrie file`, `amrie single`, `amrie qc`, delimiters, exit codes |
| [Configuration](configuration.md) | every JSON key, defaults, loader rules, ready-made configs |
| [Data formats](data-formats.md) | column naming, input files, output layouts, user-defined breakpoint files, the bundled tables |
| [Web UI & REST API](web.md) | running the server, each page, every endpoint with real requests and responses, Docker |
| [Quality control](quality-control.md) | checking reference strains against QC ranges |

## Understand the results

| Document | Explains |
|---|---|
| [Breakpoint selection](breakpoint-selection.md) | exactly how the engine picks one breakpoint out of 51,001 |
| [Intrinsic resistance](intrinsic-resistance.md) | where `R*` comes from |
| [Expert rules](expert-rules.md) | where `R!` comes from — MRS, ESBL, BLNAR, ICR |
| [Troubleshooting & FAQ](troubleshooting.md) | blank results, surprising categories, file problems |

## Develop

| Document | Covers |
|---|---|
| [Architecture](architecture.md) | modules, data flow, caches, threading, C# → Python mapping |
| [Development guide](development.md) | setup, tests, golden file, updating resource tables, coding conventions |
| [Upstream sync](upstream-sync.md) | which upstream commit this port matches and how to port new ones |
| [`reference/amrie-config.schema.json`](reference/amrie-config.schema.json) | JSON Schema for configuration files |

---

## Conventions used in these docs

- Commands are run from the repository root. `amrie …` assumes the package is
  installed (`pip install -e .`); `PYTHONPATH=src python -m amrie.cli …` works too.
- Results shown as `eco AMP_ND10 19 → S` mean *organism code*, *antibiotic test
  column*, *raw measurement* and *interpretation*.
- Unless stated otherwise, examples use the bundled
  [`SampleConfig.json`](../src/amrie/resources/SampleConfig.json) and guideline
  year **2026**.
- Every interpretation quoted in these docs is asserted by
  [`tests/test_doc_examples.py`](../tests/test_doc_examples.py).
