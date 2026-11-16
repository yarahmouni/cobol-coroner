# EBCDIC/control-break demo tasks

Priority 9 (D-33, D-34, D-45).

## Task 1: Multi-row minimal case reducer
- [x] **Requirements**: Req 1.
- [x] Write `coroner/diag/minimal.py` function `reduce_multirow_case(cobol_path, copybooks_path, java_path, schema, case_rows, base_dir)` that applies delta reduction to the input rows and returns the minimal subset that still diverges.
- [x] Raise an error if the final subset does not diverge.
- [x] **Done when**: The reducer is tested on a real divergent T1 case: the rows of one divergent case from a real small faulty T1 run (for example 200 cases, seed 42), reduced by actually running the T1 COBOL program and the faulty Java port; assert the result diverges on a re-run and that removing any single row of the result makes it stop diverging (1-minimality); assert it is deterministic (same result twice). The "every row necessary" and "non-divergent input raises" checks also use real runs (correct port gives a non-divergent input).

## Task 2: Multi-row failure report generation
- [x] **Requirements**: Req 1.
- [x] Modify `coroner/diag/failure.py`: when case_rows is present in the schema and a case diverges, call `reduce_multirow_case` and write both `original_case_rows` and `minimal_case_rows` to failure_report.json.
- [x] Write `minimal_case_input.csv` with the minimal subset only.
- [x] **Done when**: A T1 run with 2000 cases writes failure_report.json with both fields; `minimal_case_input.csv` contains only the minimal rows; re-running both programs on that CSV reproduces the divergence.

## Task 3: Row-level divergence description
- [x] **Requirements**: Req 2.
- [x] Modify `coroner/compare.py`: when output_key is present, return structured divergences with the output key value, position, and COBOL vs Java values (missing, extra, or value mismatch).
- [x] Update failure_report.json to use the structured description.
- [x] **Done when**: the description names the output key and both values exactly as written by the programs, and the run's divergence count is unchanged (262 at 2000 cases, seed 42).

## Task 4: Multi-row Given/When/Then card
- [x] **Requirements**: Req 3.
- [x] Modify `coroner/diag/card.py`: when case_rows is present, generate Given with the input rows (or minimal subset), Then with divergent branch values.
- [x] For schemas with group_key, include ordering and comparison statements in the COBOL lines involved, not only ADD statements.
- [x] **Done when**: A T1 card lists the input rows in Given, names the divergent branch and values in Then, and includes the match-merge comparison lines in the COBOL evidence.

## Task 5: JUnit export for multi-row cases
- [x] **Requirements**: Req 4.
- [x] Modify `coroner/diag/junit.py`: when case_rows is present in the schema, generate a test that writes the minimal case input rows (exact content of minimal_case_input.csv) to its input file, runs the port, and asserts the port's whole output file equals the COBOL output of the minimal case (exact content of minimal_case_cobol_output.csv, embedded in the test). Single-case generation unchanged.
- [x] Write function `verify_junit_test(test_path, java_path, junit_jar, work_dir)` that compiles the port and the test and runs JUnit (build/junit/junit-platform-console-standalone-6.1.3.jar), returning passed or failed with the JUnit summary.
- [x] **Done when**: A T1 run writes ZombieRegressionTest.java that compiles, fails against the faulty port, and passes against the correct port; tested on a real small faulty T1 run.

## Task 6: Demo script
- [x] **Requirements**: Req 5.
- [x] Write `scripts/demo_ebcdic.sh` per the design: faulty T1 verify (2000 cases, seed 42), print the verdict block and card, compile and run the JUnit test against both ports, replay the certificate, correct T1 verify.
- [x] Exit 0 only if every step behaved as expected. Otherwise exit 1 with the failing step named.
- [x] **Done when**: The script runs without error on the dev machine; the verdict is ZOMBIE for faulty, the JUnit test fails on faulty and passes on correct, the certificate replays VALID, the correct port is ALIVE.

## Task 7: Makefile target
- [x] **Requirements**: Req 5.
- [x] Add `demo-ebcdic` target to Makefile: `bash scripts/demo_ebcdic.sh`.
- [x] **Done when**: `make demo-ebcdic` runs the script and exits with its status.

## Task 8: Fast tests
- [x] **Requirements**: Req 6.
- [x] Write `tests/test_multirow_minimal.py`: test the reducer on real T1 cases, test row divergence description with output_key, test multi-row card generation.
- [x] **Done when**: 3 fast tests pass.

## Task 9: Slow integration test
- [x] **Requirements**: Req 6.
- [x] Write `tests/test_demo_ebcdic.py`: marked slow, runs `make demo-ebcdic` and asserts exit 0.
- [x] **Done when**: The test passes; record the measured duration.

## Task 10: README demo section
- [x] **Requirements**: Req 7.
- [x] Add a "Demo" section to README.md after "Trap catalog" with the `make demo-ebcdic` command and a placeholder sentence for the operator to fill with measured output.
- [x] **Done when**: The section exists with the command and placeholder, no number typed by hand.

## Deferred to hardening (Nov 25 to 27)

## Task 11: Trap catalog JUnit verification
- [ ] **Requirements**: Req 4.
- [ ] Modify `coroner/traps.py`: after generating the JUnit test for each trap, call `verify_junit_test` with both the faulty and correct Java paths.
- [ ] **Done when**: `make traps` verifies every generated JUnit test; a test that does not behave correctly stops the catalog with exit 2.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| Req 1 (Multi-row minimal case reduction) | 1, 2 |
| Req 2 (Row-level divergence description) | 3 |
| Req 3 (Multi-row Given/When/Then card) | 4 |
| Req 4 (JUnit test verification) | 5, 11 (deferred) |
| Req 5 (Integrated demo command) | 6, 7 |
| Req 6 (Test coverage) | 8, 9 |
| Req 7 (README demo section) | 10 |
