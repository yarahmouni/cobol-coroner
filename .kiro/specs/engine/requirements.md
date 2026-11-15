# Requirements: Coroner engine (S1)

## Introduction
The Coroner engine is the core verification system that takes a COBOL program with copybooks, its Java 17 version, and a schema describing the input and output columns, then generates test cases, runs both programs, compares the outputs field by field with no numeric tolerance, and returns a deterministic ALIVE or ZOMBIE verdict.

The engine is the foundation of independent regression auditing (D-18). It does not convert code (D-02). It verifies whether a migration kept the business behavior on N generated cases and shows exactly where it broke.

This specification covers the S1 engine only. Out of scope for this spec: fixed-width record format (D-27, built after the S1 core), Coroner Certificate rendering (separate spec, D-24), UI and API (S2), MCP tools beyond get_verdict (S2), Git pre-commit fast mode (separate spec, D-10), AI explanation (D-13).

Dependencies: Hypothesis is added to the dev dependencies at a pinned version (quality.md requires property-based tests).

### Requirement 1: Inputs and validation
**User Story:** As a user, I want to provide a COBOL program, its copybooks, the Java version, and a schema, with server-side validation and size limits for safety.

#### Acceptance Criteria
1. THE engine SHALL accept as inputs: a path to a COBOL source file (.cob or .cbl), a path to a copybook directory (may be empty if no copybooks), a path to one Java source file (.java) with a main class, and a path to a schema.json file.
2. THE engine SHALL validate that each input file exists and is readable before starting any work.
3. THE engine SHALL enforce a size limit on each input file: maximum 1 MB for the COBOL source, 1 MB for the Java source, 100 KB for each copybook, 100 KB for schema.json (per quality.md validation).
4. THE engine SHALL enforce a time limit on every subprocess run: maximum 60 seconds for COBOL compilation, 60 seconds for Java compilation, 60 seconds for one COBOL run (all cases), 60 seconds for one Java run (all cases, one JVM). These timeouts are configurable.
5. WHEN any input file exceeds the size limit THE engine SHALL report an error and exit with code 2 (usage or runtime error) without attempting compilation or execution.
6. WHEN any timeout is exceeded THE engine SHALL terminate the subprocess and report an error with exit code 2.
7. THE schema.json format SHALL match the structure of `samples/credit-fees/schema.json`: program name, description, input section with file name and columns array, output section with file name and columns array, optional internal_precision section. CSV only in V1.
8. EACH column definition SHALL include: name, type (string, decimal, or integer), pic (COBOL picture clause), and description. Decimal columns SHALL also include scale.
9. WHEN schema.json is invalid or missing required fields THE engine SHALL report a clear error and exit with code 2.

### Requirement 2: Schema and copybook parsing (coroner/parse)
**User Story:** As a developer, I need the engine to load the schema, parse copybook PIC clauses for input field properties, and parse traces keyed by source file and line.

#### Acceptance Criteria
1. THE coroner/parse module SHALL load schema.json and validate its structure per Requirement 1.
2. THE input field domains (sign, digits, scale) come from schema.json, which is the source of truth. For each input column with type decimal or integer, schema.json SHALL provide: the PIC clause, whether it is signed (leading S in PIC), the total digit count, the scale, and whether it is COMP-3 (from internal_precision) or display.
3. THE module SHALL extract for each output column: the PIC clause, the type, the scale if decimal.
4. THE module SHALL parse copybooks and the COBOL source to extract numeric constants and thresholds (boundary values) and the paragraph/branch map, not for input field domains.
5. THE module SHALL parse GnuCOBOL 3.x trace files (produced by `-ftraceall` or coverage instrumentation) and extract executed lines keyed by source file name and line number.
6. A trace with copybooks has multiple "Source:" entries. THE trace parser SHALL key each line by (source file, line number) so that execution of copybook lines is captured separately from main program lines.
7. WHEN a copybook contains syntax errors or unreadable content THE module SHALL report a clear error and exit with code 2.
8. THE trace parser SHALL return a dictionary mapping (source_file, line_number) to execution count for each line that appears in the trace.
9. THE S0 trace parser keyed lines only (review R-09). THE new parser SHALL extend it to key by (source file, line) to handle copybooks correctly.

### Requirement 3: Targeted case generation (coroner/gen)
**User Story:** As a user, I want Coroner to generate test cases that cover limits, boundaries, branches, rounding ties, and random values, all reproducibly from a fixed seed.

#### Acceptance Criteria
1. THE coroner/gen module SHALL generate cases from the schema (source of truth for input field domains) and the COBOL program (numeric constants, thresholds, paragraph/branch map) using a fixed seed (default seed documented, overridable via CLI).
2. THE same seed SHALL produce the same cases byte for byte (D-08, per quality.md).
3. THE module SHALL generate targeted cases: limits (minimum and maximum values for each PIC), boundaries around thresholds found in the schema or as numeric constants in the COBOL source (e.g., values just below and just above 10.00 if 10.00 appears as a constant), branch-driving values (values that force each IF condition true and false), exact rounding ties at scale 2 with even and odd preceding digits (e.g., 12.345, 11.345), and negative values for signed fields.
4. THE module SHALL use random.Random(seed) and derive every draw from random() only (no randrange, choice, shuffle or other helpers). Hypothesis is not used for generation (D-30).
5. THE share of exact rounding ties SHALL be configurable so that the HALF_EVEN legacy demo variant (D-06) produced by the catalog tooling (D-29) diverges on about 100 of 2,000 cases. The default configuration SHALL target approximately 5% rounding ties.
6. GENERATED inputs SHALL use canonical numeric text format: optional leading '-', digits, optional '.', more digits (e.g., "123.45", "-0.50", "100"). This is the domain where Java parity is specified (per java-credit-fees requirement 5).
7. THE module SHALL NOT generate numeric values with leading '+', scientific notation (e.g., "1E2"), or trailing/leading spaces in numeric fields. These forms are handled by the COBOL and Java parsers but are not canonical for generation.
8. CASE-ID is the first schema input column. THE case generator SHALL write all generated cases to a CSV file in `runs/<run_id>/generated_cases.csv` with columns matching the schema input columns. Generated CASE-ID values are "GEN-00001", "GEN-00002", ... and must fit the PIC clause in schema.json (for credit-fees: X(10)). The generated_cases.csv file is the authoritative input for replay, written UTF-8 with LF line endings.
9. WHEN the schema or COBOL source cannot be parsed THE module SHALL report an error and exit with code 2.

### Requirement 4: Execution with separate builds (coroner/run)
**User Story:** As a user, I need Coroner to compile and run both programs correctly, with the COBOL reference never instrumented and a separate instrumented build for coverage.

#### Acceptance Criteria
1. THE coroner/run module SHALL compile the COBOL reference source with `cobc -x -Wall -I <copybooks> -o build/<name> <source>` (the flags of the verified reference build) without instrumentation. Never add `-std=...` (it can change semantics). Flags are configurable per program.
2. THE module SHALL compile a separate instrumented COBOL build with the same flags plus `-ftraceall` into `build/coverage/PROGRAM-NAME` for coverage traces only (per comparison-rules.md).
3. THE reference build SHALL be used for all case executions and output comparison. The instrumented build SHALL be used only to capture coverage traces.
4. THE module SHALL compile the Java source with `javac -Xlint:all -d build/java` and verify compilation produces no errors.
5. THE COBOL program reads the whole input file in ONE run. THE module SHALL run all generated cases through the COBOL reference binary by writing the generated_cases.csv to a temporary input file, executing the COBOL binary once, and capturing the output CSV and return code.
6. THE Java program runs in ONE JVM. THE module SHALL run all generated cases through the Java program in one JVM (single java process, one input file, one output file) and capture the output CSV and return code.
7. EACH subprocess execution SHALL have a timeout: 60 seconds for one COBOL run (configurable), 60 seconds for one Java run (configurable).
8. THE module SHALL NOT provide network access to any subprocess (no network sockets, per quality.md).
9. WHEN compilation fails for COBOL or Java THE module SHALL capture stderr, report the error, and exit with code 2.
10. WHEN a subprocess exceeds its timeout THE module SHALL terminate it, report a timeout error, and exit with code 2.
11. THE module SHALL run the instrumented COBOL build ONCE on all generated cases (one trace file, COB_SET_TRACE=Y, COB_TRACE_FILE in runs/<run_id>/) so coverage is exact over N cases. For the failure report and the minimal case, re-run the instrumented build on that single case to get its lines.

### Requirement 5: Exact comparison with normalization (coroner/compare)
**User Story:** As a user, I need Coroner to compare outputs field by field with no numeric tolerance, normalizing only per the documented rules.

#### Acceptance Criteria
1. THE coroner/compare module SHALL normalize both COBOL and Java outputs per comparison-rules.md: no numeric tolerance, decimal values normalized to the scale defined in schema.json, strings compared exactly after trimming trailing spaces, line endings normalized to LF, columns matched by name (never by position).
2. THE first column SHALL be the case id. Row counts in COBOL and Java outputs SHALL be equal; if not, the comparison SHALL report a row count mismatch and consider the case divergent.
3. THE COBOL and Java run return codes are compared per run, and per case whenever a single case is re-run (minimal case, failure report). A mismatch is a run-level divergence that makes the verdict ZOMBIE. The verdict sub-label wording is "FAIL: return code differs (COBOL x, Java y)" (D-31).
4. FOR EACH case THE module SHALL compare each output column by name. If a column value differs after normalization, the case is divergent.
5. THE module SHALL output per case: case id, divergent (boolean), list of divergent fields with (field name, COBOL value, Java value). Return codes are listed per run and per re-run case (consistent with Requirement 5.3).
6. THE comparison result SHALL be written to `runs/<run_id>/comparison_results.json` as a JSON array of case results.
7. WHEN a column is missing in one output but present in the other THE module SHALL report the column as divergent with value "missing".
8. WHEN the schema specifies a decimal column with scale 2 THE module SHALL normalize both COBOL and Java values to exactly 2 decimal places before comparison (e.g., "10.5" becomes "10.50").
9. THE module SHALL have property-based tests using Hypothesis (per quality.md) that verify: normalization is idempotent (normalizing twice gives the same result), trailing space trimming works correctly, scale normalization preserves value, and LF normalization handles CRLF and LF correctly.

### Requirement 6: Deterministic verdict with honest wording
**User Story:** As a user, I need a clear ALIVE or ZOMBIE verdict with the exact sub-label and honest wording.

#### Acceptance Criteria
1. THE verdict SHALL be ALIVE when 0 divergences are found on N cases (D-20).
2. THE verdict SHALL be ZOMBIE when at least 1 divergence is found on N cases (D-20).
3. THE ALIVE sub-label SHALL be "PASS: business behavior preserved on N cases" (per no-formal-proof.md). The detail line MAY also show "0 divergence found on N cases".
4. THE ZOMBIE sub-label SHALL be "FAIL: business behavior diverged on M cases" where M is the number of cases with at least one divergent field (per no-formal-proof.md). When the exit statuses differ, both divergences are shown: "FAIL: business behavior diverged on M cases; return code differs (COBOL x, Java y)". When there are only exit status differences and no field divergences (M=0), the sub-label is "FAIL: return code differs (COBOL x, Java y)" (D-31).
5. THE verdict output SHALL include the wording "Validated under GnuCOBOL 3.x" (per no-formal-proof.md).
6. THE Verdict type SHALL be moved from `coroner/mcp/server.py` into the engine module (per review R-13: no business logic in MCP handlers).
7. THE Verdict type SHALL be a dataclass with fields: status (ALIVE or ZOMBIE), sub_label (string), cases_total (int), cases_divergent (int), validation_notice (string, always "Validated under GnuCOBOL 3.x").
8. THE MCP server get_verdict tool SHALL return the Verdict object from the engine, not construct its own verdict.
9. THE verdict SHALL be written to `runs/<run_id>/verdict.json` as a JSON object with the Verdict fields.

### Requirement 7: Failure and coverage reports (coroner/diag)
**User Story:** As a user, when I get a ZOMBIE verdict, I need a detailed failure report showing exactly what diverged and where, plus a minimal failing case with a JUnit regression test.

#### Acceptance Criteria
1. THE coroner/diag module SHALL generate a failure report for ZOMBIE verdicts including: the failing case id, the full input row (all input column values), the COBOL output row, the Java output row, the divergent field name and values, and the COBOL lines executed for that case (extracted from the coverage trace).
2. THE module SHALL include a minimal-case submodule that selects the minimal failing case from all divergent cases using this deterministic rule: among divergent cases, compare the numeric input columns in schema order by absolute value (smallest first), then the case id. On credit-fees this gives PRINCIPAL, then FEE-RATE, then CASE-ID.
3. THE minimal-case submodule SHALL write a JUnit 5 source test `ZombieRegressionTest.java` that reproduces the divergence on the Java side (D-25). The Java main class calls System.exit and reads INPUT_FILE/OUTPUT_FILE, so the test must NOT call main in-process. ZombieRegressionTest.java writes the minimal case input (header + row) to a temporary file, runs the Java program as a subprocess (ProcessBuilder, `java -cp <classes dir> <MainClass>`, environment INPUT_FILE and OUTPUT_FILE, timeout), reads the output row and asserts the divergent field equals the COBOL value (and the return code when it diverges).
4. THE JUnit test SHALL be written to `runs/<run_id>/ZombieRegressionTest.java`. Compilation and run in Coroner's own tests use junit-jupiter-api and junit-platform-console-standalone at pinned versions with SHA-256 checksums, downloaded into build/junit/ by a make target, never committed (EPL-2.0, used as a tool, not redistributed). When the jars are missing, those tests skip with a clear reason.
5. THE minimal-case submodule SHALL be reused by the fault catalog for its minimal failing case selection and JUnit test generation (per fault-catalog requirement 8). No duplicated selection logic.
6. THE module SHALL generate a coverage report with "Paragraph coverage X/Y" and "Branch coverage (Coroner definition) X/Y" from the coverage traces (per no-formal-proof.md).
7. A branch is covered when its first statement appears in the trace of at least one case (D-07, per no-formal-proof.md).
8. THE coverage report SHALL include the D-07 fallback: if branch coverage is not reliable by 2026-11-23, report "Paragraph coverage X/Y" and "Statement coverage X/Y" instead.
9. THE failure report SHALL be written to `runs/<run_id>/failure_report.json` as a JSON object. The coverage report SHALL be written to `runs/<run_id>/coverage_report.json`.
10. WHEN the verdict is ALIVE THE failure report SHALL NOT be generated (no failures to report). The coverage report SHALL still be generated.

### Requirement 8: Run storage and deterministic run IDs
**User Story:** As a user, I need every run to be stored in a reproducible way so I can retrieve results later and build the Coroner Certificate.

#### Acceptance Criteria
1. THE engine SHALL write all run data to `runs/<run_id>/` where run_id is the first 12 hex characters of the SHA-256 of (input file hashes, seed, case count, tool versions). The same inputs give the same run_id and the directory is rewritten. The timestamp is stored in inputs.json but is not part of the run_id.
2. THE run directory SHALL contain: `inputs.json` (SHA-256 hash of each input file, seed, tool versions from `cobc --version`, `javac -version`, `python --version`), `generated_cases.csv`, `comparison_results.json`, `verdict.json`, `coverage_report.json`, and if ZOMBIE `failure_report.json` and `ZombieRegressionTest.java`.
3. THE `inputs.json` file SHALL include: cobol_source_sha256, java_source_sha256, schema_sha256, copybook_hashes (array of {name, sha256} for each copybook), seed, cobc_version, javac_version, python_version, cases_file_sha256, cases_file_encoding ("utf-8"), cases_file_line_ending ("LF"), random_seed, timestamp. The additional fields (D-30, D-24) are for the Coroner Certificate reproducibility.
4. THE runs/ directory SHALL be created if it does not exist. Old runs SHALL NOT be deleted automatically (user manages disk space).
5. THE engine SHALL ensure runs/<run_id>/ is fully written before returning a verdict. If the run fails partway through, partial results MAY be left in the directory with a `run_error.txt` file explaining the failure.
6. THE Coroner Certificate spec (D-24, separate spec) will read the inputs.json, verdict.json, and comparison_results.json files to render a certificate. This requirement only ensures the data is stored correctly.

### Requirement 9: CLI interface and Makefile targets
**User Story:** As a user, I need a simple CLI command to verify a migration and clear Makefile targets to run demos.

#### Acceptance Criteria
1. THE CLI command SHALL be `python -m coroner verify --cobol PATH --copybooks PATH --java PATH --schema PATH [--cases N] [--seed S]`.
2. THE command SHALL print the verdict status and sub-label to stdout (e.g., "ALIVE: PASS: business behavior preserved on 2000 cases").
3. THE command SHALL print the coverage summary (e.g., "Paragraph coverage 15/15, Branch coverage 28/28").
4. THE command SHALL exit with code 0 when the verdict is ALIVE, code 1 when the verdict is ZOMBIE, code 2 on usage or runtime error (invalid inputs, timeout, compilation failure).
5. THE `--cases N` option SHALL override the default number of cases generated (default 2000).
6. THE `--seed S` option SHALL override the default fixed seed (default seed documented in the code and docs).
7. THE Makefile target `make demo` SHALL run `python -m coroner verify` on the correct Java version (`samples/credit-fees/java/CreditFees.java`) and print the ALIVE verdict. This target replaces the S0 placeholder ("not available yet").
8. THE Makefile target `make zombie` SHALL run `python -m coroner verify` on the HALF_EVEN legacy demo variant (produced by the catalog tooling, D-29, path `samples/credit-fees/java/variants/CreditFees_F01.java`) and print the ZOMBIE verdict. This target replaces the S0 placeholder.
9. WHEN the COBOL source, copybooks, or schema are missing or invalid THE command SHALL print a clear error message and exit with code 2.
10. THE CLI SHALL accept any Java source path, not only the samples directory (per Requirement 10, the engine must accept the HALF_EVEN legacy demo variant path).

### Requirement 10: S1 acceptance criteria from sprints.md
**User Story:** As a product owner, I need the engine to meet the S1 acceptance criteria: correct verdicts on 2,000 cases, performance under 60 seconds, and zero false verdicts.

#### Acceptance Criteria
1. THE engine SHALL produce an ALIVE verdict when run on `samples/credit-fees/CREDIT-FEES.cob` and `samples/credit-fees/java/CreditFees.java` with 2,000 cases and the default seed.
2. THE engine SHALL produce a ZOMBIE verdict when run on the same COBOL and the HALF_EVEN legacy demo variant `samples/credit-fees/java/variants/CreditFees_F01.java` (produced by the catalog tooling, D-29) with 2,000 cases and the default seed.
3. THE wall-clock time of one `python -m coroner verify` with 2,000 cases on the dev machine SHALL be under 60 seconds, compilation included. This timing is measured by a test and printed by the CLI.
4. THE engine SHALL produce 0 false ZOMBIE verdicts on 10 runs of the correct Java with 10 different documented fixed seeds (seeds s1 through s10 documented in the test or code).
5. THE engine SHALL produce 0 false ALIVE verdicts on 10 runs of the HALF_EVEN variant with the same 10 seeds.
6. THE 10 fixed seeds and their expected verdicts SHALL be documented in the test file or in a comment in the CLI module.
7. WHEN any of these acceptance tests fail THE engine is not ready for S1 completion.
8. THE engine SHALL accept any Java source path (not only the samples directory) so it can verify the HALF_EVEN legacy demo variant and other fault catalog variants.

### Requirement 11: Comprehensive tests
**User Story:** As a developer, I need unit tests, property-based tests, and end-to-end tests to ensure the engine works correctly.

#### Acceptance Criteria
1. THE engine SHALL have unit tests for each module: coroner/parse, coroner/gen, coroner/run, coroner/compare, coroner/diag (per quality.md).
2. THE coroner/compare module SHALL have property-based tests using Hypothesis (per quality.md) that verify normalization correctness, idempotence, and edge cases.
3. THE engine SHALL have end-to-end tests: one test that runs the engine on the correct Java and asserts ALIVE, one test that runs the engine on the HALF_EVEN variant and asserts ZOMBIE (per quality.md).
4. TESTS that require `cobc` or `javac` SHALL skip with a clear pytest skip reason when the tool is missing (e.g., `pytest.skip("cobc not available")`).
5. EVERY subprocess call in tests SHALL have a timeout to prevent hanging tests.
6. THE test suite SHALL run with `pytest` and produce a clear pass/fail result.
7. THE tests SHALL use a smaller case count (e.g., 200 cases) for speed, except for the 10-seed acceptance tests which must use 2,000 cases.
8. THE end-to-end tests SHALL verify: the verdict status (ALIVE or ZOMBIE), the sub-label wording, the coverage report presence, and for ZOMBIE the failure report and JUnit test file presence.
9. THE tests SHALL NOT modify the samples/ directory. Temporary files SHALL be written to build/test_temp/ and cleaned up after each test.
