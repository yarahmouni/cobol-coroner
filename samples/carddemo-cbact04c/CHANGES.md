# Changes from Upstream CardDemo CBACT04C

Source: https://github.com/aws-samples/aws-mainframe-modernization-carddemo commit 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e (2025-10-16)

## Only change to the upstream program

Lines 614-621 in CBACT04C.cob: FUNCTION CURRENT-DATE replaced by PARM-DATE parameter, fixed time to 12:00:00.

ASSIGN clauses unchanged (TCATBALF, XREFFILE, ACCTFILE, DISCGRP, TRANSACT map from environment variables as written).

## Additions (new files)

1. RUN-CBACT04C.cob: Driver program that calls CBACT04C with PARM-DATE from environment variable
   Header written for this project (an earlier version copied the CardDemo header by mistake).
2. CEE3ABD.cob: Stub for z/OS Language Environment abend service, not replaced inside CBACT04C
3. LOAD-FILES.cob: Loads text fixtures into indexed files; inserts ACCT-ADDR-ZIP (10 bytes) omitted in upstream acctdata.txt
4. DUMP-ACCT.cob: Account record dump utility
5. Makefile, datasets
6. HARNESS-CBACT04C.cob: the program Coroner compiles and runs. Reads one CSV row per case (157 columns: accounts, category balance slots, rate slots), writes the four text inputs in a unique work directory, runs LOAD-FILES, RUN-CBACT04C and DUMP-ACCT as separate processes, reads the TRANSACT file and the dumped balances, writes one output row (exit code, balances, transactions). It builds the helpers itself at start with `make -C <sample dir> BUILD_DIR=<work dir>/bin harness-helpers` and removes the work directory at the end. The Makefile `all` target no longer builds the harness (`make harness` does, by hand).
7. tools/dataset_to_row.py: converts a dataset folder (the four fixed-width text files) into harness input rows, with `--repeat N` for N rows with distinct CASE-IDs. Upstream marks signs with an EBCDIC zoned overpunch ("{" is +0, "}" is -0, A to I are +1 to +9, J to R are -1 to -9); the converter decodes them with that meaning only, which is how the programs read them when compiled with `-fsign=EBCDIC` (see Build options). Cycle credit and cycle debit that cannot be decoded become 0.00 with a warning (CBACT04C never reads them).
8. harness-check/: one-row inputs produced by dataset_to_row.py from datasets/probe-nonzero and datasets/missing-default (empty PARM-DATE, as in the probes).
9. probe/sign-convention/SIGN-PROBE.cob and `make probe-sign`: a 42-line probe program compiled with and without `-fsign=EBCDIC`; its two recorded outputs are the evidence for the build option (PROBE.md).
10. schema.json: the harness's 157 input and 98 output columns for `coroner verify`, `cobc_flags` `["-fsign=EBCDIC"]` and `generator_script` `generator.py`. The output amounts and counts are string columns because they are empty when absent.
11. generator.py: builds the generated cases for the harness (accounts, category balances, rates, accounts without cross-reference, categories without rate). It draws only from the random generator the engine gives it and never computes an expected outcome. The engine runs it only if it is inside this folder (coroner/parse/schema.py, `resolve_generator_script`).

## Build options

Every program of this sample is compiled with `cobc -fsign=EBCDIC` (Makefile variable `COBFLAGS`, applied to LOAD-FILES, CBACT04C, CEE3ABD, RUN-CBACT04C, DUMP-ACCT and the harness; the engine takes it from `cobc_flags` in the schema). It is a compiler option, not a source change. Reason, measured: under the default convention GnuCOBOL reads the upstream overpunch characters inconsistently (`0000010000{` displays +1000.00 but ADD gives -1000.11), see PROBE.md.

Makefile: BUILD_DIR defaults to the absolute path build/carddemo under the repository root; targets harness, harness-helpers and probe-sign added; COBFLAGS added.

All changes preserve the business logic under audit; it does not emulate z/OS VSAM.
