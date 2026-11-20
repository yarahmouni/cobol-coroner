# Guided Story Design

## Architecture

A guided 8-step story served by FastAPI with htmx for step navigation. Each step is a plain sentence with supporting data from bundled demo runs, trap metadata, or visitor audit results. Gate enforcement determined server-side from real gate logic.

## Step content

### Step 1: Bank process
Plain sentence: "Every night, the bank reconciles branch subtotals to catch posting errors before opening."

Supporting visual: optional illustration or simple text.

### Step 2: COBOL result
Sentence: "The COBOL mainframe processed 2000 transactions and reconciled every branch."

Supporting data:
- Read runs/29c15f04407b/verdict.json (T1 correct, bundled)
- Show: ALIVE, 2000 cases, 0 divergences
- Optional: snippet of COBOL output with branch subtotals

### Step 3: Java migration
Sentence: "A Java migration was built to replace the mainframe."

Supporting visual: COBOL arrow Java, or simple text.

### Step 4: Coroner compares
Sentence: "Coroner ran both programs on the same 2000 transactions."

Supporting data:
- Read runs/f584d5f35228/verdict.json (T1 faulty, bundled)
- Show: ZOMBIE, 682 of 2000 divergences, exposure sum 3995184.38
- Gate enforcement: form with run_id posts to /api/gate-check, shows "This ZOMBIE migration cannot be committed" in a target div when result arrives (15 to 20 s replay, visitor can click Next meanwhile)
- Progress indicator: "Checking gate status..." while replay runs
- Link: "run it yourself" triggers POST /api/run with {sample: "T1", port: "faulty", seed: 42, cases: 2000}, polls /api/job/{job_id}/status, updates this step with visitor's result when done

### Step 5: Where and why
Sentence: "Coroner found which branch broke and why."

Supporting data:
- Read runs/f584d5f35228/branch_reconciliation.json and failure_report.json
- Show: branch 001 or 9ZZ mismatch (the branch with max difference)
- Read samples/traps/T1-ebcdic-match-merge/trap.json business_cause
- Show: "Control-break logic processes branches in the wrong order, misposting amounts to suspense while grand totals still balance."

### Step 6: Apply the fix
Sentence: "The Java migration was corrected to sort in EBCDIC order."

Supporting data:
- Read samples/traps/T1-ebcdic-match-merge/trap.json business_fix
- Show: "Make the Java migration sort and match branch codes in the same order as the mainframe."

### Step 7: ALIVE certificate
Sentence: "Coroner verified the fixed migration on 2000 transactions."

Supporting data:
- Read runs/29c15f04407b/verdict.json and certificate.json (T1 correct, bundled)
- Show: ALIVE, 2000 cases, 0 divergences, certificate VALID
- Gate enforcement: form with run_id posts to /api/gate-check, shows "Commit allowed" in a target div when result arrives
- Progress indicator: "Checking gate status..." while replay runs
- Link: "run it yourself" triggers POST /api/run with {sample: "T1", port: "correct", seed: 42, cases: 2000}

### Step 8: Try to cheat
Sentence: "Try editing the certificate to change the verdict."

Interactive:
- Form with certificate fields: status (ALIVE/ZOMBIE), cases_total, cases_divergent (read from runs/29c15f04407b/certificate.json as defaults)
- Button "Tamper and verify" posts to /api/tamper with run_id=29c15f04407b and edited fields
- Show result: "Certificate: INVALID, replay mismatch (status: expected ALIVE, got ZOMBIE)" or similar
- Explanation: "Editing a certificate makes it INVALID. This proves the audit result cannot be faked."

## Routes

### GET /story
Story container page:
- Loads story.html with htmx
- Initial state: step 1
- Query parameter ?step=N for direct links

### GET /story/step/{step_number}
Returns HTML fragment for one step (1 to 8):
- Reads bundled run files for steps 2, 4, 5, 7, 8
- Reads trap.json for steps 5, 6
- Renders step content with Next/Back buttons
- hx-get="/story/step/{next}" hx-target="#story-content" for navigation

### POST /api/gate-check
Gate enforcement check:
- Accepts form field run_id (12 lowercase hex, validated)
- Reads runs/{run_id}/certificate.json (1 MB limit, 413 beyond)
- Builds scope from certificate: {cobol: cert["cobol_file"], java: cert["java_file"], schema: cert["schema_file"], copybooks: cert["copybook_dir"]}
- Calls gate_certificate(cert_path, scope, base_dir) to get (status, replay, hash_match)
- Calls gate_decision(status, replay, hash_match) to get exit code
- Maps exit code: 0 for ALIVE with hash match and VALID replay, 1 otherwise
- Runs replay_with_timeout (same function as /api/verify) off the event loop to avoid blocking the server during the 15 to 20 s replay at 2000 cases
- Returns JSON: {status: "blocked" or "allowed", exit_code: 0 or 1, message: "..."}
- Rate limit: 1 per 10 seconds per client (like /api/verify and /api/tamper)
- Cache-Control: no-store, no-cache on all responses (success and error)
- 404 if run_id not found, 422 if invalid format

## Templates

### story.html
Extends base.html, contains:
- Progress indicator (Step X of 8)
- `<div id="story-content" hx-get="/story/step/1" hx-trigger="load"></div>`
- Keyboard event listeners (arrow keys, enter, escape) that call hx-get on step divs

### step_*.html (or one step.html with conditionals)
Each step fragment:
- One plain sentence
- Supporting data (verdict badge, amounts, business cause, etc.)
- Next button: `<button hx-get="/story/step/{next}" hx-target="#story-content">Next</button>`
- Back button: `<button hx-get="/story/step/{prev}" hx-target="#story-content">Back</button>`
- Step 1: no Back or disabled
- Step 8: Next shows "Finish", hx-get="/" (return to home)

For step 4 and step 7, "run it yourself" link:
- `<button hx-post="/api/run" hx-vals='{"sample":"T1","port":"faulty","seed":42,"cases":2000}' hx-target="#audit-result">Run it yourself</button>`
- `<div id="audit-result" hx-get="/api/job/{job_id}/status" hx-trigger="every 2s"></div>`
- When job done, show updated verdict and gate status

## Data flow

1. Visitor clicks "Try the bank failure" on home page
2. Browser navigates to /story (or htmx swaps main content)
3. htmx loads /story/step/1 into #story-content
4. Visitor clicks Next
5. htmx loads /story/step/2, reads runs/29c15f04407b/verdict.json server-side, renders ALIVE badge
6. Steps 3, 4, 5, 6 follow same pattern
7. Step 4: reads runs/f584d5f35228/verdict.json (ZOMBIE), calls POST /api/gate-check with run_id form field (htmx posts form-encoded), shows "blocked" when gate check result arrives asynchronously (replay takes 15 to 20 s, visitor can click Next meanwhile)
8. Step 7: reads runs/29c15f04407b/certificate.json (VALID), calls POST /api/gate-check with run_id form field, shows "allowed" asynchronously
9. Step 8: visitor edits certificate fields, posts /api/tamper, sees INVALID
10. Visitor clicks Finish, returns to home

## Gate enforcement logic

coroner.gate.gate_certificate:
- Input: certificate path, scope dict (cobol, java, schema, copybooks), base_dir
- Computes current file hashes from repository and compares with certificate
- Calls replay_certificate(cert_path, base_dir) if hashes match
- Returns: (status, replay result, hash_match)
  - status: "ALIVE" or "ZOMBIE" from certificate
  - replay result: "VALID" or "INVALID" or None
  - hash_match: True if current files match certificate hashes, False otherwise

The story endpoint maps these to exit codes:
- Exit 0 if status "ALIVE" and hash_match True and replay "VALID"
- Exit 1 otherwise (ZOMBIE, or hash mismatch, or INVALID replay, or missing certificate)
- Exit 2 not applicable in story (only for ERROR verdict when reference did not run)

Map exit codes to status strings:
- Exit 0: {status: "allowed", exit_code: 0, message: "Commit allowed"}
- Exit 1: {status: "blocked", exit_code: 1, message: "This ZOMBIE migration cannot be committed"}

Implementation: refactor a pure decision function gate_decision(status, replay, hash_match) -> exit_code from run_gate, used by both run_gate and the /api/gate-check endpoint to ensure identical exit codes.

## Rate limiting

/api/gate-check: same limiter as /api/verify, 1 per 10 seconds per client.

## Accessibility

- Keyboard navigation: arrow keys move between steps, enter advances, escape exits
- Focus visible on buttons
- Buttons min 44px height for touch
- Text min 16px
- Verdict badges include text label (not color only)

## Responsive design

At 375px width:
- Stack all content vertically
- Full-width buttons
- Text wraps
- Amounts and code blocks scroll horizontally if needed (rare, most content fits)

## Error handling

- Invalid step number: redirect to step 1
- Missing bundled run: display error "Bundled demo runs missing. Run docker compose up to generate them."
- Gate check on non-existent run_id: return 404

## Integration with existing modules

- Reuses coroner.gate.gate_certificate (reads certificate, builds scope, checks hashes, calls replay_certificate with base_dir, returns status/replay/hash_match)
- BUG FIX: gate_certificate must pass base_dir to replay_certificate (currently drops it), included as a task
- Reuses coroner.certificate.replay_certificate(cert_path, base_dir) for the actual replay
- Reuses replay_with_timeout from coroner/ui/app.py to run replay off the event loop with timeout (like /api/verify)
- Reuses existing run data loading from coroner/ui/app.py
- Reuses existing rate limiter (1 per 10 s per client for gate-check)
- No new CLI or MCP changes

## Security

- Run ids validated (12 hex)
- Gate check read-only, no execution
- Rate limited like Verify
- Cache-Control: no-store on /api/gate-check

## Dependencies

No new dependencies. Uses existing FastAPI, htmx, Jinja2.
