# Guided Story Requirements

## Overview

A guided story on Case 1 ("The Missing Branch", trap T1) for a non-technical visitor, plus a second page, "Can you fool Coroner?", with three toggles that each inject one real defect. Both pages read only measured files (run files, the trap catalog, trap metadata, the COBOL source) and the real gate endpoint. Nothing measured is typed in a template.

The story has 8 steps: bank process, COBOL result, Java migration, Coroner compares, where and why, apply the fix, ALIVE certificate, try to cheat.

Every page has a Business view (plain language) and an Engineer view (the same step with technical details), and a legacy listing panel that shows the COBOL lines that matter for the current step, read from the COBOL file.

Task 1 of the earlier version of this spec (POST /api/gate-check) is built and stays as it is (docs/reviews.md R-114, R-120, R-128, R-132). Where this document describes that endpoint it describes what was built.

## Requirements (EARS format)

### Req 1: Story structure
**WHERE** the home page is loaded, the system **SHALL** display one large link "Try the bank failure" that opens the story.

**WHERE** the story is opened, the system **SHALL** display exactly 8 steps in sequence:
1. Bank process (the nightly branch reconciliation batch)
2. COBOL result (the reference output: branch subtotals and grand total)
3. Java migration (the Java grand total next to the COBOL grand total)
4. Coroner compares (the audit verdict and the real gate)
5. Where and why (the autopsy: cause of death, time of death, exhibits)
6. Apply the fix (the business fix and the rule the Java port must reproduce)
7. ALIVE certificate (the audit of the corrected port and the real gate)
8. Try to cheat (Tamper on the certificate of the rejected migration gives INVALID)

**WHERE** a step is displayed, the system **SHALL** show "Step N of 8", a Back link and a Next link; Back is absent at step 1 and Next reads "Finish" at step 8 and goes to the home page.

**WHERE** a step number outside 1 to 8 is requested, the system **SHALL** redirect to step 1.

**WHERE** a visitor opens /story/step/N directly, the system **SHALL** return the full page (shell plus step); **WHERE** the request carries the HX-Request header, the system **SHALL** return only the step fragment, with the header `Vary: HX-Request`.

### Req 2: Accessibility
**WHERE** the story or the "Can you fool Coroner?" page is displayed, the system **SHALL** meet all of the following:
- Every interactive element is reachable and operable with the keyboard, with a visible focus indicator.
- Next and Back are real links (`<a href>`), so they work with the keyboard and without JavaScript; htmx only enhances them.
- After a step change the focus moves to the step heading (`tabindex="-1"`), so a keyboard or screen reader visitor is not left on a removed element.
- Left and Right arrow keys go to the previous and next step, Escape returns to the home page. These shortcuts **SHALL NOT** fire when focus is in an input, select, textarea or button, or when a modifier key is held. The Enter key is not bound globally: the native behavior of the focused link or button is kept (this replaces the earlier requirement that Enter advances the story).
- Every region that changes after an asynchronous request (gate result, audit progress and result, Tamper result, toggle counter) is a live region: `role="status" aria-live="polite"` for progress and results, `role="alert"` for errors (429, 503, 404, validation failure).
- A verdict is never conveyed by color alone: each carries its text label and its shape (ALIVE green circle, ZOMBIE red square, INVALID amber triangle, ERROR grey diamond), reusing the existing badge styles (D-56).
- Text and badge colors keep the contrast ratios already tested in tests/test_ui_pages.py and tests/test_ui_app.py in dark and light mode; new elements use the existing CSS variables.
- The listing panel scrolls horizontally inside its own container, which has `tabindex="0"`, `role="region"` and an `aria-label` naming the file and lines, so a keyboard visitor can scroll it.
- Animations respect `prefers-reduced-motion` (already in base.html).
- Every form control has a visible `<label>`; buttons have at least 44 px height.

### Req 3: Measured values only
**WHERE** any step or page shows a number, verdict, count, amount, branch code, run id, line number or certificate status, the system **SHALL** read it at request time from one of these sources and from no other:
- `runs/<run_id>/verdict.json`, `branch_reconciliation.json`, `failure_report.json`, `card.txt`, `comparison_results.json`, `inputs.json`, `certificate.json`, `timing.json`, `generated_cases.csv`
- `runs/trap_catalog.json` (run ids and per-trap counts)
- the JSON body of POST /api/gate-check, /api/tamper and the job status of /api/run
- samples/traps/<trap folder>/trap.json and the COBOL file named in `inputs.json`

**WHERE** a run id is needed, the system **SHALL** read it from `runs/trap_catalog.json` (`faulty_run_id`, `correct_run_id` of the trap entry). No run id is typed in code, templates or tests. (The earlier version of this spec typed f584d5f35228 and 29c15f04407b; both appear in the local catalog today, but the story must not depend on them.)

**WHERE** a step says "transactions", the system **SHALL** use the number of data rows of `generated_cases.csv`; **WHERE** it says "test batches" or "cases", the system **SHALL** use `cases_total` of `verdict.json`. A case of Case 1 is a batch of transactions, so the two numbers differ and must not be mixed (the earlier draft said "2000 transactions" for 2000 cases).

**WHERE** a step names where the COBOL ran, the system **SHALL** say "the COBOL program" or "the COBOL reference", never "the mainframe": the reference runs under GnuCOBOL and Coroner does not emulate z/OS.

**WHERE** a step shows a certificate as VALID, the system **SHALL** take that result from the real replay (the gate-check or Verify response), never from a field of `certificate.json` (the file has no validity field).

**WHERE** a measured file or the catalog is missing, the system **SHALL** show "Bundled demo runs missing. Run docker compose up to generate them." in a `role="alert"` region and **SHALL NOT** show any default number.

**WHERE** a step shows business cause, business fix, technical cause or fix sentence, the system **SHALL** read it from trap.json.

### Req 4: The real gate and the existing endpoints
**WHERE** steps 4 and 7 show enforcement, the system **SHALL** call the built POST /api/gate-check logic (form field `run_id`; response `{status: "blocked"|"allowed", exit_code, message}`; 404, 413, 422, 429 with Retry-After, 503 `{status: "unavailable"}` when a replay did not complete; responses cached by the SHA-256 of the certificate file bytes for 600 s; the gate-check rate bucket is consumed only when a replay is about to start). The text "This ZOMBIE migration cannot be committed" and "Commit allowed" are the endpoint's `message` values, printed as returned.

**WHERE** the story needs HTML for these results, the system **SHALL** add story fragment routes that call the same route functions as the API (`gate_check`, `run_audit`, `job_status`, `tamper_certificate`), parse their JSON or HTML result and render a fragment. The fragment routes **SHALL NOT** copy validation, rate limiting, caching, the queue, the replay or the tamper logic, so every limit of D-54 applies unchanged. (Reason: htmx would insert the raw JSON of the API routes into the page.)

**WHERE** a gate-check or run request is answered 429, 503 or 404, the fragment **SHALL** show the endpoint's message, the Retry-After seconds when present, and a "Check again" or "Try again" button; it **SHALL NOT** retry automatically.

**WHERE** a story step is displayed, the gate check **SHALL** start only when the visitor presses "Check the gate" (the replay uses CPU and a visitor who moves quickly from step 4 to step 7 would otherwise hit the 1 per 10 seconds bucket).

**WHERE** the story needs Tamper, the system **SHALL** reuse POST /api/tamper (fields `run_id`, `status`, `cases_total`, `cases_divergent`, `random_seed`; HTML fragment result). The form **SHALL** contain only keys that exist in a real `certificate.json`; if `cases_total` is not a certificate key (the certificate records `case_count`) the task that builds step 8 reports it and fixes it with a test.

### Req 5: Works from bundled runs, optional "run it yourself"
**WHERE** the visitor never starts an audit, the story **SHALL** work entirely from the bundled runs generated by scripts/init_demo_runs.sh. That script runs `coroner verify` for T1 faulty (exit 1), T1 correct (exit 0), credit-fees correct and the credit-fees HALF_EVEN variant, then `python -m coroner traps`, which runs the faulty and the correct port of T1 to T5 at 2000 cases, seed 42, into CORONER_BASE_DIR/runs and writes `trap_catalog.json` and `trap_catalog.txt`. The story and the fool page therefore need no new audit.

**WHERE** steps 4 and 7 show an audit, they **SHALL** display the bundled run by default and offer "Run it yourself" with fields seed and cases (bounds of /api/run: seed 0 to 1000000, cases 10 to 2000; the port is fixed by the step: faulty at step 4, correct at step 7).

**WHERE** the visitor's audit is accepted (202), the fragment **SHALL** poll a story job fragment route every 2 seconds with htmx (`hx-trigger="every 2s"`) inside a live region, stop when the job is done or in error, and then show that run's numbers read from its `verdict.json`.

**WHERE** /api/run answers 200 with `cached: true` (identical parameters reuse the engine's run id), the fragment **SHALL** say that this exact audit already exists and show the stored run.

### Req 6: Plain English
**WHERE** a step is shown in the Business view, the system **SHALL** use words a bank operations manager understands, state the business effect first (a branch does not reconcile, the grand total still balances) and keep technical terms to the Engineer view.

**WHERE** step 1 is displayed, the system **SHALL** describe the business process: every night the bank reconciles branch subtotals to catch posting errors before opening.

**WHERE** step 8 is displayed, the system **SHALL** explain that editing a certificate makes it INVALID, so the audit result cannot be faked.

### Req 7: Phone width
**WHERE** the story or the fool page is displayed at a viewport of 375 px, the system **SHALL** stack content vertically, use at least 16 px body text and 44 px tap targets, and avoid horizontal page scroll (tables and listings scroll inside their own container).

### Req 8: Design and htmx
**WHERE** the story changes step, the system **SHALL** use htmx (`hx-get` with `hx-target="#story-content"` and `hx-push-url` to the step URL) on the same links that work without it, and plain HTML otherwise. No new JavaScript library. The only custom script is the keyboard shortcut handler (about 20 lines), served as a static file.

**WHERE** a step shows a verdict, amounts or code, the system **SHALL** reuse the existing verdict badges, right-aligned amounts and monospace code styles.

### Req 9: Tests
**WHERE** the story and the fool page are tested, the system **SHALL** include tests with FastAPI TestClient and real runs, with one test per step and one per toggle state. Each test reads the expected values from the same files the page reads (Req 3) through a test helper and compares them with the response, never with a literal.

**WHERE** a test needs runs, it **SHALL** produce them with the real engine in a temporary CORONER_BASE_DIR (a session-scoped fixture that runs `run_catalog` with a small case count, as tests/test_gate_check.py does with `engine_runs`), assert that `runs/` of the repository is unchanged, and **SHALL NOT** skip when a run is missing (CORONER_NO_SKIP=1 applies). The case count of the fixture is the smallest at which the T1, T2 and T4 faulty ports are all ZOMBIE; the implementer measures it and records it in the fixture. Tests that need these runs carry the `slow` marker (they run in `make test-all` and `make acceptance`); tests that need no run (registry, listing extractor, navigation, shell, positioning sentence, accessibility attributes, no em dash) stay in the default suite.

**WHERE** a test checks gate enforcement, it **SHALL** call the real gate logic through the route, not a mock.

### Req 10: Constraints
**WHERE** any file is created or modified, the system **SHALL NOT** use the em dash character, create summary or helper files, or leave files at the repository root. A new file at the root or in scripts/ must first be listed in docs/architecture.md.

### Req 11: Case names
**WHERE** a page or document names a case, the system **SHALL** use one registry, `samples/traps/cases.json`, with these entries and no others:

| Trap | Case | Name |
|---|---|---|
| T1 | 1 | The Missing Branch |
| T2 | 2 | The Vanishing Cent |
| T3 | 3 | The Negative That Wasn't |
| T4 | 4 | The Sign of Zero |
| T5 | 5 | The Silent Zero |
| T6 | 6 | reserved |

The display form is "Case N Name" ("Case 6 reserved" for T6, with no numbers). The registry is read at request time. It **SHALL** be used by: the story, the fool page, the Detection Matrix page, the Run audit sample selector on the home page, the run page header, the entries of `runs/trap_catalog.json` (new fields `case_number`, `case_name`), and a test that compares the case names in the README trap table with the registry. The names sit beside the existing `business_name` of each trap.json (D-55), which is kept as the descriptor (for example "Branch subtotal mismatch").

### Req 12: Legacy listing panel
**WHERE** a story step has listing anchors, the system **SHALL** show the COBOL source lines named by those anchors, read from the COBOL file recorded in the run's `inputs.json`, with their real line numbers from the file. The lines are never copied into a template, trap.json or a test.

**WHERE** anchors are defined, they **SHALL** be stored in trap.json (key `listing`, a list of objects `{id, label, start_pattern, until_pattern}`; the range runs from the first line matching `start_pattern` to the line before the next line matching `until_pattern`, trailing blank lines dropped). Line numbers are found at request time, so a change to the COBOL file moves the displayed numbers and never shows a wrong one. A pattern that matches no line gives a visible error in the panel, not an empty panel.

**WHERE** the file has a known executed-line list for the run (the "COBOL lines involved" of `card.txt`, which come from the minimal case trace), the panel **SHALL** mark those lines as executed in the minimal case, with text ("executed") and not only a color.

For Case 1, the anchors are, with the line numbers of MATCH-MERGE.cob in the current tree (the listing test recomputes them from the file independently and compares):
- `collation`: SPECIAL-NAMES through PROGRAM COLLATING SEQUENCE, lines 10 to 13 (line 11 `ALPHABET EBC IS EBCDIC.`, line 13 `PROGRAM COLLATING SEQUENCE IS EBC.`)
- `table`: the branch table moves, lines 79 to 87 (A01, B02, C03, D04, E05, F06, Z99, 001, 9ZZ in EBCDIC order)
- `sort`: the SORT statement, lines 90 to 95 (line 93 `COLLATING SEQUENCE IS EBC`)
- `match`: the BALANCE-LINE paragraph, lines 201 to 223 (line 204 `IF TABLE-CODE(TABLE-INDEX) < TXN-BRANCH`, line 207 `IF TABLE-CODE(TABLE-INDEX) = TXN-BRANCH`, line 212 the amount goes to suspense)

Steps and anchors: step 1 `table`; step 2 `collation` and `sort`; step 5 and step 6 `match`; steps 3, 4, 7 and 8 show no panel.

**WHERE** the Business view is active, the panel **SHALL** be a closed `<details>` titled "Show the COBOL lines"; **WHERE** the Engineer view is active, the panel **SHALL** be open.

### Req 13: Business and Engineer views
**WHERE** a story step or the fool page is displayed, the system **SHALL** offer two links, "Business view" and "Engineer view", in a labelled navigation (`aria-label="View"`, `aria-current="true"` on the active one). The view is the query parameter `view` (`business`, default, or `engineer`; any other value gives business) and is carried by every Next, Back, fragment and form of the page.

**WHERE** the Engineer view is active, the system **SHALL** show the same step with technical details taken from files, at least: the run id, the seed and the case count (`inputs.json`), the duration (`timing.json`), the divergent field and output key (`failure_report.json` `divergent_fields`), the COBOL lines executed (`card.txt`), the exposure sum, maximum, affected branches and suspense difference (`verdict.json`), and the first 12 characters of `certificate_sha256` (`certificate.json`), each only on the steps where it applies. The Business view shows none of these labels.

### Req 14: Autopsy vocabulary
**WHERE** step 5 shows a ZOMBIE run, the system **SHALL** use these three headings, each over measured data:
- "Cause of death": the divergent field and the COBOL rule broken. Business view: `business_cause` of trap.json. Engineer view: the `kind`, `output_key` and field names of the first `divergent_fields` entries of `failure_report.json`, the `technical_cause` of trap.json, the `cobol_rule` text of trap.json (new key, one sentence written from the COBOL source of the trap, for Case 1 "Branch codes are compared in EBCDIC order: PROGRAM COLLATING SEQUENCE IS EBC") and the line numbers of its anchor (Req 12), never typed.
- "Time of death": the first divergent case in the order of `comparison_results.json` (its case id and its position "case k of N", with N = `cases_total`). It is not the minimal case; the minimal case is shown as the example under "Exhibits".
- "Exhibits": a numbered list of the evidence files that exist for the run, each with its file name and a download link through the existing download route: the certificate (`certificate.json`), the failure report (`failure_report.json`), the minimal case (`minimal_case_input.csv`, with the Given and Then lines of `card.txt` shown as text) and the JUnit test (`ZombieRegressionTest.java`). A missing file is omitted, never shown as a dead link.

**WHERE** the run is ALIVE (step 7), the system **SHALL NOT** show "Cause of death" or "Time of death" (there is no divergent case); it **SHALL** show "Exhibits" with the certificate only.

### Req 15: Can you fool Coroner?
**WHERE** the page /fool is opened, the system **SHALL** show exactly three toggles, each injecting one real defect by switching from the correct port to the faulty port of one trap:
1. Case 1 The Missing Branch (T1): branch codes compared in ASCII order instead of EBCDIC order
2. Case 2 The Vanishing Cent (T2): the T2 faulty port (rounding rule ported wrongly; see Uncertain in tasks.md for the label)
3. Case 4 The Sign of Zero (T4): the zero overpunch characters "{" and "}" forgotten

**WHERE** a toggle is off, the system **SHALL** show the verdict of the correct port's bundled run; **WHERE** it is on, the verdict of the faulty port's bundled run. Both runs are found through `runs/trap_catalog.json` and their verdicts, case counts and divergent counts are read from `verdict.json`. No audit is started and no code is uploaded; the page says so in one sentence.

**WHERE** at least one toggle is on, the system **SHALL** show a counter "Coroner detected D of N injected defects", where N is the number of toggles that are on and whose faulty run exists, and D is the number of those runs whose `verdict.json` status is ZOMBIE. **WHERE** no toggle is on, the counter reads "No defect injected" and the page shows "Coroner certified C of M clean ports", with M the number of correct runs found and C the number whose status is ALIVE. Neither number is typed or assumed equal to the other.

**WHERE** a toggle's run is missing, the toggle **SHALL** be disabled with the message "Bundled run missing" and be left out of N and D.

**WHERE** the Engineer view is active, each toggle **SHALL** also show its run id, the divergent case count, the "COBOL lines involved" of the trap's catalog entry (`cobol_lines`), and, for T2, the divergent counts per output column (FEE1 and FEE2) computed from `comparison_results.json`.

**WHERE** JavaScript is unavailable, the toggles **SHALL** work as a plain GET form (checkboxes `case1`, `case2`, `case4` and an "Update" button, parameters in the URL); with htmx the form updates the result region on `change`, inside a live region.

**WHERE** a toggle is displayed, the system **SHALL** reuse `generate_zombie_sentence(trap_id, run_dir)` for its ZOMBIE sentence, so the sentence equals the one on that run's page.

### Req 16: Positioning sentence
**WHERE** any page of the story or the fool page is displayed (full page, outside the swapped fragment), the system **SHALL** show this exact sentence in visible text: "Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result."

### Req 17: Without JavaScript
**WHERE** JavaScript is disabled, the story and the fool page **SHALL** still show every text, number, verdict, listing, case name and view of Req 1, 3, 11 to 16 (server-rendered), with working Next, Back, Business view, Engineer view and toggle links. The three actions that start a replay or an audit (Check the gate, Run it yourself, Tamper) need htmx; a `<noscript>` message next to each says so and names the equivalent: the run page and the CLI command `python3 -m coroner verify <certificate.json>`.

## Done when
- The 8 steps, the Business and Engineer views, the listing panel, the autopsy headings, the fool page, the case registry and the positioning sentence exist and read only measured files and the real gate.
- No run id, count, amount, branch code, line number or certificate status is typed anywhere in code, templates or tests.
- Every async result is in a live region; keyboard use, focus move, contrast and 375 px width are tested.
- Text content works with JavaScript disabled.
- No em dash, no summary files, nothing at the repository root.
