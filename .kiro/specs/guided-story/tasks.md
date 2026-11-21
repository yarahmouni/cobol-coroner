# Guided Story Tasks

Order matters: each task builds on the previous ones. Every task ends with `pytest` of the files it touches plus the existing UI suites (tests/test_ui*.py, tests/test_gate_check.py) passing, and the operator's checks of docs/reviews.md. Tests that need runs use the session fixture of Req 9 and carry the `slow` marker.

## Task 1: Gate check endpoint and logic
- [x] BUG FIX in coroner/gate.py: gate_certificate must pass base_dir to replay_certificate (currently drops it); signature becomes gate_certificate(cert_path, scope, base_dir) -> (status, replay, hash_match) with replay_certificate(cert_path, base_dir) call
- [x] REFACTOR: extract pure decision function gate_decision(status, replay, hash_match) -> exit_code from run_gate logic, used by both run_gate and the /api/gate-check endpoint; also extract certificate_matches_files(cert, scope, repo_root) -> bool for hash checking
- [x] Add POST /api/gate-check route in coroner/ui/app.py (form-encoded, not path parameter)
- [x] Validate form field run_id (12 lowercase hex)
- [x] Read certificate from CORONER_BASE_DIR/runs/{run_id}/certificate.json (1 MB limit, 413 beyond)
- [x] Build scope from certificate: {cobol: cert["cobol_file"], java: cert["java_file"], schema: cert["schema_file"], copybooks: cert["copybook_dir"]}
- [x] Call certificate_matches_files and replay_with_timeout (not gate_certificate, which would replay on the event loop); compute exit_code from gate_decision
- [x] Run replay with replay_with_timeout (same function as /api/verify, off the event loop, 90 s default timeout)
- [x] Return JSON: {status: "allowed" or "blocked", exit_code: 0 or 1, message: "Commit allowed" or "This ZOMBIE migration cannot be committed"}
- [x] Rate limit: reuse existing limiter, 1 per 10 seconds per client (same as /api/verify and /api/tamper)
- [x] Cache-Control: no-store, no-cache on all responses (success and error)
- [x] Cache response by certificate SHA-256 for 600 s, so repeated story visits do not start a new replay
- [x] Test: POST with form data run_id=f584d5f35228 (bundled T1 faulty), assert {status: "blocked", exit_code: 1}
- [x] Test: POST with form data run_id=29c15f04407b (bundled T1 correct), assert {status: "allowed", exit_code: 0}
- [x] Test: POST with invalid run_id, assert 422
- [x] Test: POST with non-existent run_id, assert 404
- [x] Test: response has Cache-Control: no-store
- [x] Test: run_gate and /api/gate-check give the same exit code on the same certificate (test run_gate and POST /api/gate-check with same inputs, assert identical exit codes)
- [x] Test: gate_decision table covering every branch
- [x] Test: second POST within 600 s returns cached response without replay
- [x] Test: certificate edited after first call is not served from cache

**Requirements:** 3, 4
**Done when:** POST /api/gate-check endpoint works, calls real gate logic with base_dir fix, runs replay off the event loop, returns correct status for ZOMBIE and ALIVE runs, rate limited, no-store, tests pass.

## Task 2: Case registry and case names
- [x] Create samples/traps/cases.json with the six entries of Req 11 (T1 to T6). Proof: tests/test_story_registry.py::test_registry_has_exactly_the_six_entries. The loader is coroner/cases.py (shared by coroner/traps.py and the UI).
- [x] coroner/traps.py: add `case_number` and `case_name` from the registry to every catalog entry including the T6 placeholder; trap_catalog.txt prints "Case N Name". Proof: tests/test_story_registry.py::test_catalog_entries_carry_case_number_and_name and ::test_catalog_text_prints_case_names (slow).
- [x] Matrix page (matrix.html and matrix_page in coroner/ui/app.py), the Run audit sample selector in index.html and the run page header read the names from the registry; the typed labels "T1 (EBCDIC collation)" and the like are removed from index.html. The Matrix gets a "Case" column beside the Trap column. Proof: tests/test_story_registry.py::test_home_selector_reads_the_registry, ::test_templates_have_no_typed_sample_labels, ::test_matrix_and_run_page_show_case_names (slow).
- [ ] README trap table: add the case name to each row (T6 row "Case 6 reserved"). NOT DONE in this call: the call forbade editing README.md. The docs track makes this edit; then the test "README table names equal the registry" is added.
- [x] Do not touch `business_name` in any trap.json (untouched).
- [x] Test (fast): registry has exactly the six entries; every trap folder T1 to T6 has a registry entry; home selector shows the case names; T6 shows "Case 6 reserved" and no measured number. The Matrix and run page checks need a real catalog, so they carry the slow marker (test_matrix_and_run_page_show_case_names). The README part is open (previous item).
- [x] Test (slow): the catalog written by `run_catalog` in a temporary base has `case_number` and `case_name` for each entry. The README numbers are untouched because README.md was not edited; they are not recomputed at the fixture's 9 cases.
- [x] Report to the owner of docs/video-plan.md that its MEASURED markers name `unreconciled_exposure.sum` and `unreconciled_exposure.branches_affected` while verdict.json has `exposure_sum` and `affected_branches`; not edited. Reported in the answer of this call.

**Requirements:** 11
**Done when:** `pytest tests/test_story_registry.py` passes; grep of coroner/ui/templates for "EBCDIC collation)" and "(rounding)" in the sample selector returns nothing; `make traps` output contains "Case 1 The Missing Branch"; the existing Matrix tests still pass with the new names.

## Task 3: Story data layer (coroner/ui/story.py)
- [x] Create coroner/ui/story.py with the functions listed in design.md: load_cases_registry, load_catalog, load_run, first_divergent_case, exhibits, transaction_count, t2_column_counts, normalize_view (listing and fool_state come in tasks 4 and 12). `listing` is done in task 4. Proof: tests/test_story_data.py.
- [x] Typed error for a missing catalog or run, with the message "Bundled demo runs missing. Run docker compose up to generate them." (StoryDataError). Proof: test_missing_catalog_gives_the_typed_error, test_missing_run_gives_the_typed_error, test_a_catalog_run_missing_on_disk_is_the_typed_error.
- [x] No default numbers: an absent optional file gives None. Proof: test_absent_files_give_none_not_defaults, test_missing_optional_file_in_a_copy_gives_none. Finding: the runs written by `run_catalog` have no timing.json (only `coroner verify` writes it), so `Run.timing` is None for them unless the same run was also made by the CLI (init_demo_runs.sh does that for T1 first). Step 4 must show "not recorded" for the duration when it is None.
- [x] Move any helper shared with the run page into story.py or pages.py and import it from the run page; run page output unchanged. Done: `parse_card` and `RUN_ID_PATTERN` moved to coroner/ui/pages.py; the run page and app.py import them. Proof: test_parse_card_splits_the_sections_and_keeps_file_names, test_run_page_still_shows_the_card_it_parses (slow), and the existing UI suites.
- [x] Session fixture `story_runs` in tests/conftest.py: real `run_catalog` in a tmp base, case count 9 (the smallest where the T1, T2 and T4 faulty verdicts are ZOMBIE: T1 4, T2 7, T4 1 divergent cases, seed 42; at 8 cases T4 is ALIVE), asserts repository runs/ unchanged. The measured counts are in the fixture docstring. Risk for task 9: with 4 divergent T1 cases the first divergent case may be the minimal case; the test that needs them to differ may need a larger count.
- [x] Tests (slow): each function against real files, with expected values computed independently in the test. Proof: tests/test_story_data.py (slow tests).
- [x] Tests (fast): normalize_view table; typed error when the catalog is missing. Proof: test_normalize_view_table, test_missing_catalog_gives_the_typed_error.

**Requirements:** 3, 9, 13, 14
**Done when:** `pytest tests/test_story_data.py` passes in a clean checkout (no local runs/ folder); the fixture docstring states the measured case count; `git status` shows no change under runs/.

## Task 4: Legacy listing extractor and anchors
- [x] Add `listing` anchors and `cobol_rule` to samples/traps/T1-ebcdic-match-merge/trap.json: anchors `collation`, `table`, `sort`, `match` with start and until patterns as in Req 12. `cobol_rule` is "Branch codes are compared in EBCDIC order, which the program sets with its alphabet and collating sequence clauses." (the spec's example quoted a COBOL clause, which the rule "no line of MATCH-MERGE.cob text in trap.json" forbids). Proof: tests/test_story_listing.py::test_anchors_equal_an_independent_scan_of_the_real_file.
- [x] Implement `listing()` in story.py: resolve the COBOL path from the run's inputs.json under samples/traps (`resolve_cobol_path`), find line numbers by pattern, return line number, text and executed flag (from the "COBOL lines involved" of card.txt, `executed_lines_from_card`), explicit error object when a pattern matches nothing. Proof: test_pattern_matching_nothing_gives_an_explicit_error_not_an_empty_panel, test_resolve_cobol_path_refuses_other_files.
- [x] Render function for the panel (`render_listing`: details closed in Business view, open in Engineer view, region with tabindex and aria-label, HTML escaped, "executed" word on marked lines). Proof: test_render_views_region_attributes_and_executed_word, test_special_characters_in_a_source_line_are_escaped. No CSS yet (task 13): the markup carries classes story-listing, story-listing-region, listing-line, listing-number, listing-executed.
- [x] Test (fast): on the real MATCH-MERGE.cob the anchors give 10 to 13, 79 to 87, 90 to 95 and 201 to 223; the test computes these ranges itself by scanning the file for the patterns, and asserts the numbers above only as a sentinel (test_anchors_equal_an_independent_scan_of_the_real_file, test_sentinel_line_numbers_of_the_spec).
- [x] Test (fast): a copy of the file with three lines inserted before line 10 gives numbers shifted by 3 (test_three_inserted_lines_shift_every_number_by_three); a pattern that matches nothing gives the explicit error, not an empty panel; `<`, `&` and `"` in a source line are escaped.
- [x] Test (slow): executed lines marked on `match` equal the line numbers of the card.txt "COBOL lines involved" of the T1 faulty run (test_executed_lines_on_match_equal_the_card_lines_of_the_t1_faulty_run).

**Requirements:** 12
**Done when:** `pytest tests/test_story_listing.py` passes; changing a line number in the COBOL copy changes the rendered number in the same test; no line of MATCH-MERGE.cob text appears in any template, trap.json or test file (grep for `PROGRAM COLLATING SEQUENCE` in coroner/ui/templates returns nothing).

## Task 5: Story shell, step routing, views, positioning sentence, keyboard
- [ ] coroner/ui/templates/story.html (extends base.html): heading, the positioning sentence of Req 16 as visible text, the Business and Engineer view links (labelled nav, aria-current), "Step N of 8", `<main>` containing `#story-content`
- [ ] Routes GET /story (step 1) and GET /story/step/{n}: full page without HX-Request, fragment with it, `Vary: HX-Request`, `Cache-Control: no-store`, redirect to step 1 for n outside 1 to 8, `view` parameter carried in every link
- [ ] Next and Back are `<a href>` with hx-get, hx-target and hx-push-url; Finish links to /
- [ ] Step heading `tabindex="-1"` and focus move after swap
- [ ] coroner/ui/static/story.js (guards of Req 2) loaded with `defer`; no inline script
- [ ] `<noscript>` notes slot used by later tasks
- [ ] Test (fast): full page contains the exact positioning sentence, "Step 1 of 8", the two view links with the correct aria-current; fragment request returns no `<html>`; step 9 and step 0 redirect to step 1; `view=engineer` is carried in Next and Back; unknown view gives business; Vary and no-store headers; story.js text contains the guard conditions

**Requirements:** 1, 2, 8, 13, 16, 17
**Done when:** `pytest tests/test_story_shell.py` passes; the page is usable with Tab and Enter only (checked by the operator with Chrome, result in the review entry); `grep -c "<script>" coroner/ui/templates/story.html` is 0.

## Task 6: Steps 1 to 3
- [ ] Step 1 (bank process) with the `table` listing; Engineer details per design.md
- [ ] Step 2 (COBOL result): prose, transactions and cases from files, branch table with COBOL subtotals and the suspense row, COBOL grand total, `collation` and `sort` listings; no verdict badge
- [ ] Step 3 (Java migration): the two grand totals and "They match." or "They differ." decided by comparing the values; no verdict; Engineer shows the Java file name from certificate.json
- [ ] Fast tests where no run is needed (step 1 text, listing lines equal the file); slow tests for steps 2 and 3: every number in the response equals the value read from branch_reconciliation.json, verdict.json and generated_cases.csv by the test; the response contains "They match." only when the two grand totals read from the file are equal; the Business page contains no Engineer label and the Engineer page contains the run id and seed read from inputs.json
- [ ] Test: "mainframe" does not appear in any step (Req 3)

**Requirements:** 1, 3, 6, 12, 13
**Done when:** `pytest tests/test_story_pages.py -k "step1 or step2 or step3"` passes with the slow marker; changing one subtotal in a temporary copy of branch_reconciliation.json changes the displayed number in the test (proves it is read, not typed).

## Task 7: Fragment routes for the gate, Run it yourself and job polling
- [ ] POST /story/gate-check calls `gate_check` and renders: blocked (red square), allowed (green circle), invalid certificate (amber triangle), 429, 503, 404, 413, 500 as in design.md; live regions; "Check again" button; no automatic retry
- [ ] POST /story/run calls `run_audit` with sample T1, port fixed by the step, seed and cases from the form; 202 returns the polling div; 200 cached; 422 and 429 alerts
- [ ] GET /story/job/{job_id} calls `job_status` and returns the polling div, the finished result (verdict badge, divergent count read from the run's verdict.json, link to the run) or the error alert; polling stops when done
- [ ] Both fragments carry `view`
- [ ] Tests (slow): blocked for the T1 faulty run and allowed for the T1 correct run through the real route (same assertions as tests/test_gate_check.py: message equals the endpoint's message); 429 with CORONER_GATE_CHECK_RATE_WINDOW=3600 shows the Retry-After seconds from the response header; 503 with CORONER_REPLAY_TIMEOUT=1 shows the unavailable alert and a second request starts a new replay; run it yourself with the real worker on 20 cases (temporary exchange directory, as tests/test_ui_run_audit.py does) shows the numbers from the new run's verdict.json and the polling div disappears when done; identical parameters give the cached message
- [ ] Test: the fragment routes use no limiter of their own (the module has no new check_rate_limit key; the test counts calls to check_rate_limit made through the route and equals those of the API route)
- [ ] Test (fast): every dynamic region has `role="status"` and `aria-live="polite"` or `role="alert"`

**Requirements:** 2, 4, 5
**Done when:** `pytest tests/test_story_fragments.py` passes; the gate fragment's text for each case equals the JSON message returned by `/api/gate-check` for the same run in the same test; no replay or audit code is duplicated (grep for `replay_with_timeout` in the new fragment code finds no call).

## Task 8: Step 4 (Coroner compares)
- [ ] Step 4 template: prose, verdict badge, ZOMBIE sentence from `generate_zombie_sentence`, "{cases_divergent} of {cases_total} batches diverge", three figures, the gate form (button "Check the gate"), Run it yourself (faulty), `<noscript>` note
- [ ] Engineer details: run id, seed, duration from timing.json, exposure maximum, suspense difference, return codes
- [ ] Tests (slow): each figure equals the file value; the gate form targets /story/gate-check with the faulty run id read from the catalog; the ZOMBIE sentence equals the one on that run's page; Business view has no run id

**Requirements:** 1, 3, 4, 5, 13
**Done when:** `pytest tests/test_story_pages.py -k step4` passes; clicking "Check the gate" in Chrome (operator check) shows "This ZOMBIE migration cannot be committed" in the live region and the review entry records it.

## Task 9: Step 5 (where and why, autopsy)
- [ ] Mismatch-only branch table, "N other branches match", "Posted to suspense instead of a branch" from branch_reconciliation.json
- [ ] "Cause of death", "Time of death", "Exhibits" per Req 14, both views; the example from card.txt Given and Then lines; the `match` listing with executed lines marked
- [ ] Exhibit links use the existing download route; omit files that do not exist
- [ ] Tests (slow): Cause of death Business text equals trap.json `business_cause`; Engineer view lists the `kind` and `output_key` of the first two `divergent_fields`, `technical_cause`, `cobol_rule` and the anchor line numbers recomputed from the file; Time of death case id and "case k of N" equal an independent scan of comparison_results.json and differ from the minimal case id in the T1 run (assert the two are computed separately); Exhibits equal the file list of the run folder; deleting `ZombieRegressionTest.java` from a temporary copy removes that exhibit
- [ ] Test (slow): the example text equals card.txt lines, and does not equal the `input_row` of failure_report.json (guards the observed trap)

**Requirements:** 3, 6, 12, 13, 14
**Done when:** `pytest tests/test_story_pages.py -k step5` passes; the page shows the three autopsy headings and no heading appears on step 7.

## Task 10: Steps 6 and 7
- [ ] Step 6: prose, `business_fix` (Business) or `fix_sentence` (Engineer) from trap.json, `match` listing
- [ ] Step 7: prose, verdict badge for the correct run, "{cases_divergent} of {cases_total} batches diverge", exposure sum, gate form, Run it yourself (correct), Exhibits with the certificate only, no Cause or Time of death
- [ ] The certificate is described as valid only through the gate result; no certificate field is read as a validity flag
- [ ] Tests (slow): step 6 text equals the trap.json fields; step 7 figures equal verdict.json of the catalog's correct run; the page has no "Cause of death" and no "Time of death"; gate allowed through the real route returns "Commit allowed"

**Requirements:** 1, 3, 4, 5, 12, 13, 14
**Done when:** `pytest tests/test_story_pages.py -k "step6 or step7"` passes.

## Task 11: Step 8 (try to cheat)
- [ ] From a real certificate.json and the code of tamper_certificate, list which form fields are real certificate keys; the certificate records `case_count` while the endpoint sets `cases_total`: report the finding in the review entry, and fix with a test if editing that field does not change what is replayed
- [ ] Step 8 template: Tamper form for the T1 faulty run prefilled from its certificate.json, instruction line, result region, closing sentence; `<noscript>` note
- [ ] POST /story/tamper calls `tamper_certificate`; 429 and 422 become alerts
- [ ] Tests (slow): the form values equal certificate.json; posting status ALIVE and divergent 0 gives "Certificate: INVALID" and the replay reason from the real response; the original certificate's SHA-256 is identical before and after; posting the unmodified values gives VALID; a 429 shows an alert with the retry time
- [ ] The Finish link goes to /

**Requirements:** 1, 4, 6, 13
**Done when:** `pytest tests/test_story_pages.py -k step8` passes; the finding about the case-count key is written in docs/reviews.md by the operator with its test result.

## Task 12: "Can you fool Coroner?" page
- [ ] `fool_state` in story.py and GET /fool with the GET form, three toggles, counter, clean-ports line, per-toggle sentence from `generate_zombie_sentence`, Engineer details (run id, divergent count, `cobol_lines` from the catalog entry, T2 FEE1 and FEE2 counts, the count of divergent T4 values ending in "}"), positioning sentence, one sentence stating that no code is uploaded and no audit starts
- [ ] Fragment update with htmx on `change`, live region; plain form without JavaScript
- [ ] Disabled toggle with "Bundled run missing" when a run is missing
- [ ] Tests (slow): for each of the 8 toggle combinations the counter equals counts computed by the test from the verdict.json files of the catalog runs; with none on, the page shows "No defect injected" and C and M from the correct runs; editing the verdict.json of one faulty run in a temporary copy to ALIVE lowers D and leaves N (the counter is computed); deleting a run folder disables its toggle and lowers N; each shown ZOMBIE sentence equals the sentence on the run page
- [ ] Test (fast): exactly three checkboxes named case1, case2, case4; labels present; the page lists the case names from the registry

**Requirements:** 2, 3, 13, 15, 16, 17
**Done when:** `pytest tests/test_story_fool.py` passes; the operator toggles each defect in Chrome and the counter text matches the three verdict files (recorded in the review entry).

## Task 13: Home page link, navigation and responsive layout
- [ ] index.html: large "Try the bank failure" link to /story and a link "Can you fool Coroner?" to /fool; story and fool pages link to each other and to the home page and Detection Matrix
- [ ] CSS in the existing variable system for the story, listing panel, toggles, and 375 px rules (stacked layout, 16 px text, 44 px targets, contained scrolling)
- [ ] Test (fast): home page contains the two links; stylesheet contains the 375 px rules; the new colors keep the contrast ratios of tests/test_ui_pages.py in both modes
- [ ] Operator check with Playwright and the installed Chrome at 375 px for the story steps 1 to 8 and /fool: no horizontal page scroll, targets at least 44 px, keyboard shortcuts and focus move work; screenshots kept out of the repository; result in the review entry

**Requirements:** 1, 2, 7
**Done when:** `pytest tests/test_story_shell.py -k home` passes and the operator's 375 px check is recorded.

## Task 14: Accessibility and no-JavaScript tests
- [ ] tests/test_story_a11y.py: positioning sentence present on every page type; Next and Back are `<a href>`; every async target has a live-region role; the listing region has tabindex and aria-label; form controls have labels; badges carry text and shape
- [ ] tests/test_story_nojs.py (slow): without HX-Request each step page contains its measured values, listing, case name and view links; the fool GET form with parameters shows the right counter; `<noscript>` notes exist next to the three action forms
- [ ] Record in the review entry that coroner/ui had no aria-live, role or noscript before this task (grep result) and that the pre-existing home Run audit region, Verify and Tamper pages are outside this spec

**Requirements:** 2, 17
**Done when:** `pytest tests/test_story_a11y.py tests/test_story_nojs.py` passes; the grep for `aria-live` in coroner/ui/templates lists the new story and fool templates.

## Task 15: Integration, constraints and full suite
- [ ] Navigate steps 1 to 8 through the real routes in one slow test, each step response containing its measured values from the files
- [ ] Test: no em dash in the new templates, story.js, story.py, cases.json, trap.json, and these three spec files
- [ ] Test: the repository root has no new file after the story and fool tests; runs/ of the repository is unchanged (listing before and after)
- [ ] Run `make test-all` and `make acceptance`; run the default suite in the CI image built from a clean export with CORONER_NO_SKIP=1 (`make smoke-ui`) and confirm no story test skips
- [ ] Update docs/architecture.md only for new files at the root or in scripts/ (none expected) and list the new routes in the review entry

**Requirements:** 9, 10
**Done when:** the three commands above exit 0 and their pass counts are recorded; `git status` shows only intended files.

## Task 16: Deploy check additions and hand-over notes
- [ ] scripts/deploy_check.py: after the existing checks add PASS or FAIL lines for GET /story/step/5 (contains "Cause of death", the positioning sentence and a branch table row) and GET /fool (contains "Coroner certified" or "Coroner detected" and three checkboxes); the expected texts are headings and structure, never numbers or run ids; `--skip-build` behavior unchanged
- [ ] Test the new checks against a real uvicorn and worker in temporary directories, as the existing deploy-check test does
- [ ] Hand over to the docs track (no edit here): a line for SECURITY.md (the /story fragment routes share the limits of /api/run, /api/gate-check and /api/tamper and add none of their own), a line for docs/judge-guide.md (the story and fool pages and their URLs), and the correction of the case names in other documents if any

**Requirements:** 4, 9
**Done when:** `make deploy-check URL=http://127.0.0.1:8000` against the compose stack prints the two new PASS lines and exits 0; the hand-over text is in the review entry.

## Coverage table

| Requirement | Tasks |
|-------------|-------|
| Req 1 (structure, 8 steps) | 5, 6, 8, 9, 10, 11, 13 |
| Req 2 (accessibility) | 5, 7, 12, 13, 14 |
| Req 3 (measured values only) | 3, 6, 8, 9, 10, 12 |
| Req 4 (real gate, fragments) | 1, 7, 8, 10, 11, 16 |
| Req 5 (bundled runs, run it yourself) | 7, 8, 10 |
| Req 6 (plain English) | 6, 9, 11 |
| Req 7 (phone width) | 13 |
| Req 8 (design, htmx) | 5 |
| Req 9 (tests) | 3, 15, 16 |
| Req 10 (constraints) | 15 |
| Req 11 (case names) | 2 |
| Req 12 (listing panel) | 4, 6, 9, 10 |
| Req 13 (Business and Engineer views) | 3, 5, 6, 8, 9, 10, 11, 12 |
| Req 14 (autopsy vocabulary) | 3, 9, 10 |
| Req 15 (fool page) | 12 |
| Req 16 (positioning sentence) | 5, 12, 14 |
| Req 17 (without JavaScript) | 5, 12, 14 |

## Uncertain:

1. Case 2 "The Vanishing Cent" and the "HALF_EVEN" toggle. The T2 faulty port has two defects (header of samples/traps/T2-rounding/java/faulty/RoundingCalc.java): FEE1 uses HALF_UP where the COBOL truncates, FEE2 uses HALF_EVEN where the COBOL ROUNDED is HALF_UP. Measured on the local T2 faulty run 26b427d5d678 (comparison_results.json, 2000 cases): 924 divergent fee values, 856 in FEE1 (445 higher, 411 lower in Java) and 68 in FEE2 (33 higher, 35 lower). So HALF_EVEN explains 68 of 924 differences; most of the divergence is truncation ported as rounding. The label "HALF_EVEN" would describe 7 percent of what the toggle shows, and "Vanishing Cent" fits only the lower-in-Java half. The pure HALF_EVEN defect is the credit-fees variant (run 08d14a07bcdb, 86 of 2000), which is not Case 2. The spec keeps the brief (toggle on T2) and adds the per-column counts in the Engineer view; the caption for Case 2 is left to the owner: either "Rounding rule ported wrongly" (accurate for T2) or switch the toggle to the credit-fees HALF_EVEN run (accurate for the label, but then it is not a catalog trap).
2. Case 3 "The Negative That Wasn't". T3 faulty reads positive amounts (sign nibble F) as negative (trap.json; 429 of 429 divergent values positive in COBOL and negative in Java, R-90). The name can be read in two opposite ways: an amount that was not negative but became negative (the real defect), or a negative that was not treated as negative. It fits the real defect only under the first reading. T3 is not used in the story or the toggles, only in the registry and catalog.
3. Case 4 "The Sign of Zero" fits (the faulty port forgets the zero overpunch characters). Measured R-87: only "}" (minus zero) diverges (87 of 2000); "{" (plus zero) does not, because the old handling also reads it as +0. A toggle caption saying "{ and } forgotten" is true of the code and incomplete about the effect; the Engineer view shows the count of "}" divergences from the file.
4. Case 1 "The Missing Branch" and Case 5 "The Silent Zero" fit what the traps do. For Case 5, trap.json `probable_cause` says the faulty port "rejects" invalid data while `business_name` says it is "silently treated as zero"; the measured R-90 effect is the zero (Java writes the fee alone). No README exists for T1 to T5 (only T6 has one), so the check used trap.json, the COBOL and Java files and R-90.
5. Two names per trap. D-55 gave business scenario names (trap.json `business_name`, for example "Branch subtotal mismatch" for T1, "Fee rounding difference" for T2). The brief gives story names. The spec keeps both: the case name is the title, `business_name` the descriptor. Confirm whether `business_name` should be dropped from the run page header.
6. "Time of death" is read literally as the first divergent case in generated order (comparison_results.json). That differs from the minimal case that the card, the JUnit test and the failure report describe. The spec shows both and labels them separately; confirm this is intended.
7. Keyboard: the earlier spec required Enter to advance. A global Enter handler duplicates the native action of a focused link or button and breaks form entry, so this version removes it and keeps arrows and Escape with guards. Confirm.
8. Step 8 uses the rejected (faulty) migration's certificate, not the ALIVE one: editing an ALIVE certificate to ZOMBIE cheats nothing. The earlier text used the correct run with a tamper message that does not match what that edit produces (R-104 recorded "expected ALIVE, got ZOMBIE" for the faulty run).
9. Existing /api/tamper sets `cases_total` while the real certificate records `case_count` (observed in coroner/ui/app.py and runs/f584d5f35228/certificate.json). Task 11 verifies and fixes if the edit has no effect. Not verified by running it in this call.
10. The earlier text of steps 2 and 4 said "2000 transactions" for 2000 cases and "mainframe" for the COBOL run. Both are corrected in Req 3 (a case is a batch; the run is GnuCOBOL, not a mainframe). The README demo excerpt and trap.json `business_fix` ("same order as the mainframe") still use "mainframe"; not changed here (D-55 text).
11. Fragment routes (/story/gate-check, /story/run, /story/job, /story/tamper) are a design choice: the API routes return JSON, and htmx would put raw JSON in the page. The alternative is the inline polling script of the home page. The spec chooses fragment routes that call the same route functions; if calling a route function from another route proves awkward (Request dependency, form parameters), extract the shared body into a function with no behavior change and unchanged tests.
12. The gate check starts on a button press, not on arrival at the step, to avoid replay CPU on every view and to avoid hitting the 1 per 10 seconds bucket when a visitor moves from step 4 to step 7. The earlier spec auto-started it. Confirm.
13. The brief's sentence ("Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result.") differs from the D-60 wording ("... It audits any Java migration, whether produced by Kiro, an LLM, AWS Transform or a human."). The spec uses the brief's text exactly.
14. Tests: story tests that need runs are `slow` (run by `make test-all` and `make acceptance`, not by the CI default job), following R-96 and R-97. Coverage of these pages in CI therefore relies on the fast tests plus the deploy check of Task 16. The smallest case count at which the T2 and T4 faulty ports are ZOMBIE is unmeasured: T4 diverges on 4.35 percent of 2000 cases, so a very small count could give zero divergent cases. The fixture measures it.
15. docs/video-plan.md markers use `unreconciled_exposure.sum` and `unreconciled_exposure.branches_affected`, which are not keys of verdict.json (`exposure_sum`, `affected_branches`). Reported in Task 2, not edited.
16. coroner/ui/templates/run.html.backup exists next to the templates; I could not check whether Git tracks it (the shell tool refused git commands in this call). If tracked, it is a stray file.
17. I could not run `git status` to confirm the tree is clean at b292905; the spec files were read and written from disk. Only the three spec files in .kiro/specs/guided-story/ were changed. The name "reserved" for T6 follows the brief; T6 has no trap.json, so `cases.json` is the only place for it.
18. Existing UI accessibility coverage found: WCAG contrast tests (tests/test_ui_pages.py, test_ui_app.py, test_ui_error.py, test_ui_run_page_fixes.py), `prefers-reduced-motion` in base.html, a focus style in tamper.html, "verdict not conveyed by color alone" in the web-ui requirements. No test or template in coroner/ui uses aria-live, role, aria-label or noscript, and no test checks keyboard use. The story therefore introduces these; the home page Run audit region and the Verify and Tamper pages stay as they are.
