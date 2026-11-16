# GnuCOBOL encoding behavior verified by the operator (D-46)

Date: 2026-11-15. cobc (GnuCOBOL) 3.2.0 on macOS (Homebrew), test programs compiled with `cobc -free -x` (plus the -fsign option where shown). These are the rules the trap programs and their Java ports are built on. They describe GnuCOBOL behavior, not IBM Enterprise COBOL on z/OS.

## Collating sequence (trap 1), see also R-35
- `SORT ... COLLATING SEQUENCE IS EBC` with `ALPHABET EBC IS EBCDIC`, `PROGRAM COLLATING SEQUENCE IS EBC`, and `-fdefault-colseq=EBCDIC` all order: space, lowercase, uppercase, digits. Without them (ASCII): space, digits, uppercase, lowercase.
- On letters, digits, space and hyphen this order equals the byte order of IBM037, IBM1047, IBM500 and IBM1140 in the JDK; on all printable punctuation no JDK charset matches (IBM1047 differs at 10 positions).

## Zoned decimal sign (trap 4)
| Case | default (= -fsign=ASCII) | -fsign=EBCDIC |
|---|---|---|
| PIC S9(5) value -12345, stored bytes | "1234u" (hex 3132333475: last digit + 0x40) | "1234N" (hex 313233344E) |
| PIC S9(5) value +12345, stored bytes | "12345" (hex 3132333435) | "1234E" (hex 3132333445) |
| input text "1234}" read through a REDEFINES as PIC S9(5) | +12340 (silently wrong) | -12340 |
| input text "1234u" read the same way | -12345 | +12345 |
| input text "1234M" read the same way | +12340 | -12344 |
The engine compiles without -fsign, so trap programs use the default convention.

## Packed decimal COMP-3 sign nibble (trap 3)
- Stored: PIC S9(5) COMP-3 -12345 = hex 12345D; +12345 = hex 12345C; PIC 9(5) COMP-3 12345 = hex 12345F.
- Bytes built with FUNCTION HEX-TO-CHAR from hex text and read through a REDEFINES (moved to a signed edited field):
| hex | as S9(5) COMP-3 | as 9(5) COMP-3 | S9(5) COMP-3 IS NUMERIC |
|---|---|---|---|
| 12345C | +12345 | +12345 | yes |
| 12345D | -12345 | -12345 | yes |
| 12345F | +12345 | +12345 | no |
| 12345B | +12345 | +12345 | no |
| 12345A | +12345 | +12345 | no |
- Note: GnuCOBOL reads nibble B as positive (IBM documentation treats B as negative): a port that follows the IBM rule diverges from this reference.

## Invalid numeric data under REDEFINES (trap 5)
- "12A45" in PIC X(5) redefined as PIC 9(5): IS NUMERIC is false; `COMPUTE RES = BAD-NUM + 1` gives 12146 with no abend and no message (no S0C7 in GnuCOBOL), rc 0.
- Low-nibble rule (operator run, same day): a non-digit byte in a PIC 9(5) read through a REDEFINES contributes its LOW NIBBLE as the digit value. "12A45" (A = x41) is used as 12145, so +1 gives 12146; "12B45" (x42) gives 12246; "12J45" (x4A, low nibble 10) gives 13046 (the 10 carries into the next position); "12Z45" (x5A) also 13046; "12 45" (space x20) gives 12046. Every run rc 0, no message. DISPLAY of the field shows the original characters (for example 012A45).

## Zoned overpunch, full table (operator run, 2026-11-16)
Input "1234x" in PIC X(5) read through a REDEFINES as PIC S9(5), for every last character x:
| last character | -fsign=EBCDIC | default (ASCII) |
|---|---|---|
| "{" and "A" to "I" | +0 to +9 (+12340 to +12349) | +12340 for every letter (letter read as digit 0) |
| "}" and "J" to "R" | -0 to -9 (-12340 to -12349) | +12340 for every letter |
| plain digit "0" to "9" | positive (+12340, +12345, +12349) | positive |
| "p", "u", "y" (ASCII convention) | positive (+12340, +12345, +12349): sign lost | -12340, -12345, -12349 |
Side effect: reading the field rewrites its stored last byte to the canonical form of the active convention (under -fsign=EBCDIC "12340" is stored back as "1234{"; under the default "1234{" becomes "12340").
