# Web UI Tasks

## Task 1: Dependencies and htmx vendor file
- [x] Add fastapi==0.163.1, uvicorn==0.54.0, jinja2==3.1.6, python-multipart==0.0.33 to pyproject.toml dependencies
- [x] Add httpx==0.28.1 to dev dependencies
- [x] Operator downloaded htmx.min.js 2.0.4 to build/vendor/htmx.min.js (50917 bytes, SHA-256 e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447)
- [x] Copy build/vendor/htmx.min.js to coroner/ui/static/htmx.min.js with cp
- [x] Add a test that reads coroner/ui/static/htmx.min.js and computes its SHA-256 hash (assert equals the expected hash)

**Requirements:** 1, 11
**Done when:** Dependencies in pyproject.toml with exact versions, htmx file at coroner/ui/static/htmx.min.js with correct hash, hash test passes.

## Task 2: FastAPI app skeleton and base template
- [x] Create coroner/ui/__init__.py
- [x] Create coroner/ui/app.py with FastAPI app, CORONER_BASE_DIR logic, run_id validation regex
- [x] Create coroner/ui/templates/base.html with dark theme CSS (colors: background #1a1a1a, text #e0e0e0, ALIVE bg #1b4d3e text #4ade80, ZOMBIE bg #4d1b1b text #f87171, ERROR bg #4d3d1b text #fbbf24), htmx script tag
- [x] Serve coroner/ui/static/htmx.min.js as /static/htmx.min.js
- [x] Add a test that reads the colors from the CSS and computes every contrast ratio with the WCAG 2 relative-luminance formula, asserting each is at least 4.5:1
- [x] `make serve` target: `uvicorn coroner.ui.app:app --host 127.0.0.1 --port 8000`

**Requirements:** 1, 2, 3, 8, 9
**Done when:** FastAPI app runs on 127.0.0.1, base template has dark theme with specified colors, htmx loads, run_id validation in place, contrast ratios computed and verified.

## Task 3: Index page
- [x] Create coroner/ui/templates/index.html extending base.html
- [x] GET / route: render index with project title, tagline, link to Detection Matrix
- [x] List recent runs: up to 10, newest first, shown as runs/<id> with verdict and date

**Requirements:** 4 (structure)
**Done when:** Index page renders with title, tagline, links, and recent runs list; accessible at http://127.0.0.1:8000/.

## Task 4: Run page for ALIVE verdict
- [x] Create coroner/ui/templates/run.html extending base.html
- [x] GET /run/{run_id} route: validate run_id, read verdict.json, inputs.json, certificate.json (optional)
- [x] Display: verdict (large, green, text label "ALIVE"), cases, divergences, paragraph coverage, branch coverage, duration, "Validated under GnuCOBOL 3.x"
- [x] Certificate panel: display certificate fields, Verify button (htmx post, target cert-result div)
- [x] Test: ALIVE credit-fees run at 30 cases, assert no home directory in response

**Requirements:** 4, 5, 7, 8, 9, 12
**Done when:** ALIVE run page renders with all required fields, certificate panel with Verify button, test passes.

## Task 5: Run page for ZOMBIE verdict
- [x] Extend GET /run/{run_id}: read failure_report.json, card.txt for ZOMBIE
- [x] Display: verdict (large, red, text label "ZOMBIE"), card (Given/When/Then), COBOL lines from failure_report, divergent field with values
- [x] Read inputs.json schema for group_key; if present, display Unreconciled branch exposure (sum, max, branches affected, grand total matches)
- [x] timing.json written by the CLI, not hashed in the certificate
- [x] Tests: ZOMBIE credit-fees legacy variant (assert card, COBOL lines), ZOMBIE T1 faulty (assert exposure line with "grand total matches: yes")

## Task 6: Run page for ERROR verdict
- [x] Extend GET /run/{run_id}: when verdict.json absent, read run_error.txt
- [x] Display: verdict (large, orange, text label "ERROR"), error reason, reference stderr
- [x] Test: ERROR run (broken reference per D-51: the run directory contains inputs.json, generated_cases.csv, run_error.txt; no verdict.json, no certificate.json), assert error reason displayed

**Requirements:** 4, 7, 8, 12
**Done when:** ERROR run page renders with error reason and stderr, test produces a real broken-reference run and passes.

## Task 7: Certificate verification endpoint
- [x] POST /api/verify route: receive JSON with run_id, validate, call coroner.certificate.replay_certificate
- [x] Return JSON: status (VALID/INVALID), verdict (if valid), reason (if invalid)
- [x] htmx response updates cert-result div with replay result
- [x] Test: forge a certificate (edit status, recompute hash), POST verify, assert INVALID with reason

**Requirements:** 5, 12
**Done when:** Verify endpoint returns correct JSON, htmx updates panel, forgery test passes.

## Task 8: Detection Matrix page
- [x] Create coroner/ui/templates/matrix.html extending base.html
- [x] GET /matrix route: check if runs/trap_catalog.json exists
- [x] If exists: load, display table with columns Trap ID, Description, Detected (of N), Rate, Correct port verdict
- [x] T6: show as placeholder without numbers
- [x] If absent: display "Detection Matrix not available yet: run make traps"
- [x] Tests: with catalog (assert T1, T6 placeholder), without catalog (assert "not available yet")

**Requirements:** 6, 7, 12
**Done when:** Matrix page renders with trap table or fallback message, both tests pass.

## Task 9: Path sanitization and 404 handling
- [x] All file paths shown: repository-relative for sources, runs/<run_id> for run directories
- [x] Invalid run_id: HTTP 404
- [x] Missing verdict.json: HTTP 404
- [x] Test: request /run/invalid, assert 404

**Requirements:** 7, 9, 12
**Done when:** No absolute paths in responses, invalid run_id gives 404, test passes.

## Task 10: Final integration and README
- [ ] Run all UI tests with TestClient in a tmp base directory
- [ ] Verify no test contains hardcoded values (all read from run files)
- [ ] Update README Quick start: mention `make serve`
- [ ] Update architecture.md: add coroner/ui module

**Requirements:** 12
**Done when:** All UI tests pass (ALIVE, ZOMBIE with card, ZOMBIE T1 with exposure, ERROR, verify forged cert, matrix with/without catalog, 404, no home directory), README and architecture.md updated.

## Task 11: Docker image UI tests and third-party components
- [ ] Update Dockerfile to install runtime and test dependencies (fastapi, uvicorn, jinja2, python-multipart, httpx)
- [ ] Add `make smoke-ui` target: build the coroner:smoke image, run `pytest -q tests/test_ui*.py` inside the container
- [ ] Run `make smoke-ui` and verify all UI tests pass
- [ ] Add README section "Third-party components": htmx 2.0.4 (0BSD, vendored, SHA-256 e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447), fastapi 0.163.1 MIT, uvicorn 0.54.0 BSD-3-Clause, Jinja2 3.1.6 BSD-3-Clause, python-multipart 0.0.33 Apache-2.0, httpx 0.28.1 BSD-3-Clause (test only)

**Requirements:** 11, 12
**Done when:** Docker image includes UI dependencies, `make smoke-ui` passes, README lists all third-party components with licenses.

## Coverage table

| Requirement | Tasks |
|-------------|-------|
| Req 1 (technology stack, htmx) | 1, 2 |
| Req 2 (server binding) | 2 |
| Req 3 (data directory) | 2 |
| Req 4 (run page structure) | 3, 4, 5, 6 |
| Req 5 (certificate panel) | 4, 7 |
| Req 6 (Detection Matrix) | 8 |
| Req 7 (measured values) | 4, 5, 6, 8, 9 |
| Req 8 (visual design) | 2, 4, 5, 6 |
| Req 9 (validation) | 2, 9 |
| Req 10 (read-only) | (design only, no write endpoints) |
| Req 11 (dependencies) | 1 |
| Req 12 (tests) | 4, 5, 6, 7, 8, 9, 10 |


## Task 12: Engine/API container split with exchange directory (D-54)
- [ ] Create coroner/engine_worker.py: polls /exchange/jobs/, picks oldest queued job, runs coroner verify, writes result.json and status.json
- [ ] Update coroner/ui/app.py: add CORONER_ENGINE_MODE environment variable (api or worker)
- [ ] When CORONER_ENGINE_MODE=worker, run engine_worker.py main loop instead of FastAPI
- [ ] When CORONER_ENGINE_MODE=api, FastAPI routes remain unchanged
- [ ] Exchange directory structure: /exchange/jobs/{job_id}/ with request.json, status.json, result files
- [ ] Job hand-off: API writes request.json and status.json (queued), engine updates status (running, done, error), writes result
- [ ] Add timeout: engine sets alarm(60) at job start, catches SIGALRM, writes status.json (error, timeout)
- [ ] Test: create request.json in tmp exchange dir, run engine_worker once, assert result.json written and status done

**Requirements:** 13, 14
**Done when:** Engine worker polls exchange directory, executes jobs, writes results, timeout enforced, test passes with real job execution in tmp directory.

## Task 13: Run audit endpoint with sandbox controls (D-53, D-54)
- [ ] Add POST /api/run route: accepts RunAuditRequest (sample, port, seed, cases), validates with Pydantic
- [ ] Compute deterministic run_id from parameters hash
- [ ] Check if run_id exists in CORONER_BASE_DIR/runs/; if yes, return existing run
- [ ] Check queue length (bounded, for example max 3); if full, return HTTP 429 "Queue full, try again later"
- [ ] Check active audits per IP (client address from CF-Connecting-IP only when the request comes from the cloudflared container, otherwise the direct peer address); if one active, return HTTP 429 "One audit per client at a time"
- [ ] Create job_id, write request.json to /exchange/jobs/{job_id}/
- [ ] Return 202 Accepted with Location: /api/job/{job_id}/status
- [ ] Add GET /api/job/{job_id}/status: read status.json, return {status: queued/running/done/error, run_id: ...}
- [ ] When status done, copy result from exchange to CORONER_BASE_DIR/runs/{run_id}/, delete job directory
- [ ] Disk quota: count visitor runs in coroner-data, remove oldest beyond limit (for example 100), keep bundled runs
- [ ] Tests: valid request (assert 202), queue full (assert 429), second audit from same IP (assert 429), unknown field rejected, seed out of bounds rejected, case count out of bounds rejected, invalid sample rejected, body over size limit rejected

**Requirements:** 15, 16
**Done when:** Run audit endpoint accepts requests, computes deterministic run_id, enforces queue and per-IP limits, validates input, returns 202 and job status, sandbox controls tested.

## Task 14: Tamper endpoint (D-53, D-54)
- [ ] Add GET /tamper page: form with run_id input, loads certificate fields (status, cases_total, cases_divergent, random_seed) when run_id valid
- [ ] Add POST /api/tamper route: accepts TamperRequest (run_id, status, cases_total, cases_divergent, random_seed), validates with Pydantic
- [ ] Read original certificate from CORONER_BASE_DIR/runs/{run_id}/certificate.json
- [ ] Copy certificate to /exchange/tamper/{tamper_id}.json
- [ ] Apply visitor edits to copy, recompute certificate_sha256
- [ ] Call replay_certificate on copy
- [ ] Return replay result: {status: VALID/INVALID, reason: ...}
- [ ] Delete tamper copy
- [ ] Enforce certificate size limit (for example 1 MB)
- [ ] Tests: tamper with status ALIVE to ZOMBIE (assert INVALID with mismatch reason), tamper with recomputed hash (assert INVALID), read original before and after (assert byte-identical), certificate over size limit rejected

**Requirements:** 15, 16
**Done when:** Tamper page and endpoint implemented, works server-side on a copy, original never modified, size limit enforced, tests pass.

## Task 15: Rate limits and validation tests (D-54)
- [ ] Implement a small in-app rate limiter (sliding window per key, in memory, thread-safe)
- [ ] Add rate limiters: global 100/min, per client address 20/min, per endpoint /api/run 5/min per address, /api/verify 1 per 10 seconds
- [ ] Client address: read CF-Connecting-IP Cloudflare header ONLY when the request arrives from the cloudflared container on the internal network; otherwise the direct peer address from the socket
- [ ] Return HTTP 429 with Retry-After header when rate limit exceeded
- [ ] Set Cache-Control headers: static assets "public, max-age=86400", audit endpoints "no-store, no-cache, must-revalidate"
- [ ] Tests: exceed rate limit (assert 429 with Retry-After), audit response has Cache-Control no-store, static asset response cacheable

**Requirements:** 16, 17, 21
**Done when:** Rate limits enforced with in-app limiter, 429 with Retry-After, Cache-Control headers set correctly, tests pass.

## Task 16: Docker Compose file and cloudflared (D-52, D-54)
- [ ] Create docker-compose.yml: three services (coroner-api, coroner-engine, cloudflared)
- [ ] Network: coroner-net for api and cloudflared, none for engine (isolated)
- [ ] Volumes: coroner-data (runs), coroner-samples (read-only), coroner-exchange (job hand-off)
- [ ] Limits per service: coroner-api (1 CPU, 512 MB, no swap, pids 128), coroner-engine (2 CPUs, 2 GB, no swap, pids 256), cloudflared (0.25 CPU, 128 MB, no swap, pids 32)
- [ ] Engine hardening: network none, user 1000:1000, cap_drop ALL, no-new-privileges, read_only root, tmpfs /tmp and /app/work
- [ ] API hardening: user 1000:1000, no-new-privileges, read_only root, tmpfs /tmp
- [ ] cloudflared: mounts credentials file from ${TUNNEL_CREDENTIALS_FILE} (path in .env, never committed), config from cloudflared-config.yml
- [ ] Create cloudflared-config.yml: ingress routes coroner.iqoba.com to http://coroner-api:8000, 404 for anything else
- [ ] Platform: linux/amd64 for all services
- [ ] Add .env to .gitignore (already present, verify)
- [ ] Add CI test: grep for patterns matching tunnel credentials (for example ey*, base64 with specific prefix), fail if any tracked file matches
- [ ] Test: parse docker-compose.yml, assert engine has network: none, user: "1000:1000", cap_drop: [ALL], security_opt: [no-new-privileges:true], read_only: true

**Requirements:** 13, 14, 17, 21
**Done when:** Compose file with three services, limits, hardening, cloudflared config, credentials not in repository, CI test blocks credential leaks, container definition test passes.

## Task 17: Resource usage measurement under limits (Req 18, owner capacity decision)
- [ ] Build coroner:live image for linux/amd64 with all dependencies
- [ ] For each sample (credit-fees, T1, T2, T3, T4, T5): run 2,000 case audit inside engine container with limits (2 CPUs, 2 GB, no swap)
- [ ] Measure peak memory and CPU with docker stats sampling or read cgroup v2 files (memory.peak and cpu.stat; Docker Desktop and Ubuntu 24.04 use cgroup v2); record the method used
- [ ] Measure duration
- [ ] Assert every audit completes in under 60 seconds
- [ ] Assert every audit fits within 2 GB memory
- [ ] Record measured values in docs/deploy.md: per-sample peak memory, CPU, duration

**Requirements:** 18
**Done when:** Measurements taken for all samples at 2,000 cases under engine limits, all complete in under 60 s, all fit in 2 GB, values recorded in docs/deploy.md.

## Task 18: Test book and make test-book (Req 19, owner test book)
- [ ] Create docs/test-book.md: numbered scenarios with Purpose, Preconditions, Steps, Expected result (RULE), Actual result field
- [ ] Scenarios: Run audit on each sample (credit-fees, T1 to T5) with faulty and correct port, Verify on real certificate, Tamper (edit copy, INVALID), Detection Matrix page, ERROR page (broken reference), D-54 controls (unknown field rejected, out-of-bound case count rejected, second concurrent audit rejected, 429 with Retry-After)
- [ ] Create coroner/test_book.py: parses docs/test-book.md, executes scenarios via TestClient (local) or httpx (URL given), writes measured results into Actual result fields between GENERATED_START and GENERATED_END markers, computes hash of generated block, writes PASS or FAIL with date and Coroner version
- [ ] Add `make test-book` target: runs coroner/test_book.py locally, exits 1 if any scenario fails
- [ ] Add `make test-book URL=https://coroner.iqoba.com` form: runs against given URL
- [ ] Add test (tests/test_test_book.py): reads docs/test-book.md, checks every Actual result has GENERATED_START marker and hash matches content, fails if any Actual result not generated

**Requirements:** 19
**Done when:** Test book with scenarios written, generator executes all scenarios and writes measured results, make test-book works locally and against URL, test checks Actual results are generated.

## Task 19: Automated deployment check (Req 19, D-53)
- [ ] Add `make deploy-check` target: accepts URL parameter (for example `make deploy-check URL=https://coroner.iqoba.com`)
- [ ] Subset of test book scenarios: Run audit on T1 faulty (assert ZOMBIE), T1 correct (assert ALIVE), Tamper (assert INVALID with reason)
- [ ] Use httpx to call the URL, check responses
- [ ] Exit 1 if any check fails, exit 0 if all pass
- [ ] Test: run deploy-check against local TestClient, assert exit 0

**Requirements:** 19
**Done when:** make deploy-check runs automated checks against a URL, fails loudly on unexpected result, works locally and against live site.

## Task 20: Deployment documentation and README update (Req 20, D-52)
- [ ] Create docs/deploy.md: prerequisites, tunnel creation commands with placeholders (cloudflared tunnel create, cloudflared tunnel route dns), container limits, measured resource usage from Task 17, demo data generation commands (make traps, make demo-ebcdic, make demo, make zombie), how to update, how to stop, uptime monitor setup with placeholders (no email or account id)
- [ ] State limits: engine 2 CPUs 2 GB, API 1 CPU 512 MB, cloudflared 0.25 CPU 128 MB, sum 2688 MB
- [ ] State free memory requirement: at least 8 GiB for host's other service
- [ ] State platform: linux/amd64
- [ ] Note: "The server currently uses Wi-Fi; a wired Ethernet connection is recommended for the judging period."
- [ ] Update README.md: add Live demo section with link https://coroner.iqoba.com and link to docs/deploy.md

**Requirements:** 20
**Done when:** docs/deploy.md complete with placeholders for secrets, limits and measured usage documented, README Live demo section added with coroner.iqoba.com link.

## Task 21: Security control tests (Req 21, D-54)
- [ ] Test: unknown field in RunAuditRequest JSON rejected (assert 422)
- [ ] Test: seed -1 rejected, seed 1000001 rejected (assert 422)
- [ ] Test: cases 9 rejected, cases 2001 rejected (assert 422)
- [ ] Test: sample "invalid" rejected (assert 422)
- [ ] Test: request body over size limit rejected (for example 20 KB JSON, assert 413 or 422)
- [ ] Test: rate limit exceeded returns 429 with Retry-After header
- [ ] Test: second audit from same IP while one active returns 429
- [ ] Test: queue full returns 429
- [ ] Test: 60 second timeout ends job (job timeout is configurable; the timeout test runs a REAL audit with a short configured timeout, for example 1 s with 2000 cases, which takes longer than 1 s, and asserts the job ends with status error and reason timeout)
- [ ] Test: Tamper never modifies original (read original certificate before and after, assert SHA-256 equal)
- [ ] Test: certificate over size limit rejected (for example 2 MB file, assert error)
- [ ] Test: audit response has Cache-Control: no-store
- [ ] Test: static asset response cacheable (Cache-Control: public)
- [ ] Test: parse docker-compose.yml (already in Task 16), assert engine definition correct

**Requirements:** 21
**Done when:** All security controls have tests, all tests pass.

## Coverage table (extended)

| Requirement | Tasks |
|-------------|-------|
| Req 1 (technology stack, htmx) | 1, 2 |
| Req 2 (server binding) | 2 |
| Req 3 (data directory) | 2 |
| Req 4 (run page structure) | 3, 4, 5, 6 |
| Req 5 (certificate panel) | 4, 7 |
| Req 6 (Detection Matrix) | 8 |
| Req 7 (measured values) | 4, 5, 6, 8, 9 |
| Req 8 (visual design) | 2, 4, 5, 6 |
| Req 9 (validation) | 2, 9 |
| Req 10 (read-only V1) | (design only, Run audit added in deployment) |
| Req 11 (dependencies) | 1 |
| Req 12 (tests) | 4, 5, 6, 7, 8, 9, 10 |
| Req 13 (Docker Compose) | 16 |
| Req 14 (container hardening) | 12, 16 |
| Req 15 (interactive live demo) | 13, 14 |
| Req 16 (validation, rate limits) | 13, 14, 15, 21 |
| Req 17 (Cloudflare, security) | 15, 16 |
| Req 18 (resource limits measured) | 17 |
| Req 19 (test book, automated checks) | 18, 19 |
| Req 20 (deployment docs) | 20 |
| Req 21 (security control tests) | 15, 16, 21 |
