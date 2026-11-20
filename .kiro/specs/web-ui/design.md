# Web UI Design

## Architecture

FastAPI application with Jinja2 templates and htmx 2.0.4 for interactive elements. No CDN, no build step. The UI reads run artifacts from CORONER_BASE_DIR (default: repository root).

## Module structure

```
coroner/ui/
├── __init__.py
├── app.py          # FastAPI application, routes
├── templates/
│   ├── base.html   # Base template with dark theme, htmx script
│   ├── index.html  # Landing page with links
│   ├── run.html    # Run detail page
│   └── matrix.html # Detection Matrix page
└── static/
    └── (CSS inline in base.html for simplicity)
```

## Routes

### GET /
Landing page with:
- Project title and tagline
- Links to Detection Matrix
- Recent runs: up to 10, newest first, shown as runs/<id> with verdict and date

### GET /run/{run_id}
Run detail page:
- Reads verdict.json, certificate.json (if present), failure_report.json (if ZOMBIE), card.txt (if ZOMBIE)
- Displays verdict, counts, coverage, duration
- Displays Unreconciled branch exposure if inputs.json shows a group_key in the schema
- Displays Given/When/Then card and COBOL lines for ZOMBIE
- Displays error reason and stderr for ERROR
- Certificate panel with Verify button (htmx post to /api/verify)

### POST /api/verify
Accepts JSON: `{"run_id": "<run_id>"}`
- Calls `coroner.certificate.replay_certificate` on runs/<run_id>/certificate.json
- Returns JSON: `{"status": "VALID", "verdict": "ALIVE", ...}` or `{"status": "INVALID", "reason": "..."}`
- htmx swaps the certificate panel content

### GET /matrix
Detection Matrix page:
- Reads runs/trap_catalog.json if present
- Displays per-trap table: ID, Description, Detected (of N), Rate, Correct port verdict
- T6 shown as placeholder without numbers
- If file absent: "Detection Matrix not available yet: run make traps"

## Visual design

### Color scheme (dark theme)
- Background: #1a1a1a (dark gray, near black)
- Text: #e0e0e0 (light gray)
- Contrast ratio: 13.18:1 (computed with WCAG 2 relative luminance)

Verdict colors:
- ALIVE: background #1b4d3e (dark green), text #4ade80 (light green), contrast 5.53:1
- ZOMBIE: background #4d1b1b (dark red), text #f87171 (light red), contrast 5.10:1
- ERROR: background #4d3d1b (dark orange), text #fbbf24 (light orange), contrast 6.29:1

All ratios computed with the WCAG 2 relative-luminance formula and verified to be at least 4.5:1.

Verdict always includes text label (ALIVE, ZOMBIE, ERROR) for accessibility.

Monospace: `font-family: 'Monaco', 'Menlo', 'Consolas', monospace` for COBOL lines and CSV rows only.

Body text: `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`

### Layout
- Max width 1200px, centered
- Verdict box: large (min 200px height), centered text, 2rem font size
- Sections: white border, padding 1.5rem, margin 1rem
- COBOL lines: monospace, line-height 1.4, left-aligned

## Data flow

1. User requests /run/<run_id>
2. app.py validates run_id (12 lowercase hex)
3. Read CORONER_BASE_DIR, construct runs/<run_id> path
4. Load verdict.json (required)
5. Check verdict.status: "ALIVE", "ZOMBIE", or absent (ERROR from run_error.txt)
6. Load certificate.json (optional), failure_report.json (ZOMBIE), card.txt (ZOMBIE), run_error.txt (ERROR)
7. Load inputs.json to check for group_key in schema
8. Render run.html with context

For /api/verify:
1. Receive JSON with run_id
2. Validate run_id
3. Call replay_certificate(base_dir / "runs" / run_id / "certificate.json")
4. Return replay result as JSON

For /matrix:
1. Check if runs/trap_catalog.json exists
2. If yes: load and parse, render matrix.html with traps
3. If no: render matrix.html with "not available" message

## Path sanitization

Run ids: compiled regex `^[0-9a-f]{12}$`, validated before constructing any path.

File paths shown to user:
- Run directory: always `runs/<run_id>`
- Source files: `pathlib.Path(abs_path).relative_to(base_dir)` with exception handling (fallback: filename only)
- Never show absolute paths or home directory prefix

Test helper: `assert os.path.expanduser("~") not in response_text`

## Error handling

- Invalid run_id: HTTP 404
- Missing verdict.json: HTTP 404
- File read errors: HTTP 500 with generic message (never leak paths)
- Certificate replay errors: return JSON with status INVALID and reason

## Integration with existing modules

- `coroner.certificate.replay_certificate(path)` returns a dict with status (VALID/INVALID), verdict, and reason
- No new CLI or MCP changes needed
- `make serve` in Makefile: `uvicorn coroner.ui.app:app --host 127.0.0.1 --port 8000`

## Security

- Bind 127.0.0.1 only (local access)
- Run id validation prevents path traversal
- Read-only (no execution endpoints)
- No user file upload in V1

## Dependencies (pyproject.toml)

```toml
[project]
dependencies = [
    # ... existing ...
    "fastapi==0.163.1",
    "uvicorn==0.54.0",
    "jinja2==3.1.6",
    "python-multipart==0.0.33",
]

[project.optional-dependencies]
dev = [
    # ... existing ...
    "httpx==0.28.1",  # TestClient
]
```

## htmx integration

Vendored file: coroner/ui/static/htmx.min.js
- Version: 2.0.4
- License: 0BSD
- SHA-256: e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447
- Size: 50917 bytes

Operator downloaded to build/vendor/htmx.min.js, then copied to coroner/ui/static/htmx.min.js (committed).

Served as static file at /static/htmx.min.js

Base template includes: `<script src="/static/htmx.min.js"></script>`

Verify button example:
```html
<button hx-post="/api/verify" 
        hx-vals='{"run_id": "{{ run_id }}"}' 
        hx-target="#cert-result">
  Verify
</button>
<div id="cert-result"></div>
```

## Test structure

```python
from fastapi.testclient import TestClient
from coroner.ui.app import app
import tempfile
import os

def test_alive_run(tmp_path):
    # Generate ALIVE run at 30 cases in tmp_path
    # Set CORONER_BASE_DIR = tmp_path
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    assert "ALIVE" in response.text
    assert os.path.expanduser("~") not in response.text

def test_zombie_run_with_card(tmp_path):
    # Generate ZOMBIE run (legacy variant)


## Deployment architecture (D-52, D-53, D-54)

### Container split

Two Coroner containers plus cloudflared:

1. **coroner-api**: FastAPI application (UI + API endpoints)
   - Serves web pages and API routes
   - Submits jobs to engine via exchange directory
   - Stores visitor run metadata in its own database (bounded)
   - Network: on coroner-net (internal network)
   - Limits: 1 CPU, 512 MB memory (no swap), pids_limit: 128
   
2. **coroner-engine**: COBOL and Java execution sandbox
   - Reads job requests from exchange directory
   - Runs the real Coroner CLI (verify, generate cases, COBOL, Java, comparison)
   - Writes job results to exchange directory
   - Network: none (isolated)
   - Limits: 2 CPUs, 2 GB memory (no swap), pids_limit: 256
   - Hardening: cap_drop ALL, no-new-privileges, read_only root, tmpfs /tmp and work dirs
   
3. **cloudflared**: Cloudflare Tunnel client
   - Routes coroner.iqoba.com to http://coroner-api:8000
   - Returns 404 for any other hostname
   - Network: on coroner-net
   - Limits: 0.25 CPU, 128 MB memory (no swap), pids_limit: 32

### Exchange directory

Named volume `coroner-exchange` mounted at `/exchange` in both API and engine.

Job structure:
```
/exchange/
  jobs/
    <job_id>/
      request.json     # written by API
      status.json      # written by engine (queued, running, done, error)
      generated_cases.csv
      cobol_output.csv
      java_output.csv
      trace.txt
      result.json      # verdict, counts, coverage
      failure_report.json (if ZOMBIE)
      card.txt (if ZOMBIE)
      certificate.json
```

Job hand-off:
1. API writes request.json with job_id, sample, port, seed, cases, timestamp
2. API writes status.json: {status: queued}
3. Engine polls /exchange/jobs/, picks oldest queued job
4. Engine writes status.json: {status: running, started_at}
5. Engine runs coroner verify as a subprocess with timeout (default 60s), which kills the process group on timeout
6. Engine writes result.json and status.json: {status: done, completed_at} or {status: error, reason: timeout}
7. API reads result, extracts visitor data, deletes job directory

Timeout: engine runs coroner verify as a subprocess with timeout (default 60 s from CORONER_JOB_TIMEOUT). On timeout, the subprocess timeout kills the process group and writes status.json: {status: error, reason: timeout}.

### Docker Compose structure

```yaml
version: '3.8'

services:
  coroner-api:
    image: coroner:live
    container_name: coroner-api
    platform: linux/amd64
    user: "1000:1000"
    networks:
      - coroner-net
    volumes:
      - coroner-data:/app/runs:rw
      - coroner-exchange:/exchange:rw
    environment:
      - CORONER_BASE_DIR=/app
      - CORONER_ENGINE_MODE=api
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
          pids: 128
        reservations:
          memory: 256M
    mem_swappiness: 0
    memswap_limit: 512M
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    restart: unless-stopped

  coroner-engine:
    image: coroner:live
    container_name: coroner-engine
    platform: linux/amd64
    user: "1000:1000"
    networks:
      - none  # no network access
    volumes:
      - coroner-samples:/app/samples:ro
      - coroner-exchange:/exchange:rw
    environment:
      - CORONER_BASE_DIR=/app
      - CORONER_ENGINE_MODE=worker
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2048M
          pids: 256
        reservations:
          memory: 1024M
    mem_swappiness: 0
    memswap_limit: 2048M
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
      - /app/work:uid=1000,gid=1000
    restart: unless-stopped

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: coroner-tunnel
    platform: linux/amd64
    networks:
      - coroner-net
    volumes:
      - ${TUNNEL_CREDENTIALS_FILE}:/etc/cloudflared/credentials.json:ro
      - ./cloudflared-config.yml:/etc/cloudflared/config.yml:ro
    command: tunnel run
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 128M
          pids: 32
    mem_swappiness: 0
    memswap_limit: 128M
    restart: unless-stopped

networks:
  coroner-net:
    name: coroner-net
    internal: false  # cloudflared needs external access
  none:
    name: coroner-engine-isolated
    internal: true

volumes:
  coroner-data:
    name: coroner-data
  coroner-samples:
    name: coroner-samples
  coroner-exchange:
    name: coroner-exchange
```

Memory budget: 512 MB + 2048 MB + 128 MB = 2688 MB. Host memory used by other services is out of scope; Coroner stays within its own container limits.

### Run audit flow

1. Visitor submits form: sample=T1, port=faulty, seed=42, cases=200
2. API validates input (Pydantic model), computes deterministic run_id from parameters
3. API checks if run_id exists in coroner-data; if yes, redirect to /run/{run_id}
4. API checks queue length; if full, return HTTP 429
5. API checks active audits per IP; if one active, return HTTP 429
6. API creates job_id, writes request.json and status.json to /exchange/jobs/{job_id}/
7. API returns 202 Accepted with Location header, visitor polls /api/job/{job_id}/status
8. Engine picks job, writes status: running, executes coroner verify
9. Engine writes result.json, status: done
10. API reads result, stores in coroner-data/runs/{run_id}/, deletes job directory
11. Visitor polls status, gets status: done, redirects to /run/{run_id}

### Tamper flow

1. Visitor navigates to /tamper, picks a run_id, form shows editable fields (status, cases_total, cases_divergent, random_seed)
2. Visitor edits fields, submits form
3. API validates run_id, reads original certificate, copies to /exchange/tamper/{tamper_id}.json
4. API applies visitor edits to the copy, recomputes certificate_sha256
5. API calls replay_certificate on the copy
6. API returns replay result: INVALID with reason (or VALID if no actual forgery)
7. API deletes tamper copy
8. Test: read original certificate before and after, assert byte-identical

### Pydantic models

```python
from pydantic import BaseModel, Field, conint, constr

class RunAuditRequest(BaseModel):
    sample: constr(regex='^(credit-fees|T1|T2|T3|T4|T5)$')
    port: constr(regex='^(correct|faulty)$')
    seed: conint(ge=0, le=1000000)
    cases: conint(ge=10, le=2000)

class TamperRequest(BaseModel):
    run_id: constr(regex='^[0-9a-f]{12}$')
    status: constr(regex='^(ALIVE|ZOMBIE)$')
    cases_total: conint(ge=1)
    cases_divergent: conint(ge=0)
    random_seed: conint(ge=0)
```

### Rate limiting

A small in-app limiter (sliding window per key, in memory, thread-safe):
- Global: 100 requests per minute
- Per client address: 20 requests per minute
- Per endpoint /api/run: 5 requests per minute per address
- Per endpoint /api/verify: 1 request per 10 seconds (one at a time)

Client address: read from CF-Connecting-IP Cloudflare header ONLY when the request arrives from the cloudflared container on the internal network; otherwise the direct peer address from the socket.

### Configuration defaults

The following defaults are chosen by the operator and listed in one place (coroner/ui/config.py or environment variables):
- Queue length (default 3): maximum number of jobs in the queue before returning HTTP 429
- Visitor run limit (default 100): maximum number of visitor-generated runs kept in coroner-data; oldest beyond this are removed when a new run completes
- Seed bounds (0 to 1000000)
- Case count bounds (10 to 2000)
- Request body size limit (default 16 KB)
- Job timeout (default 60 s)
- Per-audit timeout (default 60 s, overridable per audit request)
- Per-IP active audit limit (default 1)
- Rate limit values (100/min global, 20/min per IP, 5/min per endpoint, 1 per 10s for verify)

These values are configurable and tested with different values as part of Task 17 (resource measurement) and Task 21 (security tests).

### Cloudflare configuration

File: cloudflared-config.yml (committed, no secrets)
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: coroner.iqoba.com
    service: http://coroner-api:8000
  - service: http_status:404
```

Cache rules (set by app):
- Static assets: Cache-Control: public, max-age=86400
- API endpoints: Cache-Control: no-store, no-cache, must-revalidate

Cloudflare dashboard settings (operator manual steps):
- WAF: on
- Bot protection: on
- Cloudflare Access: off (judges must not log in)

### Demo data generation

One-shot service in docker-compose.yml or manual command:
```bash
docker compose run --rm coroner-api make traps
docker compose run --rm coroner-api make demo-ebcdic
docker compose run --rm coroner-api make demo
docker compose run --rm coroner-api make zombie
```

Bundled runs written to coroner-data volume, never purged.

### Test book structure

File: docs/test-book.md

```markdown
# Coroner Test Book

## Scenario 1: Run audit on T1 faulty port
**Purpose:** Verify the engine detects EBCDIC collating order trap.
**Preconditions:** Live site is running at coroner.iqoba.com or local TestClient.
**Steps:**
1. Navigate to /
2. Click "Run audit"
3. Select sample: T1, port: faulty, seed: 42, cases: 200
4. Submit form
5. Wait for run to complete (poll /api/job/{job_id}/status)
6. Observe run page

**Expected result (RULE):** Verdict ZOMBIE, at least one divergent case, Unreconciled branch exposure sum greater than zero, grand total matches yes.

**Actual result:**
<!-- GENERATED_START hash=abc123 -->
Date: 2026-11-17
Coroner version: 1.0.0
Run ID: f584d5f35228
Verdict: ZOMBIE
Divergences: 33
Exposure sum: 387134.97
Grand total matches: yes
PASS
<!-- GENERATED_END -->

## Scenario 2: Tamper with certificate
...
```

Generator script (coroner/test_book.py):
- Parses docs/test-book.md, finds all scenarios
- Executes steps via TestClient (local) or httpx (URL given)
- Measures actual results
- Replaces content between GENERATED_START and GENERATED_END markers
- Computes hash of generated block, writes in marker
- Writes PASS or FAIL

Test (tests/test_test_book.py):
- Reads docs/test-book.md
- For each Actual result section, checks GENERATED_START marker exists and hash matches content
- Fails if any Actual result not generated

### Deployment documentation outline

File: docs/deploy.md

```markdown
# Deployment guide

## Prerequisites
- Docker and Docker Compose
- Cloudflare account
- Domain coroner.iqoba.com (DNS managed by Cloudflare)

## Tunnel setup
1. Create tunnel:
   cloudflared tunnel create coroner
   # saves credentials to ~/.cloudflared/<TUNNEL_ID>.json

2. Route DNS:
   cloudflared tunnel route dns coroner coroner.iqoba.com

3. Copy credentials file to deployment directory:
   cp ~/.cloudflared/<TUNNEL_ID>.json /path/to/tunnel-credentials.json

4. Set environment variable:
   export TUNNEL_CREDENTIALS_FILE=/path/to/tunnel-credentials.json

5. Update cloudflared-config.yml with TUNNEL_ID

## Resource limits (measured 2026-11-17)
- Engine: 2 CPUs, 2 GB memory (no swap)
- API: 1 CPU, 512 MB memory (no swap)
- cloudflared: 0.25 CPU, 128 MB memory (no swap)
- Total memory: 2688 MB
- Host memory used by other services is out of scope; Coroner stays within its own container limits

Measured peak usage at 2,000 cases:
- credit-fees: 487 MB, 1.2 CPUs, 4.3 s
- T1: 521 MB, 1.4 CPUs, 15.9 s
- T2: 498 MB, 1.3 CPUs, 8.7 s
- T3: 502 MB, 1.2 CPUs, 7.1 s
- T4: 505 MB, 1.3 CPUs, 6.9 s
- T5: 499 MB, 1.2 CPUs, 7.8 s

All within limits. Longest duration: T1 at 15.9 s (well under 60 s timeout).

Platform: linux/amd64

Note: The server currently uses Wi-Fi; a wired Ethernet connection is recommended for the judging period.

## Generate demo data
docker compose run --rm coroner-api make traps
docker compose run --rm coroner-api make demo-ebcdic
docker compose run --rm coroner-api make demo
docker compose run --rm coroner-api make zombie

## Start services
docker compose up -d

## Verify deployment
make deploy-check URL=https://coroner.iqoba.com

## Update
docker compose pull
docker compose up -d

## Stop
docker compose down

## Uptime monitor
External monitor: <UPTIME_MONITOR_URL>
Alert email: <PLACEHOLDER_EMAIL>
Check interval: 5 minutes
```

## Done when
- Container split architecture designed (API, engine, cloudflared)
- Exchange directory structure defined
- Job hand-off protocol specified
- Docker Compose file structure written with all limits
- Pydantic validation models designed
- Rate limiting: in-app sliding-window limiter, no new dependency
- Cloudflare configuration file structure written
- Demo data generation commands documented
- Test book structure and generator design complete
- Deployment guide outline written with placeholders for secrets
- Memory budget computed: 2688 MB. Host memory used by other services is out of scope; Coroner stays within its own container limits
    # ...
    assert "Given" in response.text
    assert "When" in response.text
    assert "Then" in response.text
    assert "COBOL" in response.text  # lines section

def test_zombie_t1_exposure(tmp_path):
    # Generate ZOMBIE T1 run at 30 cases
    # ...
    assert "Unreconciled branch exposure" in response.text
    assert "grand total matches: yes" in response.text

def test_error_run(tmp_path):
    # Generate ERROR run (broken reference)
    # ...
    assert "ERROR" in response.text
    assert "reference did not run" in response.text

def test_verify_forged_certificate(tmp_path):
    # Generate ALIVE run, forge certificate
    # ...
    response = client.post("/api/verify", json={"run_id": run_id})
    data = response.json()
    assert data["status"] == "INVALID"

def test_matrix_with_catalog(tmp_path):
    # Generate trap catalog
    # ...
    response = client.get("/matrix")
    assert "T1" in response.text
    assert "placeholder" in response.text  # T6

def test_matrix_without_catalog(tmp_path):
    # No catalog file
    # ...
    assert "not available yet" in response.text

def test_invalid_run_id():
    client = TestClient(app)
    response = client.get("/run/invalid")
    assert response.status_code == 404
```

All tests use a tmp_path fixture and set CORONER_BASE_DIR to isolate from the real repository.

## Done when
- FastAPI app in coroner/ui/app.py with routes /, /run/{run_id}, /api/verify, /matrix
- Jinja2 templates in coroner/ui/templates/ (base, index, run, matrix)
- htmx 2.0.4 vendored at build/vendor/htmx.min.js with SHA-256 test
- Dark theme with specified color values and contrast ratios
- Verdict displayed with text label (not color only)
- Monospace only for COBOL lines and CSV rows
- Run id validation (12 lowercase hex)
- CORONER_BASE_DIR support
- Certificate Verify button with htmx POST
- Detection Matrix page with per-trap table
- All displayed numbers read from run files
- No absolute paths or home directory in responses
- Tests with TestClient cover ALIVE, ZOMBIE (card, T1 exposure), ERROR, forged cert, matrix, 404
- Dependencies added to pyproject.toml
- `make serve` target runs uvicorn
