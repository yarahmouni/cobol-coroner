# Tasks: synthetic COBOL sample credit-fees

- [x] 1. Create schema and copybooks
  - Create `samples/credit-fees/schema.json` with input columns (CASE-ID, PRINCIPAL, FEE-RATE, DURATION-MONTHS, CUSTOMER-SEGMENT, INCOME) and output columns (CASE-ID, FEE-AMOUNT, ELIGIBLE, REASON-CODE) with complete type, pic, and scale metadata
  - Create `samples/credit-fees/copybooks/` directory
  - Create `samples/credit-fees/copybooks/INPUT-WORK-FIELDS.cpy` with alphanumeric parsing fields and numeric fields
  - Create `samples/credit-fees/copybooks/OUTPUT-RECORD.cpy` with OUT-CASE-ID, OUT-FEE-AMOUNT (PIC +9(7).99), OUT-ELIGIBLE, OUT-REASON-CODE
  - Create `samples/credit-fees/copybooks/CONSTANTS.cpy` with WS-MIN-FEE (10.00), WS-MIN-INCOME (25000.00), WS-MIN-DURATION (12)

_Requirements: 1.1_

Done when: `python3.12 -m json.tool samples/credit-fees/schema.json` exits 0 with valid JSON output, and all three copybooks exist with complete field definitions.

- [x] 2. Create CREDIT-FEES COBOL program
  - Create `samples/credit-fees/CREDIT-FEES.cob` with complete program structure per the design
  - ENVIRONMENT DIVISION with FILE-CONTROL using ASSIGN DYNAMIC TO <data-name> for INPUT-FILE and OUTPUT-FILE
  - WORKING-STORAGE with INPUT-FILE-PATH and OUTPUT-FILE-PATH accepting from ENVIRONMENT
  - MAIN-PROCESS paragraph with environment variable validation and file status checks
  - PROCESS-RECORD paragraph with INITIALIZE at entry to prevent state leaks between records
  - PARSE-INPUT paragraph with UNSTRING ... ON OVERFLOW
  - VALIDATE-INPUT and VALIDATE-NUMERIC-FIELDS paragraphs with TEST-NUMVAL and NUMVAL equality checks for all numeric fields
  - COMPUTE-FEE paragraph with ROUNDED and ON SIZE ERROR
  - APPLY-SEGMENT-DISCOUNT paragraph with EVALUATE on CUSTOMER-SEGMENT (WHEN 'P', WHEN 'S', WHEN 'B', WHEN OTHER), each branch with ROUNDED and ON SIZE ERROR
  - CHECK-ELIGIBILITY paragraph checking income and duration
  - REJECT-RECORD paragraph for E01 handling
  - Every IF has explicit ELSE, no GO TO statements
  - Return codes: 0 (success), 4 (validation error), 16 (file error)

_Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2_

Done when: `mkdir -p build && cobc -x -Wall -I samples/credit-fees/copybooks -o build/credit-fees samples/credit-fees/CREDIT-FEES.cob` exits 0 with empty stderr (no warnings, no errors), and `wc -l samples/credit-fees/CREDIT-FEES.cob` shows between 300 and 800 lines.

- [x] 3. Smoke test CREDIT-FEES program
  - Create `build/` directory if not present
  - Create hand-written test input file in build/ with 4 rows: header, one valid eligible row (segment B, income 50000.00, duration 24), one E01 row (blank CASE-ID), one valid row after E01 to test no state leak
  - Run with INPUT_FILE=<hand-written input> and OUTPUT_FILE=build/smoke-output.csv
  - Verify exit code 4 (E01 present)
  - Verify output has header plus 3 rows
  - Verify first row has normal output (Y, A00), second row has E01 output (+0000000.00, N, E01), third row has normal output
  - Run with missing INPUT_FILE environment variable
  - Verify exit code 16 with error message on stderr

_Requirements: 1.4, 1.5_

Done when: smoke test with hand-written input exits 4, output has correct E01 and normal rows, and missing file test exits 16 with error message.

- [x] 4. Create fixture generator and oracle test
  - Create `scripts/` directory if not present
  - Create `scripts/gen_rounding_ties.py` that generates at least 20 exact rounding tie cases using Python Decimal with fixed seed
  - Generator verifies each tie: abs(Decimal(PRINCIPAL) * Decimal(FEE-RATE) % Decimal('0.01')) equals Decimal('0.005')
  - Generator ensures at least 16 even-digit ties, at least 4 odd-digit ties, at least 6 negative even-digit ties
  - Generator writes to `samples/credit-fees/fixtures/rounding-ties.csv` with header
  - All rows have segment B (no discount), income >= 25000.00, duration >= 12, absolute base fee >= 10.00
  - Create `tests/test_rounding_ties_oracle.py` that verifies ties without running COBOL
  - Oracle test computes product with sufficient precision, asserts exact tie, computes COBOL expected (ROUND_HALF_UP) and HALF_EVEN expected, asserts divergence when preceding digit is even
  - Oracle test asserts fixture counts (16 even, 4 odd, 6 negative even)

_Requirements: 3.1_

Done when: `python3.12 scripts/gen_rounding_ties.py` creates `samples/credit-fees/fixtures/rounding-ties.csv` with at least 20 rows, and `.venv/bin/pytest tests/test_rounding_ties_oracle.py -q` passes with all assertions verified.

- [x] 5. Create edge-cases and validation-errors fixtures
  - Create `samples/credit-fees/fixtures/` directory if not present
  - Create `samples/credit-fees/fixtures/edge-cases.csv` with boundary value rows: PRINCIPAL zero, PRINCIPAL 999999999.99, PRINCIPAL -999999999.99, FEE-RATE 0.00000, FEE-RATE 0.99999, DURATION-MONTHS 0, DURATION-MONTHS 999, INCOME 0.00, INCOME 999999999.99, CUSTOMER-SEGMENT 'P', 'S', 'B', 'X', space, overflow case (PRINCIPAL 999999999.99 and FEE-RATE 0.99999), all with valid CASE-ID and complete fields
  - Create `samples/credit-fees/fixtures/validation-errors.csv` with E01 test rows: 5 fields, 7 fields, blank CASE-ID, CASE-ID 11 characters, CASE-ID with comma, blank PRINCIPAL, non-numeric PRINCIPAL, PRINCIPAL with 3 decimals, PRINCIPAL above 999999999.99, blank FEE-RATE, FEE-RATE 1.00000, negative FEE-RATE, DURATION-MONTHS 12.5, negative DURATION-MONTHS, negative INCOME, CUSTOMER-SEGMENT 2 characters, overflow case, plus valid rows interleaved to test no state leak

_Requirements: 1.5_

Done when: validation-errors.csv has one row per E01 cause listed in the design (at least 15) with valid rows interleaved, and edge-cases.csv has one row per edge case listed in the design.

- [x] 6. Generate and verify expected-output.csv
  - Add Makefile targets `cobol-sample` (runs credit-fees on rounding-ties into build/) and `sample-expected` (manual regeneration target that writes to fixtures/expected-output.csv with warning message)
  - Run `make sample-expected` to generate `samples/credit-fees/fixtures/expected-output.csv` from rounding-ties.csv
  - Manually verify a sample of at least 5 rows from expected-output.csv against the oracle test expected values (check that even-digit ties match ROUND_HALF_UP, odd-digit ties match both)
  - Document in a note under this task that manual verification was done

_Requirements: 3.2_

Done when: `make sample-expected` writes expected-output.csv, and an automated check (added to tests/test_rounding_ties_oracle.py) asserts that EVERY row's FEE-AMOUNT in expected-output.csv equals the oracle value quantize(0.01, ROUND_HALF_UP) of PRINCIPAL x FEE-RATE, formatted as +9(7).99. Not a manual sample.

- [x] 7. Write comprehensive unit tests for CREDIT-FEES
  - Create `tests/test_cobol_sample.py` with pytest functions
  - Test 1: compilation without warnings (cobc -x -Wall exits 0, stderr empty)
  - Test 2: rounding-ties fixture (exit 0, output row count matches input, byte-exact comparison with expected-output.csv)
  - Test 3: edge-cases fixture (exit 0 or 4, verify zero fee, max values, segments, overflow E01, income R01, duration R02)
  - Test 4: negative PRINCIPAL rounding (at least 6 negative tie rows, verify rounded away from zero)
  - Test 5: segment discount branches (verify P 10%, S 5%, B and X no discount)
  - Test 6: minimum fee enforcement (case where discounted fee < 10.00, verify FEE-AMOUNT +0000010.00 and REASON-CODE A01)
  - Test 7: eligibility rules (income < 25000.00 gives R01, duration < 12 gives R02, both sufficient gives Y)
  - Test 8: validation rules (validation-errors.csv, exit 4, all E01 rows have +0000000.00 N E01, valid interleaved rows correct)
  - Test 9: missing file error (INPUT_FILE set to non-existent path, exit 16, stderr has error message)
  - All tests compile into build/ directory and skip with clear reason if cobc not on PATH

_Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.2, 2.3, 3.1, 3.2_

Done when: `.venv/bin/pytest tests/test_cobol_sample.py -q` shows all tests passing on host with GnuCOBOL 3.2, and tests skip gracefully when cobc is missing.

- [x] 8. Verify requirement 2.1 with review checklist
  - Create script `scripts/check_cobol_rules.py` (Python) that verifies: (1) no GO TO statements, (2) number of EVALUATE equals number of WHEN OTHER, (3) every IF has a corresponding ELSE (counts match per line-starting patterns)
  - Script prints counts and exits non-zero on any violation
  - Run script and verify all checks pass

_Requirements: 2.1_

Done when: `python3.12 scripts/check_cobol_rules.py` exits 0 with output showing GO TO count 0, EVALUATE count equals WHEN OTHER count, and IF count equals ELSE count.

## Requirements Coverage

| Requirement | Covered by Tasks |
|-------------|------------------|
| 1.1 | 1, 2, 7 |
| 1.2 | 2, 7 |
| 1.3 | 2, 7 |
| 1.4 | 2, 3, 7 |
| 1.5 | 2, 3, 5, 7 |
| 1.6 | 2, 7 |
| 2.1 | 2, 8 |
| 2.2 | 2, 7 |
| 2.3 | 7 |
| 3.1 | 4, 7 |
| 3.2 | 6, 7 |
