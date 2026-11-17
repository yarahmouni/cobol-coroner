# Web UI Tasks

## Task 1: Dependencies and htmx vendor file
- [ ] Add fastapi==0.163.1, uvicorn==0.54.0, jinja2==3.1.6, python-multipart==0.0.33 to pyproject.toml dependencies
- [ ] Add httpx==0.28.1 to dev dependencies
- [ ] Operator downloaded htmx.min.js 2.0.4 to build/vendor/htmx.min.js (50917 bytes, SHA-256 e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447)
- [ ] Copy build/vendor/htmx.min.js to coroner/ui/static/htmx.min.js with cp
- [ ] Add a test that reads coroner/ui/static/htmx.min.js and computes its SHA-256 hash (assert equals the expected hash)

**Requirements:** 1, 11
**Done when:** Dependencies in pyproject.toml with exact versions, htmx file at coroner/ui/static/htmx.min.js with correct hash, hash test passes.

## Task 2: FastAPI app skeleton and base template
- [ ] Create coroner/ui/__init__.py
- [ ] Create coroner/ui/app.py with FastAPI app, CORONER_BASE_DIR logic, run_id validation regex
- [ ] Create coroner/ui/templates/base.html with dark theme CSS (colors: background #1a1a1a, text #e0e0e0, ALIVE bg #1b4d3e text #4ade80, ZOMBIE bg #4d1b1b text #f87171, ERROR bg #4d3d1b text #fbbf24), htmx script tag
- [ ] Serve coroner/ui/static/htmx.min.js as /static/htmx.min.js
- [ ] Add a test that reads the colors from the CSS and computes every contrast ratio with the WCAG 2 relative-luminance formula, asserting each is at least 4.5:1
- [ ] `make serve` target: `uvicorn coroner.ui.app:app --host 127.0.0.1 --port 8000`

**Requirements:** 1, 2, 3, 8, 9
**Done when:** FastAPI app runs on 127.0.0.1, base template has dark theme with specified colors, htmx loads, run_id validation in place, contrast ratios computed and verified.

## Task 3: Index page
- [ ] Create coroner/ui/templates/index.html extending base.html
- [ ] GET / route: render index with project title, tagline, link to Detection Matrix
- [ ] List recent runs: up to 10, newest first, shown as runs/<id> with verdict and date

**Requirements:** 4 (structure)
**Done when:** Index page renders with title, tagline, links, and recent runs list; accessible at http://127.0.0.1:8000/.

## Task 4: Run page for ALIVE verdict
- [ ] Create coroner/ui/templates/run.html extending base.html
- [ ] GET /run/{run_id} route: validate run_id, read verdict.json, inputs.json, certificate.json (optional)
- [ ] Display: verdict (large, green, text label "ALIVE"), cases, divergences, paragraph coverage, branch coverage, duration, "Validated under GnuCOBOL 3.x"
- [ ] Certificate panel: display certificate fields, Verify button (htmx post, target cert-result div)
- [ ] Test: ALIVE credit-fees run at 30 cases, assert no home directory in response

**Requirements:** 4, 5, 7, 8, 9, 12
**Done when:** ALIVE run page renders with all required fields, certificate panel with Verify button, test passes.

## Task 5: Run page for ZOMBIE verdict (after ui branch rebased onto main, priority 9 merged)
- [ ] Extend GET /run/{run_id}: read failure_report.json, card.txt for ZOMBIE
- [ ] Display: verdict (large, red, text label "ZOMBIE"), card (Given/When/Then), COBOL lines from failure_report, divergent field with values
- [ ] Read inputs.json schema for group_key; if present, display Unreconciled branch exposure (sum, max, branches affected, grand total matches)
- [ ] timing.json written by the CLI, not hashed in the certificate (separate task after rebase)
- [ ] Tests: ZOMBIE credit-fees legacy variant (assert card, COBOL lines), ZOMBIE T1 faulty (assert exposure line with "grand total matches: yes")

**Requirements:** 4, 7, 8, 12
**Done when:** ZOMBIE run pages render with card, COBOL lines, exposure when applicable, both tests pass.

**Note:** This task depends on priority 9 code (card.txt generation from failure_report) not yet on this branch. Proceed with other tasks first; rebase ui branch onto main after priority 9 is merged.

## Task 6: Run page for ERROR verdict
- [ ] Extend GET /run/{run_id}: when verdict.json absent, read run_error.txt
- [ ] Display: verdict (large, orange, text label "ERROR"), error reason, reference stderr
- [ ] Test: ERROR run (broken reference per D-51: the run directory contains inputs.json, generated_cases.csv, run_error.txt; no verdict.json, no certificate.json), assert error reason displayed

**Requirements:** 4, 7, 8, 12
**Done when:** ERROR run page renders with error reason and stderr, test produces a real broken-reference run and passes.

## Task 7: Certificate verification endpoint
- [ ] POST /api/verify route: receive JSON with run_id, validate, call coroner.certificate.replay_certificate
- [ ] Return JSON: status (VALID/INVALID), verdict (if valid), reason (if invalid)
- [ ] htmx response updates cert-result div with replay result
- [ ] Test: forge a certificate (edit status, recompute hash), POST verify, assert INVALID with reason

**Requirements:** 5, 12
**Done when:** Verify endpoint returns correct JSON, htmx updates panel, forgery test passes.

## Task 8: Detection Matrix page
- [ ] Create coroner/ui/templates/matrix.html extending base.html
- [ ] GET /matrix route: check if runs/trap_catalog.json exists
- [ ] If exists: load, display table with columns Trap ID, Description, Detected (of N), Rate, Correct port verdict
- [ ] T6: show as placeholder without numbers
- [ ] If absent: display "Detection Matrix not available yet: run make traps"
- [ ] Tests: with catalog (assert T1, T6 placeholder), without catalog (assert "not available yet")

**Requirements:** 6, 7, 12
**Done when:** Matrix page renders with trap table or fallback message, both tests pass.

## Task 9: Path sanitization and 404 handling
- [ ] All file paths shown: repository-relative for sources, runs/<run_id> for run directories
- [ ] Invalid run_id: HTTP 404
- [ ] Missing verdict.json: HTTP 404
- [ ] Test: request /run/invalid, assert 404

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
