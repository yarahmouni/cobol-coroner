# EBCDIC/control-break demo tasks

Priority 9 (D-33, D-34, D-45).

## Task 1: Multi-row minimal case reducer
- [ ] **Requirements**: Req 1.
- [ ] Write `coroner/diag/minimal.py` function `reduce_multirow_case(cobol_path, copybooks_path, java_path, schema, case_rows, base_dir)` that applies delta reduction to the input rows and returns the minimal subset that still diverges.
- [ ] Raise an error if the final subset does not diverge.
- [ ] **Done when**: The reducer is tested on a real divergent T1 case: the rows of one divergent case from a real small faulty T1 run (for example 200 cases, seed 42), reduced by actually running the T1 COBOL program and the faulty Java port; assert the result diverges on a re-run and that removing any single row of the result makes it stop diverging (1-minimality); assert it is deterministic (same result twice). The "every row necessary" and "non-divergent input raises" checks also use real runs (correct port gives a non-divergent input).

## Task 2: Multi-row failure report generation
- [ ] **Requirements**: Req 1.
- [ ] Modify `coroner/diag/failure.py`: when case_rows is present in the schema and a case diverges, call `reduce_multirow_case` and write both `original_case_rows` and `minimal_case_rows` to failure_report.json.
- [ ] Write `minimal_case_input.csv` with the minimal subset only.
- [ ] **Done when**: A T1 run with 2000 cases writes failure_report.json with both fields; `minimal_case_input.csv` contains only the minimal rows; re-running both programs on that CSV reproduces the divergence.

## Task 3: Row-level divergence description
- [ ] **Requirements**: Req 2.
- [ ] Modify `coroner/compare.py`: when output_key is present, return structured divergences with the output key value, position, and COBOL vs Java values (missing, extra, or value mismatch).
- [ ] Update failure_report.json to use the structured description.
- [ ] **Done when**: the description names the output key and both values exactly as written by the programs, and the run's divergence count is unchanged (262 at 2000 cases, seed 42).

## Task 4: Multi-row Given/When/Then card
- [ ] **Requirements**: Req 3.
- [ ] Modify `coroner/diag/card.py`: when case_rows is present, generate Given with the input rows (or minimal subset), Then with divergent branch values.
- [ ] For schemas with group_key, include ordering and comparison statements in the COBOL lines involved, not only ADD statements.
- [ ] **Done when**: A T1 card lists the input rows in Given, names the divergent branch and values in Then, and includes the match-merge comparison lines in the COBOL evidence.

## Task 5: Demo script
- [ ] **Requirements**: Req 5.
- [ ] Write `scripts/demo_ebcdic.sh` per the design: faulty T1 verify (2000 cases, seed 42), print the verdict block and card, compile and run the JUnit test against both ports, replay the certificate, correct T1 verify.
- [ ] Exit 0 only if every step behaved as expected. Otherwise exit 1 with the failing step named.
- [ ] **Done when**: The script runs without error on the dev machine; the verdict is ZOMBIE for faulty, the JUnit test fails on faulty and passes on correct, the certificate replays VALID, the correct port is ALIVE.

## Task 6: Makefile target
- [ ] **Requirements**: Req 5.
- [ ] Add `demo-ebcdic` target to Makefile: `bash scripts/demo_ebcdic.sh`.
- [ ] **Done when**: `make demo-ebcdic` runs the script and exits with its status.

## Task 7: Fast tests
- [ ] **Requirements**: Req 6.
- [ ] Write `tests/test_multirow_minimal.py`: test the reducer on real T1 cases, test row divergence description with output_key, test multi-row card generation.
- [ ] **Done when**: 3 fast tests pass.

## Task 8: Slow integration test
- [ ] **Requirements**: Req 6.
- [ ] Write `tests/test_demo_ebcdic.py`: marked slow, runs `make demo-ebcdic` and asserts exit 0.
- [ ] **Done when**: The test passes; record the measured duration.

## Task 9: README demo section
- [ ] **Requirements**: Req 7.
- [ ] Add a "Demo" section to README.md after "Trap catalog" with the `make demo-ebcdic` command and a placeholder sentence for the operator to fill with measured output.
- [ ] **Done when**: The section exists with the command and placeholder, no number typed by hand.

## Deferred to hardening (Nov 25 to 27)

## Task 10: Trap catalog JUnit verification
- [ ] **Requirements**: Req 4.
- [ ] Modify `coroner/traps.py`: after generating the JUnit test for each trap, call `verify_junit_test` with both the faulty and correct Java paths.
- [ ] **Done when**: `make traps` verifies every generated JUnit test; a test that does not behave correctly stops the catalog with exit 2.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| Req 1 (Multi-row minimal case reduction) | 1, 2 |
| Req 2 (Row-level divergence description) | 3 |
| Req 3 (Multi-row Given/When/Then card) | 4 |
| Req 4 (JUnit test verification) | 10 (deferred) |
| Req 5 (Integrated demo command) | 5, 6 |
| Req 6 (Test coverage) | 7, 8 |
| Req 7 (README demo section) | 9 |
