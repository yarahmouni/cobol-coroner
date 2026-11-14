---
inclusion: always
---

# Scope V1

In scope:
- One standalone batch COBOL program (300 to 800 lines), 1 to 3 copybooks.
- One target: Java 17.
- Input and output: CSV described by `schema.json`.
- Reference runtime: GnuCOBOL 3.2.
- One screen UI, CLI, MCP server, Git and Kiro hooks.

Out of scope, and shown as such in the UI and README:
CICS, DB2, IMS, VSAM, JCL, EBCDIC, multi-program applications, Pacbase, any target other than Java 17, automatic conversion, real banking connectors.

Do not add features outside this list. If a task seems to need one, stop and ask.
