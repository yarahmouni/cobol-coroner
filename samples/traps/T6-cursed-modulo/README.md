# Case 6: The Cursed Modulo (T6)

A rotation slot (a weekday slot, 0 to 6) is computed from a signed day offset relative to a reference date. A negative offset means days before the reference date. The COBOL program uses `FUNCTION MOD(DAY-OFFSET, 7)`.

## The trap

The Java port computes the slot with `%`. The two operations are different mathematical definitions of "remainder":

- COBOL `FUNCTION MOD(a, b)` takes the sign of the divisor `b`. `MOD(-11, 7)` is 3.
- Java `a % b` takes the sign of the dividend `a`. `-11 % 7` is -4.

For a positive offset the two agree. For a negative offset that is not a multiple of 7, the faulty port writes a negative slot (-6 to -1) where COBOL writes 0 to 6. `Math.floorMod` has the same definition as `FUNCTION MOD`.

Measured by the operator on GnuCOBOL 3.2.0 (`cobc -x -Wall`) and OpenJDK 17.0.21, 2026-11-23: `FUNCTION MOD(-11, 7)` = 3, `FUNCTION REM(-11, 7)` = -4, `FUNCTION MOD(-11, 5)` = 4, `FUNCTION MOD(11, -5)` = -4, `DIVIDE -11 BY 7 GIVING Q REMAINDER R` gives Q = -1 and R = -4. In Java, `-11 % 7` = -4 and `Math.floorMod(-11, 7)` = 3.

The twist: `DIVIDE ... REMAINDER` and `FUNCTION REM` in COBOL behave like Java `%`. A port that maps one construct correctly can map another one wrongly, so each construct must be checked separately. This program uses `FUNCTION MOD`, the construct whose result differs from `%`.

## How it differs from Case 3

Case 3 loses a sign in storage. Case 6 uses a different mathematical definition of the operation.

## Public sources

- IBM Enterprise COBOL language reference, FUNCTION MOD, with its table `MOD(-11,5) = 4` and `MOD(11,-5) = -4`: https://www.ibm.com/docs/en/SS6SG3_6.5/lr/ref/rlinfmod.html
- Java Language Specification, section 15.17.3, Remainder Operator %: https://docs.oracle.com/javase/specs/jls/se17/html/jls-15.html#jls-15.17.3
- SEI CERT Oracle Coding Standard for Java, rule NUM51-J: https://wiki.sei.cmu.edu/confluence/x/IxRMBQ

The measurements above come from the GnuCOBOL 3.2.0 reference used by Coroner. They do not claim the behaviour of IBM Enterprise COBOL on z/OS beyond what the IBM page states.

## Files

- `ROTATION-SLOT.cob`: the COBOL reference program.
- `schema.json`: input `CASE-ID`, `DAY-OFFSET` (PIC S9(3), range -999 to 999, about half negative from the generator); output `CASE-ID`, `DAY-OFFSET`, `SLOT` (a code, compared as exact text).
- `java/correct/RotationSlot.java`: uses `Math.floorMod`.
- `java/faulty/RotationSlot.java`: uses `%`.
- `fixtures/offsets.csv`: fixed offsets, including -11. `fixtures/expected-output.csv` is the output of the COBOL program on that file, never edited by hand.
