---
name: cobol-semantics-safety
description: COBOL semantic rules a Java port must preserve
---

# COBOL Semantics Safety

COBOL semantic rules that a Java 17 port must preserve to maintain business behavior.

## Rounding

- **ROUNDED** (no MODE) means NEAREST-AWAY-FROM-ZERO: Java `RoundingMode.HALF_UP`.
- Without ROUNDED, COBOL truncates toward zero: Java `RoundingMode.DOWN`.

## Numeric representation

- Use `BigDecimal` with explicit scale for all monetary amounts.
- Never use `double` or `float`.
- Intermediate results keep at least the precision COBOL keeps.

## Output formatting

- Use `setScale(scale).toPlainString()` for output.
- Pad with zeros to match COBOL edited picture width.

## Sign handling

- `SIGN LEADING SEPARATE`: explicit sign character in output.
- Negative zero prints as `+0000000.00` (COBOL normalizes it).

## EBCDIC collating sequence

- When COBOL uses `SORT ... COLLATING SEQUENCE IS EBCDIC`, Java must use a Comparator with the EBCDIC order (space, lowercase, uppercase, digits).
- Default `String.compareTo()` uses Unicode (ASCII-like) order and will break control breaks.

## Reference

See `.kiro/steering/cobol-semantics.md` for the complete rules.

## Procedure

1. For every `COMPUTE` or `MOVE` with `ROUNDED`, ensure Java uses `RoundingMode.HALF_UP`.
2. For every `COMPUTE` or `MOVE` without `ROUNDED`, ensure Java uses `RoundingMode.DOWN`.
3. Check all numeric fields are `BigDecimal` with explicit scale.
4. Check SORT statements for EBCDIC collating sequence.
5. Verify with `@coroner/run_differential_check` using at least 2,000 cases.

**Rule**: Report a semantic rule violation or verification result only when it comes from a Coroner tool result in this session. If a tool is not available or fails, say so and stop; never write a result from memory or from the documentation.
