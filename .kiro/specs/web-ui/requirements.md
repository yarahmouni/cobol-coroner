# Web UI Requirements

## Overview

A dark, modern, readable web interface for viewing Coroner differential verification results and the trap catalog Detection Matrix.

## Requirements (EARS format)

### Req 1: Technology stack
**WHILE** serving the web UI, the system **SHALL** use FastAPI with uvicorn, Jinja2 templates and htmx 2.0.4 for interactivity.

**WHERE** htmx is required, the system **SHALL** vendor htmx.min.js 2.0.4 as a static file (SHA-256 e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447, 0BSD license) at build/vendor/htmx.min.js with no CDN dependency and no build step.

### Req 2: Server binding
**WHERE** the UI server is started, the system **SHALL** bind to 127.0.0.1 only (local access only).

**WHERE** `make serve` is invoked, the system **SHALL** start the FastAPI server with uvicorn.

### Req 3: Data directory
**WHERE** the UI needs the data directory, the system **SHALL** read CORONER_BASE_DIR (default: repository root), consistent with the MCP server.

### Req 4: Run page structure
**WHERE** a run page is requested for a valid run_id, the system **SHALL** display:
- Large central verdict (ALIVE, ZOMBIE, or ERROR with the verdict message or error reason)
- Cases count
- Divergences count
- Paragraph coverage (X/Y format)
- Branch coverage (Coroner definition) (X/Y format)
- Duration
- "Validated under GnuCOBOL 3.x"

**WHERE** the run's schema declares a group key, the system **SHALL** also display the Unreconciled branch exposure line: sum, max, branches affected, and grand total matches status.

**WHERE** the verdict is ZOMBIE, the system **SHALL** display:
- The Given/When/Then card from card.txt
- The COBOL lines involved (from failure_report.json)
- The divergent field with COBOL and Java values

**WHERE** the verdict is ERROR, the system **SHALL** display the error reason and reference stderr.

### Req 5: Certificate panel
**WHERE** a run page has a certificate, the system **SHALL** display a Certificate panel with:
- Certificate fields: run_id, status, cases, divergences, coverage
- A Verify button

**WHERE** the Verify button is clicked, the system **SHALL** replay the certificate via an htmx POST request and display the replay result: VALID or INVALID with the replay reason.

### Req 6: Detection Matrix page
**WHERE** the Detection Matrix page is requested, **IF** runs/trap_catalog.json exists, the system **SHALL** display a table with columns: Trap ID, Description, Detected (of N), Rate, Correct port verdict.

**WHERE** the Detection Matrix page is requested, **IF** runs/trap_catalog.json does not exist, the system **SHALL** display "Detection Matrix not available yet: run make traps".

**WHERE** trap T6 is displayed, the system **SHALL** show it as a placeholder without numbers.

### Req 7: Measured values only
**WHERE** any page displays a number or metric, the system **SHALL** read that value from the run files (verdict.json, failure_report.json, card.txt, certificate.json, trap_catalog.json) or from a certificate replay.

**WHERE** any page displays a file path, the system **SHALL** show repository-relative paths for sources and runs/<run_id> for run directories, never absolute paths or home directory prefixes.

### Req 8: Visual design
**WHERE** the UI is rendered, the system **SHALL** use a dark, modern, readable design with:
- Dark background
- High contrast text (at least 4.5:1 ratio)
- No terminal-emulator aesthetics (no monospace walls, no green-on-black, no blinking cursor)
- Monospace font only for COBOL lines and CSV rows

**WHERE** the verdict is displayed, the system **SHALL** use:
- ALIVE: green background or border with text label "ALIVE"
- ZOMBIE: red background or border with text label "ZOMBIE"
- ERROR: orange or yellow background or border with text label "ERROR"
- Verdict not conveyed by color only (text label always present for accessibility)

### Req 9: Input validation
**WHERE** a run_id is received in a URL, the system **SHALL** validate it as exactly 12 lowercase hexadecimal characters before any file access.

**WHERE** an invalid run_id is received, the system **SHALL** return HTTP 404.

### Req 10: Read-only mode
**WHERE** the UI is running in V1, the system **SHALL** provide no endpoint that starts a COBOL or Java run (read-only except certificate replay).

### Req 11: Dependencies
**WHERE** the system is installed, pyproject.toml **SHALL** declare:
- fastapi (tested with 0.163.1)
- uvicorn (tested with 0.54.0)
- jinja2 (tested with 3.1.6)
- python-multipart (tested with 0.0.33)
- httpx (tested with 0.28.1) as a dev dependency for tests

### Req 12: Tests
**WHERE** the UI is tested, the system **SHALL** include tests with FastAPI TestClient that:
- Request an ALIVE run page (credit-fees correct)
- Request a ZOMBIE run page (credit-fees legacy variant) and assert the card and COBOL lines are present
- Request a ZOMBIE run page (T1 faulty) and assert the Unreconciled branch exposure line with "grand total matches: yes"
- Request an ERROR run page (broken reference) and assert the error reason
- POST to the Verify endpoint with a forged certificate and assert INVALID with a reason
- Request the Detection Matrix page with and without a catalog file
- Request a page with an invalid run_id and assert 404
- Assert no response contains the home directory prefix

All tests use real runs produced by the engine at small case counts in a tmp base directory.

### Req 13: Docker Compose for live demo (D-52, D-54)
**WHERE** the live demo is deployed, the system **SHALL** use docker-compose.yml with three services:
- coroner-api: FastAPI application serving the UI and API on port 8000 inside the container network (no host port published)
- coroner-engine: runs COBOL and Java with network none, non-root user, cap_drop ALL, no-new-privileges, read-only root filesystem, tmpfs work directories
- cloudflared: Cloudflare Tunnel client connecting coroner.iqoba.com to coroner-api

**WHERE** the Compose file is written, all three services **SHALL** run on a named network internal to this project with named volumes.

**WHERE** the API and engine services are defined, they **SHALL** have strict limits: cpus (decimal), memory and memswap (equal, no swap), pids_limit, user (existing image user 1000:1000), platform linux/amd64.

**WHERE** the cloudflared service is configured, the system **SHALL** mount a credentials file from outside the repository (path in .env, never committed) read-only, and configure ingress to route coroner.iqoba.com to http://coroner-api:8000 with 404 for anything else.

**WHERE** limits are set, the system **SHALL** use defaults: coroner-engine at most 2 CPUs and 2 GB memory (no swap), coroner-api at most 1 CPU and 512 MB (no swap), cloudflared 0.25 CPU and 128 MB (no swap), all with pids_limit.

### Req 14: Container hardening (D-54)
**WHERE** the engine container runs a job, the system **SHALL** enforce:
- Network none (no network access)
- Non-root user 1000:1000
- security_opt: no-new-privileges:true
- cap_drop: ALL
- Read-only root filesystem with tmpfs for /tmp and work directories
- CPU, memory and PID limits per Req 13

**WHERE** the API and engine containers communicate, the system **SHALL** use a dedicated exchange directory on a named volume with:
- Job hand-off through files (job request JSON, result JSON, generated cases CSV, outputs, trace)
- A separate directory per audit, purged after the visitor data is extracted
- No writable volume shared except the exchange directory

**WHERE** a job is submitted, the system **SHALL** enforce a per-job timeout of 60 seconds and a global limit of one audit at a time with a bounded queue (reject with HTTP 429 when full).

### Req 15: Interactive live demo (D-53)
**WHERE** the live demo is accessed at coroner.iqoba.com, the system **SHALL** provide:
- Run audit form: visitor selects sample (credit-fees, T1, T2, T3, T4, T5), port (correct or faulty), seed (integer in bounded range), case count (bounded, at most 2000)
- The real engine runs the selected sample in the sandbox
- Visitor is redirected to the real run page with verdict, exposure, card, COBOL lines, JUnit download, certificate
- Identical parameters give the same run_id (deterministic) and reuse the existing run

**WHERE** a visitor uses the Tamper feature, the system **SHALL**:
- Display a form to edit a copy of a certificate (uses only keys that exist in a real certificate: open runs/<id>/certificate.json to list them; for example status in the verdict part, cases_total, cases_divergent; the editable fields are an explicit allow-list of real keys)
- Replay the edited copy server-side
- Display INVALID with the replay reason
- Never modify the original certificate

**WHERE** the visitor triggers an audit, the system **SHALL** enforce sandbox controls:
- A separate directory per audit, purged after extraction
- Disk quota on the data volume: remove oldest visitor runs beyond a bounded number (bundled reference runs kept)
- At most 2,000 cases
- Global 60 second timeout
- One audit at a time with a queue
- One active audit per IP (client address from CF-Connecting-IP Cloudflare header ONLY when the request arrives from the cloudflared container on the internal network; otherwise the direct peer address from the socket)
- Reject with HTTP 429 when queue is full

### Req 16: Input validation and rate limits (D-54)
**WHERE** any API endpoint receives input, the system **SHALL** validate with Pydantic:
- Unknown fields rejected
- Bounds on seed (integer 0 to 1000000), case count (integer 10 to 2000), sample id (one of: credit-fees, T1, T2, T3, T4, T5)
- Maximum request body size (for example 16 KB)
- No user-controlled file path, no shell command built from input, no user code

**WHERE** rate limits are enforced, the system **SHALL** apply a small in-app limiter (sliding window per key, in memory, thread-safe):
- Global rate limit
- Per-client address rate limit
- Per-endpoint rate limit
- Return HTTP 429 with Retry-After header

**WHERE** the Verify endpoint is called, the system **SHALL**:
- Read only server-side certificates by validated run_id
- Limit to one replay at a time (second concurrent request gets HTTP 429 with clear message)
- Per-replay timeout

**WHERE** the Tamper endpoint is called, the system **SHALL**:
- Work server-side on a logged copy
- Never modify the original certificate
- Enforce strict certificate schema and size limit
- Use only safe YAML loading (yaml.safe_load), never pickle

### Req 17: Cloudflare and security (D-54)
**WHERE** the application serves responses, the system **SHALL** set Cache-Control headers:
- Static assets (htmx.min.js, CSS): cacheable
- Audit endpoints (/api/run, /api/verify, /api/tamper): Cache-Control: no-store, no-cache

**WHERE** Cloudflare is configured, the operator **SHALL** enable WAF and bot protection with no Cloudflare Access (judges must not log in).

**WHERE** the tunnel credentials are stored, the system **SHALL** never commit any tunnel token or credential in the repository (.env in .gitignore, CI test fails if a file matching the credentials pattern is tracked).

### Req 18: Resource limits measured (D-54, owner capacity decision)
**WHERE** the deployment is prepared, a task **SHALL** measure the peak memory and CPU of the heaviest allowed audit (2,000 cases, each sample credit-fees, T1, T2, T3, T4, T5) inside the engine container under the limits (2 CPUs, 2 GB memory, no swap) using docker stats sampling or cgroup v2 files (memory.peak and cpu.stat; Docker Desktop and Ubuntu 24.04 use cgroup v2); record which method was used.

**WHERE** the measurements are complete, docs/deploy.md **SHALL** record:
- Engine limits: 2 CPUs, 2 GB memory (memswap equal, no swap)
- API limits: 1 CPU, 512 MB memory (no swap)
- cloudflared limits: 0.25 CPU, 128 MB memory (no swap)
- Sum of all Coroner memory limits
- Host memory used by other services is out of scope; Coroner stays within its own container limits
- Measured peak memory and CPU per sample at 2,000 cases
- Which measurement method was used (docker stats or cgroup files)
- Platform: linux/amd64
- Note: "The server currently uses Wi-Fi; a wired Ethernet connection is recommended for the judging period."

**WHERE** any allowed audit is measured, the system **SHALL** complete in under 60 seconds and fit within the engine limits, or the deployment is not ready.

### Req 19: Test book and automated checks (D-53, owner test book)
**WHERE** docs/test-book.md is written, the system **SHALL** list numbered scenarios a judge can execute step by step on the live site and locally:
- Run audit on each bundled sample (credit-fees, T1 to T5) with faulty and correct port
- Verify on a real certificate
- Tamper (edit copy, replay, INVALID with reason)
- Detection Matrix page
- ERROR page (broken reference per D-51)
- D-54 controls a visitor can observe: unknown field rejected, out-of-bound case count rejected, second concurrent audit from same address rejected, HTTP 429 with Retry-After

**WHERE** each scenario is documented, it **SHALL** include:
- Purpose
- Preconditions
- Steps (numbered, executable)
- Expected result as a RULE (for example "verdict ZOMBIE, at least one divergent case, grand total matches yes"), never a typed number
- Actual result field (initially empty)

**WHERE** `make test-book` is run, the system **SHALL**:
- Replay every scenario against real runs locally (engine and UI with TestClient)
- Write measured values (verdict, counts, exposure, certificate status, HTTP status codes) into Actual result fields
- Write PASS or FAIL per scenario with date and Coroner version
- Exit 1 if any scenario fails

**WHERE** `make test-book URL=https://coroner.iqoba.com` is run, the system **SHALL** replay scenarios against the given URL and write the same measured results.

**WHERE** docs/test-book.md is committed, every Actual result field **SHALL** have been produced by the generator (marker and hash of the generated block checked by a test), never edited by hand.

**WHERE** `make deploy-check URL=...` is run, the system **SHALL** run the automated end-to-end check subset:
- Before checking the URL, build the image from a real `git clone` of the commit being deployed (no working-tree files) and fail if it does not build; same rule as make smoke-ui (owner, 2026-11-18)
- Run audit on T1 faulty gives ZOMBIE
- Run audit on T1 correct gives ALIVE
- Tamper gives INVALID with reason
- Exit 1 if any check fails

### Req 20: Deployment documentation (D-52, D-54)
**WHERE** docs/deploy.md is written, the system **SHALL** document:
- Prerequisites (Docker, Cloudflare account, coroner.iqoba.com domain)
- Tunnel creation commands with placeholders for secrets (cloudflared tunnel create, cloudflared tunnel route dns)
- Container limits and measured resource usage per Req 18
- How to generate demo data inside the container (make traps, make demo-ebcdic, make demo, make zombie)
- How to update the deployment
- How to stop the services
- External uptime monitor setup with placeholders (no email address or account identifier)

**WHERE** README.md is updated, the system **SHALL** add a Live demo line:
- Link: https://coroner.iqoba.com
- Link to docs/deploy.md

### Req 21: Tests for security controls (D-54)
**WHERE** the security controls are tested, the system **SHALL** include tests that:
- Unknown field in request JSON is rejected
- Seed below 0 or above 1000000 is rejected
- Case count below 10 or above 2000 is rejected
- Sample id not in the list is rejected
- Request body over size limit is rejected
- HTTP 429 with Retry-After header returned when rate limit exceeded
- Second audit from same IP while one is active is rejected with HTTP 429
- Queue full returns HTTP 429
- Job timeout is configurable (default 60 s); the timeout test runs a REAL audit with a short configured timeout (for example 1 s with 2000 cases, which takes longer than 1 s) and asserts the job ends with status error and reason timeout
- Tamper never modifies the original certificate (read original before and after, assert equal)
- Certificate over size limit is rejected
- Audit responses have Cache-Control: no-store
- Static asset responses are cacheable
- Engine container definition has network: none, user: "1000:1000", cap_drop: [ALL], security_opt: [no-new-privileges:true], read_only: true

## Done when
- EARS requirements cover the technology stack, run page, Detection Matrix page, visual design, validation and tests.
- Only measured values: every displayed number is read from run files or replay, never typed in templates.
- The dark design is accessible (text label for verdict, contrast ratio specified).
- CORONER_BASE_DIR used for data directory.
- D-53 interactive live demo requirements: Run audit, Tamper, sandbox controls, test book scenarios.
- D-54 security requirements: engine/API split, container hardening, input validation, rate limits, Cloudflare setup, no credentials in repository.
- Req 18 measurement requirement: peak memory and CPU recorded for each sample at 2,000 cases.
- Req 19 test book: scenarios, make test-book, make deploy-check; deploy-check builds image from clean git clone (owner 2026-11-18).
- Req 20 deployment docs: tunnel setup, limits, demo data generation, uptime monitor.
- Req 21 security control tests.
