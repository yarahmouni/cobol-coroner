# Design: Java 17 version of CREDIT-FEES

## Overview

This spec defines the Java 17 implementation of the COBOL program CREDIT-FEES.cob. The Java version is the correct migration that produces byte-identical output to the COBOL reference for every test case. It serves as the ALIVE baseline that Coroner will verify against automatically injected faulty variants from the fault catalog (see separate spec).

The Java implementation follows the COBOL reference exactly: same input validation, same BigDecimal arithmetic with RoundingMode.HALF_UP for COBOL ROUNDED (nearest away from zero), same business rules for segment discounts and eligibility, same error handling with exit codes 0, 4, 16. The output format matches the COBOL edited picture PIC +9(7).99 with always a leading sign, 7 zero-padded digits, a decimal point, and 2 decimals.

The design settles all parity points discovered by the operator during COBOL review. Where the COBOL behavior is ambiguous or depends on NUMVAL implementation details, the design requires parity test verification rather than assumption. The single Java source file compiles with javac, runs with no dependencies, and processes input in a single JVM batch run.

Success criteria: byte-identical output with the COBOL program on all fixture files (rounding-ties.csv, edge-cases.csv, validation-errors.csv), same exit codes, pytest test green with both programs running under timeouts, rules check confirms no double, float, Math.round, or int/long for amounts.

## Architecture

### High-level flow

```
Environment variables INPUT_FILE, OUTPUT_FILE
         |
         v
   CreditFees.main()
         |
         +---> validate environment variables
         |     (missing -> stderr + exit 16)
         |
         +---> open input file
         |     (cannot open -> stderr + exit 16)
         |
         +---> open output file
         |     (cannot open -> stderr + exit 16)
         |
         +---> skip header line
         |     (empty input -> write header + exit 0)
         |
         +---> write output header
         |
         +---> for each data line:
         |         |
         |         +---> parseLine() -> String[]
         |         |
         |         +---> validateRecord() -> ValidationResult
         |         |     (field count, CASE-ID, numeric parsing,
         |         |      by-value range and scale checks)
         |         |
         |         +---> if valid:
         |         |         computeFee() -> FeeResult
         |         |         (base fee, segment discount, minimum fee,
         |         |          overflow detection)
         |         |     else:
         |         |         reject with E01
         |         |
         |         +---> checkEligibility() -> EligibilityResult
         |         |     (income, duration rules)
         |         |
         |         +---> formatOutputLine() -> String
         |         |
         |         +---> write output line
         |
         +---> close files
         |
         +---> exit with code 0 or 4
```

### Key decisions

- Single class `CreditFees` with `public static void main(String[] args)` and several private static helper methods.
- No dependencies: java.io.BufferedReader/BufferedWriter for file I/O, java.math.BigDecimal for all amounts, java.util for environment variables.
- One JVM run processes the entire input file (batch processing).
- Compile with `javac -d build/java samples/credit-fees/java/CreditFees.java`; run with `java -cp build/java CreditFees`.
- Input line length: COBOL reads PIC X(200), characters beyond 200 are cut. Java reads the line, truncates to 200 characters, removes a trailing CR if present (CRLF input).
- Field split: `String.split(",", -1)` to keep trailing empty fields; more than 6 or fewer than 6 fields is E01.
- Numeric validation is BY VALUE: parse the text with BigDecimal constructor, check the value fits the target PIC with `value.setScale(targetScale, RoundingMode.DOWN).compareTo(value) == 0` (BigDecimal.equals compares scale, which is wrong). For example, "10.5" is valid for S9(9)V99 because 10.5 truncated to scale 2 equals 10.5 (no loss), "10.505" is E01 because 10.50 does not equal 10.505.
- Accepted numeric text format: after trimming leading and trailing spaces, match the regex `^[+-]?\\d+(\\.\\d+)?$` (optional leading sign, digits, optional decimal point and decimals, no exponent, no trailing signs). Blank (all spaces or empty) is E01. Exponents ("1E2") and non-canonical formats (trailing signs, CR/DB, embedded spaces, parentheses) are E01. The regex is provisional: COBOL NUMVAL may accept ".5", "5." and leading '+'; the parity test decides, and the regex is adjusted to match the COBOL output.
- CASE-ID: raw field up to 20 characters from UNSTRING, trim trailing spaces only, invalid if the trimmed length is greater than 10 or if blank (all spaces). Output CASE-ID is the trailing-trimmed value cut to 10 characters, also on E01 rows.
- CUSTOMER-SEGMENT: trim trailing spaces only, invalid if the trimmed length is greater than 1. Empty (after trimming trailing spaces only) is valid and takes the no-discount branch.
- FEE-AMOUNT output: format = sign ('+' when signum >= 0, '-' when negative) followed by the absolute value with setScale(2) and toPlainString, left-padded with zeros to 10 characters (7 integer digits, point, 2 decimals), total 11 characters. BigDecimal has no negative zero, so a fee rounding to 0.00 prints '+'; the parity test confirms COBOL does the same.
- Range checks: PRINCIPAL in S9(9)V99 range (-999999999.99 to 999999999.99), FEE-RATE in [0, 1) by value, DURATION 0 to 999 integer by value, INCOME 0 to 999999999.99 by value. Overflow: absolute value of the rounded fee greater than 9999999.99 is E01. All range checks apply after parsing the BigDecimal value, not to the text.
- Rounding: COBOL ROUNDED uses RoundingMode.HALF_UP. The fee computation is `baseFee.setScale(2, RoundingMode.HALF_UP)`. Overflow check happens after rounding.
- Discount computation: `baseFee.multiply(BigDecimal.ONE.subtract(discountRate)).setScale(2, RoundingMode.HALF_UP)`. The discount rate is a BigDecimal constant. A discount never increases the absolute value, but the overflow check stays.
- Minimum fee: if the discounted fee is positive and less than 10.00, raise it to 10.00 and set REASON-CODE to A01.
- Exit codes: 16 when environment variables are missing or input file cannot be opened, 4 when at least one validation error occurred (error counter greater than zero), 0 otherwise. Empty input (no header) writes the header and exits 0.
- Record initialization: all record-level variables (input fields, output fields, intermediate results) are reset before processing each row to prevent state leakage.

## Components and Interfaces

### Component 1: Main method and file I/O

**Method signature:**
```java
public static void main(String[] args)
```

**Purpose:** Entry point. Validate environment variables, open files, process the input file line by line, write output, close files, exit with the correct code.

**Pseudo-code:**
```
errorCount = new int[1]  // mutable reference

inputPath = System.getenv("INPUT_FILE")
outputPath = System.getenv("OUTPUT_FILE")

if inputPath == null or outputPath == null:
    System.err.println("ERROR: INPUT_FILE or OUTPUT_FILE not set")
    System.exit(16)

try:
    open inputPath for reading (BufferedReader)
except IOException:
    System.err.println("ERROR: Cannot open input file " + inputPath)
    System.exit(16)

try:
    open outputPath for writing (BufferedWriter)
except IOException:
    System.err.println("ERROR: Cannot open output file " + outputPath)
    inputReader.close()
    System.exit(16)

headerLine = inputReader.readLine()
if headerLine == null:
    outputWriter.write("CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE\n")
    outputWriter.close()
    inputReader.close()
    System.exit(0)

outputWriter.write("CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE\n")

while (line = inputReader.readLine()) != null:
    processRecord(line, outputWriter, errorCount)

outputWriter.close()
inputReader.close()

if errorCount[0] > 0:
    System.exit(4)
else:
    System.exit(0)
```

**Parity point 4: COBOL PIC X(200)**
- COBOL reads INPUT-LINE PIC X(200), characters beyond 200 are cut before parsing.
- Java: `if (line.length() > 200) { line = line.substring(0, 200); }`
- If the line ends with CR (CRLF input), remove it: `if (line.endsWith("\r")) { line = line.substring(0, line.length() - 1); }`

**Parity point 9: Header and empty input**
- The first line read is the header and is always skipped (whatever its content).
- Empty input (no line to read) writes the output header and exits 0.

**Parity point 10: Exit codes and error messages**
- Exit 16: environment variables missing or input file cannot be opened. Error message on stderr.
- Exit 4: at least one validation error (E01) occurred. No error message (COBOL does not print one for validation errors).
- Exit 0: all records processed without validation errors, or empty input.

### Component 2: Line parsing

**Method signature:**
```java
private static String[] parseLine(String line)
```

**Purpose:** Split the CSV line on commas, keeping trailing empty fields. Return the field array.

**Pseudo-code:**
```
fields = line.split(",", -1)
return fields
```

**Parity point 3: Field split**
- Split on every comma, keeping empty fields. `String.split(",", -1)` does this.
- More than 6 fields is E01.
- Fewer than 6 fields is E01.
- An empty data line (empty string or only spaces) split on comma gives one field (empty string), so field count not 6, E01.

### Component 3: Input validation

**Method signature:**
```java
private static ValidationResult validateRecord(String[] fields)
```

**Purpose:** Validate field count, CASE-ID, and all numeric fields. Return a ValidationResult with valid flag, parsed values (if valid), CASE-ID for output, and E01 flag.

**Data structures:**
```java
class ValidationResult {
    boolean valid;
    String caseId;  // for output, trimmed trailing and cut to 10
    BigDecimal principal;
    BigDecimal feeRate;
    int durationMonths;
    String customerSegment;  // length 0 or 1 after trimming trailing
    BigDecimal income;
}
```

**Pseudo-code:**
```
result = new ValidationResult()
result.valid = true

if fields.length != 6:
    result.valid = false
    result.caseId = trimTrailing(fields[0]).substring(0, min(10, length))
    return result

caseIdRaw = fields[0]
if caseIdRaw.length() > 20:
    caseIdRaw = caseIdRaw.substring(0, 20)

caseIdTrimmed = trimTrailing(caseIdRaw)

if caseIdTrimmed.isEmpty():
    result.valid = false
    result.caseId = caseIdTrimmed  // empty
    return result

if caseIdTrimmed.length() > 10:
    result.valid = false
    result.caseId = caseIdTrimmed.substring(0, 10)
    return result

result.caseId = caseIdTrimmed

// Validate PRINCIPAL
principalText = fields[1]
principalValue = parseNumeric(principalText)
if principalValue == null:
    result.valid = false
    return result

// Check by-value range
if principalValue.abs().compareTo(new BigDecimal("999999999.99")) > 0:
    result.valid = false
    return result

// Check value fits S9(9)V99: truncate to scale 2 and compare
truncated = principalValue.setScale(2, RoundingMode.DOWN)
if truncated.compareTo(principalValue) != 0:
    result.valid = false
    return result

result.principal = principalValue

// Validate FEE-RATE (similar logic, range [0, 1), scale at most 5)
...

// Validate DURATION-MONTHS (integer 0 to 999)
...

// Validate CUSTOMER-SEGMENT (trimmed trailing length at most 1)
segmentRaw = fields[4]
segmentTrimmed = trimTrailing(segmentRaw)
if segmentTrimmed.length() > 1:
    result.valid = false
    return result
result.customerSegment = segmentTrimmed

// Validate INCOME (non-negative, scale at most 2, at most 999999999.99)
...

return result
```

**Parity point 1: Numeric validation by value**
- COBOL validates "moved value equals NUMVAL": a text is valid if NUMVAL(text) can be moved to the target PIC without truncation or sign loss.
- For PRINCIPAL S9(9)V99 (scale 2): after parsing the BigDecimal, check value in range. Check value fits: `value.setScale(2, DOWN).compareTo(value) == 0`. The text "10.5" is valid (10.5 truncated to scale 2 equals 10.5). The text "10.505" is E01 (10.50 does not equal 10.505).
- For DURATION 9(3) (integer): check value fits scale 0. The text "12.0" is valid (`value.setScale(0, DOWN).compareTo(value) == 0`). The text "12.5" is E01.
- For FEE-RATE V9(5): check value in [0, 1) and fits scale 5. The text "0.010000" is valid (0.01 truncated to scale 5 equals 0.01).
- For INCOME 9(9)V99: check value non-negative, in range, and fits scale 2.
- Implementation: `value.setScale(targetScale, RoundingMode.DOWN).compareTo(value) == 0` checks if the value fits the target PIC.

**Parity point 2: Accepted numeric text format**
- COBOL NUMVAL accepts leading and trailing spaces, an optional leading sign. It does not accept exponents, trailing signs, CR/DB suffixes, embedded spaces, or parentheses for negatives.
- Java BigDecimal constructor accepts exponents ("1E2"), which NUMVAL rejects.
- Define the accepted format: after trimming leading and trailing spaces, the text must match `^[+-]?\\d+(\\.\\d+)?$` (optional leading sign, digits, optional decimal point and decimals, no exponent, no trailing sign).
- Blank (all spaces or empty string) is E01.
- Treat anything else as E01.
- The parity test will include an exponent case ("1E2"), which COBOL rejects; Java must also reject it.

**Helper method:**
```java
private static BigDecimal parseNumeric(String text) {
    if (text == null) return null;
    String trimmed = text.trim();
    if (trimmed.isEmpty()) return null;
    if (!trimmed.matches("^[+-]?\\d+(\\.\\d+)?$")) return null;
    try {
        return new BigDecimal(trimmed);
    } catch (NumberFormatException e) {
        return null;
    }
}
```

**Parity point 5: CASE-ID trimming and length**
- COBOL: UNSTRING into WS-IN-CASE-ID-RAW PIC X(20) (up to 20 characters), then FUNCTION TRIM(... TRAILING) (trim trailing spaces only), then check length greater than 10, then move to OUT-CASE-ID PIC X(10) (cut to 10 characters).
- Java: raw field up to 20 characters (UNSTRING receiver limit, but CSV split gives the full field; apply substring(0, 20) if longer), trim trailing spaces only with a helper method, check trimmed length greater than 10 is E01, blank (all spaces) is E01. Output CASE-ID is the trailing-trimmed value cut to 10 characters, also on E01 rows.

**Helper method:**
```java
private static String trimTrailing(String s) {
    int end = s.length();
    while (end > 0 && s.charAt(end - 1) == ' ') {
        end--;
    }
    return s.substring(0, end);
}
```

**Parity point 6: CUSTOMER-SEGMENT trimming and length**
- COBOL: raw field into WS-IN-SEGMENT-TXT PIC X(20), then FUNCTION TRIM(... TRAILING), then check length greater than 1 is E01. Empty after trimming trailing spaces is valid and goes to WHEN OTHER (no discount).
- Java: trim trailing spaces only, check trimmed length greater than 1 is E01. Empty is valid.

**Parity point 8: Range checks**
- PRINCIPAL: S9(9)V99, range -999999999.99 to 999999999.99, by value check with `setScale(2, DOWN).compareTo(value) == 0`.
- FEE-RATE: V9(5), range [0, 1) (0 inclusive, 1 exclusive), by value check with `setScale(5, DOWN).compareTo(value) == 0`. COBOL PIC V9(5) is unsigned and has 5 decimal places. Value 1.0 or greater is E01.
- DURATION: 9(3), range 0 to 999, integer by value. Valid when `value.setScale(0, DOWN).compareTo(value) == 0` and 0 <= value <= 999. "12.0" is valid, "12.5" is E01. Use intValueExact for the stored int.
- INCOME: 9(9)V99, range 0 to 999999999.99, non-negative, by value check with `setScale(2, DOWN).compareTo(value) == 0`.
- Fee result after rounding: S9(7)V99, absolute value at most 9999999.99. Check `feeValue.abs().compareTo(new BigDecimal("9999999.99")) > 0` is E01.

### Component 4: Fee computation

**Method signature:**
```java
private static FeeResult computeFee(ValidationResult input)
```

**Purpose:** Compute base fee, apply segment discount, apply minimum fee, detect overflow. Return FeeResult with the fee amount, reason code, and overflow flag.

**Data structures:**
```java
class FeeResult {
    BigDecimal feeAmount;
    String reasonCode;  // "E01" on overflow, "A01" on minimum fee, "A00" otherwise
}
```

**Pseudo-code:**
```
result = new FeeResult()

// Compute base fee with ROUNDED (HALF_UP)
baseFee = input.principal.multiply(input.feeRate)
baseFee = baseFee.setScale(2, RoundingMode.HALF_UP)

// Check overflow after rounding
if baseFee.abs().compareTo(new BigDecimal("9999999.99")) > 0:
    result.reasonCode = "E01"
    result.feeAmount = BigDecimal.ZERO
    return result

// Apply segment discount
discountedFee = baseFee
segment = input.customerSegment

if segment.equals("P"):
    discountRate = new BigDecimal("0.10")
    discountedFee = baseFee.multiply(BigDecimal.ONE.subtract(discountRate))
    discountedFee = discountedFee.setScale(2, RoundingMode.HALF_UP)
else if segment.equals("S"):
    discountRate = new BigDecimal("0.05")
    discountedFee = baseFee.multiply(BigDecimal.ONE.subtract(discountRate))
    discountedFee = discountedFee.setScale(2, RoundingMode.HALF_UP)
else if segment.equals("B"):
    discountedFee = baseFee
else:
    // WHEN OTHER
    discountedFee = baseFee

// Check overflow after discount
if discountedFee.abs().compareTo(new BigDecimal("9999999.99")) > 0:
    result.reasonCode = "E01"
    result.feeAmount = BigDecimal.ZERO
    return result

// Apply minimum fee rule
minFee = new BigDecimal("10.00")
if discountedFee.compareTo(BigDecimal.ZERO) > 0 
   and discountedFee.compareTo(minFee) < 0:
    result.feeAmount = minFee
    result.reasonCode = "A01"
else:
    result.feeAmount = discountedFee
    result.reasonCode = "A00"

return result
```

**Key points:**
- COBOL ROUNDED means RoundingMode.HALF_UP (nearest away from zero). For example, 12.345 rounds to 12.35, -12.345 rounds to -12.35.
- Overflow check happens after rounding and after discount. COBOL uses ON SIZE ERROR on the COMPUTE statements. The Java equivalent is to check the absolute value of the result against 9999999.99 (the maximum for S9(7)V99).
- Segment discount: 'P' gives 10% discount (multiply by 0.90), 'S' gives 5% discount (multiply by 0.95), 'B' and any other segment give no discount. The discount computation uses ROUNDED, so `setScale(2, RoundingMode.HALF_UP)`.
- Minimum fee: if the discounted fee is greater than zero and less than 10.00, raise it to 10.00 and set REASON-CODE to A01. This rule applies only to positive fees, not negative fees (rebates).
- The reason code priority is: E01 (overflow), A01 (minimum fee applied), A00 (normal). Eligibility reason codes R01 and R02 are set by checkEligibility, not by computeFee.

**Parity point 7: Negative zero**
- A fee that rounds to zero from a negative product (e.g., PRINCIPAL -0.40, FEE-RATE 0.01000, product -0.004, rounds to 0.00) might print as +0000000.00 or -0000000.00 depending on the COBOL runtime behavior.
- BigDecimal in Java represents zero with a sign (BigDecimal.ZERO is positive, but a rounded result might be negative zero in some representations).
- The parity test will include a negative zero case and verify the COBOL output. The Java code must match whatever COBOL prints. If COBOL prints +0000000.00, Java String.format("%+010.2f", 0.0) will also print +0000000.00. If COBOL prints -0000000.00, Java must detect the sign of the BigDecimal before rounding to zero and preserve it; this is not automatic, so the parity test will pin the behavior.
- Implementation: after rounding, check if the result is zero. If zero, the sign is determined by the original value before rounding. If the original product was negative and rounds to zero, the output might need to be -0000000.00. This is ambiguous and depends on the COBOL runtime; the parity test will clarify.

**Parity point 8 (continued): Overflow detection**
- Range check for the fee result happens after rounding to scale 2. COBOL uses ON SIZE ERROR with ROUNDED, which checks the range after rounding.
- Java: `feeValue.setScale(2, RoundingMode.HALF_UP).abs().compareTo(new BigDecimal("9999999.99")) > 0` is E01.

### Component 5: Eligibility check

**Method signature:**
```java
private static EligibilityResult checkEligibility(ValidationResult input, FeeResult fee)
```

**Purpose:** Check income and duration rules. Return EligibilityResult with eligible flag and reason code.

**Data structures:**
```java
class EligibilityResult {
    String eligible;  // "Y" or "N"
    String reasonCode;  // "R01", "R02", or fee.reasonCode if eligible
}
```

**Pseudo-code:**
```
result = new EligibilityResult()

minIncome = new BigDecimal("25000.00")
minDuration = 12

if input.income.compareTo(minIncome) < 0:
    result.eligible = "N"
    result.reasonCode = "R01"
else if input.durationMonths < minDuration:
    result.eligible = "N"
    result.reasonCode = "R02"
else:
    result.eligible = "Y"
    result.reasonCode = fee.reasonCode  // A00 or A01

return result
```

**Key points:**
- R01 has priority over R02 (COBOL checks income first).
- If eligible, the reason code is the one from computeFee (A00 or A01).
- If not eligible, the reason code is R01 or R02 and the fee is still written to output (not zero).

### Component 6: Output formatting

**Method signature:**
```java
private static String formatOutputLine(String caseId, BigDecimal feeAmount, 
                                       String eligible, String reasonCode)
```

**Purpose:** Format the output CSV line with the exact COBOL output format.

**Pseudo-code:**
```
// Format: sign + 7 integer digits zero-padded + point + 2 decimals = 11 characters
sign = (feeAmount.signum() >= 0) ? "+" : "-"
absValue = feeAmount.abs().setScale(2).toPlainString()
// Left-pad absValue to 10 characters (7 integer + point + 2 decimals)
feeFormatted = sign + padLeft(absValue, 10, '0')

return caseId + "," + feeFormatted + "," + eligible + "," + reasonCode
```

**Parity point 7 (continued): FEE-AMOUNT output format**
- COBOL PIC +9(7).99 produces a sign (+ or -), 7 integer digits zero-padded, a decimal point, and 2 decimals (11 characters total). Examples: +0000002.03, -0000002.03, +0000000.00.
- Java: format = sign ('+' when signum >= 0, '-' when negative) followed by the absolute value with setScale(2) and toPlainString, left-padded with zeros to 10 characters (7 integer digits, point, 2 decimals), total 11 characters.
- BigDecimal has no negative zero, so a fee rounding to 0.00 prints '+'. The parity test confirms COBOL does the same.

### Component 7: Record processing

**Method signature:**
```java
private static void processRecord(String line, BufferedWriter writer, 
                                   int[] errorCount)
```

**Purpose:** Parse, validate, compute, check eligibility, format, write. Increment error count on E01.

**Note:** errorCount is a single-element int array (mutable reference). Alternatively, processRecord could return a boolean indicating E01, and main increments a plain int field.

**Pseudo-code:**
```
// Truncate to 200 characters (COBOL PIC X(200))
if line.length() > 200:
    line = line.substring(0, 200)

// Remove trailing CR if present (CRLF input)
if line.endsWith("\r"):
    line = line.substring(0, line.length() - 1)

fields = parseLine(line)

validation = validateRecord(fields)

if !validation.valid:
    // E01 record
    errorCount[0]++
    outputLine = formatOutputLine(validation.caseId, BigDecimal.ZERO, 
                                   "N", "E01")
    writer.write(outputLine + "\n")
    return

fee = computeFee(validation)

if fee.reasonCode.equals("E01"):
    // Overflow
    errorCount[0]++
    outputLine = formatOutputLine(validation.caseId, BigDecimal.ZERO, 
                                   "N", "E01")
    writer.write(outputLine + "\n")
    return

eligibility = checkEligibility(validation, fee)

outputLine = formatOutputLine(validation.caseId, fee.feeAmount, 
                               eligibility.eligible, eligibility.reasonCode)
writer.write(outputLine + "\n")
```

**Key points:**
- Error count is incremented only when REASON-CODE is E01 (validation or overflow errors).
- E01 records write FEE-AMOUNT as +0000000.00, ELIGIBLE as N.
- Record-level variables (fields, validation, fee, eligibility) are all local to this method, so no state leakage between records.

## Data Models

### Input record (after validation)
```java
class ValidationResult {
    boolean valid;
    String caseId;           // PIC X(10), trimmed trailing, cut to 10
    BigDecimal principal;    // S9(9)V99, scale 2
    BigDecimal feeRate;      // V9(5), scale 5
    int durationMonths;      // 9(3), integer 0 to 999
    String customerSegment;  // X(1), length 0 or 1 after trimming trailing
    BigDecimal income;       // 9(9)V99, scale 2, non-negative
}
```

### Fee computation result
```java
class FeeResult {
    BigDecimal feeAmount;  // S9(7)V99, scale 2
    String reasonCode;     // "E01" on overflow, "A01" on minimum fee, "A00" otherwise
}
```

### Eligibility check result
```java
class EligibilityResult {
    String eligible;       // "Y" or "N"
    String reasonCode;     // "R01", "R02", or fee.reasonCode
}
```

### Constants
```java
private static final BigDecimal MIN_FEE = new BigDecimal("10.00");
private static final BigDecimal MIN_INCOME = new BigDecimal("25000.00");
private static final int MIN_DURATION = 12;
private static final BigDecimal MAX_FEE = new BigDecimal("9999999.99");
private static final BigDecimal MAX_PRINCIPAL = new BigDecimal("999999999.99");
private static final BigDecimal MAX_FEE_RATE = new BigDecimal("1.00");
private static final BigDecimal MAX_INCOME = new BigDecimal("999999999.99");
private static final int MAX_DURATION = 999;
```

## Error Handling

### Environment variables missing or file open failure
- Check `System.getenv("INPUT_FILE")` and `System.getenv("OUTPUT_FILE")`. If either is null, print `"ERROR: INPUT_FILE or OUTPUT_FILE not set"` to `System.err` and exit with code 16.
- If the input file cannot be opened (FileNotFoundException or IOException), print `"ERROR: Cannot open input file " + inputPath` to `System.err` and exit with code 16.
- If the output file cannot be opened, print `"ERROR: Cannot open output file " + outputPath` to `System.err`, close the input file, and exit with code 16.

### Empty input file
- If the first `readLine()` returns null (no header), write the output header, close both files, and exit with code 0.

### Validation errors (E01)
- Invalid field count, blank CASE-ID, CASE-ID longer than 10, numeric parse failure, range or scale violation, segment longer than 1: set REASON-CODE to E01, ELIGIBLE to N, FEE-AMOUNT to +0000000.00, increment error count, write the output line, continue with the next record.
- At the end of processing, if error count is greater than 0, exit with code 4.

### Overflow errors (E01)
- Base fee or discounted fee absolute value greater than 9999999.99 after rounding: set REASON-CODE to E01, ELIGIBLE to N, FEE-AMOUNT to +0000000.00, increment error count, write the output line, continue with the next record.

### Eligibility failures (R01, R02)
- Income below 25000.00: REASON-CODE R01, ELIGIBLE N, FEE-AMOUNT is the computed fee (not zero).
- Duration below 12: REASON-CODE R02, ELIGIBLE N, FEE-AMOUNT is the computed fee.
- Exit code is 0 (eligibility failures are not validation errors).

### No exceptions on valid input
- All numeric parsing is validated before BigDecimal construction, so no NumberFormatException on valid input.
- All file I/O uses try-catch blocks. If an IOException occurs during processing (not at open time), print an error to stderr and exit with code 16.

## Testing Strategy

### Pytest test: byte-identical output with COBOL

**Test file:** `tests/test_java_credit_fees.py`

**Test method:** `test_java_cobol_equivalence`

**Purpose:** For each fixture file, compile the Java program once per session, run both the COBOL program and the Java program with the same input, assert byte-identical outputs and equal exit codes.

**Fixtures:**
- `samples/credit-fees/fixtures/rounding-ties.csv` (at least 30 exact rounding ties, including negatives)
- `samples/credit-fees/fixtures/edge-cases.csv` (negative PRINCIPAL, zero, large values, all segments, eligibility boundaries)
- `samples/credit-fees/fixtures/validation-errors.csv` (every E01 cause from the requirements)
- `samples/credit-fees/fixtures/parity-cases.csv` (see below)

**Pseudo-code:**
```python
@pytest.fixture(scope="session")
def compile_java():
    if not shutil.which("javac"):
        pytest.skip("javac not found")
    os.makedirs("build/java", exist_ok=True)
    subprocess.run(["javac", "-d", "build/java", 
                    "samples/credit-fees/java/CreditFees.java"],
                   check=True, timeout=30)

@pytest.fixture(scope="session")
def compile_cobol():
    if not shutil.which("cobc"):
        pytest.skip("cobc not found")
    os.makedirs("build", exist_ok=True)
    subprocess.run(["cobc", "-x", "-o", "build/credit-fees",
                    "-I", "samples/credit-fees/copybooks",
                    "samples/credit-fees/CREDIT-FEES.cob"],
                   check=True, timeout=30)

@pytest.mark.parametrize("fixture", [
    "samples/credit-fees/fixtures/rounding-ties.csv",
    "samples/credit-fees/fixtures/edge-cases.csv",
    "samples/credit-fees/fixtures/validation-errors.csv",
    "samples/credit-fees/fixtures/parity-cases.csv",
])
def test_java_cobol_equivalence(fixture, compile_java, compile_cobol, tmp_path):
    cobol_output = tmp_path / "cobol-output.csv"
    java_output = tmp_path / "java-output.csv"

    # Run COBOL
    cobol_env = {
        "INPUT_FILE": fixture,
        "OUTPUT_FILE": str(cobol_output)
    }
    cobol_result = subprocess.run(
        ["./build/credit-fees"],
        env=cobol_env,
        capture_output=True,
        timeout=10
    )

    # Run Java
    java_env = {
        "INPUT_FILE": fixture,
        "OUTPUT_FILE": str(java_output)
    }
    java_result = subprocess.run(
        ["java", "-cp", "build/java", "CreditFees"],
        env=java_env,
        capture_output=True,
        timeout=10
    )

    # Assert exit codes match
    assert java_result.returncode == cobol_result.returncode

    # Assert outputs are byte-identical
    cobol_bytes = cobol_output.read_bytes()
    java_bytes = java_output.read_bytes()
    assert java_bytes == cobol_bytes
```

**Key points:**
- Compile once per session (session-scoped fixtures).
- Skip if cobc or java is not available (not fail).
- Timeout 10 seconds per run to prevent hanging.
- Use `tmp_path` for temporary output files, no cleanup needed (pytest cleans up).

### Parity fixture

**File:** `samples/credit-fees/fixtures/parity-cases.csv`

**Purpose:** One row per parity point to pin the COBOL behavior where it is ambiguous or not obvious from the code.

**Rows (example headers, actual data TBD):**
1. By-value decimals: PRINCIPAL "10.500" (valid, equals 10.50), "10.505" (E01, does not fit S9(9)V99 scale 2).
2. Spaces around numbers: PRINCIPAL " 100.00 " (valid after trimming).
3. Leading plus: PRINCIPAL "+100.00" (valid).
4. Exponent: PRINCIPAL "1E2" (E01, not accepted by NUMVAL).
5. Half decimal: PRINCIPAL "12.5" (valid, equals 12.50).
6. Trailing decimal: PRINCIPAL "5." (valid, equals 5.00).
7. Seven fields: (E01, field count not 6).
8. Five fields: (E01, field count not 6).
9. Empty line: (E01, one field, count not 6).
10. 201+ character line: (cut to 200, then parsed).
11. CRLF line: (CR removed, parsed normally).
12. CASE-ID 11 characters: (E01, length greater than 10 after trimming trailing).
13. CASE-ID 21 characters: (cut to 20 by UNSTRING, then trimmed, then E01 if greater than 10).
14. CUSTOMER-SEGMENT " B": (trimTrailing(" B") is " B" with length 2, E01).
15. CUSTOMER-SEGMENT empty: (valid, goes to WHEN OTHER, no discount).
16. Negative zero fee: PRINCIPAL -0.40, FEE-RATE 0.01000 (product -0.004, rounds to 0.00, observe COBOL output sign).

**Note:** The COBOL output on this fixture is the specification. The design does not guess the behavior; the Java code will be written to match the COBOL output byte-for-byte after the parity test is run.

### Rules check test

**Test file:** `tests/test_java_credit_fees.py`

**Test method:** `test_java_rules`

**Purpose:** Ensure the Java code does not use forbidden types or methods.

**Pseudo-code:**
```python
def test_java_rules():
    java_file = "samples/credit-fees/java/CreditFees.java"
    with open(java_file) as f:
        content = f.read()
    
    # No double or float for amounts
    assert " double " not in content
    assert " float " not in content
    
    # No Math.round
    assert "Math.round" not in content
    
    # No int or long for amounts (allowed for counters, duration)
    # This is a soft check: grep for suspicious patterns
    # Example: "int fee" or "long principal" would be violations
    # Allow "int duration", "int count", "int errorCount"
    # This check is heuristic and can be refined
```

**Key points:**
- Simple grep-based check to catch obvious violations.
- Does not parse Java AST, just text search.
- Can be refined if false positives occur.

### Independent oracle test (optional, for the test writer)

**Purpose:** Verify the rounding behavior with Python Decimal as an independent oracle.

**Pseudo-code:**
```python
from decimal import Decimal, ROUND_HALF_UP

def test_rounding_oracle():
    # Example from the COBOL fixture
    principal = Decimal("1234.50")
    fee_rate = Decimal("0.01000")
    product = principal * fee_rate
    rounded = product.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    assert rounded == Decimal("12.35")
    assert str(rounded) == "12.35"
    
    # Verify this matches the COBOL output and Java output
```

**Note:** This test is not required for the Java program itself, but can be used to verify the expected output before comparing COBOL and Java.

### Coverage check (future)

**Purpose:** Ensure the fixture files exercise all branches in the Java code.

**Method:** Use JaCoCo or a similar tool to measure branch coverage. This is out of scope for the initial implementation but noted here for completeness.

## Build and Run

### Compile
```bash
mkdir -p build/java
javac -d build/java samples/credit-fees/java/CreditFees.java
```

### Run
```bash
export INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv
export OUTPUT_FILE=build/java-output.csv
java -cp build/java CreditFees
echo $?  # Exit code: 0, 4, or 16
```

### Makefile targets (optional, for convenience)

**Target:** `java-compile`
```makefile
java-compile:
	mkdir -p build/java
	javac -d build/java samples/credit-fees/java/CreditFees.java
```

**Target:** `java-test`
```makefile
java-test: java-compile
	pytest tests/test_java_credit_fees.py -v
```

## Parity Points Summary

The design explicitly settles these parity points discovered by the operator. Where the COBOL behavior is not obvious from the code, the parity test will pin the behavior and the Java code will match it.

1. **Numeric validation by value:** "10.5" is valid (truncate to scale 2 equals original), "10.505" is E01. "12.0" is valid, "12.5" is E01 for DURATION. Check with `value.setScale(targetScale, DOWN).compareTo(value) == 0`.

2. **Accepted numeric text format:** After trimming leading and trailing spaces, match `^[+-]?\\d+(\\.\\d+)?$`. Exponents ("1E2") are E01. Blank is E01. The regex is provisional and adjusted after the parity test.

3. **Field split:** `String.split(",", -1)` keeps trailing empty fields. More than 6 or fewer than 6 is E01. Empty line gives one field, E01.

4. **Line length:** Truncate to 200 characters before parsing. Remove trailing CR if present.

5. **CASE-ID:** Raw field up to 20 characters, trim trailing spaces only, invalid if blank or longer than 10 after trimming. Output CASE-ID is trailing-trimmed and cut to 10, also on E01 rows.

6. **CUSTOMER-SEGMENT:** Trim trailing spaces only, invalid if longer than 1 after trimming. Empty after trimming is valid.

7. **FEE-AMOUNT output:** Format = sign ('+' or '-') followed by absolute value with setScale(2).toPlainString, left-padded to 10 characters (7 integer digits, point, 2 decimals), total 11 characters. BigDecimal has no negative zero, so 0.00 prints '+'.

8. **Range checks:** PRINCIPAL S9(9)V99, FEE-RATE [0, 1), DURATION 0 to 999 integer, INCOME 0 to 999999999.99. All checked by value with compareTo. Fee result overflow check after rounding: absolute value greater than 9999999.99 is E01.

9. **Header and empty input:** First line is skipped. Empty input writes header and exits 0.

10. **Exit codes:** 16 (env vars missing or file open failure), 4 (validation errors), 0 (success). Error messages on stderr for exit 16 only.

All parity points will be verified by the parity-cases.csv fixture with byte-identical comparison between COBOL and Java output.
