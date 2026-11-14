---
inclusion: always
---

# COBOL semantics (rules for writing the sample and its Java version)

## Sample COBOL coding rules
- Every IF has an explicit ELSE. Every EVALUATE has a WHEN OTHER. This is required by the coverage metric.
- No GO TO, no ALTER, no nested programs.
- COMP-3 fields are internal (WORKING-STORAGE) only.
- Numeric output fields use SIGN LEADING SEPARATE and an explicit decimal point (edited PIC), never overpunched signs.
- Write portable ANSI COBOL that compiles with GnuCOBOL 3.2.

## Rounding
- `ROUNDED` without a MODE means NEAREST-AWAY-FROM-ZERO in GnuCOBOL and IBM Enterprise COBOL.
- The Java equivalent is `BigDecimal.setScale(scale, RoundingMode.HALF_UP)`.
- Without ROUNDED, COBOL truncates: Java uses `RoundingMode.DOWN`.

## Java rules
- `BigDecimal` with explicit scale for every amount. `double` and `float` are forbidden.
- Output formatting: `setScale(scale).toPlainString()`.
- Intermediate results keep at least the precision COBOL keeps; document any choice in the spec.

## Return codes
- COBOL `RETURN-CODE` maps to the Java process exit code.
