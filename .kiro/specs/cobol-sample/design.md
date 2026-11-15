# Design: Synthetic COBOL sample "credit-fees"

## Overview

This spec defines the reference COBOL program for demonstrating COBOL Coroner, the independent regression auditor for COBOL-to-Java migrations. The program computes credit file fees with segment discounts and eligibility rules, and deliberately includes the rounding trap that a buggy Java migration would trigger.

The synthetic program represents a realistic banking batch operation: reading credit applications from CSV, computing fees with COBOL ROUNDED arithmetic (nearest away from zero), applying business rules through EVALUATE and IF/ELSE, and writing results with eligibility decisions. It contains no real bank code or data.

The design ensures the program has measurable paragraph coverage and branch coverage (Coroner definition per D-07), includes at least 20 exact rounding ties to expose the HALF_UP vs HALF_EVEN bug (D-06), and compiles cleanly with GnuCOBOL 3.2 following the coding rules in cobol-semantics.md.

Per D-06, HALF_EVEN diverges from COBOL ROUNDED only when the exact product ends in .005 (or .015, .025, etc.) and the preceding digit is even. For example: 2.025 with preceding digit 2 (even) rounds to 2.03 in COBOL but 2.02 in HALF_EVEN; 2.035 with preceding digit 3 (odd) rounds to 2.04 in both.

**Worked examples (verified with Python Decimal):**
- 1234.50 x 0.01000 = 12.3450000, tie, preceding digit 4 even: COBOL +0000012.35, HALF_EVEN 12.34 (diverges)
- -1234.50 x 0.01000 = -12.3450000, even: COBOL -0000012.35, HALF_EVEN -12.34 (diverges)
- 2469.00 x 0.00500 = 12.3450000, even: COBOL 12.35, HALF_EVEN 12.34 (diverges)
- -4115.00 x 0.00300 = -12.3450000, even: COBOL -12.35, HALF_EVEN -12.34 (diverges)
- 1023.50 x 0.01000 = 10.2350000, preceding digit 3 odd: both 10.24 (control)
- 500.00 x 0.02051 = 10.2550000, odd: both 10.26 (control)
- -2047.00 x 0.00500 = -10.2350000, odd: both -10.24 (control)

Success criteria: the program compiles without warnings, runs on a fixture of rounding-tie cases, produces expected-output.csv that Coroner will later verify against a Java version, and the program alone (CREDIT-FEES.cob) stays within 300 to 800 lines (target about 400 lines), plus 1 to 3 copybooks.

## Architecture

### High-level flow

```
┌────────────────────────────────────────────────────────────────────┐
│ samples/credit-fees/                                               │
│                                                                    │
│   input.csv                                                        │
│   (CASE-ID, PRINCIPAL, FEE-RATE, DURATION-MONTHS,                 │
│    CUSTOMER-SEGMENT, INCOME)                                       │
│         │                                                          │
│         v                                                          │
│   ┌──────────────────┐                                            │
│   │ CREDIT-FEES      │  (COBOL program)                           │
│   │                  │                                            │
│   │ reads CSV        │  <- INPUT-WORK-FIELDS.cpy                  │
│   │ UNSTRING         │  <- OUTPUT-RECORD.cpy                      │
│   │                  │  <- CONSTANTS.cpy                          │
│   │ EVALUATE         │                                            │
│   │ CUSTOMER-SEGMENT │  (P, S, B, OTHER)                          │
│   │                  │                                            │
│   │ IF INCOME        │  (eligibility)                             │
│   │ IF FEE-AMOUNT    │  (minimum fee)                             │
│   │                  │                                            │
│   │ ROUNDED          │  (nearest away from zero)                  │
│   │                  │                                            │
│   │ writes CSV       │  (writes to build/, not fixtures/)         │
│   └──────────────────┘                                            │
│         │                                                          │
│         v                                                          │
│   build/credit-fees-output.csv                                    │
│   (CASE-ID, FEE-AMOUNT, ELIGIBLE, REASON-CODE)                    │
│                                                                    │
│   schema.json                                                      │
│   (input columns, output columns, types, PIC, scale)               │
│                                                                    │
│   fixtures/                                                        │
│     rounding-ties.csv       (at least 20 exact ties)               │
│     expected-output.csv     (reference from COBOL run)             │
│     edge-cases.csv          (negative, zero, large values)         │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Key decisions

- CSV input and output with line sequential files. The COBOL program reads each line as a string and uses UNSTRING with comma delimiter to populate alphanumeric work fields, then validates with FUNCTION TEST-NUMVAL and converts with FUNCTION NUMVAL (UNSTRING into numeric DISPLAY fields would ignore decimal points and signs).
- Numeric output fields use an edited picture with explicit sign and decimal point (PIC +9(7).99, always a leading + or -, explicit point, no spaces). Output format examples: +0000002.03, -0000002.03, +0000000.00.
- CASE-ID is written without trailing spaces using STRING ... DELIMITED BY SPACE so the CSV has no padding.
- COMP-3 fields are internal only (FEE-AMOUNT in WORKING-STORAGE). All input fields are parsed from alphanumeric. Output numeric field FEE-AMOUNT uses PIC +9(7).99.
- ROUNDED means nearest away from zero in GnuCOBOL (maps to Java RoundingMode.HALF_UP per cobol-semantics.md).
- Intermediate FEE-AMOUNT is S9(7)V99 COMP-3 (9 digits, scale 2). This precision is documented in schema.json and the Java version must match it.
- All COMPUTE statements use ON SIZE ERROR to catch silent overflow; an overflow makes the record invalid (E01).
- EVALUATE on CUSTOMER-SEGMENT has WHEN 'P', WHEN 'S', WHEN 'B', WHEN OTHER (required by coverage metric per D-07).
- Every IF has an explicit ELSE (required by coverage metric per cobol-semantics.md).
- Validation (requirement 1.5): field count, blank CASE-ID, TEST-NUMVAL on all numeric fields, range checks on PRINCIPAL, FEE-RATE, DURATION-MONTHS, INCOME, CUSTOMER-SEGMENT length. Invalid records get REASON-CODE E01, ELIGIBLE N, FEE-AMOUNT zero, and RETURN-CODE 4 at the end. Processing continues with the next record.
- REASON-CODE is PIC X(3) with 3-character codes: E01 (invalid record), R01 (not eligible, income below 25000.00), R02 (not eligible, duration below 12 months), A01 (eligible, minimum fee applied), A00 (eligible, normal). Priority (highest first): E01, R01, R02, A01, A00.
- RETURN-CODE is set to 4 when any validation fails (E01), otherwise 0. An input file with only a header produces only the output header and RETURN-CODE 0.
- File paths for input and output CSV are provided via environment variables INPUT_FILE and OUTPUT_FILE. File assignment uses ASSIGN DYNAMIC with a WORKING-STORAGE field holding the path from ACCEPT ... FROM ENVIRONMENT (verified in the compile task). If INPUT_FILE or OUTPUT_FILE environment variable is missing, or the input file cannot be opened, DISPLAY an error message on UPON SYSERR and end with RETURN-CODE 16.
- Runs write output to build/ (e.g., build/credit-fees-output.csv). The committed fixtures/expected-output.csv is regenerated only by an explicit manual step (make target 'sample-expected', documented).

## Components and Interfaces

### Component 1: schema.json

**Purpose:** Define the structure and types of input and output CSV columns so Coroner modules can parse, generate and compare values precisely.

**Location:** `samples/credit-fees/schema.json`

**Format:**
```json
{
  "program": "CREDIT-FEES",
  "description": "Synthetic credit file fee computation with eligibility check",
  "input": {
    "file": "input.csv",
    "columns": [
      {
        "name": "CASE-ID",
        "type": "string",
        "pic": "X(10)",
        "description": "Unique case identifier"
      },
      {
        "name": "PRINCIPAL",
        "type": "decimal",
        "pic": "S9(9)V99",
        "scale": 2,
        "description": "Credit principal amount, may be negative"
      },
      {
        "name": "FEE-RATE",
        "type": "decimal",
        "pic": "V9(5)",
        "scale": 5,
        "description": "Fee rate as decimal (e.g., 0.02500 for 2.5%)"
      },
      {
        "name": "DURATION-MONTHS",
        "type": "integer",
        "pic": "9(3)",
        "description": "Credit duration in months"
      },
      {
        "name": "CUSTOMER-SEGMENT",
        "type": "string",
        "pic": "X(1)",
        "description": "Customer segment: P, S, B, or other"
      },
      {
        "name": "INCOME",
        "type": "decimal",
        "pic": "9(9)V99",
        "scale": 2,
        "description": "Annual income, unsigned"
      }
    ]
  },
  "output": {
    "file": "output.csv",
    "columns": [
      {
        "name": "CASE-ID",
        "type": "string",
        "pic": "X(10)",
        "description": "Case identifier from input"
      },
      {
        "name": "FEE-AMOUNT",
        "type": "decimal",
        "pic": "+9(7).99",
        "scale": 2,
        "description": "Computed fee with leading sign and decimal point (e.g., +0000002.03 or -0000002.03)"
      },
      {
        "name": "ELIGIBLE",
        "type": "string",
        "pic": "X(1)",
        "description": "Eligibility: Y or N"
      },
      {
        "name": "REASON-CODE",
        "type": "string",
        "pic": "X(3)",
        "description": "Reason code: A00 (eligible, normal), A01 (eligible, minimum fee applied), R01 (not eligible, income), R02 (not eligible, duration), E01 (invalid record)"
      }
    ]
  },
  "internal_precision": {
    "FEE-AMOUNT": {
      "pic": "S9(7)V99 COMP-3",
      "description": "Internal computation uses 9 digits, scale 2"
    }
  }
}
```

**Key schema conventions:**
- Column `name` matches COBOL field names with hyphens.
- `type` is one of: `string`, `decimal`, `integer`.
- `pic` is the COBOL PICTURE clause. For output decimal fields with explicit sign and decimal point, the PIC uses the edited format (e.g., `+9(7).99`).
- `scale` is the number of decimal places for decimal types.
- Input decimal fields without SIGN clause are unsigned (e.g., INCOME is `9(9)V99`).
- Output decimal field FEE-AMOUNT uses an edited picture with leading sign and decimal point (PIC +9(7).99).
- The first column is always the case identifier for matching rows between COBOL and Java output.

### Component 2: Copybooks

**Purpose:** Separate record layouts and reduce duplication, following standard COBOL practice.

**Location:** `samples/credit-fees/copybooks/`

**Copybook 1: INPUT-WORK-FIELDS.cpy**

Alphanumeric work fields for parsing CSV input with UNSTRING, then validating with TEST-NUMVAL and converting with NUMVAL.

```
01  INPUT-WORK-FIELDS.
    05  WS-IN-CASE-ID-RAW        PIC X(20).
    05  WS-IN-PRINCIPAL-TXT      PIC X(20).
    05  WS-IN-FEE-RATE-TXT       PIC X(20).
    05  WS-IN-DURATION-TXT       PIC X(20).
    05  WS-IN-SEGMENT-TXT        PIC X(20).
    05  WS-IN-INCOME-TXT         PIC X(20).
    05  WS-FIELD-COUNT           PIC 9 VALUE 0.

01  INPUT-NUMERIC-FIELDS.
    05  IN-PRINCIPAL             PIC S9(9)V99.
    05  IN-FEE-RATE              PIC V9(5).
    05  IN-DURATION-MONTHS       PIC 9(3).
    05  IN-CUSTOMER-SEGMENT      PIC X(1).
    05  IN-INCOME                PIC 9(9)V99.
```

**Copybook 2: OUTPUT-RECORD.cpy**

```
01  OUTPUT-RECORD.
    05  OUT-CASE-ID              PIC X(10).
    05  OUT-FEE-AMOUNT           PIC +9(7).99.
    05  OUT-ELIGIBLE             PIC X(1).
    05  OUT-REASON-CODE          PIC X(3).
```

**Copybook 3: CONSTANTS.cpy**

```
01  CONSTANTS.
    05  WS-MIN-FEE               PIC 9(5)V99 COMP-3 VALUE 10.00.
    05  WS-MIN-INCOME            PIC 9(9)V99 COMP-3 VALUE 25000.00.
    05  WS-MIN-DURATION          PIC 9(3) VALUE 12.
```

### Component 3: COBOL program CREDIT-FEES

**Purpose:** Implement the business logic with measurable coverage and rounding ties.

**Location:** `samples/credit-fees/CREDIT-FEES.cob`

**Structure:**
```
IDENTIFICATION DIVISION.
PROGRAM-ID. CREDIT-FEES.

ENVIRONMENT DIVISION.
INPUT-OUTPUT SECTION.
FILE-CONTROL.
    SELECT INPUT-FILE ASSIGN DYNAMIC TO INPUT-FILE-PATH
        ORGANIZATION IS LINE SEQUENTIAL
        FILE STATUS IS WS-FILE-STATUS.
    SELECT OUTPUT-FILE ASSIGN DYNAMIC TO OUTPUT-FILE-PATH
        ORGANIZATION IS LINE SEQUENTIAL
        FILE STATUS IS WS-FILE-STATUS.

DATA DIVISION.
FILE SECTION.
FD  INPUT-FILE.
01  INPUT-LINE         PIC X(200).

FD  OUTPUT-FILE.
01  OUTPUT-LINE        PIC X(200).

WORKING-STORAGE SECTION.
COPY INPUT-WORK-FIELDS.
COPY OUTPUT-RECORD.
COPY CONSTANTS.

01  INPUT-FILE-PATH    PIC X(256).
01  OUTPUT-FILE-PATH   PIC X(256).
01  WS-CSV-LINE        PIC X(200).
01  WS-HEADER-FLAG     PIC 9 VALUE 1.
01  WS-ERROR-FLAG      PIC 9 VALUE 0.
01  WS-FILE-STATUS     PIC XX.

01  WS-FEE-AMOUNT      PIC S9(7)V99 COMP-3.
01  WS-DISCOUNT-RATE   PIC V9(3) COMP-3.
01  WS-DISCOUNTED-FEE  PIC S9(7)V99 COMP-3.
01  WS-BASE-FEE        PIC S9(7)V99 COMP-3.

PROCEDURE DIVISION.
MAIN-PROCESS.
    ACCEPT INPUT-FILE-PATH FROM ENVIRONMENT "INPUT_FILE"
    ACCEPT OUTPUT-FILE-PATH FROM ENVIRONMENT "OUTPUT_FILE"
    
    IF INPUT-FILE-PATH = SPACES OR OUTPUT-FILE-PATH = SPACES
        DISPLAY "ERROR: INPUT_FILE or OUTPUT_FILE not set"
            UPON SYSERR
        MOVE 16 TO RETURN-CODE
        STOP RUN
    ELSE
        CONTINUE
    END-IF
    
    OPEN INPUT INPUT-FILE
    IF WS-FILE-STATUS NOT = "00"
        DISPLAY "ERROR: Cannot open input file " INPUT-FILE-PATH
            UPON SYSERR
        MOVE 16 TO RETURN-CODE
        STOP RUN
    ELSE
        CONTINUE
    END-IF
    
    OPEN OUTPUT OUTPUT-FILE
    IF WS-FILE-STATUS NOT = "00"
        DISPLAY "ERROR: Cannot open output file " OUTPUT-FILE-PATH
            UPON SYSERR
        MOVE 16 TO RETURN-CODE
        STOP RUN
    ELSE
        CONTINUE
    END-IF
    
    PERFORM READ-HEADER
    PERFORM WRITE-HEADER
    
    PERFORM UNTIL EXIT
        READ INPUT-FILE INTO WS-CSV-LINE
            AT END
                EXIT PERFORM
            NOT AT END
                PERFORM PROCESS-RECORD
        END-READ
    END-PERFORM
    
    CLOSE INPUT-FILE
    CLOSE OUTPUT-FILE
    
    IF WS-ERROR-FLAG = 1
        MOVE 4 TO RETURN-CODE
    ELSE
        MOVE 0 TO RETURN-CODE
    END-IF
    
    STOP RUN.

READ-HEADER.
    READ INPUT-FILE INTO WS-CSV-LINE
        AT END
            DISPLAY "ERROR: Input file is empty" UPON SYSERR
            MOVE 16 TO RETURN-CODE
            STOP RUN
        NOT AT END
            CONTINUE
    END-READ.

WRITE-HEADER.
    MOVE "CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE" TO OUTPUT-LINE
    WRITE OUTPUT-LINE.

PROCESS-RECORD.
    INITIALIZE INPUT-WORK-FIELDS
    INITIALIZE INPUT-NUMERIC-FIELDS
    INITIALIZE OUTPUT-RECORD
    INITIALIZE WS-FEE-AMOUNT
    INITIALIZE WS-DISCOUNT-RATE
    INITIALIZE WS-DISCOUNTED-FEE
    INITIALIZE WS-BASE-FEE
    PERFORM PARSE-INPUT
    PERFORM VALIDATE-INPUT
    IF OUT-REASON-CODE = "E01"
        PERFORM REJECT-RECORD
    ELSE
        PERFORM COMPUTE-FEE
        IF OUT-REASON-CODE = "E01"
            PERFORM REJECT-RECORD
        ELSE
            PERFORM CHECK-ELIGIBILITY
            PERFORM WRITE-OUTPUT
        END-IF
    END-IF.

PARSE-INPUT.
    MOVE ZERO TO WS-FIELD-COUNT
    UNSTRING WS-CSV-LINE DELIMITED BY ","
        INTO WS-IN-CASE-ID-RAW
             WS-IN-PRINCIPAL-TXT
             WS-IN-FEE-RATE-TXT
             WS-IN-DURATION-TXT
             WS-IN-SEGMENT-TXT
             WS-IN-INCOME-TXT
        TALLYING IN WS-FIELD-COUNT
        ON OVERFLOW
            MOVE "E01" TO OUT-REASON-CODE
        NOT ON OVERFLOW
            CONTINUE
    END-UNSTRING.

VALIDATE-INPUT.
    IF OUT-REASON-CODE = "E01"
        MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) TO OUT-CASE-ID
    ELSE
        IF WS-FIELD-COUNT NOT = 6
            MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) TO OUT-CASE-ID
            MOVE "E01" TO OUT-REASON-CODE
        ELSE
            IF WS-IN-CASE-ID-RAW = SPACES
                MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) 
                    TO OUT-CASE-ID
                MOVE "E01" TO OUT-REASON-CODE
            ELSE
                IF FUNCTION LENGTH(
                   FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING)) > 10
                    MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) 
                        TO OUT-CASE-ID
                    MOVE "E01" TO OUT-REASON-CODE
                ELSE
                    MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) 
                        TO OUT-CASE-ID
                    PERFORM VALIDATE-NUMERIC-FIELDS
                END-IF
            END-IF
        END-IF
    END-IF.

VALIDATE-NUMERIC-FIELDS.
    IF WS-IN-PRINCIPAL-TXT = SPACES
        MOVE "E01" TO OUT-REASON-CODE
    ELSE
        IF FUNCTION TEST-NUMVAL(WS-IN-PRINCIPAL-TXT) NOT = 0
            MOVE "E01" TO OUT-REASON-CODE
        ELSE
            MOVE FUNCTION NUMVAL(WS-IN-PRINCIPAL-TXT) TO IN-PRINCIPAL
            IF IN-PRINCIPAL NOT = FUNCTION NUMVAL(WS-IN-PRINCIPAL-TXT)
                MOVE "E01" TO OUT-REASON-CODE
            ELSE
                IF IN-PRINCIPAL < -999999999.99 
                   OR IN-PRINCIPAL > 999999999.99
                    MOVE "E01" TO OUT-REASON-CODE
                ELSE
                    CONTINUE
                END-IF
            END-IF
        END-IF
    END-IF
    
    IF OUT-REASON-CODE = SPACES
        IF WS-IN-FEE-RATE-TXT = SPACES
            MOVE "E01" TO OUT-REASON-CODE
        ELSE
            IF FUNCTION TEST-NUMVAL(WS-IN-FEE-RATE-TXT) NOT = 0
                MOVE "E01" TO OUT-REASON-CODE
            ELSE
                MOVE FUNCTION NUMVAL(WS-IN-FEE-RATE-TXT) TO IN-FEE-RATE
                IF IN-FEE-RATE NOT = FUNCTION NUMVAL(WS-IN-FEE-RATE-TXT)
                    MOVE "E01" TO OUT-REASON-CODE
                ELSE
                    IF IN-FEE-RATE < 0 OR IN-FEE-RATE >= 1
                        MOVE "E01" TO OUT-REASON-CODE
                    ELSE
                        CONTINUE
                    END-IF
                END-IF
            END-IF
        END-IF
    ELSE
        CONTINUE
    END-IF
    
    IF OUT-REASON-CODE = SPACES
        IF WS-IN-DURATION-TXT = SPACES
            MOVE "E01" TO OUT-REASON-CODE
        ELSE
            IF FUNCTION TEST-NUMVAL(WS-IN-DURATION-TXT) NOT = 0
                MOVE "E01" TO OUT-REASON-CODE
            ELSE
                MOVE FUNCTION NUMVAL(WS-IN-DURATION-TXT) TO IN-DURATION-MONTHS
                IF IN-DURATION-MONTHS 
                   NOT = FUNCTION NUMVAL(WS-IN-DURATION-TXT)
                    MOVE "E01" TO OUT-REASON-CODE
                ELSE
                    IF IN-DURATION-MONTHS < 0 OR IN-DURATION-MONTHS > 999
                        MOVE "E01" TO OUT-REASON-CODE
                    ELSE
                        CONTINUE
                    END-IF
                END-IF
            END-IF
        END-IF
    ELSE
        CONTINUE
    END-IF
    
    IF OUT-REASON-CODE = SPACES
        IF FUNCTION LENGTH(FUNCTION TRIM(WS-IN-SEGMENT-TXT TRAILING)) > 1
            MOVE "E01" TO OUT-REASON-CODE
        ELSE
            MOVE WS-IN-SEGMENT-TXT TO IN-CUSTOMER-SEGMENT
        END-IF
    ELSE
        CONTINUE
    END-IF
    
    IF OUT-REASON-CODE = SPACES
        IF WS-IN-INCOME-TXT = SPACES
            MOVE "E01" TO OUT-REASON-CODE
        ELSE
            IF FUNCTION TEST-NUMVAL(WS-IN-INCOME-TXT) NOT = 0
                MOVE "E01" TO OUT-REASON-CODE
            ELSE
                MOVE FUNCTION NUMVAL(WS-IN-INCOME-TXT) TO IN-INCOME
                IF IN-INCOME NOT = FUNCTION NUMVAL(WS-IN-INCOME-TXT)
                    MOVE "E01" TO OUT-REASON-CODE
                ELSE
                    IF IN-INCOME < 0 OR IN-INCOME > 999999999.99
                        MOVE "E01" TO OUT-REASON-CODE
                    ELSE
                        CONTINUE
                    END-IF
                END-IF
            END-IF
        END-IF
    ELSE
        CONTINUE
    END-IF.

COMPUTE-FEE.
    COMPUTE WS-BASE-FEE ROUNDED = IN-PRINCIPAL * IN-FEE-RATE
        ON SIZE ERROR
            MOVE "E01" TO OUT-REASON-CODE
            MOVE 1 TO WS-ERROR-FLAG
        NOT ON SIZE ERROR
            CONTINUE
    END-COMPUTE
    
    IF OUT-REASON-CODE NOT = "E01"
        MOVE WS-BASE-FEE TO WS-FEE-AMOUNT
        PERFORM APPLY-SEGMENT-DISCOUNT
        
        IF OUT-REASON-CODE NOT = "E01"
            IF WS-DISCOUNTED-FEE > ZERO 
               AND WS-DISCOUNTED-FEE < WS-MIN-FEE
                MOVE WS-MIN-FEE TO WS-DISCOUNTED-FEE
                MOVE "A01" TO OUT-REASON-CODE
            ELSE
                IF OUT-REASON-CODE = SPACES
                    MOVE "A00" TO OUT-REASON-CODE
                ELSE
                    CONTINUE
                END-IF
            END-IF
            
            MOVE WS-DISCOUNTED-FEE TO OUT-FEE-AMOUNT
        ELSE
            CONTINUE
        END-IF
    ELSE
        CONTINUE
    END-IF.

APPLY-SEGMENT-DISCOUNT.
    EVALUATE IN-CUSTOMER-SEGMENT
        WHEN 'P'
            MOVE 0.10 TO WS-DISCOUNT-RATE
            COMPUTE WS-DISCOUNTED-FEE ROUNDED = 
                WS-FEE-AMOUNT * (1 - WS-DISCOUNT-RATE)
                ON SIZE ERROR
                    MOVE "E01" TO OUT-REASON-CODE
                    MOVE 1 TO WS-ERROR-FLAG
                NOT ON SIZE ERROR
                    CONTINUE
            END-COMPUTE
        WHEN 'S'
            MOVE 0.05 TO WS-DISCOUNT-RATE
            COMPUTE WS-DISCOUNTED-FEE ROUNDED = 
                WS-FEE-AMOUNT * (1 - WS-DISCOUNT-RATE)
                ON SIZE ERROR
                    MOVE "E01" TO OUT-REASON-CODE
                    MOVE 1 TO WS-ERROR-FLAG
                NOT ON SIZE ERROR
                    CONTINUE
            END-COMPUTE
        WHEN 'B'
            MOVE WS-FEE-AMOUNT TO WS-DISCOUNTED-FEE
        WHEN OTHER
            MOVE WS-FEE-AMOUNT TO WS-DISCOUNTED-FEE
    END-EVALUATE.

CHECK-ELIGIBILITY.
    IF IN-INCOME < WS-MIN-INCOME
        MOVE "N" TO OUT-ELIGIBLE
        MOVE "R01" TO OUT-REASON-CODE
    ELSE
        IF IN-DURATION-MONTHS < WS-MIN-DURATION
            MOVE "N" TO OUT-ELIGIBLE
            MOVE "R02" TO OUT-REASON-CODE
        ELSE
            MOVE "Y" TO OUT-ELIGIBLE
        END-IF
    END-IF.

REJECT-RECORD.
    MOVE 1 TO WS-ERROR-FLAG
    MOVE ZERO TO OUT-FEE-AMOUNT
    MOVE "N" TO OUT-ELIGIBLE
    PERFORM WRITE-OUTPUT.

WRITE-OUTPUT.
    MOVE SPACES TO OUTPUT-LINE
    STRING FUNCTION TRIM(OUT-CASE-ID TRAILING) DELIMITED BY SIZE
           "," DELIMITED BY SIZE
           OUT-FEE-AMOUNT DELIMITED BY SIZE
           "," DELIMITED BY SIZE
           OUT-ELIGIBLE DELIMITED BY SIZE
           "," DELIMITED BY SIZE
           OUT-REASON-CODE DELIMITED BY SIZE
        INTO OUTPUT-LINE
    END-STRING
    WRITE OUTPUT-LINE.
```

**Business rules summary:**
- Base fee: `PRINCIPAL * FEE-RATE`, ROUNDED (nearest away from zero), with ON SIZE ERROR.
- Segment discounts (EVALUATE on CUSTOMER-SEGMENT):
  - 'P' (Premium): 10% discount on base fee, ROUNDED, with ON SIZE ERROR.
  - 'S' (Standard): 5% discount on base fee, ROUNDED, with ON SIZE ERROR.
  - 'B' (Basic): no discount.
  - Other: no discount.
- Minimum fee: if discounted fee > 0 and < 10.00, raise to 10.00, set REASON-CODE "A01".
- Eligibility (priority order, highest first):
  - E01: validation error (field count not 6, 7+ fields via ON OVERFLOW, blank CASE-ID, CASE-ID longer than 10 characters, CASE-ID contains comma, blank numeric field, TEST-NUMVAL failure, MOVE truncation from NUMVAL, range check failure, overflow).
  - R01: not eligible, INCOME < 25000.00.
  - R02: not eligible, DURATION-MONTHS < 12.
  - A01: eligible, minimum fee applied.
  - A00: eligible, normal.
- Validation: field count = 6 (ON OVERFLOW for 7+), CASE-ID not blank and at most 10 characters (parsed into X(20) field first, trimmed, then length checked; CASE-ID must not contain commas), all numeric fields not blank, all numeric fields pass TEST-NUMVAL, after MOVE from NUMVAL the field equals NUMVAL of the text (catches silent truncation from too many decimals, out of range, or lost sign), PRINCIPAL in S9(9)V99 range with at most 2 decimals, FEE-RATE in [0, 1) with at most 5 decimals, DURATION-MONTHS integer 0 to 999, INCOME non-negative with at most 2 decimals and within 9(9)V99, CUSTOMER-SEGMENT length at most 1 character.
- Invalid records: REASON-CODE "E01", ELIGIBLE "N", FEE-AMOUNT zero, RETURN-CODE 4 at end, processing continues with next record.
- Negative PRINCIPAL (rebates): allowed, rounded away from zero (e.g., -100.005 becomes -100.01).
- File errors: if INPUT_FILE or OUTPUT_FILE environment variable is missing, or input file cannot be opened, or input file is empty, DISPLAY error on SYSERR and end with RETURN-CODE 16.
- State between records: PROCESS-RECORD starts with INITIALIZE of INPUT-WORK-FIELDS, INPUT-NUMERIC-FIELDS, OUTPUT-RECORD, and fee work fields to prevent stale values from leaking.

**REASON-CODE values (3 characters, priority highest to lowest):**
- "E01": invalid record (validation or overflow error).
- "R01": not eligible due to income below 25000.00.
- "R02": not eligible due to duration below 12 months.
- "A01": eligible, minimum fee applied.
- "A00": eligible, normal processing.

**Rounding steps:**
- Step 1: `WS-BASE-FEE = PRINCIPAL * FEE-RATE` with ROUNDED (nearest away from zero, scale 2), ON SIZE ERROR -> E01.
- Step 2: If segment P or S, `WS-DISCOUNTED-FEE = WS-FEE-AMOUNT * (1 - DISCOUNT-RATE)` with ROUNDED (scale 2), ON SIZE ERROR -> E01.
- Without ROUNDED keyword: COBOL truncates (maps to Java RoundingMode.DOWN per cobol-semantics.md).

**Line count estimate:**
- IDENTIFICATION, ENVIRONMENT, DATA: ~90 lines.
- MAIN-PROCESS with file error handling and explicit ELSE: ~60 lines.
- READ-HEADER with AT END, WRITE-HEADER: ~15 lines.
- PARSE-INPUT with ON OVERFLOW, VALIDATE-INPUT with explicit ELSE, VALIDATE-NUMERIC-FIELDS with explicit ELSE per field: ~150 lines.
- COMPUTE-FEE with explicit ELSE, APPLY-SEGMENT-DISCOUNT with explicit ELSE: ~80 lines.
- CHECK-ELIGIBILITY with explicit ELSE, REJECT-RECORD, WRITE-OUTPUT: ~40 lines.
- Total: ~435 lines. With copybooks (~85 lines), total ~520 lines, meeting the 300-800 target.

### Component 4: Build and run commands

**Purpose:** Compile and execute the COBOL program with environment variable configuration.

**Compilation:**
```bash
cobc -x -Wall -I samples/credit-fees/copybooks \
    -o build/credit-fees samples/credit-fees/CREDIT-FEES.cob
```

**Flags:**
- `-x`: Produce executable.
- `-Wall`: Enable all warnings (must compile with zero warnings, exit code 0, empty stderr).
- `-o build/credit-fees`: Output to build directory.
- `-I samples/credit-fees/copybooks`: Copybook search path.

**File assignment verification:** The compile task verifies that GnuCOBOL accepts `ASSIGN DYNAMIC TO <data-name>` with the data name holding the path from ACCEPT ... FROM ENVIRONMENT.

**Execution:**
```bash
INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv \
OUTPUT_FILE=build/credit-fees-output.csv \
build/credit-fees
```

**Return codes:**
- 0: All records processed successfully.
- 4: At least one validation error (E01).
- 16: Missing environment variable or cannot open input file.

**Makefile targets:**
```make
build/credit-fees: samples/credit-fees/CREDIT-FEES.cob
	mkdir -p build
	cobc -x -Wall -I samples/credit-fees/copybooks \
	    -o build/credit-fees samples/credit-fees/CREDIT-FEES.cob

cobol-sample: build/credit-fees
	INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv \
	OUTPUT_FILE=build/credit-fees-output.csv \
	build/credit-fees

sample-expected: build/credit-fees
	@echo "Regenerating expected-output.csv (manual step)"
	INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv \
	OUTPUT_FILE=samples/credit-fees/fixtures/expected-output.csv \
	build/credit-fees
	@echo "Verify output manually before committing"
```

The `sample-expected` target is documented as a manual step that overwrites the committed expected-output.csv. It must be run only when the fixture or program changes, and the output must be manually verified before committing.

### Component 5: Test fixtures

**Purpose:** Provide test data with known characteristics for validating the COBOL program and later testing Coroner.

**Location:** `samples/credit-fees/fixtures/`

**Fixture 1: rounding-ties.csv (at least 20 exact ties)**

An exact rounding tie at scale 2 occurs when `PRINCIPAL * FEE-RATE` (computed at scale 7, the sum of input scales 2 + 5) has an absolute remainder of exactly 0.005 when truncated to scale 2. In other words, the exact product ends in .XX5 where XX is any two digits.

Per D-06, COBOL ROUNDED (HALF_UP) rounds ties away from zero. Java HALF_EVEN rounds ties to the nearest even digit. Divergence occurs only when the digit preceding the .005 is even.

Examples:
- 2.025: preceding digit is 2 (even). COBOL ROUNDED: 2.03. HALF_EVEN: 2.02. Diverges.
- 2.035: preceding digit is 3 (odd). COBOL ROUNDED: 2.04. HALF_EVEN: 2.04. No divergence.
- -2.025: preceding digit is 2 (even). COBOL ROUNDED: -2.03 (away from zero). HALF_EVEN: -2.02. Diverges.

**Tie selection strategy:**
- The fixture must contain at least 20 exact ties.
- At least 16 ties must have an even preceding digit (these will diverge under HALF_EVEN).
- At least 4 ties must have an odd preceding digit (controls, no divergence).
- Include both positive and negative PRINCIPAL (at least 6 negative ties with even preceding digit).
- Use CUSTOMER-SEGMENT 'B' or other non-discounted segment so the printed FEE-AMOUNT equals the base fee (the 10.00 minimum would mask ties below 10.00).
- Ensure INCOME >= 25000.00 and DURATION-MONTHS >= 12 so records are eligible and the fee is printed as computed.
- Choose absolute base fees of at least 10.00 to avoid the minimum fee rule.

**Generation rule:**
1. For each target tie value T (e.g., 12.345), compute PRINCIPAL and FEE-RATE such that PRINCIPAL * FEE-RATE = T exactly at scale 7.
2. Verify the tie: the exact product at scale 7 ends in .XX500.
3. Verify the preceding digit parity: for T = 12.345, truncated to scale 2 is 12.34, last digit 4 (even), so this tie diverges.
4. Verify the absolute value is at least 10.00.

**Worked examples (verified exact ties):**
- 1234.50 x 0.01000 = 12.3450000, tie, preceding digit 4 even: COBOL +0000012.35, HALF_EVEN 12.34 (diverges)
- -1234.50 x 0.01000 = -12.3450000, even: COBOL -0000012.35, HALF_EVEN -12.34 (diverges)
- 2469.00 x 0.00500 = 12.3450000, even: COBOL 12.35, HALF_EVEN 12.34 (diverges)
- -4115.00 x 0.00300 = -12.3450000, even: COBOL -12.35, HALF_EVEN -12.34 (diverges)
- 1023.50 x 0.01000 = 10.2350000, preceding digit 3 odd: both 10.24 (control)
- 500.00 x 0.02051 = 10.2550000, odd: both 10.26 (control)
- -2047.00 x 0.00500 = -10.2350000, odd: both -10.24 (control)

**Fixture rows:** The actual fixture rows are generated and verified by a Python script during the tasks, not hand-listed in the design. The script must:
1. Generate at least 20 exact tie cases.
2. Verify each case: `Decimal(PRINCIPAL) * Decimal(FEE-RATE)` with sufficient precision, then quantize to scale 2 with ROUND_DOWN, remainder in absolute value equals 0.005.
3. Count ties by preceding digit parity: at least 16 even, at least 4 odd, at least 6 negative with even digit.
4. Write to `samples/credit-fees/fixtures/rounding-ties.csv`.

**Oracle test (pytest):**

A separate test `tests/test_rounding_ties_oracle.py` that does NOT rely on the COBOL output:
- Read rounding-ties.csv.
- For each row:
  - Compute `product = Decimal(PRINCIPAL) * Decimal(FEE-RATE)` with context precision sufficient for exact computation (at least 20 digits).
  - Verify it is an exact tie: `product % Decimal('0.01')` in absolute value equals `Decimal('0.005')`.
  - Compute the COBOL expected fee: `product.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)` (Python ROUND_HALF_UP rounds ties away from zero, matching COBOL ROUNDED).
  - Compute the HALF_EVEN fee: `product.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)`.
  - If the preceding digit (last digit of `product.quantize(Decimal('0.01'), rounding=ROUND_DOWN)`) is even, assert COBOL fee != HALF_EVEN fee.
  - If odd, assert COBOL fee == HALF_EVEN fee.
- Verify counts: at least 16 even-digit ties, at least 4 odd-digit ties, at least 6 negative even-digit ties.

This oracle test runs during fixture generation and as part of the test suite. It proves the fixture is correct without running COBOL.

**Fixture 2: edge-cases.csv (boundary and special values)**

Additional test cases for boundary conditions:
- PRINCIPAL = 0.00 (zero fee).
- PRINCIPAL = 999999999.99 (near S9(9)V99 limit, not 99999999.99).
- PRINCIPAL = -999999999.99.
- FEE-RATE = 0.00000 (zero rate).
- FEE-RATE = 0.99999 (maximum rate near 100%).
- DURATION-MONTHS = 0 (ineligible, R02).
- DURATION-MONTHS = 999 (maximum).
- INCOME = 0.00 (ineligible, R01).
- INCOME = 999999999.99 (maximum).
- CUSTOMER-SEGMENT values: 'P', 'S', 'B', 'X' (other), ' ' (space, treated as other).
- Invalid CASE-ID: spaces (E01 validation error).
- Overflow case: PRINCIPAL = 999999999.99, FEE-RATE = 0.99999, product overflows S9(7)V99, expect E01.

**Fixture 3: validation-errors.csv (E01 test cases)**

Validation error test cases, each demonstrating a specific E01 cause:
- Field count not 6 (5 fields): E01
- Field count not 6 (7 fields): E01
- CASE-ID blank (SPACES): E01
- CASE-ID longer than 10 characters (11 characters): E01
- CASE-ID contains comma (rejected by parsing): E01
- PRINCIPAL blank: E01
- PRINCIPAL non-numeric text: E01
- PRINCIPAL with 3 decimals (loses precision in MOVE): E01
- PRINCIPAL above 999999999.99: E01
- FEE-RATE blank: E01
- FEE-RATE = 1.00000 (not < 1): E01
- FEE-RATE negative: E01
- DURATION-MONTHS with decimals (12.5, not integer): E01
- DURATION-MONTHS negative: E01
- INCOME negative: E01
- CUSTOMER-SEGMENT longer than 1 character (2 characters): E01
- Arithmetic overflow (PRINCIPAL x FEE-RATE exceeds S9(7)V99): E01

Each row expects REASON-CODE E01, ELIGIBLE N, FEE-AMOUNT +0000000.00. A valid row placed after an invalid row and another valid row after that proves no state leaks between records (tests fix A).

**Fixture 4: expected-output.csv**

Generated by running the COBOL program on rounding-ties.csv:
```bash
INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv \
OUTPUT_FILE=samples/credit-fees/fixtures/expected-output.csv \
build/credit-fees
```

This file is the COBOL reference output and will be compared against Java output by Coroner. It must be manually verified (at least a sample of tie cases matches the oracle) and then committed to the repository using the `make sample-expected` target.

## Data Models

### CSV format conventions

**Input CSV:**
- First row: header with column names (CASE-ID, PRINCIPAL, FEE-RATE, DURATION-MONTHS, CUSTOMER-SEGMENT, INCOME).
- Separator: comma.
- Decimal point: period (e.g., 100.00).
- Signed decimals: leading sign with no space (e.g., -100.00).
- Unsigned decimals: no sign (e.g., 25000.00).
- Strings: no quotes, may contain spaces.
- Line ending: LF or CRLF (COBOL LINE SEQUENTIAL handles both).

**Output CSV:**
- First row: header with column names (CASE-ID, FEE-AMOUNT, ELIGIBLE, REASON-CODE).
- FEE-AMOUNT format from edited PIC +9(7).99: always a leading + or -, followed by 7 digits, a decimal point, and 2 digits.
  - Positive: `+0000002.03`
  - Negative: `-0000002.03`
  - Zero: `+0000000.00`
- No leading or trailing spaces in FEE-AMOUNT.
- CASE-ID: no trailing spaces (STRING ... DELIMITED BY SPACE).
- ELIGIBLE: 'Y' or 'N' (single character, no quotes).
- REASON-CODE: 3-character string (A00, A01, R01, R02, E01).

**Normalization rules for comparison (used by Coroner normalizer):**
- Trim leading and trailing spaces from all string fields.
- For decimal fields: parse as BigDecimal with the scale from schema.json, compare values exactly (no tolerance per D-09).
- Line endings: normalize to LF before comparison.
- Column order: match by column name, not position.

### Internal computation precision

**FEE-AMOUNT (WORKING-STORAGE):**
```
PIC S9(7)V99 COMP-3
```
- Total digits: 9 (7 before decimal, 2 after).
- Scale: 2.
- Signed: yes.
- Range: -9999999.99 to +9999999.99.

**DISCOUNTED-FEE (WORKING-STORAGE):**
```
PIC S9(7)V99 COMP-3
```
- Same precision as FEE-AMOUNT.

**DISCOUNT-RATE (WORKING-STORAGE):**
```
PIC V9(3) COMP-3
```
- Decimal only, 3 digits: 0.000 to 0.999.
- Used for 0.10 (10%) and 0.05 (5%).

**Rounding precision:**
- All COMPUTE statements with ROUNDED produce scale 2 results.
- Intermediate multiplication `PRINCIPAL * FEE-RATE`: input scales are 2 and 5, product scale is 7. COBOL rounds to target scale 2.
- Discount multiplication `FEE-AMOUNT * (1 - DISCOUNT-RATE)`: scales 2 and 3, product scale 5. COBOL rounds to target scale 2.

### Return code contract

| Condition | RETURN-CODE |
|-----------|-------------|
| All records valid, processed successfully | 0 |
| At least one record with E01 error | 4 |
| Missing environment variable or cannot open input file | 16 |

## Error Handling

### Validation errors

| Error condition | Handling |
|----------------|----------|
| Field count not 6 (including 7+ via ON OVERFLOW) | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| CASE-ID is blank (SPACES) | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| CASE-ID longer than 10 characters | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| CASE-ID contains comma | Parsing stops, field count < 6, treated as field count error |
| Any numeric field is blank (SPACES) | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| Any numeric field fails FUNCTION TEST-NUMVAL | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| MOVE from NUMVAL truncates (field != NUMVAL of text) | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| PRINCIPAL outside S9(9)V99 range (-999999999.99 to 999999999.99) | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| FEE-RATE not in [0, 1) or more than 5 decimals | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| DURATION-MONTHS not an integer 0 to 999 | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| INCOME negative, more than 2 decimals, or above 999999999.99 | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| CUSTOMER-SEGMENT longer than 1 character (after trimming) | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| Arithmetic overflow (ON SIZE ERROR) in COMPUTE | Set REASON-CODE "E01", OUT-ELIGIBLE "N", OUT-FEE-AMOUNT zero, set WS-ERROR-FLAG, continue processing other records |
| INPUT_FILE or OUTPUT_FILE environment variable missing | DISPLAY error message on UPON SYSERR, MOVE 16 TO RETURN-CODE, STOP RUN (program ends immediately) |
| Cannot open input file | DISPLAY error message on UPON SYSERR, MOVE 16 TO RETURN-CODE, STOP RUN (program ends immediately) |
| Input file is empty (no header) | DISPLAY error message on UPON SYSERR, MOVE 16 TO RETURN-CODE, STOP RUN (program ends immediately) |

All validation errors (E01) write a record with REASON-CODE "E01", ELIGIBLE "N", FEE-AMOUNT zero, and set WS-ERROR-FLAG to 1. Processing continues for subsequent records (partial output is produced). At the end, if WS-ERROR-FLAG is 1, RETURN-CODE is set to 4.

File errors (missing environment variable, cannot open input file, or empty input file) cause the program to end immediately with RETURN-CODE 16 and an error message on stderr.

### Runtime errors

| Error condition | Handling |
|----------------|----------|
| Division by zero | Does not occur in this program (no division operations) |
| Arithmetic overflow (result exceeds S9(7)V99) | Caught with ON SIZE ERROR in all COMPUTE statements, sets REASON-CODE "E01" for that record |
| File I/O error during read | COBOL runtime error, program may abort |
| File I/O error during write | COBOL runtime error, program may abort |

## Testing Strategy

### Unit test 1: Compilation without warnings

**Test:** `tests/test_cobol_sample.py::test_compilation`
- Given: CREDIT-FEES.cob and copybooks
- When: `cobc -x -Wall -I samples/credit-fees/copybooks -o build/credit-fees samples/credit-fees/CREDIT-FEES.cob` runs
- Then: exit code 0, stderr is empty (no warnings, no errors)

### Unit test 2: Rounding ties oracle (does not rely on COBOL output)

**Test:** `tests/test_rounding_ties_oracle.py::test_oracle`
- Given: rounding-ties.csv
- For each row:
  - Compute `product = Decimal(PRINCIPAL) * Decimal(FEE-RATE)` with sufficient precision
  - Assert it is an exact tie: `abs(product % Decimal('0.01'))` equals `Decimal('0.005')`
  - Compute COBOL expected: `product.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`
  - Compute HALF_EVEN: `product.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)`
  - If preceding digit (last digit of `product.quantize(Decimal('0.01'), rounding=ROUND_DOWN)`) is even, assert COBOL != HALF_EVEN
  - If odd, assert COBOL == HALF_EVEN
- Assert fixture has at least 16 even-digit ties, at least 4 odd-digit ties, at least 6 negative even-digit ties

### Unit test 3: Run on rounding-ties fixture

**Test:** `tests/test_cobol_sample.py::test_rounding_ties_fixture`
- Given: rounding-ties.csv with at least 20 exact tie cases
- When: CREDIT-FEES runs with INPUT_FILE=rounding-ties.csv and OUTPUT_FILE=build/credit-fees-output.csv
- Then: exit code 0 (all rows valid and eligible)
- Then: build/credit-fees-output.csv exists with same row count as input (excluding headers)
- Then: build/credit-fees-output.csv matches expected-output.csv byte for byte (no normalization)

### Unit test 4: Edge cases

**Test:** `tests/test_cobol_sample.py::test_edge_cases`
- Given: edge-cases.csv
- When: CREDIT-FEES runs with OUTPUT_FILE=build/credit-fees-edge-output.csv
- Then: exit code 0 or 4 (4 if E01 cases present, 0 if all valid)
- Then: zero PRINCIPAL produces zero fee
- Then: maximum PRINCIPAL (999999999.99) with small fee rate does not overflow
- Then: CUSTOMER-SEGMENT 'X' and ' ' treated as OTHER (no discount)
- Then: invalid CASE-ID (blank) produces E01
- Then: overflow case (999999999.99 * 0.99999) produces E01
- Then: INCOME below 25000.00 produces R01
- Then: DURATION-MONTHS below 12 produces R02

### Unit test 5: Negative PRINCIPAL rounding

**Test:** `tests/test_cobol_sample.py::test_negative_rounding`
- Given: cases with negative PRINCIPAL and exact ties (at least 6 from rounding-ties.csv)
- When: CREDIT-FEES runs
- Then: fee rounded away from zero (e.g., -2.025 becomes -2.03)
- Then: output matches expected-output.csv for negative rows

### Unit test 6: Segment discount branches

**Test:** `tests/test_cobol_sample.py::test_segment_discounts`
- Given: cases with CUSTOMER-SEGMENT 'P', 'S', 'B', 'X' from edge-cases.csv or a separate discount-test.csv
- When: CREDIT-FEES runs
- Then: 'P' discount is 10% (verify calculation against expected-output.csv)
- Then: 'S' discount is 5% (verify calculation)
- Then: 'B' and 'X' no discount (fee equals base fee)

### Unit test 7: Minimum fee enforcement

**Test:** `tests/test_cobol_sample.py::test_minimum_fee`
- Given: case where base fee is 8.00 and discounted fee would be below 10.00 (e.g., segment P gives 7.20)
- When: CREDIT-FEES runs
- Then: FEE-AMOUNT is +0000010.00
- Then: REASON-CODE is "A01"
- Then: ELIGIBLE is "Y" (if income and duration are sufficient)

### Unit test 8: Eligibility rules

**Test:** `tests/test_cobol_sample.py::test_eligibility`
- Given: cases with various INCOME and DURATION-MONTHS combinations from edge-cases.csv
- When: CREDIT-FEES runs
- Then: INCOME < 25000.00 produces ELIGIBLE "N", REASON-CODE "R01"
- Then: INCOME >= 25000.00 and DURATION-MONTHS < 12 produces ELIGIBLE "N", REASON-CODE "R02"
- Then: INCOME >= 25000.00 and DURATION-MONTHS >= 12 produces ELIGIBLE "Y", REASON-CODE "A00" or "A01"

### Unit test 9: Validation rules

**Test:** `tests/test_cobol_sample.py::test_validation`
- Given: validation-errors.csv with cases: 5 fields, 7 fields, blank CASE-ID, CASE-ID of 11 characters, CASE-ID with comma (triggers field count error), blank PRINCIPAL, non-numeric PRINCIPAL, PRINCIPAL with 3 decimals (truncation), PRINCIPAL above range, blank FEE-RATE, FEE-RATE = 1.00000, negative FEE-RATE, DURATION-MONTHS 12.5, negative DURATION-MONTHS, negative INCOME, CUSTOMER-SEGMENT of 2 characters, overflow case, plus valid rows interleaved to test no state leak between records
- When: CREDIT-FEES runs
- Then: exit code 4
- Then: all invalid cases produce REASON-CODE "E01", ELIGIBLE "N", FEE-AMOUNT +0000000.00
- Then: valid rows interleaved among invalid rows produce correct results (no state leak from previous record)

### Unit test 10: Missing file error

**Test:** `tests/test_cobol_sample.py::test_missing_file`
- Given: INPUT_FILE environment variable set to a non-existent file
- When: CREDIT-FEES runs
- Then: exit code 16
- Then: stderr contains an error message

### Integration test: Generate expected-output.csv

**Manual step (done once, then committed):**
1. Generate rounding-ties.csv with at least 20 exact tie cases using the Python fixture generation script.
2. Run the oracle test to verify the fixture is correct.
3. Run CREDIT-FEES on rounding-ties.csv to produce expected-output.csv using `make sample-expected`.
4. Manually inspect a sample of expected-output.csv rows to confirm rounding results match COBOL ROUNDED semantics (compare against the oracle test expected values).
5. Commit expected-output.csv to repository.

**Verification:**
- For each exact tie case (e.g., product 10.255), verify the output FEE-AMOUNT matches the oracle expected value (e.g., +0000010.26 for positive tie with odd preceding digit 5, or +0000010.25 vs +0000010.26 showing the HALF_EVEN bug if preceding digit is even).

### Acceptance criteria validation

**Requirement 1: Business behavior**
- Verified by: tests confirm all business rules (segment discounts, minimum fee, eligibility, validation).
- Pass condition: pytest suite passes for all fixtures.

**Requirement 2: Coding rules**
- Verified by: compilation with -Wall produces no warnings (empty stderr); manual review confirms every IF has ELSE, every EVALUATE has WHEN OTHER.
- Pass condition: cobc exit code 0 with -Wall and empty stderr.

**Requirement 3: Demo trap**
- Verified by: oracle test proves the fixture has at least 20 exact ties with correct parity distribution; expected-output.csv shows COBOL ROUNDED results.
- Pass condition: oracle test passes, expected-output.csv committed, ready for Coroner verification.

**Line count target:**
- Verified by: `wc -l` on CREDIT-FEES.cob and copybooks.
- Pass condition: CREDIT-FEES.cob alone between 300 and 800 lines (target about 400 lines), plus 1 to 3 copybooks (about 80 lines total for copybooks).

All tests must pass and expected-output.csv must be committed before this spec is marked complete.
