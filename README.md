# COBOL Coroner

**The independent regression auditor for COBOL-to-Java migrations.**

It checks whether a migration kept the business behavior on N generated cases, and shows exactly where it broke.

COBOL Coroner does not just compare outputs. It detects the banking migration traps that silently corrupt totals, control breaks and data ordering.

> AI accelerates. Coroner certifies.

COBOL Coroner does not convert code. It verifies a migration that already exists, whoever produced it (AWS Transform, Kiro, Claude or a human).

Give it:
- a batch COBOL program and its copybooks,
- its Java 17 version,
- a `schema.json` describing input and output columns.

Coroner runs both programs on the same generated test cases, compares the outputs field by field with no numeric tolerance, and returns a deterministic verdict:

- **ALIVE**: PASS: business behavior preserved on N cases (0 divergence found).
- **ZOMBIE**: FAIL: business behavior diverged on M cases, with the failing case, the COBOL output, the Java output, the divergent field and the COBOL lines executed.

## Status

Work in progress for Kiroween 2026 (category: Resurrection). See `docs/sprints.md`.

## What Coroner is not

- Not a converter.
- Not a formal proof of equivalence. An ALIVE verdict means "business behavior preserved on N cases", nothing more.
- Validated under GnuCOBOL 3.x only, not IBM Enterprise COBOL.

## Out of scope (V1)

CICS, DB2, IMS, VSAM, JCL, EBCDIC-encoded data (the EBCDIC collating sequence trap is in scope), multi-program applications, Pacbase, target languages other than Java 17.

## How Kiro was used

To be completed during the build: specs, steering, hooks and MCP server, see `/.kiro`.

## Data

All COBOL programs and data in this repository are synthetic. No code or data from any real bank is used.

## License

Apache-2.0. See LICENSE.
