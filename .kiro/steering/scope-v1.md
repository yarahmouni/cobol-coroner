---
inclusion: always
---

# Scope V1

In scope:
- One standalone batch COBOL program (300 to 800 lines for the demo sample, 1 to 3 copybooks). Real migration cases (public, license-compatible, for example the MIT LegacyWeaver INTEREST program) are exempt from the line count (D-28).
- The veteran's catalog trap programs (small, exempt from the line count, D-29).
- One target: Java 17.
- Input and output: CSV described by `schema.json`.
- Reference runtime: GnuCOBOL 3.2.
- One screen UI, CLI, MCP server, Git and Kiro hooks.
- Coroner Certificate (JSON run record, D-24).
- Minimal failing case exported as JUnit 5 source test (D-25).
- Probable cause and one-sentence suggested fix (D-26).
- Fixed-width record format after the S1 core (D-27).
- A GitHub Action running Coroner in CI as a bonus (D-22).

Out of scope, and shown as such in the UI and README:
CICS, DB2, IMS, VSAM, JCL, EBCDIC-encoded data (the EBCDIC collating sequence trap is in scope, D-29), multi-program applications, Pacbase, any target other than Java 17, automatic conversion, real banking connectors.

Do not add features outside this list. If a task seems to need one, stop and ask.
