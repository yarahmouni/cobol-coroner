# Tasks: Java 17 version of CREDIT-FEES

- [x] 1. Create parity fixture and expected output
  - Create `samples/credit-fees/fixtures/parity-cases.csv` with one row per parity case from the design (by-value decimals like "10.500" and "10.505", spaces around numbers, leading plus "+100.00", exponent "1E2", half decimal "12.5", trailing decimal "5.", seven fields, five fields, empty line, CASE-ID 11 and 21 characters, CUSTOMER-SEGMENT " B" and empty, negative zero fee case with PRINCIPAL -0.40 and FEE-RATE 0.01000)
  - Create `scripts/gen_parity_cases.py` that generates the 201+ character line case and the CRLF case with reproducible bytes, writes them to the parity-cases.csv file (append mode)
  - Run the generator script
  - Compile the COBOL program with `mkdir -p build && cobc -x -Wall -I samples/credit-fees/copybooks -o build/credit-fees samples/credit-fees/CREDIT-FEES.cob`
  - Run the COBOL program on parity-cases.csv with INPUT_FILE and OUTPUT_FILE environment variables, save its output as `samples/credit-fees/fixtures/parity-expected.csv`
  - Record the exit code in a note under this task
  - Note: Exit code 4 (validation errors present). COBOL accepted: "10.500" (PAR-01), spaces around numbers (PAR-03), leading plus (PAR-04), "12.5" (PAR-06), "5." (PAR-07), CRLF line (PAR-16), empty segment (PAR-14), negative -0.40 printed as +0000000.00 (PAR-15). COBOL rejected: "10.505" (PAR-02), exponent "1E2" (PAR-05), 7 fields (PAR-08), 5 fields (PAR-09), empty line (PAR-10), 201+ char line (PAR-11 cut to 10), CASE-ID 11+ chars (PAR-12 cut to 10), segment " B" with leading space (PAR-13).

_Requirements: 2.1, 2.2, 5.9_

Done when: `INPUT_FILE=samples/credit-fees/fixtures/parity-cases.csv OUTPUT_FILE=samples/credit-fees/fixtures/parity-expected.csv ./build/credit-fees; echo $?` exits with the code recorded in the task note, and parity-expected.csv exists with one output row per input data row.

- [x] 2. Adjust provisional numeric regex in design.md
  - Read parity-expected.csv and identify which numeric formats COBOL accepted (look for rows without E01 where the input had ".5", "5.", "+5", spaces around numbers)
  - Update the numeric regex in design.md Component 3 (parseNumeric method) to match the COBOL behavior
  - Document the final regex in a note under this task
  - Note: Final regex `^[+-]?(\\d+\\.?\\d*|\\.\\d+)$` accepts optional leading sign, then either digits with optional decimal point and optional decimals, or decimal point with required decimals. COBOL accepted: "10.500" (PAR-01), " 100.00 " (PAR-03), "+100.00" (PAR-04), "12.5" (PAR-06), "5." (PAR-07), ".50" (PAR-18), ".01000" (PAR-17). COBOL rejected: "1E2" (PAR-05 exponent), "10.505" (PAR-02 doesn't fit scale 2).

_Requirements: 5.9_

Done when: design.md parseNumeric method has the final regex pattern that accepts exactly the numeric formats COBOL accepted in parity-expected.csv, and the note lists which parity cases were accepted.

- [x] 3. Create CreditFees.java
  - Create `samples/credit-fees/java/` directory if not present
  - Create `samples/credit-fees/java/CreditFees.java` with the complete implementation per the design
  - Single class with public static void main(String[] args) and private static helper methods
  - No dependencies, only JDK 17 standard library (BigDecimal, BufferedReader, BufferedWriter)
  - Input validation with by-value checks using setScale(targetScale, RoundingMode.DOWN).compareTo(value) == 0
  - Fee computation with RoundingMode.HALF_UP for COBOL ROUNDED
  - Segment discounts (P 10%, S 5%, B and other no discount) with HALF_UP rounding
  - Minimum fee enforcement (raise to 10.00 if positive and less than 10.00, set A01)
  - Eligibility check (income below 25000.00 gives R01, duration below 12 gives R02, R01 priority)
  - Output formatting: sign (+ or -) followed by 7 zero-padded digits, point, 2 decimals (11 characters total)
  - Exit codes 0, 4, 16 matching COBOL
  - Record-level variables reset before each row to prevent state leakage
  - Numeric regex adjusted to match the final regex from task 2

_Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.2, 7.3, 7.4, 7.5_

Done when: `javac -Xlint:all -d build/java samples/credit-fees/java/CreditFees.java` exits 0 with no warnings on stderr.

- [x] 4. Write comprehensive tests for Java version
  - Create `tests/test_java_credit_fees.py` with pytest functions
  - Session-scoped fixtures to compile COBOL (build/credit-fees) and Java (build/java/CreditFees.class) once per session
  - Parametrized test `test_java_cobol_equivalence` for each fixture file (rounding-ties.csv, edge-cases.csv, validation-errors.csv, parity-cases.csv)
  - Each parametrized test runs COBOL and Java with the same input (timeout 10 seconds each), asserts equal exit codes and byte-identical outputs
  - Test `test_empty_input` with no input file (just header), asserts exit 0 and output has header only
  - Test `test_missing_file` with INPUT_FILE set to non-existent path, asserts exit 16 and stderr has error message
  - Test `test_java_rules` that CreditFees.java contains no 'double', 'float', 'Math.round', and no "int fee" or "long principal" patterns (grep-based)
  - All tests skip with clear reason when cobc or javac is missing

_Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

Done when: `.venv/bin/pytest tests/test_java_credit_fees.py -q` shows all tests passing or skipped with clear skip reasons when cobc or java is missing.

- [x] 5. Add Makefile target for Java sample
  - Add `java-sample` target to Makefile that compiles CreditFees.java into build/java/, then runs it on rounding-ties.csv with OUTPUT_FILE=build/java-rounding-ties-output.csv, without changing other existing targets

_Requirements: 1.1_

Done when: `make java-sample` compiles the Java program, runs it on rounding-ties.csv, writes output to build/java-rounding-ties-output.csv, and exits 0.

## Requirements Coverage

| Requirement | Covered by Tasks |
|-------------|------------------|
| 1.1 | 3, 5 |
| 1.2 | 3 |
| 1.3 | 3 |
| 1.4 | 3 |
| 1.5 | 3 |
| 2.1 | 1, 3 |
| 2.2 | 1, 3 |
| 2.3 | 3 |
| 3.1 | 3 |
| 3.2 | 3 |
| 3.3 | 3 |
| 3.4 | 3 |
| 3.5 | 3 |
| 3.6 | 3 |
| 4.1 | 3 |
| 4.2 | 3 |
| 4.3 | 3 |
| 5.1 | 3 |
| 5.2 | 3 |
| 5.3 | 3 |
| 5.4 | 3 |
| 5.5 | 3 |
| 5.6 | 3 |
| 5.7 | 3 |
| 5.8 | 3 |
| 5.9 | 1, 2, 3 |
| 5.10 | 3 |
| 5.11 | 3 |
| 5.12 | 3 |
| 6.1 | 3 |
| 6.2 | 3 |
| 6.3 | 3 |
| 6.4 | 3 |
| 6.5 | 3 |
| 6.6 | 3 |
| 6.7 | 3 |
| 7.1 | 3 |
| 7.2 | 3 |
| 7.3 | 3 |
| 7.4 | 3 |
| 7.5 | 3 |
| 9.1 | 4 |
| 9.2 | 4 |
| 9.3 | 4 |
| 9.4 | 4 |
| 9.5 | 4 |
