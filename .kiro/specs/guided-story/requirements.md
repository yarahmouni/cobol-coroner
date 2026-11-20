# Guided Story Requirements

## Overview

A 90-second guided story on the home page that walks a non-technical visitor through the T1 EBCDIC trap with 8 steps: bank process, COBOL result, Java migration, Coroner compares, where and why, apply the fix, ALIVE certificate, try to cheat.

## Requirements (EARS format)

### Req 1: Story structure
**WHERE** the home page is loaded, the system **SHALL** display one large button "Try the bank failure" that starts the guided story.

**WHERE** the story is started, the system **SHALL** display exactly 8 steps in sequence, one plain sentence each:
1. Bank process (nightly branch reconciliation batch)
2. COBOL result (the reference output)
3. Java migration (the faulty port)
4. Coroner compares (Run audit on T1 faulty)
5. Where and why (the branch that does not reconcile and the business cause)
6. Apply the fix (the correct port)
7. ALIVE certificate (Run audit on T1 correct)
8. Try to cheat (Tamper gives INVALID)

**WHERE** each step is displayed, the system **SHALL** show Next and Back buttons for navigation.

**WHERE** the story is at step 1, the Back button **SHALL** be disabled or hidden.

**WHERE** the story is at step 8, the Next button **SHALL** show "Finish" or similar and return to the home page.

### Req 2: Keyboard accessibility
**WHERE** the story is displayed, the system **SHALL** support:
- Arrow keys (left/right or up/down) for navigation between steps
- Enter key to advance to next step
- Escape key to exit the story
- Focus visible on Next and Back buttons
- All interactive elements keyboard-accessible with tab navigation

### Req 3: Measured values only
**WHERE** any step displays a verdict, count, exposure or certificate status, the system **SHALL** read that value from:
- The bundled demo runs (f584d5f35228 T1 faulty, 29c15f04407b T1 correct) generated at first start, OR
- A visitor's Run audit result if they clicked "run it yourself"

**WHERE** any step displays business cause or fix, the system **SHALL** read that text from samples/traps/T1-ebcdic-match-merge/trap.json (business_cause, business_fix).

**WHERE** any step displays gate enforcement ("This ZOMBIE migration cannot be committed", "Commit allowed"), the system **SHALL** determine that text ONLY from:
- Calling `gate_certificate` with the run's certificate path, scope and base_dir
- Calling `gate_decision(status, replay, hash_match)` to map the result to exit code
- Exit 1 for ZOMBIE/missing/invalid/hash mismatch = "This ZOMBIE migration cannot be committed"
- Exit 0 for ALIVE with hash match and VALID replay = "Commit allowed"
- Exit 2 for ERROR is not applicable in the story (certificates exist)

**WHERE** enforcement text is shown, the system **SHALL** never hard-code verdict text: every verdict comes from the run's verdict.json or certificate.json.

### Req 4: Reuse existing endpoints
**WHERE** the story needs run data, the system **SHALL** reuse:
- GET /run/{run_id} for run page data
- Existing run data loading logic (verdict.json, certificate.json, failure_report.json, branch_reconciliation.json)
- samples/traps/T1-ebcdic-match-merge/trap.json for trap metadata

**WHERE** the story needs to verify gate enforcement, the system **SHALL** add:
- POST /api/gate-check endpoint that accepts form field run_id (12 hex), builds scope from the run's certificate (cobol_file, java_file, schema_file, copybook_dir), calls gate logic server-side and returns {status: "blocked" or "allowed", exit_code: 0 or 1}
- The endpoint **SHALL** run certificate replay off the event loop with timeout like /api/verify (replay_with_timeout from coroner/ui/app.py), never blocking the server
- Rate limit: 1 per 10 seconds per client (same as /api/verify and /api/tamper)
- Cache-Control: no-store on all responses
- GET-free of side effects (POST is acceptable for the form-encoded request)

**WHERE** the story needs Tamper behavior, the system **SHALL** reuse the existing POST /api/tamper endpoint.

### Req 5: Works offline from bundled runs
**WHERE** the story is displayed, **IF** the visitor never clicks Run audit, the system **SHALL** work entirely from the bundled demo runs (f584d5f35228 faulty, 29c15f04407b correct).

**WHERE** steps 4 or 7 show a run audit, the system **SHALL**:
- Display the bundled run result by default
- Offer a link or button "run it yourself" that triggers a real Run audit and updates the step with the visitor's result

**WHERE** the visitor's audit is running, the system **SHALL** show a progress indicator (for example "Running audit on 2000 cases...") with htmx polling /api/job/{job_id}/status.

### Req 6: Plain English for non-technical judges
**WHERE** any step displays text, the system **SHALL** use plain English understandable by a non-technical bank stakeholder or judge.

**WHERE** step 1 is displayed, the system **SHALL** describe the business process (for example "Every night, the bank reconciles branch subtotals to catch posting errors before opening.").

**WHERE** step 5 is displayed, the system **SHALL** explain the failure in business terms first (branch does not reconcile, grand total still balances) before technical details.

**WHERE** step 8 is displayed, the system **SHALL** explain that tampering the certificate proves it cannot be forged (for example "Editing a certificate makes it INVALID. This proves the audit result cannot be faked.").

### Req 7: Works at phone width
**WHERE** the story is displayed, the system **SHALL** be usable on a viewport as narrow as 375px (common phone width).

**WHERE** layout is rendered, the system **SHALL**:
- Stack content vertically
- Use readable font size (at least 16px body text)
- Keep buttons large enough for touch (at least 44px tap target)
- Avoid horizontal scroll

### Req 8: Visual design
**WHERE** the story is displayed, the system **SHALL** use htmx and plain HTML, no new JavaScript library.

**WHERE** step content changes, the system **SHALL** use htmx hx-get or hx-post with hx-target to swap step content without a full page reload.

**WHERE** a step shows a run verdict, the system **SHALL** reuse the existing verdict badge styles (ALIVE green circle, ZOMBIE red square, INVALID amber triangle per D-56).

**WHERE** a step shows amounts or COBOL lines, the system **SHALL** reuse the existing styles (monospace for code, amounts right-aligned).

### Req 9: Tests
**WHERE** the guided story is tested, the system **SHALL** include tests with FastAPI TestClient that:
- Request the home page and assert the "Try the bank failure" button is present
- Request step 1 and assert it displays the bank process sentence
- Request step 4 and assert it shows the bundled T1 faulty run verdict (ZOMBIE, divergent cases > 0) read from verdict.json
- Request step 5 and assert it shows the business cause read from trap.json
- Request step 7 and assert it shows the bundled T1 correct run verdict (ALIVE) read from verdict.json
- POST to /api/gate-check with the faulty run_id and assert {status: "blocked", exit_code: 1}
- POST to /api/gate-check with the correct run_id and assert {status: "allowed", exit_code: 0}
- Request step 8 with a tampered certificate and assert INVALID is shown

**WHERE** the tests read values, they **SHALL** read from real run files (verdict.json, certificate.json, trap.json), never mock or hard-code expected values.

**WHERE** the tests check gate enforcement, they **SHALL** call the real gate_certificate and gate_decision logic, not a mock.

### Req 10: No em dash, no summary files, nothing at root
**WHERE** any file is created or modified, the system **SHALL NOT**:
- Use the em dash character in any text
- Create summary files under docs/ or elsewhere
- Leave helper scripts or temporary files at the repository root

## Done when
- EARS requirements cover the 8-step structure, keyboard accessibility, measured values only, reuse of endpoints, works offline, plain English, phone width, htmx design, tests and constraints.
- Every verdict, count and enforcement message comes from real run files or gate logic, never hard-coded.
- A new endpoint /api/gate-check returns gate status for a run_id, rate-limited and no-store.
- Steps 4 and 7 work from bundled runs or allow "run it yourself" with htmx polling.
- Tests use real runs and real gate logic, no mocks, no hard-coded values.
- Plain English understandable by non-technical judges.
- Works at 375px viewport width.
- No em dash, no summary files, nothing left at repository root.
