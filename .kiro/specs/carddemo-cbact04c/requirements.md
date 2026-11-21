# CardDemo CBACT04C Requirements

## Overview

Coroner audits a Kiro-generated Java port of one bounded interest-calculation path in AWS's open-source CardDemo sample, program CBACT04C.

Source: https://github.com/aws-samples/aws-mainframe-modernization-carddemo commit 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e (2025-10-16), Apache 2.0 license in samples/carddemo-cbact04c/LICENSE with NOTICE in samples/carddemo-cbact04c/NOTICE.

**Public wording** (required verbatim in all public documentation):
- "Uses AWS's open-source CardDemo sample (Apache 2.0). Not affiliated with or endorsed by AWS."
- "This preserves the business logic under audit; it does not emulate z/OS VSAM."
- Verdict wording: "no behavioral difference across the tested scenarios; not a certification for all inputs."

**Never use**: "AWS-approved", "validated", "certified", "official", "audits CardDemo", "all programs".

## Isolation of the porting agent

This spec, PROBE.md and generator.py record what the audit found about CBACT04C. The Java port is made by a separate Kiro session that must not read them. That session may read only:
- samples/carddemo-cbact04c/adapted/CBACT04C.cob (the program to port)
- samples/carddemo-cbact04c/upstream/cpy/*.cpy (its copybooks)
- samples/carddemo-cbact04c/schema.json (the input and output contract: column names, types, formats)

Its prompt must not say how to compute, round or order anything.

## Bounded Path

### In Scope

The interest loop of CBACT04C and the paragraphs it performs:
- **1000-TCATBALF-GET-NEXT**: sequential read of the transaction category balance file (key order: account id, type, category)
- **1050-UPDATE-ACCOUNT**: add the account's accumulated interest to ACCT-CURR-BAL, zero the cycle credit and debit, rewrite the account
- **1100-GET-ACCT-DATA**: read the account by id; a missing account ends in the abend routine
- **1110-GET-XREF-DATA**: read the card cross-reference by account id (alternate key). INVALID KEY only displays "ACCOUNT NOT FOUND"; the status check that follows treats any status other than "00" as an error and performs the abend routine (measured: exit 231, see Findings)
- **1200-GET-INTEREST-RATE** and **1200-A-GET-DEFAULT-INT-RATE**: read the rate for (account group, type, category); when it is missing (status 23) read the DEFAULT group for the same type and category; when that is missing too, abend
- **1300-COMPUTE-INTEREST**, **1300-B-WRITE-TX**: compute the monthly interest for one category balance, add it to the account total and write one interest transaction
- **1400-COMPUTE-FEES**: empty stub
- **Z-GET-DB2-FORMAT-TIMESTAMP**: timestamps built from the run date (fixed time 12:00:00, the only upstream change, adapted/CBACT04C.cob lines 614 to 621)

### Out of Scope

- File open and close paragraphs, I/O status display paragraphs
- adapted/CEE3ABD.cob stands in for the z/OS abend service: it displays the abend code and stops with RETURN-CODE 231 (abend code 999)
- All other CardDemo programs

## Findings (measured on GnuCOBOL 3.2.0, recorded in samples/carddemo-cbact04c/PROBE.md)

1. **Sign convention.** Upstream stores signed amounts with an EBCDIC zoned overpunch in the last character ("{" is +0, "}" is -0, A to I are +1 to +9, J to R are -1 to -9). Under GnuCOBOL's default convention the same bytes are read inconsistently, so every program of the sample, harness included, is compiled with `-fsign=EBCDIC`. The engine takes it from `cobc_flags` in schema.json.
2. **Last account.** The interest of the last account of a run (in key order) is computed and written as a transaction, but 1050-UPDATE-ACCOUNT never runs for it: its balance is not updated. A single-account run updates no balance. This is upstream behavior; the audit preserves it.
3. **Abends.** Three causes, measured through the harness on the 200 cases of seed 42 from the final generator: an account without cross-reference record (10 cases), a category balance on an unused account slot, i.e. account 0 (6 cases), a needed type and category with no rate and no DEFAULT rate (14 cases); one case had two causes. Every case with at least one cause gave exit status 231 (31 cases); the 169 cases with none gave exit status 0.
4. **Interest.** The COMPUTE in 1300-COMPUTE-INTEREST has no ROUNDED phrase. Its result field WS-MONTHLY-INT is S9(09)V99.

## Harness (adapted/HARNESS-CBACT04C.cob, written, see CHANGES.md)

CBACT04C keeps state in WORKING-STORAGE between calls and ends an abend with STOP RUN. The harness therefore runs each case as separate processes (LOAD-FILES, RUN-CBACT04C, DUMP-ACCT through CALL "SYSTEM") in its own work directory, so neither state nor an abend leaks into another case. It builds the helper programs itself at start with `make -C <sample dir> BUILD_DIR=<work dir>/bin harness-helpers` and removes its work directory at the end.

The engine runs it like any other program: `cobc -x -Wall -I <copybooks> -fsign=EBCDIC`, then INPUT_FILE and OUTPUT_FILE in the environment.

### Input contract: one CSV row per case, 157 columns

- CASE-ID (X(10)), PARM-DATE (X(10), digits and hyphens only)
- 5 account slots, columns ending in -1 to -5: ACCT-ID (9(11), 0 = unused), ACCT-GROUP-ID (X(10)), ACCT-CURR-BAL, ACCT-CURR-CYC-CREDIT, ACCT-CURR-CYC-DEBIT (S9(10)V99), XREF-CARD-NUM (X(16)), XREF-EXISTS (Y or N)
- 10 category balance slots, columns ending in -1 to -10: CATBAL-ACCT-INDEX (0 = unused, 1 to 5 names an account slot; a slot that is unused means account 0; above 5 makes the row malformed), CATBAL-TYPE (X(2)), CATBAL-CAT (9(4)), CATBAL-BAL (S9(9)V99)
- 20 rate slots, columns ending in -1 to -20: RATE-GROUP (X(10), blank = unused), RATE-TYPE (X(2)), RATE-CAT (9(4)), RATE-VALUE (S9(4)V99)

### Output contract: one CSV row per case, 98 columns

- CASE-ID, EXIT-CODE (exit status of the interest run; 252 malformed row, 251 work files not written)
- UPDATED-BAL-1 to 5: the account balance after the run, empty when the account is not in the dump
- NUM-TRANSACTIONS (all interest transactions written; empty on a malformed row)
- 10 transaction slots, columns TX-n-ID, -TYPE, -CAT, -SOURCE, -DESC, -AMT, -CARD-NUM, -ORIG-TS, -PROC-TS, in write order, empty beyond NUM-TRANSACTIONS
- Amounts are plain signed decimals at scale 2 (no plus sign, no leading zeros). They are string columns in schema.json because they are empty when absent, and the engine's decimal comparison treats an empty value as a divergence. The comparison is therefore exact text after trimming trailing spaces; a port must write the same text.

## Case Generation (schema key generator_script)

The engine's built-in generator cannot express relations between columns (a category balance naming an account slot, a rate for the group of that account, abend conditions). schema.json therefore declares `"generator_script": "generator.py"`.

### Engine rules

1. The path is relative to the folder that contains schema.json. After resolving symlinks it must be inside that folder and be a regular file. Otherwise the run stops with `ERROR: generator script outside schema directory: <declared path>` (or `generator script not found`), exit status 2, no run directory, no verdict, no certificate. The check happens when the schema is loaded, before any import or execution.
2. The engine reads the script once, compiles those bytes and runs them in a fresh namespace (no import machinery, no __pycache__ next to the script).
3. The script defines `generate_cases(schema, rng, num_cases)` and returns a list of `num_cases` dicts with exactly the schema's input column names. Values are str, int or Decimal (Decimal is written at the column's scale); anything else, and any line break in a value, is an error.
4. The script draws only from the `rng` it is given, through `rng.random()` (D-30). The same seed gives the same generated_cases.csv byte for byte.
5. The script never computes an expected outcome. Expected results come only from running the COBOL harness.

### Hash and certificate

- inputs.json gains `generator_script` and `generator_script_sha256` only when the schema declares a script. The run id includes the hash only in that case, so every other run id is unchanged (bundled ids f584d5f35228, 29c15f04407b, df4d7929ce44, 08d14a07bcdb).
- certificate.json gains the same two keys under the same condition.
- Replay refuses the certificate when the schema declares a script and the certificate has no hash, when the certificate has a hash and the schema declares none, and when the script on disk no longer matches (`generator script hash mismatch`).
- The gate (coroner/gate.py) and the pre-commit lookup (coroner/hooks.py) include the script hash in the files a certificate must match.

### What the generator covers

Negative, zero and positive category balances; zero and non-zero rates; groups with their own rate; groups that fall back to DEFAULT; needed type and category with no rate and no DEFAULT (abend); accounts without a cross-reference record (abend); a category balance on an unused account slot (abend); several category balances on one account; account slots in an order different from key order; single-account cases (the last-account behavior, in every case with a category balance). Amounts stay inside their PIC limits, so no case overflows a field.

## Java Port Requirements

Java 17 port produced **only** by a Kiro agent in an isolated session (see Isolation) from the adapted CBACT04C.cob, the copybooks and the contract in schema.json (Java 17, BigDecimal for money, explicit RoundingMode and scale). The prompt does not tell the agent how to compute or round. The port reads INPUT_FILE and writes OUTPUT_FILE with the 98 output columns. Prompt, transcript and the files the agent read are saved in docs/evidence/. The port is never hand-edited: a ZOMBIE is reported as ZOMBIE, an ALIVE as ALIVE.

## Comparison Rules

Per the engine (coroner/compare/__init__.py): exact comparison, no tolerance (D-09), string columns after trimming trailing spaces, return codes compared as OS exit statuses (D-31). The harness's own exit status is 0 when the run completes; the program's abend status travels in the EXIT-CODE column.

## Acceptance Criteria

1. Feasibility probe (done, PROBE.md): the adapted program compiles and runs under GnuCOBOL; probe-nonzero exits 0, missing-default exits 231.
2. Harness written and checked against the probe outputs before any Java exists (done, tasks 2 and 3).
3. schema.json and generator.py written, the engine extension in place and tested (done, tasks 4 to 7).
4. `coroner verify` runs end to end on CardDemo with a stand-in Java program that ports nothing and gives ZOMBIE at 20 cases (done, task 7).
5. The run time of the harness fits the engine's run timeout at the case count of the audit (open, task 8).
6. A Kiro port from the isolated session is audited at 200 cases; ALIVE or ZOMBIE is reported as it comes out (open, tasks 9 and 10).
7. Documentation: CHANGES.md lists every added file; the sample README carries the public wording; nothing claims "audits CardDemo" or "all programs".

## Measured run time (this Mac, stand-in Java, seed 42, final generator)

- 20 cases, `coroner verify --timings`: reference run 9.02 s, instrumented coverage run 13.47 s, report generation 6.17 s, total 30.8 s, verdict ZOMBIE on 20 cases.
- 200 cases: the reference run took 50.66 s (under the 60 s run timeout), then the instrumented coverage run (-ftraceall) exceeded the timeout: `Error: COBOL execution timed out after 60.0s`, exit 2, 113 s in total. An earlier 200-case run (before the generator's abend probabilities were lowered) already timed out in the reference run.
- The harness binary alone on the same 200 cases (INPUT_FILE and OUTPUT_FILE set by hand, no tracing): 52.94 s real. From the 20-case and 200-case reference runs the cost looks like about 7 s fixed plus 0.22 s per case (an estimate from two points, not a profile).
- The engine runs the harness twice (reference, then the instrumented build, which is slower), each with the 60 s run timeout. On a ZOMBIE the report step also takes the instrumented binary for the single-case re-run (6.17 s at 20 cases). 200 cases therefore does not fit the timeout on this machine. This spec does not change the engine's timeout; the decision is task 8.

## Uncertain

1. Whether the generated cases reach every branch of CBACT04C. The coverage reported for the harness (20 cases, stand-in: paragraph coverage 34/34, branch coverage 66/99) describes the harness program, not CBACT04C, which runs in subprocesses and is not instrumented.
2. A CSV value containing a comma would break the harness (it splits on commas without quoting). The generator never writes one and a test checks that no quote character appears in the cases file.
