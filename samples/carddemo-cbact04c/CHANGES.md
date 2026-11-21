# Changes from Upstream CardDemo CBACT04C

Source: https://github.com/aws-samples/aws-mainframe-modernization-carddemo commit 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e (2025-10-16)

## Only change to the upstream program

Lines 614-621 in CBACT04C.cob: FUNCTION CURRENT-DATE replaced by PARM-DATE parameter, fixed time to 12:00:00.

ASSIGN clauses unchanged (TCATBALF, XREFFILE, ACCTFILE, DISCGRP, TRANSACT map from environment variables as written).

## Additions (new files)

1. RUN-CBACT04C.cob: Driver program that calls CBACT04C with PARM-DATE from environment variable
2. CEE3ABD.cob: Stub for z/OS Language Environment abend service, not replaced inside CBACT04C
3. LOAD-FILES.cob: Loads text fixtures into indexed files; inserts ACCT-ADDR-ZIP (10 bytes) omitted in upstream acctdata.txt
4. DUMP-ACCT.cob: Account record dump utility
5. Makefile, datasets

All changes preserve the business logic under audit; it does not emulate z/OS VSAM.
