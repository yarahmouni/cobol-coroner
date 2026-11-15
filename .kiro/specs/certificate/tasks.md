# Certificate Tasks

## Task 1: Implement certificate generation

_Requirements: 1.1, 1.2, 1.3, 1.4_

Create `coroner/certificate.py` with `generate_certificate()` function that:
- Loads `inputs.json`, `verdict.json`, `coverage_report.json` from `runs/<run_id>/`
- Loads `failure_report.json` when ZOMBIE for minimal_case_id and divergent_fields
- Constructs the statement with the verdict sub_label
- Builds the certificate dict with all required fields
- Makes file paths relative when inside repository
- Computes canonical JSON and certificate_sha256
- Writes to `runs/<run_id>/certificate.json` with sorted keys and LF

Done when: A helper test generates a certificate from a minimal run, loads it, verifies all fields are present and certificate_sha256 is correct.

## Task 2: Implement certificate content verification

_Requirements: 2.2 (steps 1-2)_

Add `verify_certificate_content()` function that:
- Loads certificate JSON
- Recomputes certificate_sha256 from all other fields
- Verifies the hash matches
- Checks SHA-256 of all input files (COBOL, copybooks, Java, schema, cases)

Done when: Tests verify content hash mismatch detected, file hash mismatch detected.

## Task 3: Implement engine re-run for replay

_Requirements: 2.2 (step 3)_

Add `replay_engine_run()` function that:
- Takes file paths and cases_file from certificate
- Calls the engine pipeline (compile, run, compare, coverage)
- Uses the stored cases file, never generates
- Returns verdict, counts, return codes, coverage

Done when: A test re-runs the engine on stored cases and gets matching verdict.

## Task 4: Implement metric comparison and ReplayResult

_Requirements: 2.2 (steps 4-6), 2.3_

Add `ReplayResult` dataclass and `replay_certificate()` function that:
- Calls verify_certificate_content()
- Calls replay_engine_run()
- Compares all metrics (status, counts, return codes, coverage)
- Detects version warnings (not invalid)
- Returns ReplayResult with valid/invalid status and reason

Done when: Tests verify metric mismatch detected, version warnings issued, exit codes correct.

## Task 5: Update CLI for certificate replay

_Requirements: 2.1, 2.4_

Modify `coroner/cli.py`:
- Detect single `.json` argument in verify command
- Route to replay_certificate() instead of run mode
- Add print_replay_result() function
- Remove "not implemented yet" placeholder
- Exit with correct codes: 0 (VALID+ALIVE), 1 (VALID+ZOMBIE), 3 (INVALID), 2 (ERROR)

Done when: CLI accepts `python -m coroner verify <path>.json` and prints replay output.

## Task 6: Integrate certificate generation into verify command

_Requirements: 1.1_

Modify `coroner/cli.py` run mode:
- After writing verdict.json, call generate_certificate()
- Pass run_id, inputs, verdict, coverage, failure_report, file paths
- Handle errors gracefully (warn but don't fail the run)

Done when: `make demo` writes certificate.json with all fields.

## Task 7: Write certificate tests

_Requirements: 3.1, 3.2, 3.3, 4_

Create `tests/test_certificate.py` with:
- test_generate_certificate_alive: 200 cases, correct Java
- test_generate_certificate_zombie: 200 cases, legacy variant
- test_replay_valid_alive: replay ALIVE certificate, exit 0
- test_replay_valid_zombie: replay ZOMBIE certificate, exit 1
- test_replay_invalid_content: edit one field, exit 3
- test_replay_invalid_cases_file: change cases file byte, exit 3
- test_replay_invalid_metrics: edit count, recompute hash, exit 3

Done when: All 7 tests pass with pytest.

## Task 8: Integration verification

_Requirements: 5_

Run:
- `.venv/bin/pytest -q` (all tests including certificate)
- `make demo`
- `python -m coroner verify runs/<run_id>/certificate.json`

Report both outputs.

Done when: pytest passes, demo generates certificate, replay prints "Certificate: VALID" with verdict and coverage.

## Requirements Coverage

| Requirement | Tasks |
|-------------|-------|
| 1.1 Certificate generation after verdict | 1, 6 |
| 1.2 All required fields in certificate | 1 |
| 1.3 Sub_label follows D-20 | 1 |
| 1.4 No forbidden wording | 1 |
| 2.1 CLI detects .json argument | 5 |
| 2.2 Replay steps 1-2 | 2 |
| 2.2 Replay step 3 | 3 |
| 2.2 Replay steps 4-6 | 4 |
| 2.3 Exit codes | 4, 5 |
| 2.4 Remove placeholder | 5 |
| 3.1 Detect modified content | 2, 7 |
| 3.2 Detect modified cases file | 2, 7 |
| 3.3 Detect metric tampering | 4, 7 |
| 3.4 Replay uses stored cases | 3 |
| 3.5 Replay is offline | 3 |
| 4 Test coverage | 7 |
| 5 Acceptance | 8 |
