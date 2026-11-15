---
name: banking-trap-recognition
description: Recognize six banking migration traps in COBOL and Java ports
---

# Banking Trap Recognition

Six banking migration traps that silently corrupt amounts, signs, ordering or control totals:

## Trap 1: EBCDIC vs ASCII collating sequence

**COBOL**: `SORT ... COLLATING SEQUENCE IS <alphabet>` with `ALPHABET ... IS EBCDIC` or `OBJECT-COMPUTER PROGRAM COLLATING SEQUENCE`.

**Evidence**: SORT statement, EBCDIC order (space, lowercase, uppercase, digits vs ASCII space, digits, uppercase, lowercase).

**Java mistake**: Default `String.compareTo()` uses Unicode (ASCII-like) order. Control-break subtotals diverge while grand total matches.

## Trap 2: Rounding and truncation

**COBOL**: `ROUNDED` (no MODE) means NEAREST-AWAY-FROM-ZERO. Without `ROUNDED`, COBOL truncates toward zero.

**Evidence**: `COMPUTE` with `ROUNDED`, `MOVE` to a lower-precision field.

**Java mistake**: `RoundingMode.HALF_EVEN` instead of `HALF_UP`, or missing rounding entirely.

## Trap 3: COMP-3 sign nibble

**COBOL**: Packed-decimal sign nibble: `C` (hex) = positive, `D` = negative, `F` = unsigned.

**Evidence**: `COMP-3` or `PACKED-DECIMAL` fields.

**Java mistake**: Wrong sign interpretation, reading F as positive when it should be unsigned.

## Trap 4: Zoned sign overpunch

**COBOL**: Zoned decimal sign overpunch on the last digit (A-I = positive, J-R = negative).

**Evidence**: Input files with zoned decimal fields, `SIGN IS TRAILING` or implicit sign.

**Java mistake**: Reading the last byte as a digit without interpreting the overpunch.

## Trap 5: REDEFINES and invalid numeric data

**COBOL**: `REDEFINES` lets one field overlap another. Invalid numeric data in a redefined field.

**Evidence**: `REDEFINES` clause, alphanumeric field redefined as numeric.

**Java mistake**: No validation, assuming all numeric fields contain valid numbers.

## Trap 6: Reserved for owner field trap

Placeholder for a real migration trap provided by the owner.

## Procedure

1. Scan the COBOL program for these patterns (SORT ... COLLATING, ROUNDED, COMP-3, SIGN clauses, REDEFINES).
2. Scan the Java port for common mistakes (HALF_EVEN, no validation, wrong sign handling).
3. Use `@coroner/run_differential_check` to verify the port with generated cases.
4. If ZOMBIE, use `@coroner/get_failure_report` to see which COBOL lines diverged and the minimal failing case.
5. Use `@coroner/export_junit_test` to get the regression test.

**Rule**: Report a trap detection result or coverage value only when it comes from a Coroner tool result in this session. If a tool is not available or fails, say so and stop; never write a detection from memory or from the documentation.
