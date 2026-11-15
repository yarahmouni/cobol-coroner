# Tasks: Coroner engine (S1)

- [x] 1. Dependencies and package skeleton
  - Add `hypothesis==6.170.14` to dev dependencies in pyproject.toml
  - Reinstall with `.venv/bin/pip install -e ".[dev]"`
  - Create empty package structure: `coroner/parse/__init__.py`, `coroner/gen/__init__.py`, `coroner/run/__init__.py`, `coroner/compare/__init__.py`, `coroner/diag/__init__.py`, `coroner/catalog/__init__.py`
  - Create empty module files: `coroner/verdict.py`, `coroner/store.py`, `coroner/cli.py`, `coroner/__main__.py`, `coroner/parse/schema.py`, `coroner/parse/copybook.py`, `coroner/parse/trace.py`, `coroner/diag/coverage.py`, `coroner/diag/minimal_case.py`, `coroner/diag/report.py`, `coroner/diag/junit.py`, `coroner/catalog/legacy_variant.py`

_Requirements: 1.1, 3.1_

Done when: `.venv/bin/pip install -e ".[dev]"` exits 0 and all package and module files exist.

- [x] 2. Schema parsing (coroner/parse/schema.py)
  - Implement `SchemaColumn` dataclass with: name, type, pic, description, scale (optional), signed (optional), comp3 (optional)
  - Implement `Schema` dataclass with: program_name, description, input_file, input_columns, output_file, output_columns, internal_precision (optional)
  - Implement `load_schema(path: str) -> Schema` that reads JSON, validates required fields per Requirement 1.7, parses PIC clauses (extract sign, digits, scale from PIC clause strings)
  - PIC parsing: detect leading S for signed, count numeric placeholders (9, V), identify decimal point position and compute scale
  - Raise `ValueError` with clear message on missing required fields, invalid JSON, or unparseable PIC clause
  - Create `tests/test_schema.py` with pytest functions: test valid schema load, test missing required field, test invalid JSON, test PIC parsing for S9(7)V99 and X(10) types

_Requirements: 1.7, 1.8, 2.1, 2.2, 2.3_

Done when: `.venv/bin/pytest tests/test_schema.py -q` shows all tests passing, and loading `samples/credit-fees/schema.json` returns a Schema object with input_columns length 4 and output_columns length 4.

- [x] 3. Trace parsing with source file keys (coroner/parse/trace.py)
  - Keep existing `parse_trace(path: str) -> set[int]` working as a thin wrapper for backward compatibility (smoke/run_smoke.sh and tests/test_trace_parser.py use it)
  - Implement `parse_trace_counts(path: str) -> dict[(source_file: str, line: int), int]` that streams the trace file and returns execution counts keyed by (source_file, line_number)
  - Trace format: "Source: <file>" to track current source file, "Line: N" to record executed line, count incremented for each appearance
  - Create a two-source trace fixture `tests/fixtures/two_source_trace.txt` captured from a real GnuCOBOL 3.2 run on the COBOL sample with a copybook, not hand-written (sample lines: main program lines in CREDIT-FEES.cob, copybook lines in TYPES.cpy)
  - Create `tests/test_trace_parser_engine.py` with pytest functions: test parse_trace_counts on two_source_trace.txt returns dict with (source_file, line_number) keys, test main program lines present, test copybook lines present and keyed separately, test empty trace, test parse_trace wrapper still works on simple traces

_Requirements: 2.5, 2.6, 2.8, 2.9_

Done when: `.venv/bin/pytest tests/test_trace_parser_engine.py -q` shows all tests passing, and `parse_trace_counts` on two_source_trace.txt returns at least 5 main program lines and 3 copybook lines as separate keys.

- [x] 4. Copybook and branch parsing (coroner/parse/copybook.py)
  - Implement `BranchInfo` dataclass with: paragraph (str), line_number (int), branch_type (str enum: "IF_TRUE", "IF_ELSE", "EVALUATE_WHEN", "EVALUATE_OTHER")
  - Implement `parse_cobol_structure(source_path: str, copybook_dir: str) -> dict` that returns {"constants": [...], "paragraphs": {...}, "branches": [BranchInfo(...), ...]}
  - Extract numeric constants from VALUE clauses and numeric literals in IF conditions (regex-based parsing)
  - Extract paragraph names and their starting line numbers
  - Extract branches: IF true arm (first statement after IF), IF ELSE arm (first statement after ELSE), each EVALUATE WHEN arm (first statement inside WHEN), WHEN OTHER (first statement inside WHEN OTHER)
  - Branches are identified by their first-statement line number (per design)
  - Parser targets credit-fees patterns: handles IF/ELSE, EVALUATE/WHEN, PERFORM, VALUE clauses, nested IFs; unsupported constructs do not crash
  - Create `tests/test_copybook.py` with pytest functions: test parse_cobol_structure on samples/credit-fees/CREDIT-FEES.cob returns at least 33 IF branches (33 IF / 33 ELSE per review R-26), exactly 1 EVALUATE with 4 arms (WHEN + WHEN OTHER = 5 branches if counting WHEN OTHER), constants include 10.00 and 25000.00 (thresholds from design), paragraph names include MAIN-PROCESS and VALIDATE-INPUT

_Requirements: 2.4, 2.7, 2.8_

Done when: `.venv/bin/pytest tests/test_copybook.py -q` shows all tests passing, and parse_cobol_structure on samples/credit-fees/CREDIT-FEES.cob returns 33+ branches with types IF_TRUE/IF_ELSE and 4 EVALUATE_WHEN branches.

- [x] 5. Case generation (coroner/gen/__init__.py)
  - Implement `generate_cases(schema: Schema, cobol_structure: dict, seed: int, num_cases: int, tie_share: float = 0.05) -> str` that returns path to generated_cases.csv
  - Use `random.Random(seed)` for all random draws; every draw must derive from `random()` only (no randrange, choice, shuffle, sample, uniform, randint)
  - Generate targeted cases: limits (min/max for each PIC), boundaries around constants (C - 0.01, C, C + 0.01), branch-driving values (thresholds +/- delta), rounding ties (product ties with even and odd preceding digits, about 5% of num_cases)
  - Rounding ties constructed from products of input column pairs: e.g., 1234.50 x 0.01000 = 12.3450000 (preceding digit 4, even) diverges under HALF_EVEN; 1235.50 x 0.01000 = 12.3550000 (preceding digit 5, odd) does not diverge. For 2000 cases, target 80-120 ties with even preceding digits.
  - CASE-ID format: "GEN-00001", "GEN-00002", ... zero-padded to fit schema PIC X(10)
  - Canonical text format: optional leading '-', digits, optional '.', more digits (e.g., "123.45", "-0.50", "100", ".5"). No leading '+', no exponent, no spaces.
  - Write runs/<run_id>/generated_cases.csv with UTF-8 encoding and LF line endings (use io.StringIO and manual LF)
  - Implement helper functions: `draw_int(rng, lo, hi)` and `draw_decimal(rng, lo, hi, scale)` using only `rng.random()` (design Component 4)
  - Create `tests/test_gen.py` with pytest functions: test determinism (same seed twice produces byte-identical CSV), test row count matches num_cases, test CASE-ID format and zero-padding, test canonical text (no '+', no exponent, no spaces), test boundary values present, test rounding ties count between 80 and 120 for 2000 cases with tie_share=0.05 and default seed 42
  - Create a test that greps coroner/gen for 'randrange', 'choice', 'shuffle', 'sample', 'uniform', 'randint' and fails if any are found (to prevent accidental use of other random helpers)

_Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

Done when: `.venv/bin/pytest tests/test_gen.py -q` shows all tests passing, and the grep test confirms no forbidden random functions in coroner/gen.

- [ ] 6. Compilation and execution (coroner/run/__init__.py)
  - Implement `RunResult` dataclass with: output_path (str), return_code (int), stderr (str), wall_time (float)
  - Implement `compile_cobol(source: str, copybooks: str, output: str, flags: list[str]) -> None` that runs `cobc -x -Wall -I <copybooks> -o <output> <source>` with timeout 60s, raises RuntimeError on failure
  - Implement `compile_java(source: str, output_dir: str) -> None` that runs `javac -Xlint:all -d <output_dir> <source>` with timeout 60s, raises RuntimeError on failure
  - Implement `run_cobol(binary: str, input_csv: str, output_csv: str, timeout: float = 60.0) -> RunResult` that runs COBOL binary with env vars INPUT_FILE and OUTPUT_FILE, minimal environment (PATH, INPUT_FILE, OUTPUT_FILE only), no network, captures output_path, return_code, stderr, wall_time
  - Implement `run_java(class_name: str, classpath: str, input_csv: str, output_csv: str, timeout: float = 60.0) -> RunResult` that runs Java main with same env vars, one JVM, single process
  - Implement `run_cobol_instrumented(binary: str, input_csv: str, output_csv: str, trace_file: str, timeout: float = 60.0) -> RunResult` that runs instrumented COBOL with COB_SET_TRACE=Y and COB_TRACE_FILE env vars
  - All subprocess calls use subprocess.run with timeout and capture output
  - Raise RuntimeError with message on timeout (e.g., "COBOL execution timed out after 60s")
  - Create `tests/test_run.py` with pytest functions: test compile_cobol on CREDIT-FEES.cob succeeds, test compile_java on CreditFees.java succeeds, test run_cobol returns RunResult with return_code 0 and output_path, test run_cobol_instrumented produces trace_file
  - Tests skip with clear reason when cobc or javac is missing
  - All subprocess calls in tests use timeout

_Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11_

Done when: `.venv/bin/pytest tests/test_run.py -q` shows all tests passing or skipped, and the test module compiles and runs both programs without hanging.

- [ ] 7. Output comparison (coroner/compare/__init__.py)
  - Implement `CaseResult` dataclass with: case_id (str), divergent (bool), divergent_fields (list of tuples: field_name, cobol_value, java_value)
  - Implement `ComparisonResult` dataclass with: cases (list[CaseResult]), run_return_codes (tuple[int, int]), row_count_match (bool), total_divergent (int)
  - Implement `compare_outputs(cobol_csv: str, java_csv: str, schema: Schema, cobol_return_code: int, java_return_code: int) -> ComparisonResult` that parses both CSVs, normalizes, compares field by field per comparison-rules.md
  - Normalization: decimal values parsed with `Decimal(value)`, checked for extra non-zero decimals beyond schema scale (divergent if present), padded to scale with quantize and ROUND_UNNECESSARY (never round); strings trimmed trailing spaces only; line endings normalized to LF
  - Comparison: first column is case_id, row counts must match (if not, all cases marked divergent), columns matched by name (never position), missing columns marked divergent with value "missing", return codes compared per run and per case (D-31)
  - Create sub-module `coroner/compare/normalize.py` with functions: `normalize_decimal(value: str, scale: int) -> str`, `normalize_string(value: str) -> str`
  - Create `tests/test_compare.py` with pytest functions: test equal outputs are not divergent, test divergent field is reported, test row count mismatch marks all cases divergent, test missing column marks divergent, test decimal scale normalization, test return code comparison
  - Add property-based tests with Hypothesis: `test_normalize_decimal_idempotent`, `test_normalize_string_idempotent`, `test_extra_decimals_divergent`, `test_string_trim_trailing_only` (per design)
  - All property tests use `@given` decorator and `st.decimals`, `st.text` strategies

_Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

Done when: `.venv/bin/pytest tests/test_compare.py -q` shows all tests and property tests passing.

- [ ] 8. Verdict type and computation (coroner/verdict.py)
  - Move `Verdict` dataclass from `coroner/mcp/server.py` to `coroner/verdict.py`: fields status (str: "ALIVE" or "ZOMBIE"), sub_label (str), cases_total (int), cases_divergent (int), run_return_codes (tuple[int, int]), validation_notice (str, default "Validated under GnuCOBOL 3.x")
  - Implement `compute_verdict(comparison: ComparisonResult) -> Verdict` per design Component 7
  - ALIVE: `cases_divergent == 0` and `run_return_codes[0] == run_return_codes[1]`, sub_label = "PASS: business behavior preserved on {cases_total} cases"
  - ZOMBIE with case divergences: `cases_divergent > 0`, sub_label = "FAIL: business behavior diverged on {cases_divergent} cases"
  - ZOMBIE with return code mismatch only: `cases_divergent == 0` and codes differ, sub_label = "FAIL: return code differs (COBOL {cobol_rc}, Java {java_rc})"
  - ZOMBIE with both: combine both messages
  - Update `coroner/mcp/server.py` to import Verdict from coroner.verdict instead of defining it
  - Create `tests/test_verdict.py` with pytest functions: test ALIVE sub_label, test ZOMBIE case divergence sub_label, test ZOMBIE return code mismatch sub_label, test ZOMBIE both conditions sub_label
  - Verify `tests/test_mcp_stub.py` still passes with new import

_Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

Done when: `.venv/bin/pytest tests/test_verdict.py tests/test_mcp_stub.py -q` shows all tests passing.

- [ ] 9. Run storage (coroner/store.py)
  - Implement `compute_run_id(cobol_hash: str, java_hash: str, schema_hash: str, copybook_hashes: list[tuple[str, str]], seed: int, case_count: int, tool_versions: dict) -> str` that returns first 12 hex chars of SHA-256
  - Implement `store_inputs(run_dir: str, inputs_data: dict) -> None` that writes inputs.json with: cobol_source_sha256, java_source_sha256, schema_sha256, copybook_hashes (array), seed, case_count, cobc_version, javac_version, python_version, cases_file_sha256, cases_file_encoding ("utf-8"), cases_file_line_ending ("LF"), random_seed, timestamp (ISO 8601)
  - Implement `store_verdict(run_dir: str, verdict: Verdict) -> None` that atomically writes verdict.json (write to temp, rename)
  - Implement `store_comparison(run_dir: str, comparison: ComparisonResult) -> None` that writes comparison_results.json
  - Create runs/<run_id>/ if missing
  - Create `tests/test_store.py` with pytest functions: test compute_run_id is deterministic (same inputs twice), test store_inputs writes JSON with correct fields, test store_verdict atomic write (check temp file cleanup), test run directory created, test old runs not deleted

_Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

Done when: `.venv/bin/pytest tests/test_store.py -q` shows all tests passing, and runs/ directory exists after a test with stored artifacts.

- [ ] 10. Coverage and failure reports (coroner/diag/__init__.py)
  - Implement `coroner/diag/coverage.py` with `CoverageReport` dataclass and `compute_coverage(trace: dict[(source_file, line), int], cobol_structure: dict) -> CoverageReport` that matches trace keys against paragraphs and branch first statements
  - Coverage: paragraph covered if any line inside it appears in trace, branch covered if its first statement line appears in trace (D-07)
  - Implement `coroner/diag/report.py` with `FailureReport` dataclass and `generate_failure_report(...) -> FailureReport` that selects minimal case, re-runs instrumented COBOL on single case, extracts executed lines, returns all details
  - Implement `coroner/diag/minimal_case.py` with `select_minimal_case(divergent_cases: list[CaseResult], schema: Schema, input_rows: dict) -> CaseResult` per design: smallest absolute value of numeric inputs in schema order, then case_id
  - Create `tests/test_diag.py` with pytest functions: test compute_coverage returns CoverageReport with correct counts, test select_minimal_case returns case with smallest numeric input values, test generate_failure_report produces FailureReport with executed_lines
  - Tests skip with clear reason when cobc is missing

_Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

Done when: `.venv/bin/pytest tests/test_diag.py -q` shows all tests passing or skipped.

- [ ] 11. JUnit test generation and jar management (coroner/diag/junit.py)
  - Implement `generate_junit_test(minimal_case: CaseResult, input_row: dict, expected_output: dict, java_class: str, schema: Schema, output_path: str) -> None` that writes ZombieRegressionTest.java
  - Template: JUnit 5 class with one @Test method, runs Java as subprocess (ProcessBuilder with ["java", "-cp", classpath, java_class], env INPUT_FILE and OUTPUT_FILE, timeout 10s), reads output row, asserts divergent field equals COBOL value
  - Create Makefile target `junit-jars` that downloads junit-jupiter-api and junit-platform-console-standalone at pinned versions into build/junit/, verifies SHA-256 checksums, never commits jars
  - Placeholder in the task: TODO versions and checksums filled in by operator (e.g., junit-jupiter-api 5.10.1, junit-platform-console-standalone 1.10.1)
  - Create `tests/test_junit.py` with pytest functions: test generate_junit_test writes file with correct template, test file compiles with javac (skip if jars missing), test file runs and asserts divergent field
  - Tests skip with clear reason when javac or jars are missing

_Requirements: 7.3, 7.4, 7.5_

Done when: `.venv/bin/pytest tests/test_junit.py -q` shows all tests passing or skipped with clear reasons, and `make junit-jars` downloads jars successfully.

- [ ] 12. Legacy HALF_EVEN variant generation (coroner/catalog/legacy_variant.py)
  - Implement `generate_half_even_variant(source_path: str, output_path: str) -> None` that reads Java source, replaces all "RoundingMode.HALF_UP" with "RoundingMode.HALF_EVEN", writes to output_path
  - Simple text replacement, no parsing
  - Create `tests/test_legacy_variant.py` with pytest functions: test generate_half_even_variant replaces string, test output file compiles with javac (skip if javac missing), test variant runs without error (skip if cobc missing)

_Requirements: D-06, D-29_

Done when: `.venv/bin/pytest tests/test_legacy_variant.py -q` shows all tests passing or skipped, and the generated variant compiles and runs.

- [ ] 13. CLI and Makefile targets (coroner/cli.py, coroner/__main__.py, Makefile)
  - Implement `verify_command(cobol: str, copybooks: str, java: str, schema: str, cases: int = 2000, seed: int = 42) -> int` that orchestrates the full pipeline: load inputs, validate, generate cases, compile, run, compare, compute verdict, generate reports, store results
  - Input validation: file existence, size limits per Requirement 1 (COBOL 1 MB, Java 1 MB, copybooks 100 KB each, schema 100 KB)
  - Print verdict and coverage to stdout, run_id for reference
  - Print per-step timings with `--timings` flag (optional, for performance debugging)
  - Return exit code: 0 (ALIVE), 1 (ZOMBIE), 2 (error)
  - Implement `coroner/__main__.py` with argparse for `--cobol`, `--copybooks`, `--java`, `--schema`, `--cases`, `--seed` (optional flags)
  - Update Makefile: `make demo` runs `python -m coroner verify` on correct Java (samples/credit-fees/java/CreditFees.java), expect exit 0 printing ALIVE
  - Update Makefile: `make zombie` generates HALF_EVEN variant, runs engine on it, expect exit 1 printing ZOMBIE
  - Update Makefile: `make test` (existing) excludes slow tests, runs `.venv/bin/pytest -q -m "not slow"`
  - Update Makefile: add `make acceptance` target that runs slow tests (`.venv/bin/pytest -q -m slow`)
  - pytest.ini: mark slow tests, exclude by default
  - Create `tests/test_e2e.py` with pytest functions: test_e2e_alive (runs engine on correct Java, 200 cases for speed, assert exit 0 and ALIVE), test_e2e_zombie (runs engine on HALF_EVEN variant, 200 cases, assert exit 1 and ZOMBIE with divergent cases)
  - Tests skip with clear reason when cobc or javac is missing

_Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 10.1, 10.2_

Done when: `make demo` exits 0 printing "ALIVE: PASS: business behavior preserved on 2000 cases" and coverage summary; `make zombie` exits 1 printing "ZOMBIE: FAIL: business behavior diverged on ...".

- [ ] 14. Acceptance tests (10 seeds, 2000 cases each) - marked slow, run via 'make acceptance'
  - Create `tests/test_acceptance.py` with parametrized tests using 10 documented fixed seeds (s1=42, s2=123, s3=456, s4=789, s5=1011, s6=1213, s7=1415, s8=1617, s9=1819, s10=2021)
  - Test `test_acceptance_no_false_zombie`: parametrized over 10 seeds, runs engine on correct Java with 2000 cases, asserts exit code 0 (ALIVE)
  - Test `test_acceptance_no_false_alive`: parametrized over 10 seeds, generates HALF_EVEN variant, runs engine with 2000 cases, asserts exit code 1 (ZOMBIE) and cases_divergent > 0
  - Test `test_acceptance_half_even_calibration`: runs engine on HALF_EVEN variant with default seed 42 and 2000 cases, asserts 80 to 120 divergences (calibration target, not a guarantee)
  - Test `test_acceptance_wall_clock_under_60s`: runs one verify on correct Java with 2000 cases, measures wall-clock time, asserts under 60 seconds, prints timing breakdown per step
  - Mark all acceptance tests with `@pytest.mark.slow`
  - pytest.ini: add marker definition `slow = marks tests as slow`
  - Create `tests/conftest.py` if not present with pytest configuration (e.g., skip collection warnings)
  - Tests skip with clear reason when cobc or javac is missing

_Requirements: 10.3, 10.4, 10.5, 10.6, 10.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

Done when: `make acceptance` runs all parametrized tests without hanging, exits 0 when all pass, and timing test shows wall-clock under 60 seconds per verify.

- [ ] 15. Documentation (docs/architecture.md, README.md)
  - Update docs/architecture.md Component 1 (high-level architecture): document the CLI command `python -m coroner verify --cobol PATH --copybooks PATH --java PATH --schema PATH [--cases N] [--seed S]`
  - Document Makefile targets: `demo` (correct Java, expect ALIVE), `zombie` (HALF_EVEN variant, expect ZOMBIE), `test` (unit + E2E), `acceptance` (slow, 10 seeds)
  - Document runs/<run_id>/ directory structure: inputs.json, generated_cases.csv, comparison_results.json, verdict.json, coverage_report.json, failure_report.json (ZOMBIE only), ZombieRegressionTest.java (ZOMBIE only)
  - Update README.md: document the CLI command and example usage, document exit codes (0 ALIVE, 1 ZOMBIE, 2 error), explain the runs/ directory, mention performance (2000 cases under 60 seconds)

_Requirements: 9.1, 9.9, 10.8, 11.1_

Done when: docs/architecture.md describes the CLI and Makefile targets, README.md includes CLI usage and exit code documentation, and `python -m coroner verify --help` shows all options.

## Requirements Coverage

| Requirement | Covered by Tasks |
|-------------|---|
| 1.1 | 1 |
| 1.2 | 6 |
| 1.3 | 6 |
| 1.4 | 6 |
| 1.5 | 6 |
| 1.6 | 6 |
| 1.7 | 2 |
| 1.8 | 2 |
| 1.9 | 2 |
| 2.1 | 2 |
| 2.2 | 2 |
| 2.3 | 2 |
| 2.4 | 4 |
| 2.5 | 3 |
| 2.6 | 3 |
| 2.7 | 4 |
| 2.8 | 3, 4 |
| 2.9 | 3 |
| 3.1 | 5 |
| 3.2 | 5 |
| 3.3 | 5 |
| 3.4 | 5 |
| 3.5 | 5 |
| 3.6 | 5 |
| 3.7 | 5 |
| 3.8 | 5 |
| 3.9 | 5 |
| 4.1 | 6 |
| 4.2 | 6 |
| 4.3 | 6 |
| 4.4 | 6 |
| 4.5 | 6 |
| 4.6 | 6 |
| 4.7 | 6 |
| 4.8 | 6 |
| 4.9 | 6 |
| 4.10 | 6 |
| 4.11 | 6 |
| 5.1 | 7 |
| 5.2 | 7 |
| 5.3 | 7 |
| 5.4 | 7 |
| 5.5 | 7 |
| 5.6 | 7 |
| 5.7 | 7 |
| 5.8 | 7 |
| 5.9 | 7 |
| 6.1 | 8 |
| 6.2 | 8 |
| 6.3 | 8 |
| 6.4 | 8 |
| 6.5 | 8 |
| 6.6 | 8 |
| 6.7 | 8 |
| 6.8 | 8 |
| 6.9 | 8 |
| 7.1 | 10 |
| 7.2 | 10 |
| 7.3 | 10, 11 |
| 7.4 | 11 |
| 7.5 | 11 |
| 7.6 | 10 |
| 7.7 | 10 |
| 7.8 | 10 |
| 7.9 | 10 |
| 7.10 | 10 |
| 8.1 | 9 |
| 8.2 | 9 |
| 8.3 | 9 |
| 8.4 | 9 |
| 8.5 | 9 |
| 8.6 | 9 |
| 9.1 | 13 |
| 9.2 | 13 |
| 9.3 | 13 |
| 9.4 | 13 |
| 9.5 | 13 |
| 9.6 | 13 |
| 9.7 | 13 |
| 9.8 | 13 |
| 9.9 | 13 |
| 9.10 | 13 |
| 10.1 | 14 |
| 10.2 | 14 |
| 10.3 | 14 |
| 10.4 | 14 |
| 10.5 | 14 |
| 10.6 | 14 |
| 10.7 | 14 |
| 10.8 | 15 |
| 11.1 | 1, 14 |
| 11.2 | 7 |
| 11.3 | 13, 14 |
| 11.4 | 3, 4, 6 |
| 11.5 | 14 |
| 11.6 | 13 |
| 11.7 | 14 |
| 11.8 | 14 |
| 11.9 | All tests |
