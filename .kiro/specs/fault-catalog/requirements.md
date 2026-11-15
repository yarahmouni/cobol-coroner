# Requirements: Fault catalog with automatic injection

## Introduction
A catalog of known COBOL-to-Java migration faults, each automatically injected into the correct Java version to produce a faulty variant. The catalog measures what Coroner detects on the credit-fees sample.

This is a measurement tool, not a claim of coverage. The fault catalog demonstrates Coroner's ability to catch specific common migration errors. It does not produce a global detection rate or any percentage that could be misinterpreted as a guarantee.

Per D-18 repositioning, the fault catalog is part of independent regression auditing. It shows Coroner's diagnostic precision on known error patterns.

### Requirement 1: Mandatory faults for V1
**User Story:** As a demo viewer, I want to see Coroner detect the most common COBOL-to-Java migration errors.

#### Acceptance Criteria
1. THE catalog SHALL include fault F01: HALF_EVEN instead of HALF_UP (rounding mode change only).
2. THE catalog SHALL include fault F02: wrong scale (for example setScale(3) or rounding at scale 2 at a different step than COBOL), never a rounding-mode change.
3. THE catalog SHALL include fault F03: RoundingMode.DOWN instead of HALF_UP (truncation instead of ROUNDED).
4. THE catalog SHALL include fault F04: sign loss on negative amounts, specifically using absolute value or dropping the sign during computation.
5. THE catalog SHALL include fault F05: int or long instead of BigDecimal for amounts, specifically using integer types for fee computation. The exact rewrite in the base fee computation: replace `<expr>.setScale(2, RoundingMode.HALF_UP)` with `BigDecimal.valueOf(<expr>.movePointRight(2).longValue(), 2)` (amount carried as long cents, fraction truncated). This compiles in CreditFees.java and differs from F03 because the value passes through a long.
6. EACH mandatory fault SHALL have a documented rewrite rule that is reviewable (not a black-box mutation).
7. THE rewrite rules SHALL produce code that compiles (syntax-valid Java).
8. ON the credit-fees sample faults F01 and F03 MUST be detected (at least one detected case each). A run where either F01 or F03 is not detected SHALL be considered a failure.

### Requirement 2: Optional bonus faults (time permitting)
**User Story:** As a demo viewer, I want to see Coroner detect additional common errors if time allows.

#### Acceptance Criteria
1. THE catalog MAY include fault F06: amount equality without normalization, specifically `bigDecimal1.equals(bigDecimal2)` instead of `bigDecimal1.compareTo(bigDecimal2) == 0`.
2. THE catalog MAY include fault F07: changed operation order, specifically computing discount before rounding the base fee.
3. THE catalog MAY include fault F08: leading zeros or edited output format, specifically dropping leading zeros or the explicit sign in FEE-AMOUNT output.
4. THE catalog MAY include fault F09: YYYYMMDD date handling errors (reserved, no dates in credit-fees V1).
5. THE catalog MAY include fault F10: return code errors or changed error condition handling.
6. EACH optional fault SHALL be marked clearly in the catalog report as "optional, time permitting".
7. IF an optional fault is not implemented by 2026-11-30 THE report SHALL list it as "not implemented in V1".

### Requirement 3: Automatic deterministic injection
**User Story:** As a developer, I want the fault injection to be reproducible and auditable, never random.

#### Acceptance Criteria
1. THE injection system SHALL read the correct Java source file (`samples/credit-fees/java/CreditFees.java`) and produce one mutated source file per fault.
2. THE injection system SHALL use documented rewrite rules (e.g., AST-based rewriting or regex substitution with explicit patterns).
3. EACH rewrite rule SHALL be deterministic (same input always produces the same output).
4. THE mutated source file SHALL be written to a known location (e.g., `samples/credit-fees/java/variants/CreditFees_F01.java`).
5. THE mutated source SHALL compile with `javac` without errors (syntax must be valid).
6. IF a rewrite rule finds no matching site in the source code (e.g., no RoundingMode.HALF_UP to replace for F01) THE fault SHALL be reported as "not applicable" for this program.
7. THE system SHALL NEVER silently skip a fault without reporting "not applicable" or "injected successfully".

### Requirement 4: Per-fault detection report
**User Story:** As a demo viewer, I want to see exactly which cases Coroner detected for each fault, with no misleading aggregate statistics.

#### Acceptance Criteria
1. FOR EACH injected fault THE report SHALL include: fault ID, fault description, total cases generated, the detection rate for that fault (cases detected divided by cases generated, shown per fault only), the minimal failing case (smallest input values or simplest), and the COBOL line numbers executed for that case.
2. THE detection count SHALL be "N cases detected" (where a case is detected when Coroner comparison finds at least one divergent field for that case).
3. THE report SHALL NOT include any global detection rate, percentage across all faults, or aggregate "X out of Y faults detected".
4. WHEN zero cases are detected for a fault THE report SHALL state "not detected on N cases" (per no-formal-proof.md, never "proven absent").
5. THE minimal failing case among the detected cases SHALL be determined by reusing the minimal-case module of the engine. The deterministic selection rule that module applies: the one with the smallest absolute PRINCIPAL, then the smallest FEE-RATE, then the lowest CASE-ID.
6. THE minimal failing case SHALL show the full input row (CASE-ID, PRINCIPAL, FEE-RATE, DURATION-MONTHS, CUSTOMER-SEGMENT, INCOME), the COBOL output, the faulty Java output, and the divergent field name and values.
7. THE COBOL line numbers executed SHALL be extracted from the GnuCOBOL trace or coverage instrumentation for the minimal failing case.
8. THE fault catalog SHALL reuse the minimal-case module for selection, report generation, and JUnit source test generation. No duplicated selection logic in the catalog.
9. THE report format SHALL be JSON (mandatory, written to runs/<run_id>/fault_catalog.json) plus a text rendering of the same data. The JSON SHALL document these fields per fault: id, description, status (injected or not applicable), cases_generated, cases_detected, detection_rate, minimal_case, cobol_lines, probable_cause, fix_sentence. The JSON feeds the Detection Matrix in the UI.

### Requirement 5: Honest wording per no-formal-proof.md
**User Story:** As a hackathon judge, I need honest claims that do not overstate what was measured.

#### Acceptance Criteria
1. THE report SHALL state "Coroner detected divergence on M cases" for each fault, never "Coroner caught the fault" or "Coroner proved the fault exists".
2. THE report SHALL state "not detected on N cases" when zero divergences are found, never "proven absent" or "fault does not exist".
3. THE report SHALL include a disclaimer: "This catalog measures Coroner's detection on specific injected faults in the credit-fees sample. It does not represent detection rates on other programs or other fault types."
4. THE report SHALL NOT claim the fault catalog is complete, exhaustive, or representative of all migration errors.
5. THE report SHALL use the wording "Validated under GnuCOBOL 3.x" as required by no-formal-proof.md.

### Requirement 6: Fixed seed and reproducibility
**User Story:** As a developer, I need the fault catalog run to be reproducible.

#### Acceptance Criteria
1. THE case generation for each faulty variant SHALL use the same fixed seed as the correct Java version (per quality.md).
2. THE same inputs SHALL produce the same fault catalog report (same faults, same case counts, same minimal failing cases).
3. THE fault injection, compilation, case generation, Coroner run, and report generation SHALL be deterministic with no randomness except the fixed-seed case generator.

### Requirement 7: Compilation requirement for injected faults
**User Story:** As a demo builder, I need every injected fault to produce syntactically valid Java.

#### Acceptance Criteria
1. WHEN a fault is injected THE mutated source SHALL compile with `javac` version 17 without errors.
2. IF the mutated source does not compile THE injection system SHALL report an error and halt (this is a bug in the rewrite rule, not a feature).
3. THE fault catalog run SHALL include a compilation step for each injected variant and report compilation success or failure.

### Requirement 8: Not applicable handling
**User Story:** As a demo builder, I need the fault catalog to report when a fault's rewrite rule does not apply to the program.

#### Acceptance Criteria
1. WHEN a fault's rewrite rule finds no matching site in the source code THE fault SHALL be reported as "not applicable to this program".
2. THE report SHALL list the reason (e.g., "F06 not applicable: no BigDecimal.equals() found in source").
3. THE "not applicable" faults SHALL appear in a separate section of the report, not mixed with detected or undetected faults.

### Requirement 9: Suggested fix without automatic repair
**User Story:** As a user, I want a deterministic probable cause and a one-sentence fix for each detected fault so I can repair the Java code myself.

#### Acceptance Criteria
1. FOR EACH detected fault THE report SHALL include a deterministic probable cause taken from the catalog entry.
2. THE report SHALL state the fix in one sentence (for example "use RoundingMode.HALF_UP" for F01).
3. THE user applies the fix manually, then re-runs Coroner to verify the result is ALIVE.
4. Coroner SHALL NEVER write, patch, or repair code automatically.
5. THE fix sentence SHALL be actionable and specific to the fault (not generic advice).
6. THE probable cause SHALL be worded as "Probable cause: [fault description from catalog]", labeled "deterministic, from the fault catalog".

### Requirement 10: Certificate and JUnit test are separate specs
**User Story:** As a product owner, I need the Coroner Certificate and minimal failing case JUnit test to be built by other modules.

#### Acceptance Criteria
1. THE Coroner Certificate is a separate spec in V1, not part of the fault catalog.
2. THE minimal failing case JUnit 5 source test (ZombieRegressionTest.java) is produced by the minimal-case module of the engine (D-25), not by the fault catalog.
3. THE fault catalog SHALL reuse the minimal-case module for its minimal failing case selection and JUnit test generation.
4. THE fault catalog SHALL NOT duplicate the JUnit test generation logic.
5. A JUnit XML report is a later bonus, not in V1.

### Requirement 11: Fault catalog integration with Coroner engine
**User Story:** As a developer, I need the fault catalog to reuse the Coroner engine modules without duplication.

#### Acceptance Criteria
1. THE fault catalog SHALL call the Coroner case generator (coroner/gen) with the same fixed seed as the main verification run.
2. THE fault catalog SHALL call the Coroner run module (coroner/run) to execute COBOL and Java with the same timeouts and environment setup.
3. THE fault catalog SHALL call the Coroner compare module (coroner/compare) to detect divergences.
4. THE fault catalog SHALL call the Coroner diag module (coroner/diag) to produce the failure report for the minimal failing case.
5. THE fault catalog SHALL NOT duplicate business logic from the engine modules (per quality.md).

### Requirement 12: Makefile target and CLI command
**User Story:** As a developer, I want a simple command to run the fault catalog on the credit-fees sample.

#### Acceptance Criteria
1. A Makefile target `make fault-catalog` SHALL run the fault catalog on the credit-fees sample and print the report.
2. A CLI command `python -m coroner.fault_catalog samples/credit-fees` SHALL run the fault catalog and print the report.
3. THE command SHALL exit with code 0 if all mandatory faults are injected and tested (regardless of detection results), or code 1 if any fault injection or compilation fails.
4. THE report SHALL be written to `runs/<run_id>/fault_catalog_report.txt` and also printed to stdout.
