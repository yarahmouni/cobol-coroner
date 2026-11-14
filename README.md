# COBOL Lazarus

**The zombie detector for COBOL to Java migrations.**

> AI accelerates, Lazarus certifies.

COBOL Lazarus does not convert code. It verifies a migration that already exists, whoever produced it (AWS Transform, Kiro, Claude or a human).

Give it:
- a batch COBOL program and its copybooks,
- its Java 17 version,
- a `schema.json` describing input and output columns.

Lazarus runs both programs on the same generated test cases, compares the outputs field by field with no numeric tolerance, and returns a deterministic verdict:

- **VIVANT**: 0 divergence on N cases.
- **ZOMBIE**: M divergences on N cases, with the failing case, the COBOL output, the Java output, the divergent field and the COBOL lines executed.

## Status

Work in progress for Kiroween 2026 (category: Resurrection). See `docs/sprints.md`.

## What Lazarus is not

- Not a converter.
- Not a formal proof of equivalence. A VIVANT verdict means "no divergence found on N cases", nothing more.
- Validated under GnuCOBOL 3.x only, not IBM Enterprise COBOL.

## Out of scope (V1)

CICS, DB2, IMS, VSAM, JCL, EBCDIC, multi-program applications, Pacbase, target languages other than Java 17.

## How Kiro was used

To be completed during the build: specs, steering, hooks and MCP server, see `/.kiro`.

## Data

All COBOL programs and data in this repository are synthetic. No code or data from any real bank is used.

## License

Apache-2.0. See LICENSE.
