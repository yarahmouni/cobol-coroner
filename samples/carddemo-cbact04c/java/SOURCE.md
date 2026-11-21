# Cbact04c.java provenance

- **Producer**: Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-5.5), fresh isolated session
- **Date**: 2026-11-21

## Files read

All under port-input/:

- cobol/CBACT04C.cob
- cobol/HARNESS-CBACT04C.cob
- cobol/LOAD-FILES.cob
- cobol/RUN-CBACT04C.cob
- cobol/DUMP-ACCT.cob
- cobol/CEE3ABD.cob
- copybooks/CVACT01Y.cpy
- copybooks/CVACT03Y.cpy
- copybooks/CVTRA01Y.cpy
- copybooks/CVTRA02Y.cpy
- copybooks/CVTRA05Y.cpy
- fixtures/input-example.csv
- fixtures/output-example.csv
- schema.json (partially: the first 2500 bytes, lines 166 to 183, and grep matches for the output column names)

Nothing outside port-input/ and the output folders (port/, build/cd-port/) was opened, listed or searched. No COBOL was compiled or run.

## Compile

Command: `javac -d build/cd-port port/Cbact04c.java`

Result: success, exit status 0, no errors, no output.

Compile fixes: none.

## Example check

Ran the compiled class with INPUT_FILE=port-input/fixtures/input-example.csv and OUTPUT_FILE=build/cd-port/out-example.csv, then `diff` against port-input/fixtures/output-example.csv.

Result: identical (diff exit status 0, no output).

Changes made after the check: none.

## Behaviour notes and assumptions

The port simulates the chain harness, LOAD-FILES, RUN-CBACT04C and DUMP-ACCT in memory.

- Header row: the first input line is skipped. Output header is generated with the harness column names.
- Malformed row: wrong comma count (not 156) gives EXIT-CODE 252 and an empty CASE-ID. Invalid PARM-DATE, or a CATBAL-ACCT-INDEX above 5, gives 252 with CASE-ID kept.
- Rows are loaded in order tcatbal, xref, account, discgrp. The first duplicate key stops the load, so later files never exist. Opening a missing file in the run abends, which is reported as EXIT-CODE 231 (RETURN-CODE 999 as a process exit status, 999 mod 256). This 231 value comes from reading the stub and the harness, not from an example.
- A missing account, a missing xref for an account, or a missing rate including its DEFAULT group abends with 231. Updates and transactions made before the abend are kept.
- The last account in key order is never rewritten, because the update only runs when the next account starts. The example shows this (account 5 stays 345.00).
- Interest is (balance * rate) / 1200, truncated toward zero to 2 decimals. Fields keep COBOL storage rules: truncation of extra decimals, loss of high-order digits, unsigned fields store the absolute value.
- FUNCTION NUMVAL is implemented as a lenient scan (characters other than digits, sign, decimal point and CR/DB are skipped). This is an assumption about the GnuCOBOL runtime version.
- Zero amounts are printed as 0.00.
- Transaction id is PARM-DATE (10 chars, space padded) plus a 6 digit counter. Timestamps are built from PARM-DATE with time 12.00.00.000000.
- Files are read and written as ISO-8859-1 with LF line ends. Each output value loses trailing spaces only.
