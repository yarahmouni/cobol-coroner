# Requirements: Veteran's catalog of banking migration traps

## Introduction
The veteran's catalog demonstrates detection of high-impact banking migration traps. Coroner prioritizes these traps and executes automated detection with executable differential tests: each trap is a complete COBOL program with copybooks, a typical faulty Java 17 migration, a correct Java 17 version, input fixtures, automated detection via the S1 engine, and diagnosis with a minimal failing case and JUnit regression test.

The catalog includes six mandatory traps (T01 to T06) and five bonus traps (T07 to T11). Each trap produces a deterministic probable cause from the catalog and a one-sentence fix for the user to apply and re-verify (D-26).

This specification covers the trap program structure and detection pipeline. Out of scope for this spec: UI rendering of the Detection Matrix (S2), coverage of bonus traps if not built by 2026-11-30, automatic code patching.

### Requirement 1: Trap program structure and locations
**User Story:** As a developer, I want each trap to have a standardized structure with COBOL, copybooks, schema, correct and faulty Java versions, and fixtures so the S1 engine can run them unchanged.

#### Acceptance Criteria
1. THE catalog includes six mandatory traps (T01, T02, T03, T04, T05, T06) and five optional bonus traps (T07, T08, T09, T10, T11), each built as a complete executable test case.
2. EACH trap program location SHALL follow the structure `samples/traps/<ID>-<slug>/` containing:
   - `<PROGRAM>.cob` (GnuCOBOL 3.2 COBOL program per cobol-semantics.md)
   - `copybooks/` directory (optional if copybooks are used)
   - `schema.json` (CSV input/output description, S1 engine format per engine requirements 1.7)
   - `java/correct/<Main>.java` (correct Java 17 version, BigDecimal with explicit scale)
   - `java/faulty/<Main>.java` (typical faulty migration demonstrating the trap)
   - `fixtures/` directory with input CSV files
3. EACH trap program's schema.json SHALL describe input and output columns identical to the engine format (program name, description, input section, output section, optional internal_precision section).
4. THE faulty Java version SHALL demonstrate a realistic migration mistake that causes the trap; the correct Java version SHALL reproduce the COBOL behavior exactly.
5. EACH trap SHALL have at least one input fixture CSV file in `fixtures/` directory (format: header row plus data rows, matching the input schema).
6. ALL trap programs SHALL compile with GnuCOBOL 3.2 without warnings or errors (using the reference flags: `cobc -x -Wall -I copybooks`).
7. ALL trap programs SHALL follow cobol-semantics.md coding rules: every IF has an explicit ELSE, every EVALUATE has a WHEN OTHER, no GO TO.
8. TRAP programs are exempt from the 300 to 800 line rule (per D-28).

### Requirement 2: Mandatory traps (T01 to T06)
**User Story:** As an auditor, I want the catalog to demonstrate detection of six high-impact banking migration traps that silently corrupt totals, control breaks, and data ordering.

#### Acceptance Criteria
1. T01 silent left truncation on MOVE: WHEN a COBOL MOVE operation copies a larger numeric value to a smaller PIC clause THE system SHALL silently truncate high-order digits. THE faulty Java SHALL keep all digits or throw an exception, causing divergence. THE correct Java SHALL truncate consistently with COBOL behavior using BigDecimal scale and rounding.
2. T02 ON SIZE ERROR ignored or mishandled: WHEN a COBOL arithmetic operation (ADD, SUBTRACT, MULTIPLY, DIVIDE) would overflow THE system SHALL execute the ON SIZE ERROR clause. THE faulty Java SHALL ignore the condition or use different overflow semantics, causing divergence. THE correct Java SHALL detect and handle size errors matching COBOL behavior.
3. T03 implicit decimal alignment (V99 implied point): WHEN a COBOL V99 field stores data THE system uses an implicit decimal point not stored in the data (e.g., 123 stored in S9(3)V99 represents 1.23). THE faulty Java SHALL read raw digits as units, causing divergence. THE correct Java SHALL apply the decimal scale correctly.
4. T04 EBCDIC vs ASCII collating order: WHEN a COBOL SORT operation uses COLLATING SEQUENCE THE system sorts with EBCDIC alphabet (space, lowercase, uppercase, digits). THE faulty Java SHALL sort with default String order (space, digits, uppercase, lowercase), causing divergence. THE correct Java SHALL sort with EBCDIC byte order matching COBOL.
5. T05 control breaks with level totals: WHEN a COBOL program processes records with control-break logic THE system accumulates subtotals and resets counters on key changes. THE faulty Java SHALL mishandle the break logic or accumulation, causing totals to diverge. THE correct Java SHALL implement control breaks matching COBOL behavior.
6. T06 OCCURS DEPENDING ON bounds: WHEN a COBOL OCCURS DEPENDING ON clause uses a runtime variable THE system adjusts the table size at runtime based on that variable. THE faulty Java SHALL use a fixed size or wrong bounds, causing divergence. THE correct Java SHALL handle variable-length tables matching COBOL.

### Requirement 3: Hero demo (T04 plus T05)
**User Story:** As a product owner, I want a hero demo that combines EBCDIC collating order and control breaks in one program to show the power of Coroner's detection.

#### Acceptance Criteria
1. THE hero demo program SHALL combine T04 (EBCDIC collating order) and T05 (control breaks with level totals) in one executable program at `samples/traps/hero-branch-totals/`.
2. THE hero program logic SHALL: read transaction records with branch codes, sort transactions by branch code using COLLATING SEQUENCE IS an alphabet declared as EBCDIC in SPECIAL-NAMES (in-source clause), then print totals per branch with control-break logic.
3. BRANCH codes SHALL use only uppercase letters, lowercase letters, digits, space and hyphen.
4. THE faulty Java hero version SHALL sort with default String.compareTo order, causing breaks to fall in the wrong place and totals to diverge (verdict ZOMBIE).
5. THE correct Java hero version SHALL sort with EBCDIC collating order (IBM1047 bytes within the domain of letters, digits, space and hyphen) and implement control breaks matching COBOL (verdict ALIVE).
6. THE operator constraint (verified on GnuCOBOL 3.2.0): SORT ... COLLATING SEQUENCE, PROGRAM COLLATING SEQUENCE and -fdefault-colseq=EBCDIC all produce the order space, lowercase, uppercase, digits. GnuCOBOL's EBCDIC collation on letters, digits, space and hyphen matches IBM1047 byte order (IBM1047 differs from JDK charsets at 10 positions on punctuation, outside this domain).
7. THE hero demo SHALL run with `make hero`, showing ZOMBIE on the faulty Java, then ALIVE on the correct Java.
8. WHEN `make hero` finishes THE system SHALL print the ZOMBIE verdict with diagnosis for the faulty version, then the ALIVE verdict for the correct version.

### Requirement 4: Bonus traps (optional)
**User Story:** As a developer, I may build optional traps for additional banking scenarios after the six mandatory traps are complete.

#### Acceptance Criteria
1. FIVE bonus traps MAY be built: T07 REDEFINES, T08 COMP-3 sign handling, T09 spaces vs zeros in numeric fields, T10 YYYYMMDD dates, T11 return codes and error conditions.
2. EACH bonus trap not built by 2026-11-30 SHALL be listed in the trap catalog JSON as "not implemented in V1" (no partial builds).
3. EVERY bonus trap built SHALL follow the same structure as mandatory traps (Requirement 1) and produce ZOMBIE on faulty Java, ALIVE on correct Java.

### Requirement 5: Detection and diagnosis
**User Story:** As a user, I want automated detection of each trap, a minimal failing case, and a deterministic probable cause so I can apply a one-sentence fix.

#### Acceptance Criteria
1. EACH trap SHALL have automated detection via the S1 engine: THE S1 engine run on the faulty Java SHALL produce verdict ZOMBIE with at least one detected case; THE S1 engine run on the correct Java SHALL produce verdict ALIVE.
2. EACH trap SHALL report a per-trap detection count showing: cases generated, cases detected (with divergence), and detection rate (cases_detected / cases_generated) for that trap only. THE system SHALL NOT compute a global detection rate across all traps.
3. DIAGNOSIS for each trap SHALL use the minimal-case submodule of the S1 engine (reused without duplicated logic per engine requirement 7.2) showing the minimal failing case and COBOL lines executed.
4. EACH trap SHALL provide a deterministic probable cause from the catalog entry (the trap name and description) plus the fix stated in one sentence (e.g., "sort with the EBCDIC collating order (IBM1047 bytes) instead of String.compareTo").
5. THE user SHALL apply the suggested fix to the faulty Java, then re-run Coroner to show ALIVE. Coroner SHALL never write, patch or repair code (D-26).

### Requirement 6: JSON report format
**User Story:** As a system developer, I need the catalog to produce a structured JSON report so the Detection Matrix UI can render trap results.

#### Acceptance Criteria
1. THE catalog SHALL produce a JSON report at `runs/<run_id>/trap_catalog.json` with an array of trap results.
2. EACH trap result in the JSON report SHALL include:
   - `id`: trap identifier (T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11)
   - `title`: trap description (one-line name)
   - `status`: "built" or "not implemented in V1"
   - `cases_generated`: number of test cases generated (integer)
   - `cases_detected`: number of cases where divergence was detected (integer)
   - `detection_rate`: cases_detected / cases_generated (float, 0.0 to 1.0)
   - `minimal_case`: the minimal failing case row (object with input fields)
   - `cobol_lines`: list of COBOL line numbers executed for the minimal case
   - `probable_cause`: deterministic cause description (string)
   - `fix_sentence`: one-sentence fix statement (string)
3. THE catalog SHALL produce a text rendering of the JSON report for CLI output and logging.
4. THE JSON report SHALL feed the Detection Matrix in the S2 UI (architecture.md).

### Requirement 7: Integration with the S1 engine
**User Story:** As the engine developer, I want each trap to work with the S1 engine without catalog-specific logic, reusing modules like minimal-case selection and JUnit test generation.

#### Acceptance Criteria
1. EACH trap program's CSV format SHALL be described by its own `schema.json`, so the S1 engine SHALL run it unchanged with no catalog-specific logic in the engine module per engine requirement 9.10.
2. EACH trap SHALL reuse the minimal-case submodule from the S1 engine (engine requirement 7.2 and 7.5) to select the minimal failing case and generate `ZombieRegressionTest.java` (D-25) with no duplicated selection logic.
3. THE Coroner Certificate (D-24) is a separate V1 specification (not part of this trap spec). The JUnit source test generation comes from the minimal-case module.
4. THE legacy HALF_EVEN demo variant (D-06) used by the engine (`make zombie`, engine requirement 9.8) SHALL be produced by one documented rewrite rule: RoundingMode.HALF_UP to RoundingMode.HALF_EVEN in the Java source. This variant is kept in the catalog tooling. THE engine specification SHALL remain unchanged (the catalog tooling produces the variant before passing it to the engine).

### Requirement 8: Acceptance criteria
**User Story:** As a product owner, I need the trap catalog to meet clear acceptance criteria before S2 begins.

#### Acceptance Criteria
1. EVERY mandatory trap (T01, T02, T03, T04, T05, T06) SHALL produce verdict ZOMBIE on its faulty Java version and verdict ALIVE on its correct Java version when run with the default seed and 2,000 generated cases.
2. THE hero demo (T04 plus T05 combined) SHALL run with `make hero` and show ZOMBIE on the faulty hero Java, then ALIVE on the correct hero Java.
3. THE JSON report SHALL be generated for all built traps (at least the six mandatory traps) with all required fields (id, title, status, cases_generated, cases_detected, detection_rate, minimal_case, cobol_lines, probable_cause, fix_sentence) populated and valid.
4. EVERY trap program SHALL compile without errors and run without timeouts on the developer machine and in the coroner Docker image.
5. THE faulty Java of each mandatory trap SHALL have at least one detected case with the default seed; the detection rate per trap is reported, never used as a pass threshold.
6. WHEN any acceptance criterion fails, the trap is not ready for S2 completion and SHALL be flagged in the review log.
