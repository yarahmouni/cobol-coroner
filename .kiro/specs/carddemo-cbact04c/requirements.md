# CardDemo CBACT04C Requirements

## Overview

Coroner audits a Kiro-generated Java port of one bounded interest-calculation path in AWS's open-source CardDemo sample, program CBACT04C.

Source: https://github.com/aws-samples/aws-mainframe-modernization-carddemo commit 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e (2025-10-16), Apache 2.0 license in samples/carddemo-cbact04c/LICENSE with NOTICE in samples/carddemo-cbact04c/NOTICE.

**Public wording** (required verbatim in all public documentation):
- "Uses AWS's open-source CardDemo sample (Apache 2.0). Not affiliated with or endorsed by AWS."
- "This preserves the business logic under audit; it does not emulate z/OS VSAM."
- Verdict wording: "no behavioral difference across the tested scenarios; not a certification for all inputs."

**Never use**: "AWS-approved", "validated", "certified", "official", "audits CardDemo", "all programs".

## Bounded Path

### In Scope

The interest calculation loop processing transaction category balances (adapted/CBACT04C.cob lines 186-231):
- **1000-TCATBALF-GET-NEXT**: Sequential read of transaction category balance records (lines 295-326)
- **1050-UPDATE-ACCOUNT**: Update account current balance with accumulated interest, zero out cycle credit/debit (lines 327-355)
- **1100-GET-ACCT-DATA**: Random read of account record by account ID (lines 356-378)
- **1110-GET-XREF-DATA**: Random read of card cross-reference by alternate key FD-XREF-ACCT-ID (lines 379-401); when XREFFILE-STATUS is not '00', the program abends (line 399 calls 9999-ABEND-PROGRAM)
- **1200-GET-INTEREST-RATE**: Random read of disclosure group record by (account group ID, transaction type, transaction category); when DISCGRP-STATUS is '23' (record not found), falls back to DEFAULT group via 1200-A-GET-DEFAULT-INT-RATE (lines 402-429, fallback lines 426-429)
- **1200-A-GET-DEFAULT-INT-RATE**: Reads DISCGRP-FILE with group ID 'DEFAULT' (same type and category); abends if DEFAULT is also missing (lines 431-451)
- **1300-COMPUTE-INTEREST**: Interest calculation: `COMPUTE WS-MONTHLY-INT = (TRAN-CAT-BAL * DIS-INT-RATE) / 1200` (line 457); skipped when DIS-INT-RATE = 0 (line 218)
- **1300-B-WRITE-TX**: Write interest transaction record to sequential output file; TRAN-ID built from PARM-DATE and WS-TRANID-SUFFIX (lines 464-503)
- **1400-COMPUTE-FEES**: Stub, no implementation (lines 505-507)
- **Z-GET-DB2-FORMAT-TIMESTAMP**: Builds DB2-FORMAT-TS from PARM-DATE with fixed time 12:00:00.00 (lines 576-590)

### Out of Scope

- File open/close paragraphs (0000-TCATBALF-OPEN through 0400-TRANFILE-OPEN lines 184-280, 9000-TCATBALF-CLOSE through 9400-TRANFILE-CLOSE lines 509-574): not part of business logic
- Error handling paragraphs (9999-ABEND-PROGRAM line 592, 9910-DISPLAY-IO-STATUS line 598): adapted/CEE3ABD.cob is a stub that DISPLAYs the abend code and STOPs RUN with RETURN-CODE = abend code
- All other CardDemo programs

## Adaptation Requirements

### 1. Adaptation Already Done

The following changes are already applied in adapted/CBACT04C.cob (see CHANGES.md):

**Lines 614-621**: FUNCTION CURRENT-DATE replaced by PARM-DATE parameter (X(10), format YYYY-MM-DD) with fixed time 12:00:00. This is the only change to the upstream program.

**ASSIGN clauses**: Unchanged from upstream. They use environment variables TCATBALF, XREFFILE, ACCTFILE, DISCGRP, TRANSACT without the EXTERNAL keyword (GnuCOBOL accepts them as written).

**CEE3ABD**: Not replaced inside adapted/CBACT04C.cob. Line 595 still calls 'CEE3ABD'. The stub is in adapted/CEE3ABD.cob (compiled separately with `cobc -m`): it DISPLAYs "CEE3ABD ABEND CODE <code>", moves the code to RETURN-CODE, and STOPs RUN.

**Copybooks**: Used from upstream/cpy via `-I` compiler flag (see Makefile line 18).

### 2. Probe Programs Already Built

- **adapted/RUN-CBACT04C.cob**: Driver that accepts PARM-DATE from environment variable CARDDEMO_PARM_DATE, calls CBACT04C with EXTERNAL-PARMS, then STOPs RUN.
- **adapted/LOAD-FILES.cob**: Loads text fixtures into indexed files (see Makefile targets probe-upstream, probe-nonzero, probe-missing-default).
- **adapted/DUMP-ACCT.cob**: Dumps account file records to display output (ACCT-ID and ACCT-CURR-BAL per line).
- **adapted/CEE3ABD.cob**: Stub replacing z/OS Language Environment service CEE3ABD.

### 3. New Requirement: Audit Harness

A NEW file adapted/HARNESS-CBACT04C.cob must be written to wrap CBACT04C for differential testing (documented in CHANGES.md as an addition).

## Harness Requirements

### The Problem: State Between Calls

CBACT04C (lines 167, 170, 173) maintains state in WORKING-STORAGE between calls:
- WS-LAST-ACCT-NUM: the last account processed
- WS-FIRST-TIME: 'Y' on first call, then 'N'
- WS-TRANID-SUFFIX: incremented per transaction written

It ends with GOBACK (line 232), not STOP RUN. If CANCEL is not called between cases, state from one case leaks into the next.

When an abend occurs (1110-GET-XREF-DATA line 399 or 1200-A-GET-DEFAULT-INT-RATE line 449 calls 9999-ABEND-PROGRAM), the stub CEE3ABD.cob (line 13) STOPs RUN with RETURN-CODE = abend code. This ends the whole run unit, so no case after an abend would execute.

### Solution: Separate Process Per Case

The harness runs each case in its own process by calling LOAD-FILES, RUN-CBACT04C and DUMP-ACCT through CALL "SYSTEM" (a GnuCOBOL extension). Each CALL "SYSTEM" forks a subprocess that executes the command and returns its exit code.

The engine runs a COBOL program by setting environment variables INPUT_FILE and OUTPUT_FILE, then executing the binary: `result = subprocess.run([binary], ..., env={..., 'INPUT_FILE': input_csv, 'OUTPUT_FILE': output_csv})` (from coroner/run/__init__.py run_cobol). The harness must read INPUT_FILE and write OUTPUT_FILE.

**Per-case steps**:
1. Read one case from INPUT_FILE
2. Write the case's text files (tcatbal.txt, cardxref.txt, acctdata.txt, discgrp.txt) to a temporary directory under TMPDIR or the current directory (never fixed /tmp/cbact04c-<CASE-ID>)
3. CALL "SYSTEM" to run LOAD-FILES, passing environment variables for input text paths and output .dat paths
4. CALL "SYSTEM" to run RUN-CBACT04C with CARDDEMO_PARM_DATE and the .dat paths
5. CALL "SYSTEM" to run DUMP-ACCT to read the updated account file
6. Read back the transaction file and account dump
7. Extract the case's interest amounts, updated balances, transaction count and exit code
8. Write one output CSV row to OUTPUT_FILE
9. Clean up temporary files

**Per-case cost**: The probe runs one case (7 transactions, 4 accounts) in well under a second (measured from `make probe-nonzero`). A 200-case audit will run in reasonable time (estimated under 60 seconds).

**Alternative rejected**: CANCEL 'CBACT04C' between cases would reset WORKING-STORAGE, but an abend in CEE3ABD would still end the harness. The separate-process approach isolates both state and abends.

## Data Model

### What CBACT04C Actually Does

CBACT04C reads TCATBAL-FILE sequentially (one TRAN-CAT-BAL-RECORD per iteration, copybook CVTRA01Y.cpy):
- TRANCAT-ACCT-ID (9(11))
- TRANCAT-TYPE-CD (X(02))
- TRANCAT-CD (9(04))
- TRAN-CAT-BAL (S9(09)V99)

When the account ID changes (line 199), it:
1. Calls 1050-UPDATE-ACCOUNT to add WS-TOTAL-INT to ACCT-CURR-BAL and zero ACCT-CURR-CYC-CREDIT and ACCT-CURR-CYC-DEBIT (lines 350-354)
2. Resets WS-TOTAL-INT to zero (line 203)
3. Reads the new account's ACCOUNT-RECORD via 1100-GET-ACCT-DATA (line 206)
4. Reads the CARD-XREF-RECORD via 1110-GET-XREF-DATA by alternate key FD-XREF-ACCT-ID (line 208)

For each TRAN-CAT-BAL-RECORD, it:
1. Looks up DIS-GROUP-RECORD by (ACCT-GROUP-ID, TRANCAT-TYPE-CD, TRANCAT-CD) in 1200-GET-INTEREST-RATE (line 216)
2. If DISCGRP-STATUS is '23', falls back to group 'DEFAULT' via 1200-A-GET-DEFAULT-INT-RATE (line 426)
3. If DIS-INT-RATE is not zero (line 217), computes `WS-MONTHLY-INT = (TRAN-CAT-BAL * DIS-INT-RATE) / 1200` (line 457)
4. Adds WS-MONTHLY-INT to WS-TOTAL-INT (line 459)
5. Writes one TRAN-RECORD with TRAN-ID from PARM-DATE and WS-TRANID-SUFFIX, type '01', category '05', TRAN-AMT = WS-MONTHLY-INT, TRAN-CARD-NUM from XREF-CARD-NUM (lines 464-503)

After the last TRAN-CAT-BAL-RECORD, it calls 1050-UPDATE-ACCOUNT for the last account (line 228).

### Missing XREF and Missing DEFAULT

**Missing XREF** (1110-GET-XREF-DATA INVALID KEY, line 396): The program DISPLAYs "ACCOUNT NOT FOUND: <account>" but does NOT abort. If XREFFILE-STATUS is not '00', it calls 9999-ABEND-PROGRAM (line 399). The probe missing-default dataset has XREF records for all accounts, so this path is not tested.

**Missing DEFAULT** (1200-A-GET-DEFAULT-INT-RATE, line 449): The program calls 9999-ABEND-PROGRAM, which calls CEE3ABD with code 999 (line 595), and the stub exits with RETURN-CODE 231 (operator measurement: probe/missing-default/exit-code.txt shows 231).

### Output Data

**TRANSACT file** (FD-TRANFILE-REC, copybook CVTRA05Y.cpy, 350 bytes per record): One record per interest transaction. The harness extracts:
- TRAN-ID (X(16))
- TRAN-TYPE-CD (X(02), always '01')
- TRAN-CAT-CD (9(04), always '0005')
- TRAN-SOURCE (X(10), always 'System')
- TRAN-DESC (X(100), format 'Int. for a/c <account>')
- TRAN-AMT (S9(09)V99)
- TRAN-CARD-NUM (X(16))
- TRAN-ORIG-TS (X(26), DB2 format timestamp)
- TRAN-PROC-TS (X(26), DB2 format timestamp)

**ACCOUNT file** (updated in place): Lines 350-354 add WS-TOTAL-INT to ACCT-CURR-BAL, zero ACCT-CURR-CYC-CREDIT and ACCT-CURR-CYC-DEBIT. DUMP-ACCT displays ACCT-ID and ACCT-CURR-BAL per line.

## Case Generation Rules

### Input Structure (one CSV row per case)

**Fixed columns**:
- CASE-ID: X(10), the case identifier
- PARM-DATE: X(10), the parameter date (YYYY-MM-DD)

**Per-account slots** (up to 5 accounts, indexed 1 to 5):
- ACCT-ID-N: 9(11)
- ACCT-GROUP-ID-N: X(10)
- ACCT-CURR-BAL-N: S9(09)V99
- ACCT-CURR-CYC-CREDIT-N: S9(09)V99
- ACCT-CURR-CYC-DEBIT-N: S9(09)V99
- XREF-CARD-NUM-N: X(16)
- XREF-EXISTS-N: X(1), 'Y' or 'N' (whether the account has an XREF record)

**Per-category-balance slots** (up to 20, indexed 1 to 20):
- CATBAL-ACCT-INDEX-N: 9(1), which account this balance belongs to (1 to 5)
- CATBAL-TYPE-N: X(02)
- CATBAL-CAT-N: 9(04)
- CATBAL-BAL-N: S9(09)V99

**Per-rate slots** (up to 30, indexed 1 to 30):
- RATE-GROUP-N: X(10)
- RATE-TYPE-N: X(02)
- RATE-CAT-N: 9(04)
- RATE-VALUE-N: S9(04)V99

**Per-generator rules** (schema extension needed if the engine cannot express them):
- Accounts: 1 to 5 (probe-nonzero has 4 accounts, missing-default has 2)
- Category balances per case: 1 to 10 (probe-nonzero has 7 balances)
- Rates: 5 to 20 (probe-nonzero has 9 rates, missing-default has 6 non-DEFAULT rates)
- Transactions written per case: 0 to 10 (probe-nonzero writes 7)
- Some accounts have XREF-EXISTS = 'N' (missing XREF, exercises the abend path)
- Some category balances reference a (group, type, category) with no rate entry and no DEFAULT entry (missing DEFAULT, exit 231)
- Some category balances reference a (group, type, category) with no group-specific rate but DEFAULT exists (exercises the fallback)
- Balances include negative (overdrafts), zero and positive
- Rates include 0 (no interest) and several non-zero values

The harness check (Task 3) covers only probe-nonzero and missing-default datasets (upstream-sample has 50 transactions and is too large for the 10-transaction maximum).

### Output Structure (one CSV row per case)

**Fixed columns**:
- CASE-ID: X(10), echoed from input
- EXIT-CODE: 9(3), actual exit code

**Per-account columns** (5 accounts):
- UPDATED-BAL-N: S9(09)V99, ACCT-CURR-BAL after interest posted
- UPDATED-CYC-CREDIT-N: S9(09)V99, should be zero
- UPDATED-CYC-DEBIT-N: S9(09)V99, should be zero

**Per-transaction columns** (up to 10 transactions, in write order):
- TX-N-ID: X(16)
- TX-N-TYPE: X(02)
- TX-N-CAT: 9(04)
- TX-N-SOURCE: X(10)
- TX-N-DESC: X(100)
- TX-N-AMT: S9(09)V99
- TX-N-CARD-NUM: X(16)
- TX-N-ORIG-TS: X(26)
- TX-N-PROC-TS: X(26)

**Count column**:
- NUM-TRANSACTIONS: 9(2), number of transaction records written (0 to 10)

### Engine Extension Needed

The current schema.json (coroner/parse/schema.py lines 1-230) supports:
- Per-column `domain` (list of string values or "dirty_numeric")
- Per-column `domain_weights` (dict or list)
- Optional `case_rows` (min and max rows per case)
- Optional `output_key` (list of column names for multi-row matching)

**Not supported**:
- Relations between columns (for example "CATBAL-ACCT-INDEX-1 must be 1, 2, 3, 4 or 5 and reference an existing account")
- Conditional generation (for example "when XREF-EXISTS-N is 'N', expect exit code 231")
- Variable-length arrays (for example "generate 1 to 20 category balances, each referencing one of the 5 accounts")

**Smallest extension** (new task after harness and Java port):
- Add `generator_script` optional key to schema.json: path to a Python script that takes (schema, rng, num_cases) and returns a list of dicts (one per case)
- The script can enforce any rule the schema cannot express
- Security requirement: The script path must resolve (after resolving symlinks) inside the directory that contains the schema.json, else the run stops with an ERROR verdict and message "generator script outside schema directory". Test: tests/test_generator_script_security.py creates a schema.json with generator_script pointing to /tmp/evil.py and asserts the run fails with ERROR.

## Comparison Rules

- Field-by-field exact comparison per existing engine (coroner/compare/__init__.py)
- Interest amounts: decimal with exact scale 2 (S9(09)V99)
- Transaction IDs: string exact match
- Timestamps: exact match (deterministic)
- Account balances: exact decimal match (scale 2)
- Exit code: exact integer match

## Engine Unchanged (Option A)

The current engine (coroner/cli.py run_verify, coroner/run/__init__.py, coroner/gen/__init__.py) runs one COBOL program and one Java program on the same generated input CSV, comparing their output CSVs. CBACT04C reads four INDEXED files and writes a sequential TRANSACT file plus updates ACCOUNT records.

**Option A** (chosen, engine unchanged):
- Write adapted/HARNESS-CBACT04C.cob that accepts one input CSV row per generated case
- Each row has the case's accounts, balances, rates, XREF existence flags
- The harness writes text files, calls LOAD-FILES, RUN-CBACT04C and DUMP-ACCT through CALL "SYSTEM" (separate process per case to isolate state and abends)
- The harness flattens the outputs (transactions and updated balances) into one output CSV row
- The Java side implements the same CSV contract around the ported logic
- The engine sees one CSV in, one CSV out: no engine changes

**Option B** (larger change, not chosen):
- Extend schema.json to declare multiple input files and multiple output files
- Extend coroner/run/__init__.py run_verify to set multiple environment variables per file
- Extend coroner/compare to compare multiple output files

**Decision**: Option A. The engine stays unchanged. adapted/CBACT04C.cob stays unchanged (it is the port target). The harness wraps it for differential testing.

## Java Port Requirements

### Source

Java 17 port produced **only** by a Kiro agent from:
- The adapted CBACT04C.cob (samples/carddemo-cbact04c/adapted/CBACT04C.cob)
- The copybooks (samples/carddemo-cbact04c/upstream/cpy/*.cpy)
- The I/O contract (input CSV columns and output CSV columns from schema.json)
- Language rules: Java 17, BigDecimal for money, RoundingMode explicit

**The prompt must not tell the agent how to compute or round**. No hint about the formula, no "HALF_UP rounding", no algorithm description. The agent reads the COBOL source and produces whatever it produces; that output is audited as is, never hand-edited.

The Kiro prompt (stating only the I/O contract, Java 17 and BigDecimal), the full CardDemo spec and the complete transcript are saved in docs/evidence/carddemo-cbact04c-port.txt.

### Never Hand-Edited

The Java port is **never** hand-edited to create a ZOMBIE verdict. If the Kiro-generated port is ZOMBIE, report it as ZOMBIE. If ALIVE, report ALIVE.

## Acceptance Criteria

1. **Feasibility probe succeeds** (already done, see PROBE.md): 
   - adapted/CBACT04C.cob compiles with cobc
   - adapted/LOAD-FILES.cob compiles and runs
   - adapted/RUN-CBACT04C calls CBACT04C with PARM-DATE
   - adapted/DUMP-ACCT dumps account balances
   - CBACT04C runs with loaded data: probe-nonzero exits 0 with 7 transactions, probe-missing-default exits 231

2. **Harness adapted/HARNESS-CBACT04C.cob written**: Reads one CSV row, writes text files, calls LOAD-FILES, RUN-CBACT04C and DUMP-ACCT through CALL "SYSTEM", flattens outputs into one CSV row

3. **Harness checked against probe outputs before Java exists**: Each of the three probe datasets (upstream-sample, probe-nonzero, missing-default) run through the harness gives the same interest amounts, updated balances and exit code as recorded in probe/*

4. **Schema.json or generator_script written**: Describes the per-case input and output structure (accounts, category balances, rates, transactions)

5. **Kiro agent generates Java port**: From adapted/CBACT04C.cob, the copybooks, the I/O contract and Java 17 + BigDecimal only (no algorithm hint)

6. **Coroner runs differential audit**: 
   - COBOL harness and Java on same generated cases
   - Field-by-field comparison of outputs
   - Verdict ALIVE or ZOMBIE with divergence details

7. **Documentation**:
   - samples/carddemo-cbact04c/CHANGES.md already lists the timestamp change (line 2) and the new files (lines 8-12)
   - samples/carddemo-cbact04c/LICENSE and NOTICE already preserved from upstream
   - README section stating the required public wording
   - Never claims "audits CardDemo" or "all programs"

## Time Box

Per D-62: One day of feasibility work. If the probe or Kiro port fails in a way that cannot be fixed within the bounded-path constraints, document the facts and make a go/no-go decision.

## Success Metric

A measured run on N generated cases (suggested N=200 for development, 2000 for catalog) gives:
- ALIVE verdict if the Kiro port is correct
- ZOMBIE verdict with exact divergence details if the port has a defect

The verdict wording must state: "no behavioral difference across the tested scenarios; not a certification for all inputs."


## Uncertain

1. The per-case subprocess cost: Will 200 cases complete in reasonable time? (Estimated from probe: well under a second per case, so under 2 minutes total. The 60-second target applies to verify, not individual samples.)

2. CALL "SYSTEM" return value on non-zero exit: Does GnuCOBOL correctly capture the child's exit status? (Probe measurement shows exit code 231 is returned. Accepted.)

3. Generator script signature: Does the engine's generate_cases call match what the script expects? (Checked: coroner/gen/__init__.py defines generate_cases(schema, num_cases, seed). The script receives these arguments.)
