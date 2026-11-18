# Web UI and REST API

AMRIE-py ships a browser UI and a REST API in **one Python process**:
[NiceGUI](https://nicegui.io/) serves the pages and mounts FastAPI endpoints on the
same server. The web layer (`web/`) only calls the engine (`src/amrie/`); it never
changes interpretation logic.

- [Install and run](#install-and-run)
- [Pages](#pages)
- [REST API](#rest-api)
  - [`POST /api/interpret/single`](#post-apiinterpretsingle)
  - [`POST /api/interpret/file`](#post-apiinterpretfile)
  - [`POST /api/qc`](#post-apiqc)
  - [`POST /api/breakpoints`](#post-apibreakpoints)
  - [`POST /api/expert-rules`](#post-apiexpert-rules)
  - [`POST /api/intrinsic-rules`](#post-apiintrinsic-rules)
  - [Reference lists](#reference-lists)
- [Calling the API from Python](#calling-the-api-from-python)
- [How the web layer configures the engine](#how-the-web-layer-configures-the-engine)
- [Architecture](#architecture)
- [Deployment](#deployment)

---

## Install and run

```bash
pip install -e ".[web]"        # adds nicegui>=2.0 and httpx>=0.27
amrie-web                      # or: python web/main.py
```

The server listens on **`http://0.0.0.0:8080`**:

| URL | What |
|---|---|
| `/` | single interpretation page |
| `/file` | batch file page |
| `/qc` | QC page |
| `/docs` | interactive OpenAPI (Swagger) documentation — try every endpoint in the browser |
| `/api/…` | REST endpoints |

The port is fixed in `web/main.py`. To use another one, run NiceGUI yourself:

```python
# run_web.py
import web.main                      # registers all pages and API routes
from nicegui import ui
ui.run(host="127.0.0.1", port=8765, title="AMRIE Web", storage_secret="change-me",
       fastapi_docs=True, show=False, reload=False)
```

---

## Pages

### Single interpretation — `/`

The equivalent of `amrie single`, with dropdowns.

1. **Organism** — searchable list of all organisms (code + name).
2. **Antibiotic** — searchable list of drugs.
3. **Disk** or **MIC / E-test**; for disks choose a **potency** (the choices depend on
   the drug and the active guidelines).
4. **Measurement** — zone (mm) or MIC (mg/L), modifiers allowed (`<=2`).
5. **Filters** — guidelines (CLSI, EUCAST, SFM), guideline year, optional
   breakpoint-type and site-of-infection restrictions.
6. **Get interpretations** — one line per generated test code, e.g. CLSI and EUCAST
   selected for ampicillin MIC 8 →

   ```text
   AMP_NM: S
   AMP_EM: S
   ```

Also on the page:

- **Applicable breakpoints** — every breakpoint row that would apply, with S/I/R values;
- **Applicable expert rules** — the rules that could fire for the organism;
- **Applicable intrinsic rules** — the expected-resistance rules for the organism;
- **Include interpretation comments** — show `R*` / `R!` instead of `R`.

### Batch file — `/file`

The equivalent of `amrie file`.

1. Upload the **data file**.
2. Pick the **delimiter**: pipe, comma, semicolon or tab.
3. Upload a **configuration JSON** (same format as the CLI — [Configuration](configuration.md)).
4. Set the **guideline year** for the run.
5. **Interpret** — progress is shown in batches of 50 rows; **Cancel** stops between
   batches. When finished, `interpretations.txt` downloads.

### Quality control — `/qc`

Strain (e.g. `atcc25922`), full test code (e.g. `AMP_ND10`), measurement →
`IN` / `OUT` / blank. See [Quality control](quality-control.md).

---

## REST API

JSON in, JSON out (except the file endpoint). The live schema is at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/interpret/single` | interpret one organism / drug / value for one or more guidelines |
| `POST` | `/api/interpret/file` | interpret an uploaded file with an uploaded config |
| `POST` | `/api/qc` | QC range check |
| `POST` | `/api/breakpoints` | applicable breakpoints for an organism |
| `POST` | `/api/expert-rules` | applicable expert rules |
| `POST` | `/api/intrinsic-rules` | applicable intrinsic resistance rules |
| `GET` | `/api/organisms` | organism codes and names |
| `GET` | `/api/antibiotics` | antibiotic codes, names, potencies |
| `GET` | `/api/guidelines` | guideline names |
| `GET` | `/api/breakpoint-types` | breakpoint types |
| `GET` | `/api/sites` | sites of infection, in default priority order |

### `POST /api/interpret/single`

You give the **base drug code**, the method and (for disks) the potency; the server
builds the WHONET test code for each guideline you list (`PEN` + CLSI + disk + 10 →
`PEN_ND10`).

| Field | Type | Default | Description |
|---|---|---|---|
| `organism_code` | string | — | WHONET organism code (`ent`, `eco`, …) |
| `whonet_abx_code` | string | — | drug code (`PEN`, `AMP`, …) |
| `measurement` | string | — | zone or MIC, modifiers allowed |
| `guideline_year` | integer | — | breakpoint year |
| `guidelines` | string[] | `["CLSI"]` | any of `CLSI`, `EUCAST`, `SFM` |
| `test_method` | `"disk"` \| `"mic"` | `"disk"` | |
| `potency` | string | `""` | disk potency: `10`, `10µg`, `10units`, `1.25/23.75µg` are all accepted |
| `include_comments` | boolean | `false` | return `R*` / `R!` instead of `R` |
| `restrict_breakpoint_types` | boolean | `false` | when `false`, Human breakpoints only |
| `breakpoint_types` | string[] | `[]` | used when `restrict_breakpoint_types` is `true` |
| `restrict_sites` | boolean | `false` | |
| `sites_of_infection` | string[] | `[]` | site priority when `restrict_sites` is `true` |

**Example — *Enterococcus*, penicillin 10-unit disk, 19 mm:**

```bash
curl -s -X POST http://localhost:8080/api/interpret/single \
  -H "Content-Type: application/json" \
  -d '{"organism_code": "ent", "whonet_abx_code": "PEN", "measurement": "19",
       "guidelines": ["CLSI"], "test_method": "disk", "potency": "10", "guideline_year": 2026}'
```

```json
{"results":[{"whonet_test":"PEN_ND10","interpretation":"S"}]}
```

**Two guidelines at once — *E. coli*, ampicillin MIC 8:**

```bash
curl -s -X POST http://localhost:8080/api/interpret/single \
  -H "Content-Type: application/json" \
  -d '{"organism_code": "eco", "whonet_abx_code": "AMP", "measurement": "8",
       "guidelines": ["CLSI", "EUCAST"], "test_method": "mic", "guideline_year": 2026}'
```

```json
{"results":[{"whonet_test":"AMP_NM","interpretation":"S"},{"whonet_test":"AMP_EM","interpretation":"S"}]}
```

**Comments — *K. pneumoniae*, ampicillin 25 mm:**

| `include_comments` | response `interpretation` |
|---|---|
| `false` | `"R"` |
| `true` | `"R*"` |

Expert rules are all enabled for this endpoint, but it interprets one drug at a time;
to see a rule's effect across a panel, use the file endpoint.

### `POST /api/interpret/file`

`multipart/form-data`:

| Field | Type | Description |
|---|---|---|
| `data_file` | file | the input data |
| `config_file` | file | the configuration JSON |
| `delimiter` | string | `|`, `,`, `;` or `TAB` (default `|`) |
| `guideline_year` | integer | breakpoint year for this run (overrides the config) |

```bash
curl -s -X POST http://localhost:8080/api/interpret/file \
  -F data_file=@isolates.txt \
  -F config_file=@src/amrie/resources/SampleConfig.json \
  -F delimiter='|' -F guideline_year=2026
```

Response: `text/tab-separated-values`, `Content-Disposition: attachment; filename=interpretations.txt`:

```text
ORGANISM	SPEC_TYPE	AMP_ND10	AMP_ND10_INTERP	CTX_ND30	CTX_ND30_INTERP	CIP_NM	CIP_NM_INTERP	FOX_ND30	FOX_ND30_INTERP	PEN_ND10	PEN_ND10_INTERP
eco	ur	19	S	20	R	0.5	I
kpn	bl	25	R	30	S	<=0.25	S
sau	wd					1	S	15	R	35	R
```

An unsupported delimiter is rejected with **HTTP 400**:

```bash
curl -s -w ' HTTP %{http_code}\n' -X POST http://localhost:8080/api/interpret/file \
  -F data_file=@isolates.txt -F config_file=@src/amrie/resources/SampleConfig.json \
  -F delimiter='pipe' -F guideline_year=2026
```

```text
{"detail":"Unsupported delimiter token. Supported delimiters are TAB, comma (,), semicolon (;), and pipe (|); provide TAB or exactly one character."} HTTP 400
```

### `POST /api/qc`

| Field | Type | Default |
|---|---|---|
| `strain` | string | — |
| `antibiotic` | string (full test code) | — |
| `measurement` | string | — |
| `round_half_dilutions` | boolean | `true` |

```bash
curl -s -X POST http://localhost:8080/api/qc -H "Content-Type: application/json" \
  -d '{"strain": "atcc25922", "antibiotic": "AMP_ND10", "measurement": "18"}'
```

```json
{"result":"IN"}
```

### `POST /api/breakpoints`

All applicable breakpoint rows for an organism, optionally restricted.

| Field | Type | Default | Description |
|---|---|---|---|
| `organism_code` | string | — | |
| `restrict_guidelines` / `prioritized_guidelines` | bool / string[] | `false` / `null` | |
| `restrict_years` / `prioritized_guideline_years` | bool / int[] | `false` / `null` | |
| `restrict_breakpoint_types` / `prioritized_breakpoint_types` | bool / string[] | `false` / `null` | |
| `restrict_sites` / `prioritized_sites_of_infection` | bool / string[] | `false` / `null` | |
| `restrict_drugs` | bool | `false` | when `true`, build test codes from the next three fields |
| `whonet_abx_code`, `test_method`, `potency` | string | | drug for `restrict_drugs` |
| `guidelines_for_drugs` | string[] | `[]` | guidelines used to build the test codes |
| `user_defined_breakpoints` | list | `[]` | |

```bash
curl -s -X POST http://localhost:8080/api/breakpoints -H "Content-Type: application/json" -d '{
  "organism_code": "eco",
  "restrict_guidelines": true, "prioritized_guidelines": ["CLSI"],
  "restrict_years": true, "prioritized_guideline_years": [2026],
  "restrict_drugs": true, "whonet_abx_code": "AMP", "test_method": "disk", "potency": "10",
  "guidelines_for_drugs": ["CLSI"]}'
```

```json
{"breakpoints": [
  {"GUIDELINES": "CLSI", "YEAR": 2026, "BREAKPOINT_TYPE": "Human", "HOST": "Human",
   "SITE_OF_INFECTION": "", "WHONET_TEST": "AMP_ND10", "R": "13", "I": "14-16", "S": "17",
   "ECV_ECOFF": "0", "ORGANISM_CODE": "EBC", "ORGANISM_CODE_TYPE": "FAMILY_CODE", "COMMENTS": "…"},
  …4 rows (Human, 2 × Animal, ECOFF)
]}
```

### `POST /api/expert-rules`

| Field | Type | Description |
|---|---|---|
| `organism_code` | string | |
| `full_test_codes` | string[] | the isolate's columns (antibiotic and other tests) |

```bash
curl -s -X POST http://localhost:8080/api/expert-rules -H "Content-Type: application/json" \
  -d '{"organism_code": "sau", "full_test_codes": ["FOX_ND30", "PEN_ND10", "OXA_SCREEN"]}'
```

```json
{"rules": [
  {"RULE_CODE": "MRS", "DESCRIPTION": "Methicillin-resistant Staphylococcus:  MRS = Positive",
   "ORGANISM_CODE": "STA", "ORGANISM_CODE_TYPE": "GENUS_CODE",
   "RULE_CRITERIA": "MECA_PCR=+; MRSA=+; OXA_SCREEN=+; MRSA_SCRN=+; PBP2A_AGGL=+",
   "AFFECTED_ANTIBIOTICS": "AMC, APX, CRB, … (140 codes)", "ANTIBIOTIC_EXCEPTIONS": "CPT, BPR"},
  {"RULE_CODE": "MRS", "DESCRIPTION": "Methicillin-resistant Staphylococcus:  Oxacillin or cefoxitin = Non-susceptible",
   "RULE_CRITERIA": "OXA=NS; FOX=NS", "…": "…"}
]}
```

### `POST /api/intrinsic-rules`

| Field | Type | Default |
|---|---|---|
| `organism_code` | string | — |
| `restrict_guidelines` | bool | `false` |
| `guidelines` | string[] | `null` |

```bash
curl -s -X POST http://localhost:8080/api/intrinsic-rules -H "Content-Type: application/json" \
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

### Reference lists

```bash
curl -s http://localhost:8080/api/guidelines          # ["CLSI","EUCAST","SFM"]
curl -s http://localhost:8080/api/breakpoint-types    # ["Human","Animal","ECOFF"]
curl -s http://localhost:8080/api/sites               # ["Non-meningitis","Non-endocarditis","Parenteral","(Blank)", …31]
curl -s http://localhost:8080/api/organisms           # 2,980 × {"code": "saj", "name": "Abiotrophia adiacens"}
curl -s http://localhost:8080/api/antibiotics         # {"code": "AMP", "name": "Ampicillin", "potencies": ["2µg","10µg"]}, …
```

`/api/antibiotics` returns one entry per row of `Antibiotics.txt`, so a drug listed in
several rows appears several times — de-duplicate by `code` if you build a picker.

---

## Calling the API from Python

```python
import httpx

api = httpx.Client(base_url="http://localhost:8080", timeout=60)

r = api.post("/api/interpret/single", json={
    "organism_code": "kpn", "whonet_abx_code": "AMP", "measurement": "25",
    "guidelines": ["CLSI"], "test_method": "disk", "potency": "10",
    "guideline_year": 2026, "include_comments": True,
})
r.json()      # {'results': [{'whonet_test': 'AMP_ND10', 'interpretation': 'R*'}]}

with open("isolates.txt", "rb") as data, open("src/amrie/resources/SampleConfig.json", "rb") as cfg:
    r = api.post("/api/interpret/file",
                 files={"data_file": data, "config_file": cfg},
                 data={"delimiter": "|", "guideline_year": "2026"})
r.raise_for_status()
open("results.txt", "w").write(r.text)
```

---

## How the web layer configures the engine

| Entry point | Configuration |
|---|---|
| single page, `/api/interpret/single` | built in memory by `make_single_tab_config()`: chosen year; Human breakpoints unless restricted; chosen sites or the default order; **all** expert rules; intrinsic rules on; comments as requested |
| file page, `/api/interpret/file` | the uploaded JSON (`read_configuration`) — the request's `guideline_year` overrides `GuidelineYear` |
| QC page, `/api/qc` | no configuration; bundled `QC_Ranges.txt` |
| breakpoint / rule lookups | the request fields only |

The single page and endpoint strip `*` / `!` unless *Include interpretation comments*
/ `include_comments` is set — the same behaviour as `amrie single`.

---

## Architecture

```text
browser ──► NiceGUI page (web/pages/*)     ─┐
client  ──► FastAPI route (web/api/*)      ─┼─► web/helpers.py ─► amrie (engine)
                                            ┘
```

```text
web/
├── main.py            imports every page/API module, then ui.run() on :8080
├── state.py           read-only lookup lists built once at import (organisms, drugs, sites…)
├── helpers.py         config builders, WHONET code builder, serialisers, interpret_for_display
├── api/               interpret.py · breakpoints.py · rules.py · qc.py · reference.py
├── pages/             single.py (/) · file_mode.py (/file) · qc.py (/qc)
├── components/        header, filters, breakpoint / expert / intrinsic dialogs
└── models/            requests.py, responses.py (Pydantic)
```

- Engine calls run in `asyncio.to_thread`, so a long file does not block other users.
- There is no shared mutable state between requests; every request builds or loads
  its own configuration. The engine's caches key on the full configuration, so one
  user's settings can never leak into another's results.
- Reference data is loaded once at start-up (~1 s) and shared read-only.

---

## Deployment

### Docker

```bash
docker compose up --build             # uses docker-compose.yml
# or
docker build -t amrie-web .
docker run -p 8080:8080 -e STORAGE_SECRET="$(openssl rand -hex 32)" amrie-web
```

The image (`python:3.11-slim`) copies `src/` and `web/`, installs `.[web]` and runs
`python web/main.py` on port 8080. The `amrie` CLI is available inside the container
too ([CLI → Docker](cli-reference.md#docker)).

`docker-compose.yml`:

```yaml
services:
  amrie-web:
    build: .
    ports:
      - "8080:8080"
    environment:
      - STORAGE_SECRET=change-me-in-production
    restart: unless-stopped
```

### Environment

| Variable | Default | Purpose |
|---|---|---|
| `STORAGE_SECRET` | `amrie-dev-secret` | signs NiceGUI session storage — **set a long random value in production** |

### Production checklist

- Put a reverse proxy (nginx, Caddy, Traefik) in front for TLS.
- Set `STORAGE_SECRET`.
- The app has **no authentication**; restrict access at the proxy or network level if
  it handles patient data.
- Uploaded files are written to a temporary directory for the duration of the request
  and deleted afterwards.
- For very large or frequent batch jobs, the CLI or Python API avoids HTTP upload
  overhead.
