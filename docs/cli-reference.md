# CLI reference

The `amrie` command has three sub-commands. It is installed by `pip install -e .`
(or run it without installing: `PYTHONPATH=src python -m amrie.cli …`).

```text
amrie file    -c CONFIG -d DELIMITER -i INPUT -o OUTPUT
amrie single  -c CONFIG --organism ORG --antibiotic TEST -m VALUE -o OUTPUT.json
amrie qc      --organism STRAIN --antibiotic TEST -m VALUE [-o OUTPUT.json] [--no-round-half-dilutions]
```

| Sub-command | C# equivalent | Purpose |
|---|---|---|
| `file` | `AMRIE.CLI FILE …` | interpret a whole delimited file |
| `single` | `AMRIE.CLI SINGLE_INTERPRETATION …` | interpret one measurement |
| `qc` | — (Python extension) | evaluate a QC reference-strain result |

`amrie --help` and `amrie <command> --help` print the built-in help.

---

## `amrie file`

Interpret every isolate in a delimited file and write an output file with the
interpretations.

| Option | Short | Required | Description |
|---|---|---|---|
| `--config PATH` | `-c` | ✔ | JSON configuration file ([Configuration](configuration.md)) |
| `--delimiter TEXT` | `-d` | ✔ | input delimiter: `TAB` (any case), `,`, `;` or `|` |
| `--input PATH` | `-i` | ✔ | input data file (UTF-8, BOM allowed) |
| `--output PATH` | `-o` | ✔ | output file — created or overwritten, **always tab-delimited** |

The guideline year comes from the configuration (`GuidelineYear`). To use another
year without editing the file, use the Python API's `guideline_year=` argument or
a second config file.

### Examples

```bash
# Pipe-delimited input (WHONET export style)
amrie file -c src/amrie/resources/SampleConfig.json -d "|" \
           -i src/amrie/resources/SampleInputFile.txt -o sample_out.txt

# Tab-delimited input
amrie file -c my-config.json -d TAB -i isolates.tsv -o results.txt

# CSV and semicolon-separated (European Excel) input
amrie file -c my-config.json -d "," -i isolates.csv -o results.txt
amrie file -c my-config.json -d ";" -i isolates.csv -o results.txt
```

Quote `|` and `;` on the command line — the shell treats them as operators.

### Output

stdout:

```text
Wrote interpretations to results.txt
```

For this input (`isolates.txt`):

```text
ORGANISM|SPEC_TYPE|AMP_ND10|CTX_ND30|CIP_NM|FOX_ND30|PEN_ND10
eco|ur|19|20|0.5||
kpn|bl|25|30|<=0.25||
sau|wd|||1|15|35
```

the output with the sample configuration is (tabs shown as spacing):

```text
ORGANISM SPEC_TYPE AMP_ND10 AMP_ND10_INTERP CTX_ND30 CTX_ND30_INTERP CIP_NM CIP_NM_INTERP FOX_ND30 FOX_ND30_INTERP PEN_ND10 PEN_ND10_INTERP
eco      ur        19       S               20       R               0.5    I
kpn      bl        25       R               30       S               <=0.25 S
sau      wd                                                          1      S             15       R               35       R
```

With `"IncludeInterpretationComments": true` the `kpn` ampicillin result is `R*`
and the `sau` results are `R!`; with `"HorizontalAntibioticResults": false` the
file has one row per measurement. See [Data formats → output](data-formats.md#output-files).

### What `file` does, step by step

1. Reads the configuration (and any user-defined breakpoints file it names).
2. Reads the input; the first non-blank line is the header. Blank rows, and rows
   with fewer fields than the header, are skipped.
3. Collects every distinct organism / guideline / test combination and resolves
   their breakpoints in parallel.
4. Interprets each row (intrinsic rules → breakpoints → expert rules) on a thread
   pool.
5. Writes the output in input order.

---

## `amrie single`

Interpret one organism / test / measurement, print the result and write a JSON
record.

| Option | Short | Required | Description |
|---|---|---|---|
| `--config PATH` | `-c` | ✔ | JSON configuration file |
| `--organism TEXT` | | ✔ | WHONET organism code (`eco`, `sau`, …) |
| `--antibiotic TEXT` | | ✔ | full test column (`AMP_ND10`, `CIP_EM`, `X_3_NM`, …) |
| `--measurement TEXT` | `-m` | ✔ | raw value — quote values with `<` / `>`: `-m "<=2"` |
| `--output PATH` | `-o` | ✔ | JSON output file (use `/dev/null` if you only want stdout) |

Suffixes `*` and `!` are printed only if the configuration has
`"IncludeInterpretationComments": true`; `?` is always printed.

### Examples

```bash
CFG=src/amrie/resources/SampleConfig.json

amrie single -c $CFG --organism spn --antibiotic AMC_NM   -m 2      -o r.json   # S
amrie single -c $CFG --organism eco --antibiotic AMP_ND10 -m 12     -o r.json   # R
amrie single -c $CFG --organism eco --antibiotic AMP_NM   -m "<=16" -o r.json   # S?
amrie single -c $CFG --organism kpn --antibiotic AMP_ND10 -m 25     -o r.json   # R   (R* with comments on)
amrie single -c $CFG --organism sau --antibiotic FOX_ND30 -m 15     -o r.json   # R   (R! with comments on)
amrie single -c $CFG --organism sau --antibiotic CPT_ND30 -m 22     -o r.json   # SDD
```

### Output

stdout is the interpretation alone (an empty line when uninterpretable):

```text
S
```

The JSON file:

```json
{
  "OrganismCode": "spn",
  "AntibioticCode": "AMC_NM",
  "Measurement": "2",
  "Interpretation": "S"
}
```

### Scripting with `single`

```bash
# Interpret a list of zones
for mm in 19 17 15 14 13 6; do
  printf "%3s mm → %s\n" "$mm" "$(amrie single -c $CFG --organism eco --antibiotic AMP_ND10 -m $mm -o /dev/null)"
done
```

```text
 19 mm → S
 17 mm → S
 15 mm → I
 14 mm → I
 13 mm → R
  6 mm → R
```

Each `amrie` invocation starts a new Python process and loads the reference tables
(~1 s). For more than a handful of values use `amrie file` or the Python API.

---

## `amrie qc`

Check a QC reference-strain measurement against its acceptable range.

| Option | Short | Required | Description |
|---|---|---|---|
| `--organism TEXT` | | ✔ | reference strain code, e.g. `atcc25922` |
| `--antibiotic TEXT` | | ✔ | full test column, e.g. `AMP_ND10` |
| `--measurement TEXT` | `-m` | ✔ | measured value |
| `--output PATH` | `-o` | | optional JSON output file |
| `--round-half-dilutions` / `--no-round-half-dilutions` | | | round MIC/E-test values between dilutions up before comparison (default: on) |

No configuration file is used.

### Examples

```bash
amrie qc --organism atcc25922 --antibiotic AMP_ND10 -m 18             # IN   (range 15–22 mm)
amrie qc --organism atcc25922 --antibiotic AMP_ND10 -m 10             # OUT
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

`IN` = within range, `OUT` = outside, empty = no range for that strain/test or the
value is not a valid measurement. See [Quality control](quality-control.md).

---

## Delimiters

| You pass | Delimiter used |
|---|---|
| `TAB`, `tab`, `Tab` | tab character |
| `,` | comma |
| `;` | semicolon |
| `|` | pipe |
| anything else (`pipe`, `:`, `||`, …) | **error**, exit code 2 |

```text
$ amrie file -c cfg.json -d pipe -i in.txt -o out.txt
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Invalid value for '--delimiter' / '-d': Unsupported delimiter token.         │
│ Supported delimiters are TAB, comma (,), semicolon (;), and pipe (|);        │
│ provide TAB or exactly one character.                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

Fields may be quoted with `"` to include the delimiter, and `""` inside a quoted
field is a literal quote: `eco,"Smith, J",19`. A field cannot span several lines.

Choosing the *wrong* supported delimiter (e.g. `-d ";"` for a pipe file) is not an
error: the whole line becomes one column, nothing is recognised as an antibiotic,
and the output is a copy of the input. If your output has no `_INTERP` columns,
check the delimiter first.

---

## Exit codes

| Code | When |
|---|---|
| `0` | success (including uninterpretable results) |
| `1` | an error while running — missing config or input file, invalid JSON, invalid test code (Python traceback on stderr) |
| `2` | usage error — missing/unknown option, unsupported delimiter |

---

## Running without installing

```bash
PYTHONPATH=src python -m amrie.cli single -c src/amrie/resources/SampleConfig.json \
    --organism eco --antibiotic AMP_ND10 -m 19 -o /dev/null
```

## Docker

The image's default command starts the web server; override it to run the CLI:

```bash
docker build -t amrie-web .
docker run --rm -v "$PWD:/data" amrie-web \
  amrie file -c /data/my-config.json -d "|" -i /data/isolates.txt -o /data/results.txt
```
