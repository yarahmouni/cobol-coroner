# Requirements: synthetic COBOL sample "credit-fees"

## Introduction
A synthetic batch COBOL program that computes fees and checks eligibility for credit files. It is the reference program of the demo. It contains no code, data or algorithm from a real bank.

### Requirement 1: Business behavior
**User Story:** As a demo viewer, I want a realistic but small banking program.

#### Acceptance Criteria
1. THE program SHALL read input records from a CSV file described in `samples/credit-fees/schema.json`: CASE-ID, PRINCIPAL (S9(9)V99), FEE-RATE (V9(5)), DURATION-MONTHS (9(3)), CUSTOMER-SEGMENT (X(1)), INCOME (9(9)V99).
2. THE program SHALL compute FEE-AMOUNT (S9(7)V99 COMP-3 internally) = PRINCIPAL x FEE-RATE with ROUNDED.
3. THE program SHALL apply at least 3 business branches: segment discounts (EVALUATE on CUSTOMER-SEGMENT), a minimum fee, and an eligibility rule based on INCOME and DURATION-MONTHS.
4. THE program SHALL write one output CSV row per case: CASE-ID, FEE-AMOUNT, ELIGIBLE (Y/N), REASON-CODE.
5. WHEN an input record is invalid THE program SHALL write REASON-CODE "E01" and set RETURN-CODE to 4 at the end of the run.
6. THE program SHALL accept negative PRINCIPAL values (rebates) and round them away from zero.

### Requirement 2: Coding rules
#### Acceptance Criteria
1. THE program SHALL follow `.kiro/steering/cobol-semantics.md` (explicit ELSE, WHEN OTHER, no GO TO, SIGN LEADING SEPARATE output).
2. THE program SHALL be between 300 and 800 lines and use 1 to 3 copybooks.
3. THE program SHALL compile with GnuCOBOL 3.2 without warnings.

### Requirement 3: Demo trap
#### Acceptance Criteria
1. THE sample SHALL include a fixture of at least 20 inputs where PRINCIPAL x FEE-RATE is an exact rounding tie (remainder 0.005 at scale 2), positive and negative.
2. A file `expected-output.csv` for those fixtures SHALL be produced by the COBOL program and committed.
