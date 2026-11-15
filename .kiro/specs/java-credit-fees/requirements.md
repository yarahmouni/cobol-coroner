# Requirements: Java 17 version of CREDIT-FEES

## Introduction
The Java 17 equivalent of the synthetic COBOL program samples/credit-fees/CREDIT-FEES.cob. This is the correct Java migration that Coroner will verify. It must produce byte-identical output to the COBOL reference program for every input in samples/credit-fees/fixtures.

The Java version demonstrates a correctly migrated batch program using BigDecimal with explicit scale, correct rounding mode (HALF_UP for COBOL ROUNDED), and exact business logic preservation. It serves as the ALIVE baseline that Coroner will compare against automatically injected faulty variants (fault catalog, see separate spec).

### Requirement 1: Single-file Java program with no dependencies
**User Story:** As a demo viewer, I want a simple Java program that can be compiled and run without external libraries.

#### Acceptance Criteria
1. THE Java program SHALL be a single source file at `samples/credit-fees/java/CreditFees.java`.
2. THE program SHALL require only JDK 17 with no external dependencies (no Maven, no Gradle, no third-party libraries).
3. THE program SHALL read input and output file paths from environment variables INPUT_FILE and OUTPUT_FILE.
4. THE program SHALL exit with the same return codes as the COBOL program: 0 for success, 4 when at least one validation error occurred, 16 when environment variables are missing or the input file cannot be opened.
5. THE program SHALL process the entire input file in a single JVM run (batch processing, not one JVM per case).

### Requirement 2: Byte-identical output with COBOL reference
**User Story:** As Coroner, I need the Java output to match the COBOL output exactly so differential comparison can detect any divergence.

#### Acceptance Criteria
1. WHEN the Java program runs on any input from samples/credit-fees/fixtures THE output SHALL be byte-identical to the COBOL program output (same header, same row order, same formatted values, LF line endings).
2. THE FEE-AMOUNT output SHALL use the format `+9(7).99` with always a leading sign (+ or -), 7 digits, a decimal point, and 2 decimals (e.g., `+0000012.35` or `-0000012.35`).
3. THE CASE-ID output SHALL be trimmed of trailing spaces only (COBOL FUNCTION TRIM ... TRAILING), with length measured after trimming trailing spaces only; CASE-ID is blank when all spaces.
4. THE CUSTOMER-SEGMENT length SHALL be measured after trimming trailing spaces only (so " B" is E01, empty is valid and goes to WHEN OTHER).
5. THE REASON-CODE output SHALL match COBOL priority: E01 (validation or overflow), R01 (income below 25000.00), R02 (duration below 12), A01 (minimum fee applied), A00 (normal eligible).
6. THE program SHALL write the CSV header row `CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE` before processing data rows.

### Requirement 3: BigDecimal with explicit scale, no floating-point types
**User Story:** As a banking migration, I need exact decimal arithmetic with no precision loss.

#### Acceptance Criteria
1. THE program SHALL use `java.math.BigDecimal` with explicit scale for all monetary amounts and rates.
2. THE program SHALL NOT use `double`, `float`, `int`, or `long` for any amount or rate computation.
3. THE program MAY use `int` for non-monetary values (duration months, field counts, loop counters).
4. THE internal precision for FEE-AMOUNT computation SHALL be scale 2 (matching COBOL S9(7)V99 COMP-3).
5. WHEN the COBOL program uses ROUNDED THE Java program SHALL use `BigDecimal.setScale(2, RoundingMode.HALF_UP)`.
6. WHEN the COBOL program does not use ROUNDED THE Java program SHALL use `RoundingMode.DOWN` (truncation).

### Requirement 4: COMP-3 range enforcement and rounding
**User Story:** As Coroner, I need the Java program to enforce the same overflow detection as COBOL ON SIZE ERROR, with the range check applied after rounding.

#### Acceptance Criteria
1. THE range check for COMP-3 S9(7)V99 (absolute value greater than 9999999.99) SHALL happen after rounding to scale 2 with RoundingMode.HALF_UP, matching COBOL ON SIZE ERROR with ROUNDED.
2. WHEN a rounded computed fee exceeds this range THE program SHALL set REASON-CODE to "E01" and continue processing the next record.
3. THE overflow check SHALL compare the absolute value of the BigDecimal result against 9999999.99 after all rounding operations.

### Requirement 5: Input validation equivalent to COBOL
**User Story:** As Coroner, I need the Java program to reject the same invalid inputs as the COBOL program.

#### Acceptance Criteria
1. THE program SHALL validate the field count: a row with more than 6 fields is E01 (COBOL ON OVERFLOW), trailing empty fields are kept (like String.split(",", -1)).
2. THE program SHALL validate CASE-ID: not blank (after trimming trailing spaces only), at most 10 characters.
3. THE program SHALL validate all numeric fields: not blank, parse as BigDecimal without exception.
4. THE program SHALL validate PRINCIPAL: in range -999999999.99 to 999999999.99, at most 2 decimal places; PRINCIPAL cannot have 3 decimals (that is E01).
5. THE program SHALL validate FEE-RATE: in range [0, 1), at most 5 decimal places.
6. THE program SHALL validate DURATION-MONTHS: integer 0 to 999.
7. THE program SHALL validate CUSTOMER-SEGMENT: at most 1 character after trimming trailing spaces only.
8. THE program SHALL validate INCOME: non-negative, at most 2 decimal places, at most 999999999.99.
9. WHEN input numeric text is in canonical format (optional leading `-`, digits, optional `.` and decimals, no spaces, no trailing signs, no CR or DB) THE program SHALL parse it correctly.
10. WHEN input numeric text is in non-canonical format (trailing sign, CR or DB suffix, embedded spaces, parentheses for negatives) THE behavior is defined by the COBOL reference program run on that input, and such inputs are out of scope for the V1 Coroner case generator (documented in the design and test plan).
11. WHEN any validation fails THE program SHALL set REASON-CODE to "E01", ELIGIBLE to "N", FEE-AMOUNT to `+0000000.00`, increment an error counter, and continue processing the next record.
12. WHEN the error counter is greater than zero at the end of processing THE program SHALL exit with code 4.

### Requirement 6: Business logic preservation
**User Story:** As Coroner, I need the Java program to implement the exact business rules from the COBOL program.

#### Acceptance Criteria
1. THE program SHALL compute base fee as `PRINCIPAL * FEE-RATE` rounded to scale 2 with RoundingMode.HALF_UP (COBOL ROUNDED). Example: PRINCIPAL -1234.50 x FEE-RATE 0.01000 = -12.345 gives -0000012.35 (the product -12.345 is rounded to -12.35).
2. THE program SHALL apply segment discounts: 'P' gives 10% discount, 'S' gives 5% discount, 'B' and any other segment give no discount.
3. WHEN segment is 'P' or 'S' THE discount computation SHALL be `baseFee * (1 - discountRate)` rounded to scale 2 with RoundingMode.HALF_UP.
4. WHEN the discounted fee is greater than zero and less than 10.00 THE program SHALL raise it to 10.00 and set REASON-CODE to "A01".
5. THE program SHALL check eligibility: INCOME less than 25000.00 gives "R01", DURATION-MONTHS less than 12 gives "R02" (R01 has priority over R02).
6. THE program SHALL initialize all record-level variables before processing each row to prevent state leakage between records.
7. THE program SHALL handle negative PRINCIPAL values (rebates) correctly, rounding away from zero (e.g., -100.005 becomes -100.01).

### Requirement 7: Error handling
**User Story:** As Coroner, I need the Java program to handle missing files and environment variables the same way as COBOL.

#### Acceptance Criteria
1. WHEN INPUT_FILE or OUTPUT_FILE environment variable is missing THE program SHALL print an error message to stderr and exit with code 16.
2. WHEN the input file cannot be opened THE program SHALL print an error message to stderr and exit with code 16.
3. WHEN the input file is empty (no header row) THE program SHALL write the output header row and exit with code 0.
4. WHEN a CSV row has a parsing exception THE program SHALL treat it as a validation error (E01) and continue processing the next row.

### Requirement 8: No hand-written HALF_EVEN variant
**User Story:** As a demo builder, I want the fault catalog to automatically inject bugs rather than maintaining multiple versions by hand.

#### Acceptance Criteria
1. THE design and implementation SHALL produce only the correct Java version with RoundingMode.HALF_UP.
2. THE HALF_EVEN variant (D-06 demo bug) SHALL NOT be hand-written or maintained as a separate file.
3. THE HALF_EVEN variant SHALL be produced automatically by the fault catalog's injection system (F01 fault, see separate spec).

### Requirement 9: Regression test with COBOL reference
**User Story:** As a developer, I need automated tests to ensure the Java version stays equivalent to the COBOL reference.

#### Acceptance Criteria
1. A pytest test `tests/test_java_credit_fees.py::test_java_cobol_equivalence` SHALL exist.
2. FOR EACH fixture file in samples/credit-fees/fixtures (rounding-ties.csv, edge-cases.csv, validation-errors.csv) THE test SHALL run both the COBOL program and the Java program with the same input and assert byte-identical outputs and equal exit codes.
3. WHEN `cobc` or `java` is not available on the system THE test SHALL skip with a clear skip message (not fail).
4. THE test SHALL use a timeout for each program run (e.g., 30 seconds) to prevent hanging on infinite loops or blocking input.
5. THE test SHALL clean up temporary output files after each run.
