# Guided Story Tasks

## Task 1: Gate check endpoint and logic
- [ ] BUG FIX in coroner/gate.py: gate_certificate must pass base_dir to replay_certificate (currently drops it); signature becomes gate_certificate(cert_path, scope, base_dir) -> (status, replay, hash_match) with replay_certificate(cert_path, base_dir) call
- [ ] REFACTOR: extract pure decision function gate_decision(status, replay, hash_match) -> exit_code from run_gate logic, used by both run_gate and the /api/gate-check endpoint
- [ ] Add POST /api/gate-check route in coroner/ui/app.py (form-encoded, not path parameter)
- [ ] Validate form field run_id (12 lowercase hex)
- [ ] Read certificate from CORONER_BASE_DIR/runs/{run_id}/certificate.json (1 MB limit, 413 beyond)
- [ ] Build scope from certificate: {cobol: cert["cobol_file"], java: cert["java_file"], schema: cert["schema_file"], copybooks: cert["copybook_dir"]}
- [ ] Call gate_certificate(cert_path, scope, base_dir) to get (status, replay, hash_match)
- [ ] Call gate_decision(status, replay, hash_match) to get exit code
- [ ] Run replay with replay_with_timeout (same function as /api/verify, off the event loop, 90 s default timeout)
- [ ] Return JSON: {status: "allowed" or "blocked", exit_code: 0 or 1, message: "Commit allowed" or "This ZOMBIE migration cannot be committed"}
- [ ] Rate limit: reuse existing limiter, 1 per 10 seconds per client (same as /api/verify and /api/tamper)
- [ ] Cache-Control: no-store, no-cache on all responses (success and error)
- [ ] Test: POST with form data run_id=f584d5f35228 (bundled T1 faulty), assert {status: "blocked", exit_code: 1}
- [ ] Test: POST with form data run_id=29c15f04407b (bundled T1 correct), assert {status: "allowed", exit_code: 0}
- [ ] Test: POST with invalid run_id, assert 422
- [ ] Test: POST with non-existent run_id, assert 404
- [ ] Test: response has Cache-Control: no-store
- [ ] Test: run_gate and /api/gate-check give the same exit code on the same certificate (test run_gate and POST /api/gate-check with same inputs, assert identical exit codes)

**Requirements:** 3, 4
**Done when:** POST /api/gate-check endpoint works, calls real gate logic with base_dir fix, runs replay off the event loop, returns correct status for ZOMBIE and ALIVE runs, rate limited, no-store, tests pass.

## Task 2: Story container page and step navigation
- [ ] Create coroner/ui/templates/story.html extending base.html
- [ ] Story container: progress indicator "Step X of 8", `<div id="story-content"></div>` with hx-get="/story/step/1" hx-trigger="load"
- [ ] Add keyboard navigation: JavaScript snippet listens for arrow keys (advance/back), enter (advance), escape (exit to home)
- [ ] Add GET /story route in coroner/ui/app.py: renders story.html
- [ ] Test: GET /story, assert page contains "Step 1 of 8" and hx-get="/story/step/1"

**Requirements:** 1, 2
**Done when:** Story container page renders, htmx loads first step, keyboard events wired, test passes.

## Task 3: Step 1 (bank process)
- [ ] Add GET /story/step/1 route in coroner/ui/app.py
- [ ] Render HTML fragment: sentence "Every night, the bank reconciles branch subtotals to catch posting errors before opening."
- [ ] Next button: hx-get="/story/step/2" hx-target="#story-content"
- [ ] No Back button (first step)
- [ ] Test: GET /story/step/1, assert sentence present and Next button hx-get="/story/step/2"

**Requirements:** 1, 6
**Done when:** Step 1 renders plain sentence, Next button navigates to step 2, test passes.

## Task 4: Step 2 (COBOL result)
- [ ] Add GET /story/step/2 route
- [ ] Read runs/29c15f04407b/verdict.json (T1 correct, bundled)
- [ ] Render: sentence "The COBOL mainframe processed 2000 transactions and reconciled every branch.", ALIVE badge, cases and divergences from verdict.json
- [ ] Next button: hx-get="/story/step/3"
- [ ] Back button: hx-get="/story/step/1"
- [ ] Test: GET /story/step/2, assert sentence, ALIVE badge, cases 2000, divergences 0 (read from runs/29c15f04407b/verdict.json, not hard-coded)

**Requirements:** 1, 3, 8
**Done when:** Step 2 renders COBOL result with measured values, navigation buttons work, test reads verdict.json.

## Task 5: Step 3 (Java migration)
- [ ] Add GET /story/step/3 route
- [ ] Render: sentence "A Java migration was built to replace the mainframe."
- [ ] Next button: hx-get="/story/step/4"
- [ ] Back button: hx-get="/story/step/2"
- [ ] Test: GET /story/step/3, assert sentence present

**Requirements:** 1, 6
**Done when:** Step 3 renders plain sentence, navigation buttons work, test passes.

## Task 6: Step 4 (Coroner compares)
- [ ] Add GET /story/step/4 route
- [ ] Read runs/f584d5f35228/verdict.json (T1 faulty, bundled)
- [ ] Render: sentence "Coroner ran both programs on the same 2000 transactions.", ZOMBIE badge, cases and divergences from verdict.json, exposure sum from branch_reconciliation.json
- [ ] Add form with hidden run_id field: hx-post="/api/gate-check" hx-target="#gate-status" to call gate check asynchronously, show enforcement message in #gate-status when result arrives ("This ZOMBIE migration cannot be committed" for status "blocked")
- [ ] Note in step content: "Checking gate status..." shown while replay runs (15 to 20 s at 2000 cases), visitor can click Next meanwhile
- [ ] Link "run it yourself": hx-post="/api/run" hx-vals='{"sample":"T1","port":"faulty","seed":42,"cases":2000}', polls /api/job/{job_id}/status, updates step when done
- [ ] Next button: hx-get="/story/step/5"
- [ ] Back button: hx-get="/story/step/3"
- [ ] Test: GET /story/step/4, assert sentence, ZOMBIE badge, divergences > 0, exposure sum (all from verdict.json and branch_reconciliation.json)
- [ ] Test: assert gate check form present with hx-post="/api/gate-check" and run_id field

**Requirements:** 1, 3, 4, 5, 8
**Done when:** Step 4 shows ZOMBIE result from bundled run, gate enforcement form posts to /api/gate-check asynchronously, result shown when it arrives, visitor can navigate during replay, "run it yourself" link works, tests read real files.

## Task 7: Step 5 (where and why)
- [ ] Add GET /story/step/5 route
- [ ] Read runs/f584d5f35228/branch_reconciliation.json, find branch with max absolute difference (likely 001 or 9ZZ)
- [ ] Read samples/traps/T1-ebcdic-match-merge/trap.json business_cause
- [ ] Render: sentence "Coroner found which branch broke and why.", branch code and difference, business cause from trap.json
- [ ] Next button: hx-get="/story/step/6"
- [ ] Back button: hx-get="/story/step/4"
- [ ] Test: GET /story/step/5, assert sentence, branch code, business cause equals trap.json business_cause field (not hard-coded)

**Requirements:** 1, 3, 6
**Done when:** Step 5 shows branch mismatch and business cause from real files, plain English, test passes.

## Task 8: Step 6 (apply the fix)
- [ ] Add GET /story/step/6 route
- [ ] Read samples/traps/T1-ebcdic-match-merge/trap.json business_fix
- [ ] Render: sentence "The Java migration was corrected to sort in EBCDIC order.", business fix from trap.json
- [ ] Next button: hx-get="/story/step/7"
- [ ] Back button: hx-get="/story/step/5"
- [ ] Test: GET /story/step/6, assert sentence, business fix equals trap.json business_fix field

**Requirements:** 1, 3, 6
**Done when:** Step 6 shows fix guidance from trap.json, test passes.

## Task 9: Step 7 (ALIVE certificate)
- [ ] Add GET /story/step/7 route
- [ ] Read runs/29c15f04407b/verdict.json and certificate.json (T1 correct, bundled)
- [ ] Render: sentence "Coroner verified the fixed migration on 2000 transactions.", ALIVE badge, cases, divergences, certificate status VALID
- [ ] Add form with hidden run_id field: hx-post="/api/gate-check" hx-target="#gate-status" to call gate check asynchronously, show enforcement message in #gate-status when result arrives ("Commit allowed" for status "allowed")
- [ ] Note in step content: "Checking gate status..." shown while replay runs, visitor can click Next meanwhile
- [ ] Link "run it yourself": hx-post="/api/run" hx-vals='{"sample":"T1","port":"correct","seed":42,"cases":2000}'
- [ ] Next button: hx-get="/story/step/8"
- [ ] Back button: hx-get="/story/step/6"
- [ ] Test: GET /story/step/7, assert sentence, ALIVE badge, certificate VALID, gate check form present with hx-post="/api/gate-check"

**Requirements:** 1, 3, 4, 5, 8
**Done when:** Step 7 shows ALIVE result and certificate from bundled run, gate enforcement form posts asynchronously, result shown when it arrives, "run it yourself" link works, test passes.

## Task 10: Step 8 (try to cheat)
- [ ] Add GET /story/step/8 route
- [ ] Read runs/29c15f04407b/certificate.json, prefill form with status ALIVE, cases_total 2000, cases_divergent 0
- [ ] Render: sentence "Try editing the certificate to change the verdict.", form with editable fields, button "Tamper and verify"
- [ ] Button: hx-post="/api/tamper" with run_id and edited fields, hx-target="#tamper-result"
- [ ] Show result in #tamper-result: "Certificate: INVALID, replay mismatch (status: expected ALIVE, got ZOMBIE)" or similar from /api/tamper response
- [ ] Explanation after result: "Editing a certificate makes it INVALID. This proves the audit result cannot be faked."
- [ ] Finish button: hx-get="/" hx-target="body" (return to home)
- [ ] Back button: hx-get="/story/step/7"
- [ ] Test: GET /story/step/8, assert sentence, form prefilled with certificate values (read from certificate.json)
- [ ] Test: POST /api/tamper with status changed to ZOMBIE, assert INVALID in response

**Requirements:** 1, 3, 4, 6, 8
**Done when:** Step 8 shows Tamper form with real certificate values, posts to /api/tamper, shows INVALID result, explanation in plain English, Finish returns to home, tests pass.

## Task 11: Home page button and responsive design
- [ ] Update coroner/ui/templates/index.html: add large button "Try the bank failure" that navigates to /story (or hx-get="/story" hx-target="body")
- [ ] Add CSS media query for 375px width: stack content, full-width buttons, min 44px button height, min 16px text
- [ ] Test: GET /, assert "Try the bank failure" button present with href or hx-get="/story"
- [ ] Manual check at 375px width: all steps readable, no horizontal scroll, buttons tappable

**Requirements:** 1, 7
**Done when:** Home page has story button, responsive CSS for phone width, test passes, manual check confirms usability at 375px.

## Task 12: Integration tests and no em dash check
- [ ] Test: load story container, navigate all 8 steps with htmx, assert each step loads and shows measured values
- [ ] Test: step 4 "run it yourself" posts to /api/run, job completes, step updates with visitor result (uses TestClient, small case count like 50 for speed)
- [ ] Test: step 7 "run it yourself" works similarly
- [ ] Test: keyboard navigation (simulate arrow key events, assert step changes; or manual check)
- [ ] Test: escape key returns to home (or manual check)
- [ ] Test: grep all story templates and routes for em dash character, assert 0 matches
- [ ] Test: no files created at repository root during story execution
- [ ] Run all story tests, assert 0 failures

**Requirements:** 2, 9, 10
**Done when:** Integration tests cover navigation, "run it yourself", keyboard events, no em dash, no root files, all tests pass.

## Coverage table

| Requirement | Tasks |
|-------------|-------|
| Req 1 (story structure, 8 steps) | 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| Req 2 (keyboard accessibility) | 2, 12 |
| Req 3 (measured values only) | 1, 4, 6, 7, 8, 9, 10 |
| Req 4 (reuse endpoints) | 1, 6, 9, 10 |
| Req 5 (works offline) | 4, 6, 9 |
| Req 6 (plain English) | 3, 4, 5, 6, 7, 8, 9, 10 |
| Req 7 (phone width) | 11 |
| Req 8 (htmx design) | 2, 4, 6, 9, 10 |
| Req 9 (tests) | 1, 3, 4, 5, 6, 7, 8, 9, 10, 12 |
| Req 10 (constraints) | 12 |
