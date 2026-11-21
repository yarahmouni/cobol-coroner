       IDENTIFICATION DIVISION.
       PROGRAM-ID. HARNESS-CBACT04C.
      *****************************************************************
      * Harness for differential tests of CardDemo CBACT04C (Coroner).
      *
      * Input  (INPUT_FILE): one CSV row per case, 157 columns:
      *   CASE-ID, PARM-DATE,
      *   5 account slots x 7 (ACCT-ID, ACCT-GROUP-ID, ACCT-CURR-BAL,
      *     ACCT-CURR-CYC-CREDIT, ACCT-CURR-CYC-DEBIT, XREF-CARD-NUM,
      *     XREF-EXISTS), column names end with -1 to -5,
      *   10 category balance slots x 4 (CATBAL-ACCT-INDEX, CATBAL-TYPE,
      *     CATBAL-CAT, CATBAL-BAL),
      *   20 rate slots x 4 (RATE-GROUP, RATE-TYPE, RATE-CAT,
      *     RATE-VALUE).
      * Slot is unused when ACCT-ID = 0, CATBAL-ACCT-INDEX = 0 or
      * RATE-GROUP is blank. CATBAL-ACCT-INDEX 1 to 5 names an account
      * slot; if that slot is unused the record points to account 0
      * (a missing account). An index above 5 makes the row malformed.
      *
      * Output (OUTPUT_FILE): one row per case: CASE-ID, EXIT-CODE (exit
      *   status of RUN-CBACT04C), UPDATED-BAL-1 to 5 (from DUMP-ACCT),
      *   NUM-TRANSACTIONS, then 10 transaction slots x 9 fields read
      *   from the TRANSACT file. Malformed row: EXIT-CODE 252, rest
      *   empty. Work files could not be written: EXIT-CODE 251.
      *
      * Each case runs LOAD-FILES, RUN-CBACT04C and DUMP-ACCT as
      * separate
      * processes (CALL "SYSTEM"), so the WORKING-STORAGE state of
      * CBACT04C and its abend (STOP RUN) never leak into another case.
      *
      * Helpers: at start the harness runs
      *   make -C <sample dir> BUILD_DIR=<work dir>/bin harness-helpers
      * The sample dir is the directory two levels above the source file
      * path given to cobc (FUNCTION MODULE-SOURCE); if its Makefile is
      * not there, samples/carddemo-cbact04c under the current directory
      * is tried. Work dir: $TMPDIR (default /tmp) /cbact04c-<pid>,
      * removed at the end. No path is built from CASE-ID.
      *****************************************************************

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-CSV ASSIGN TO DYNAMIC WS-INPUT-PATH
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS WS-FS.
           SELECT OUTPUT-CSV ASSIGN TO DYNAMIC WS-OUTPUT-PATH
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS WS-FS.
           SELECT TCAT-TXT ASSIGN TO DYNAMIC WS-TCAT-PATH
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS WS-FS.
           SELECT XREF-TXT ASSIGN TO DYNAMIC WS-XREF-PATH
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS WS-FS.
           SELECT ACCT-TXT ASSIGN TO DYNAMIC WS-ACCT-PATH
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS WS-FS.
           SELECT DISC-TXT ASSIGN TO DYNAMIC WS-DISC-PATH
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS WS-FS.
           SELECT TX-FILE ASSIGN TO DYNAMIC WS-TX-PATH
                  ORGANIZATION IS SEQUENTIAL
                  FILE STATUS IS WS-FS.
           SELECT DUMP-TXT ASSIGN TO DYNAMIC WS-DUMP-PATH
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS WS-FS.

       DATA DIVISION.
       FILE SECTION.
       FD  INPUT-CSV.
       01  INPUT-REC                   PIC X(4000).
       FD  OUTPUT-CSV.
       01  OUTPUT-REC                  PIC X(4000).
       FD  TCAT-TXT.
       01  TCAT-TXT-REC                PIC X(50).
       FD  XREF-TXT.
       01  XREF-TXT-REC                PIC X(50).
       FD  ACCT-TXT.
       01  ACCT-TXT-REC                PIC X(290).
       FD  DISC-TXT.
       01  DISC-TXT-REC                PIC X(50).
       FD  TX-FILE.
       01  TX-FILE-REC                 PIC X(350).
       FD  DUMP-TXT.
       01  DUMP-TXT-REC                PIC X(200).

       WORKING-STORAGE SECTION.
       COPY CVACT01Y.
       COPY CVACT03Y.
       COPY CVTRA01Y.
       COPY CVTRA02Y.
       COPY CVTRA05Y.

       01  WS-FS                       PIC XX.
       01  WS-INPUT-PATH               PIC X(400).
       01  WS-OUTPUT-PATH              PIC X(400).
       01  WS-TMPDIR                   PIC X(200).
       01  WS-SRC-PATH                 PIC X(400).
       01  WS-SAMPLE-DIR               PIC X(400).
       01  WS-CHECK-PATH               PIC X(450).
       01  WS-FILE-INFO.
           05  FILLER                  PIC X(16).
       01  WS-WORK-ROOT                PIC X(300).
       01  WS-BIN-DIR                  PIC X(320).
       01  WS-CASE-DIR                 PIC X(320).
       01  WS-TCAT-PATH                PIC X(340).
       01  WS-XREF-PATH                PIC X(340).
       01  WS-ACCT-PATH                PIC X(340).
       01  WS-DISC-PATH                PIC X(340).
       01  WS-TX-PATH                  PIC X(340).
       01  WS-DUMP-PATH                PIC X(340).
       01  WS-COMMAND                  PIC X(2400).
       01  WS-RC                       PIC S9(9) BINARY.
       01  WS-REM                      PIC S9(9) BINARY.
       01  WS-PID                      PIC S9(9) BINARY.
       01  WS-PID-TXT                  PIC 9(9).
       01  WS-CASE-SEQ                 PIC 9(6) VALUE 0.
       01  WS-CASE-SEQ-TXT             PIC 9(6).

       01  WS-STARTUP-OK               PIC X VALUE 'N'.
       01  WS-INPUT-EOF                PIC X VALUE 'N'.
       01  WS-TX-EOF                   PIC X VALUE 'N'.
       01  WS-DUMP-EOF                 PIC X VALUE 'N'.
       01  WS-ROW-OK                   PIC X.
       01  WS-IO-FAIL                  PIC X.
       01  WS-DATE-OK                  PIC X.
       01  WS-SEEN-SPACE               PIC X.

       01  WS-PTR                      PIC 9(5).
       01  WS-COMMA-COUNT              PIC 9(5).
       01  WS-F                        PIC 9(3).
       01  WS-BASE                     PIC 9(3).
       01  WS-A                        PIC 9(3).
       01  WS-C                        PIC 9(3).
       01  WS-R                        PIC 9(3).
       01  WS-T                        PIC 9(3).
       01  WS-K                        PIC 9(3).
       01  WS-L                        PIC 9(4).
       01  WS-IDX                      PIC 9(3).

       01  WS-FLD-TABLE.
           05  WS-FLD OCCURS 157 TIMES PIC X(40).

       01  WS-CASE-ID                  PIC X(10).
       01  WS-PARM-DATE                PIC X(10).
       01  WS-EXIT-CODE                PIC S9(9) BINARY.

       01  WS-ACCT-TABLE.
           05  WS-ACC OCCURS 5 TIMES.
               10  WS-A-ID             PIC 9(11).
               10  WS-A-GROUP          PIC X(10).
               10  WS-A-BAL            PIC S9(10)V99.
               10  WS-A-CREDIT         PIC S9(10)V99.
               10  WS-A-DEBIT          PIC S9(10)V99.
               10  WS-A-CARD           PIC X(16).
               10  WS-A-XREF           PIC X.
               10  WS-A-UPD            PIC S9(10)V99.
               10  WS-A-UPD-OK         PIC X.

       01  WS-CATBAL-TABLE.
           05  WS-CB OCCURS 10 TIMES.
               10  WS-CB-IDX           PIC 9(3).
               10  WS-CB-TYPE          PIC X(2).
               10  WS-CB-CAT           PIC 9(4).
               10  WS-CB-BAL           PIC S9(9)V99.

       01  WS-RATE-TABLE.
           05  WS-RT OCCURS 20 TIMES.
               10  WS-RT-GROUP         PIC X(10).
               10  WS-RT-TYPE          PIC X(2).
               10  WS-RT-CAT           PIC 9(4).
               10  WS-RT-VALUE         PIC S9(4)V99.

       01  WS-TX-COUNT                 PIC 9(5).
       01  WS-TX-TABLE.
           05  WS-TXN OCCURS 10 TIMES.
               10  WS-TX-ID            PIC X(16).
               10  WS-TX-TYPE          PIC X(2).
               10  WS-TX-CAT           PIC X(4).
               10  WS-TX-SOURCE        PIC X(10).
               10  WS-TX-DESC          PIC X(100).
               10  WS-TX-AMT           PIC S9(9)V99.
               10  WS-TX-CARD          PIC X(16).
               10  WS-TX-ORIG          PIC X(26).
               10  WS-TX-PROC          PIC X(26).

       01  WS-DUMP-ID                  PIC 9(11).
       01  WS-DUMP-BAL                 PIC S9(10)V99.

       01  WS-OUT-PTR                  PIC 9(5).
       01  WS-FIRST-COL                PIC X.
       01  WS-APP-VAL                  PIC X(120).
       01  WS-NUM                      PIC S9(10)V99.
       01  WS-EDIT                     PIC -(11)9.99.
       01  WS-INT-EDIT                 PIC Z(8)9.
       01  WS-IDX-EDIT                 PIC Z9.
       01  WS-IDX-TXT                  PIC X(2).
       01  WS-IDX-LEN                  PIC 9.

       PROCEDURE DIVISION.
       MAIN-PROC.
           PERFORM STARTUP.
           IF WS-STARTUP-OK = 'Y'
               PERFORM PROCESS-FILE
           ELSE
               MOVE 2 TO RETURN-CODE
           END-IF.
           PERFORM REMOVE-WORK-ROOT.
           STOP RUN.

       STARTUP.
           ACCEPT WS-INPUT-PATH FROM ENVIRONMENT "INPUT_FILE".
           ACCEPT WS-OUTPUT-PATH FROM ENVIRONMENT "OUTPUT_FILE".
           IF WS-INPUT-PATH = SPACES OR WS-OUTPUT-PATH = SPACES
               DISPLAY "HARNESS: INPUT_FILE, OUTPUT_FILE required"
                   UPON SYSERR
           ELSE
               PERFORM FIND-SAMPLE-DIR
               IF WS-SAMPLE-DIR = SPACES
                   DISPLAY "HARNESS: sample directory not found"
                       UPON SYSERR
               ELSE
                   PERFORM BUILD-HELPERS
               END-IF
           END-IF.

       FIND-SAMPLE-DIR.
      * Candidate 1: two levels above the source path given to cobc.
           MOVE SPACES TO WS-SAMPLE-DIR.
           MOVE FUNCTION MODULE-SOURCE TO WS-SRC-PATH.
           PERFORM CUT-LAST-SEGMENT.
           PERFORM CUT-LAST-SEGMENT.
           IF WS-SRC-PATH NOT = SPACES
               MOVE WS-SRC-PATH TO WS-SAMPLE-DIR
               PERFORM CHECK-SAMPLE-DIR
           ELSE
               CONTINUE
           END-IF.
      * Candidate 2: current directory.
           IF WS-SAMPLE-DIR = SPACES
               MOVE "samples/carddemo-cbact04c" TO WS-SAMPLE-DIR
               PERFORM CHECK-SAMPLE-DIR
           ELSE
               CONTINUE
           END-IF.

       CUT-LAST-SEGMENT.
      * Remove the last "/name" from WS-SRC-PATH (all spaces if none).
           MOVE 400 TO WS-L.
           PERFORM UNTIL WS-L = 0 OR WS-SRC-PATH(WS-L:1) = "/"
               SUBTRACT 1 FROM WS-L
           END-PERFORM.
           IF WS-L > 1
               MOVE SPACES TO WS-SRC-PATH(WS-L:)
           ELSE
               MOVE SPACES TO WS-SRC-PATH
           END-IF.

       CHECK-SAMPLE-DIR.
      * Keep WS-SAMPLE-DIR only if it holds the Makefile.
           MOVE SPACES TO WS-CHECK-PATH.
           STRING WS-SAMPLE-DIR DELIMITED BY SPACE
                  "/Makefile" DELIMITED BY SIZE
                  INTO WS-CHECK-PATH
           END-STRING.
           CALL "CBL_CHECK_FILE_EXIST" USING WS-CHECK-PATH WS-FILE-INFO
               RETURNING WS-RC
           END-CALL.
           IF WS-RC = 0
               CONTINUE
           ELSE
               MOVE SPACES TO WS-SAMPLE-DIR
           END-IF.

       BUILD-HELPERS.
           ACCEPT WS-TMPDIR FROM ENVIRONMENT "TMPDIR".
           IF WS-TMPDIR = SPACES
               MOVE "/tmp" TO WS-TMPDIR
           ELSE
               CONTINUE
           END-IF.
           CALL "C$GETPID" RETURNING WS-PID.
           MOVE WS-PID TO WS-PID-TXT.
           MOVE SPACES TO WS-WORK-ROOT.
           STRING WS-TMPDIR DELIMITED BY SPACE
                  "/cbact04c-" DELIMITED BY SIZE
                  WS-PID-TXT DELIMITED BY SIZE
                  INTO WS-WORK-ROOT
           END-STRING.
           CALL "CBL_CREATE_DIR" USING WS-WORK-ROOT
               RETURNING WS-RC
           END-CALL.
           IF WS-RC NOT = 0
               DISPLAY "HARNESS: cannot create work directory"
                   UPON SYSERR
               MOVE SPACES TO WS-WORK-ROOT
           ELSE
               MOVE SPACES TO WS-BIN-DIR
               STRING WS-WORK-ROOT DELIMITED BY SPACE
                      "/bin" DELIMITED BY SIZE
                      INTO WS-BIN-DIR
               END-STRING
               MOVE SPACES TO WS-COMMAND
               STRING "make -C " DELIMITED BY SIZE
                      WS-SAMPLE-DIR DELIMITED BY SPACE
                      " BUILD_DIR=" DELIMITED BY SIZE
                      WS-BIN-DIR DELIMITED BY SPACE
                      " harness-helpers > " DELIMITED BY SIZE
                      WS-WORK-ROOT DELIMITED BY SPACE
                      "/build.log 2>&1" DELIMITED BY SIZE
                      INTO WS-COMMAND
               END-STRING
               CALL "SYSTEM" USING WS-COMMAND RETURNING WS-RC
               IF WS-RC = 0
                   MOVE 'Y' TO WS-STARTUP-OK
               ELSE
                   DISPLAY "HARNESS: helper build failed" UPON SYSERR
                   MOVE SPACES TO WS-COMMAND
                   STRING "cat " DELIMITED BY SIZE
                          WS-WORK-ROOT DELIMITED BY SPACE
                          "/build.log 1>&2" DELIMITED BY SIZE
                          INTO WS-COMMAND
                   END-STRING
                   CALL "SYSTEM" USING WS-COMMAND
               END-IF
           END-IF.

       REMOVE-WORK-ROOT.
           IF WS-WORK-ROOT = SPACES
               CONTINUE
           ELSE
               MOVE SPACES TO WS-COMMAND
               STRING "rm -rf " DELIMITED BY SIZE
                      WS-WORK-ROOT DELIMITED BY SPACE
                      INTO WS-COMMAND
               END-STRING
               CALL "SYSTEM" USING WS-COMMAND
           END-IF.

       PROCESS-FILE.
           OPEN INPUT INPUT-CSV.
           IF WS-FS NOT = "00"
               DISPLAY "HARNESS: cannot open INPUT_FILE" UPON SYSERR
               MOVE 2 TO RETURN-CODE
           ELSE
               OPEN OUTPUT OUTPUT-CSV
               IF WS-FS NOT = "00"
                   DISPLAY "HARNESS: cannot open OUTPUT_FILE"
                       UPON SYSERR
                   MOVE 2 TO RETURN-CODE
                   CLOSE INPUT-CSV
               ELSE
                   PERFORM WRITE-HEADER
                   PERFORM READ-INPUT-ROW
                   PERFORM UNTIL WS-INPUT-EOF = 'Y'
                       PERFORM READ-INPUT-ROW
                       IF WS-INPUT-EOF = 'Y'
                           CONTINUE
                       ELSE
                           PERFORM PROCESS-ONE-CASE
                       END-IF
                   END-PERFORM
                   CLOSE INPUT-CSV
                   CLOSE OUTPUT-CSV
               END-IF
           END-IF.

       READ-INPUT-ROW.
           MOVE SPACES TO INPUT-REC.
           READ INPUT-CSV
               AT END
                   MOVE 'Y' TO WS-INPUT-EOF
               NOT AT END
                   CONTINUE
           END-READ.

       PROCESS-ONE-CASE.
           ADD 1 TO WS-CASE-SEQ.
           PERFORM CLEAR-CASE.
           PERFORM PARSE-ROW.
           IF WS-ROW-OK = 'Y'
               PERFORM RUN-CASE
           ELSE
               MOVE 252 TO WS-EXIT-CODE
           END-IF.
           PERFORM WRITE-OUTPUT-ROW.

       CLEAR-CASE.
           MOVE SPACES TO WS-CASE-ID WS-PARM-DATE.
           MOVE 0 TO WS-EXIT-CODE WS-TX-COUNT.
           MOVE 'N' TO WS-IO-FAIL.
           INITIALIZE WS-ACCT-TABLE WS-CATBAL-TABLE WS-RATE-TABLE
                      WS-TX-TABLE.

       PARSE-ROW.
           MOVE 'Y' TO WS-ROW-OK.
           MOVE 0 TO WS-COMMA-COUNT.
           INSPECT INPUT-REC TALLYING WS-COMMA-COUNT FOR ALL ",".
           IF WS-COMMA-COUNT NOT = 156
               MOVE 'N' TO WS-ROW-OK
           ELSE
               MOVE 1 TO WS-PTR
               PERFORM VARYING WS-F FROM 1 BY 1 UNTIL WS-F > 157
                   MOVE SPACES TO WS-FLD(WS-F)
                   UNSTRING INPUT-REC DELIMITED BY ","
                       INTO WS-FLD(WS-F)
                       WITH POINTER WS-PTR
                   END-UNSTRING
               END-PERFORM
               MOVE WS-FLD(1) TO WS-CASE-ID
               MOVE WS-FLD(2) TO WS-PARM-DATE
               PERFORM VALIDATE-DATE
               IF WS-DATE-OK = 'N'
                   MOVE 'N' TO WS-ROW-OK
               ELSE
                   PERFORM LOAD-TABLES
               END-IF
           END-IF.

       VALIDATE-DATE.
      * The date goes into a shell command: digits and "-" only.
           MOVE 'Y' TO WS-DATE-OK.
           MOVE 'N' TO WS-SEEN-SPACE.
           IF WS-FLD(2)(11:30) = SPACES
               CONTINUE
           ELSE
               MOVE 'N' TO WS-DATE-OK
           END-IF.
           PERFORM VARYING WS-K FROM 1 BY 1 UNTIL WS-K > 10
               IF WS-PARM-DATE(WS-K:1) = SPACE
                   MOVE 'Y' TO WS-SEEN-SPACE
               ELSE
                   IF WS-SEEN-SPACE = 'Y'
                       MOVE 'N' TO WS-DATE-OK
                   ELSE
                       IF WS-PARM-DATE(WS-K:1) IS NUMERIC
                          OR WS-PARM-DATE(WS-K:1) = "-"
                           CONTINUE
                       ELSE
                           MOVE 'N' TO WS-DATE-OK
                       END-IF
                   END-IF
               END-IF
           END-PERFORM.

       LOAD-TABLES.
           PERFORM VARYING WS-A FROM 1 BY 1 UNTIL WS-A > 5
               COMPUTE WS-BASE = 3 + (WS-A - 1) * 7
               COMPUTE WS-A-ID(WS-A) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE))
               MOVE WS-FLD(WS-BASE + 1) TO WS-A-GROUP(WS-A)
               COMPUTE WS-A-BAL(WS-A) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE + 2))
               COMPUTE WS-A-CREDIT(WS-A) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE + 3))
               COMPUTE WS-A-DEBIT(WS-A) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE + 4))
               MOVE WS-FLD(WS-BASE + 5) TO WS-A-CARD(WS-A)
               MOVE WS-FLD(WS-BASE + 6)(1:1) TO WS-A-XREF(WS-A)
           END-PERFORM.
           PERFORM VARYING WS-C FROM 1 BY 1 UNTIL WS-C > 10
               COMPUTE WS-BASE = 38 + (WS-C - 1) * 4
               COMPUTE WS-IDX = FUNCTION NUMVAL(WS-FLD(WS-BASE))
               MOVE WS-IDX TO WS-CB-IDX(WS-C)
               IF WS-IDX > 5
                   MOVE 'N' TO WS-ROW-OK
               ELSE
                   CONTINUE
               END-IF
               MOVE WS-FLD(WS-BASE + 1) TO WS-CB-TYPE(WS-C)
               COMPUTE WS-CB-CAT(WS-C) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE + 2))
               COMPUTE WS-CB-BAL(WS-C) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE + 3))
           END-PERFORM.
           PERFORM VARYING WS-R FROM 1 BY 1 UNTIL WS-R > 20
               COMPUTE WS-BASE = 78 + (WS-R - 1) * 4
               MOVE WS-FLD(WS-BASE) TO WS-RT-GROUP(WS-R)
               MOVE WS-FLD(WS-BASE + 1) TO WS-RT-TYPE(WS-R)
               COMPUTE WS-RT-CAT(WS-R) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE + 2))
               COMPUTE WS-RT-VALUE(WS-R) =
                   FUNCTION NUMVAL(WS-FLD(WS-BASE + 3))
           END-PERFORM.

       RUN-CASE.
           MOVE WS-CASE-SEQ TO WS-CASE-SEQ-TXT.
           MOVE SPACES TO WS-CASE-DIR.
           STRING WS-WORK-ROOT DELIMITED BY SPACE
                  "/c" DELIMITED BY SIZE
                  WS-CASE-SEQ-TXT DELIMITED BY SIZE
                  INTO WS-CASE-DIR
           END-STRING.
           CALL "CBL_CREATE_DIR" USING WS-CASE-DIR
               RETURNING WS-RC
           END-CALL.
           IF WS-RC NOT = 0
               MOVE 'Y' TO WS-IO-FAIL
           ELSE
               PERFORM SET-CASE-PATHS
               PERFORM WRITE-TEXT-FILES
           END-IF.
           IF WS-IO-FAIL = 'Y'
               MOVE 251 TO WS-EXIT-CODE
           ELSE
               PERFORM RUN-LOAD
               PERFORM RUN-PROGRAM
               PERFORM RUN-DUMP
               PERFORM READ-TRANSACTIONS
               PERFORM READ-BALANCES
           END-IF.
           PERFORM REMOVE-CASE-DIR.

       SET-CASE-PATHS.
           MOVE SPACES TO WS-TCAT-PATH WS-XREF-PATH WS-ACCT-PATH
                          WS-DISC-PATH WS-TX-PATH WS-DUMP-PATH.
           STRING WS-CASE-DIR DELIMITED BY SPACE
                  "/tcatbal.txt" DELIMITED BY SIZE
                  INTO WS-TCAT-PATH
           END-STRING.
           STRING WS-CASE-DIR DELIMITED BY SPACE
                  "/cardxref.txt" DELIMITED BY SIZE
                  INTO WS-XREF-PATH
           END-STRING.
           STRING WS-CASE-DIR DELIMITED BY SPACE
                  "/acctdata.txt" DELIMITED BY SIZE
                  INTO WS-ACCT-PATH
           END-STRING.
           STRING WS-CASE-DIR DELIMITED BY SPACE
                  "/discgrp.txt" DELIMITED BY SIZE
                  INTO WS-DISC-PATH
           END-STRING.
           STRING WS-CASE-DIR DELIMITED BY SPACE
                  "/transact.dat" DELIMITED BY SIZE
                  INTO WS-TX-PATH
           END-STRING.
           STRING WS-CASE-DIR DELIMITED BY SPACE
                  "/accounts-after.txt" DELIMITED BY SIZE
                  INTO WS-DUMP-PATH
           END-STRING.

       WRITE-TEXT-FILES.
      * Amounts are written with the compiler's own sign encoding (MOVE
      * from the decoded value), never with hand-made overpunch bytes.
           OPEN OUTPUT TCAT-TXT.
           IF WS-FS NOT = "00"
               MOVE 'Y' TO WS-IO-FAIL
           ELSE
               PERFORM VARYING WS-C FROM 1 BY 1 UNTIL WS-C > 10
                   IF WS-CB-IDX(WS-C) > 0
                       MOVE ZEROS TO TRAN-CAT-BAL-RECORD
                       MOVE WS-A-ID(WS-CB-IDX(WS-C)) TO TRANCAT-ACCT-ID
                       MOVE WS-CB-TYPE(WS-C) TO TRANCAT-TYPE-CD
                       MOVE WS-CB-CAT(WS-C) TO TRANCAT-CD
                       MOVE WS-CB-BAL(WS-C) TO TRAN-CAT-BAL
                       WRITE TCAT-TXT-REC FROM TRAN-CAT-BAL-RECORD
                   ELSE
                       CONTINUE
                   END-IF
               END-PERFORM
               CLOSE TCAT-TXT
           END-IF.
           OPEN OUTPUT XREF-TXT.
           IF WS-FS NOT = "00"
               MOVE 'Y' TO WS-IO-FAIL
           ELSE
               PERFORM VARYING WS-A FROM 1 BY 1 UNTIL WS-A > 5
                   IF WS-A-ID(WS-A) > 0 AND WS-A-XREF(WS-A) = "Y"
                       MOVE SPACES TO CARD-XREF-RECORD
                       MOVE WS-A-CARD(WS-A) TO XREF-CARD-NUM
                       MOVE WS-A-ID(WS-A) TO XREF-CUST-ID
                       MOVE WS-A-ID(WS-A) TO XREF-ACCT-ID
                       WRITE XREF-TXT-REC FROM CARD-XREF-RECORD
                   ELSE
                       CONTINUE
                   END-IF
               END-PERFORM
               CLOSE XREF-TXT
           END-IF.
           OPEN OUTPUT ACCT-TXT.
           IF WS-FS NOT = "00"
               MOVE 'Y' TO WS-IO-FAIL
           ELSE
               PERFORM VARYING WS-A FROM 1 BY 1 UNTIL WS-A > 5
                   IF WS-A-ID(WS-A) > 0
                       PERFORM WRITE-ACCOUNT-LINE
                   ELSE
                       CONTINUE
                   END-IF
               END-PERFORM
               CLOSE ACCT-TXT
           END-IF.
           OPEN OUTPUT DISC-TXT.
           IF WS-FS NOT = "00"
               MOVE 'Y' TO WS-IO-FAIL
           ELSE
               PERFORM VARYING WS-R FROM 1 BY 1 UNTIL WS-R > 20
                   IF WS-RT-GROUP(WS-R) = SPACES
                       CONTINUE
                   ELSE
                       MOVE ZEROS TO DIS-GROUP-RECORD
                       MOVE WS-RT-GROUP(WS-R) TO DIS-ACCT-GROUP-ID
                       MOVE WS-RT-TYPE(WS-R) TO DIS-TRAN-TYPE-CD
                       MOVE WS-RT-CAT(WS-R) TO DIS-TRAN-CAT-CD
                       MOVE WS-RT-VALUE(WS-R) TO DIS-INT-RATE
                       WRITE DISC-TXT-REC FROM DIS-GROUP-RECORD
                   END-IF
               END-PERFORM
               CLOSE DISC-TXT
           END-IF.

       WRITE-ACCOUNT-LINE.
      * The upstream text format omits ACCT-ADDR-ZIP (10 bytes).
           MOVE SPACES TO ACCOUNT-RECORD.
           MOVE WS-A-ID(WS-A) TO ACCT-ID.
           MOVE "Y" TO ACCT-ACTIVE-STATUS.
           MOVE WS-A-BAL(WS-A) TO ACCT-CURR-BAL.
           MOVE 0 TO ACCT-CREDIT-LIMIT ACCT-CASH-CREDIT-LIMIT.
           MOVE WS-A-CREDIT(WS-A) TO ACCT-CURR-CYC-CREDIT.
           MOVE WS-A-DEBIT(WS-A) TO ACCT-CURR-CYC-DEBIT.
           MOVE WS-A-GROUP(WS-A) TO ACCT-GROUP-ID.
           MOVE SPACES TO ACCT-TXT-REC.
           MOVE ACCOUNT-RECORD(1:102) TO ACCT-TXT-REC(1:102).
           MOVE ACCOUNT-RECORD(113:188) TO ACCT-TXT-REC(103:188).
           WRITE ACCT-TXT-REC.

       RUN-LOAD.
           MOVE SPACES TO WS-COMMAND.
           STRING "TCATBALTEXT=" DELIMITED BY SIZE
                  WS-TCAT-PATH DELIMITED BY SPACE
                  " XREFTEXT=" DELIMITED BY SIZE
                  WS-XREF-PATH DELIMITED BY SPACE
                  " ACCTTEXT=" DELIMITED BY SIZE
                  WS-ACCT-PATH DELIMITED BY SPACE
                  " DISCGRPTEXT=" DELIMITED BY SIZE
                  WS-DISC-PATH DELIMITED BY SPACE
                  " TCATBALF=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/tcatbal.dat XREFFILE=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/cardxref.dat ACCTFILE=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/acctdata.dat DISCGRP=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/discgrp.dat " DELIMITED BY SIZE
                  WS-BIN-DIR DELIMITED BY SPACE
                  "/LOAD-FILES > " DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/load.log 2>&1" DELIMITED BY SIZE
                  INTO WS-COMMAND
           END-STRING.
           CALL "SYSTEM" USING WS-COMMAND RETURNING WS-RC.

       RUN-PROGRAM.
           MOVE SPACES TO WS-COMMAND.
           STRING "COB_LIBRARY_PATH=" DELIMITED BY SIZE
                  WS-BIN-DIR DELIMITED BY SPACE
                  " CARDDEMO_PARM_DATE=" DELIMITED BY SIZE
                  WS-PARM-DATE DELIMITED BY SPACE
                  " TCATBALF=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/tcatbal.dat XREFFILE=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/cardxref.dat ACCTFILE=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/acctdata.dat DISCGRP=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/discgrp.dat TRANSACT=" DELIMITED BY SIZE
                  WS-TX-PATH DELIMITED BY SPACE
                  " " DELIMITED BY SIZE
                  WS-BIN-DIR DELIMITED BY SPACE
                  "/RUN-CBACT04C > " DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/run.log 2>&1" DELIMITED BY SIZE
                  INTO WS-COMMAND
           END-STRING.
           CALL "SYSTEM" USING WS-COMMAND RETURNING WS-RC.
      * CALL "SYSTEM" returns the wait status (exit status * 256, or the
      * signal number in the low byte), not the exit status itself.
           IF WS-RC < 0
               MOVE 255 TO WS-EXIT-CODE
           ELSE
               DIVIDE WS-RC BY 256 GIVING WS-EXIT-CODE
                   REMAINDER WS-REM
               IF WS-REM = 0
                   CONTINUE
               ELSE
                   COMPUTE WS-EXIT-CODE =
                       128 + FUNCTION MOD(WS-REM, 128)
               END-IF
           END-IF.

       RUN-DUMP.
           MOVE SPACES TO WS-COMMAND.
           STRING "ACCTFILE=" DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  "/acctdata.dat " DELIMITED BY SIZE
                  WS-BIN-DIR DELIMITED BY SPACE
                  "/DUMP-ACCT > " DELIMITED BY SIZE
                  WS-DUMP-PATH DELIMITED BY SPACE
                  " 2>&1" DELIMITED BY SIZE
                  INTO WS-COMMAND
           END-STRING.
           CALL "SYSTEM" USING WS-COMMAND RETURNING WS-RC.

       READ-TRANSACTIONS.
           OPEN INPUT TX-FILE.
           IF WS-FS = "00"
               MOVE 'N' TO WS-TX-EOF
               PERFORM UNTIL WS-TX-EOF = 'Y'
                   READ TX-FILE INTO TRAN-RECORD
                       AT END
                           MOVE 'Y' TO WS-TX-EOF
                       NOT AT END
                           PERFORM KEEP-TRANSACTION
                   END-READ
               END-PERFORM
               CLOSE TX-FILE
           ELSE
               CONTINUE
           END-IF.

       KEEP-TRANSACTION.
           ADD 1 TO WS-TX-COUNT.
           IF WS-TX-COUNT > 10
               CONTINUE
           ELSE
               MOVE TRAN-ID TO WS-TX-ID(WS-TX-COUNT)
               MOVE TRAN-TYPE-CD TO WS-TX-TYPE(WS-TX-COUNT)
               MOVE TRAN-CAT-CD TO WS-TX-CAT(WS-TX-COUNT)
               MOVE TRAN-SOURCE TO WS-TX-SOURCE(WS-TX-COUNT)
               MOVE TRAN-DESC TO WS-TX-DESC(WS-TX-COUNT)
               MOVE TRAN-AMT TO WS-TX-AMT(WS-TX-COUNT)
               MOVE TRAN-CARD-NUM TO WS-TX-CARD(WS-TX-COUNT)
               MOVE TRAN-ORIG-TS TO WS-TX-ORIG(WS-TX-COUNT)
               MOVE TRAN-PROC-TS TO WS-TX-PROC(WS-TX-COUNT)
           END-IF.

       READ-BALANCES.
      * DUMP-ACCT lines: "<11 digit account id> <signed balance>".
           OPEN INPUT DUMP-TXT.
           IF WS-FS = "00"
               MOVE 'N' TO WS-DUMP-EOF
               PERFORM UNTIL WS-DUMP-EOF = 'Y'
                   READ DUMP-TXT
                       AT END
                           MOVE 'Y' TO WS-DUMP-EOF
                       NOT AT END
                           PERFORM KEEP-BALANCE
                   END-READ
               END-PERFORM
               CLOSE DUMP-TXT
           ELSE
               CONTINUE
           END-IF.

       KEEP-BALANCE.
           IF DUMP-TXT-REC(1:11) IS NUMERIC
              AND DUMP-TXT-REC(12:1) = SPACE
               MOVE DUMP-TXT-REC(1:11) TO WS-DUMP-ID
               COMPUTE WS-DUMP-BAL =
                   FUNCTION NUMVAL(DUMP-TXT-REC(13:30))
               PERFORM VARYING WS-A FROM 1 BY 1 UNTIL WS-A > 5
                   IF WS-A-ID(WS-A) = WS-DUMP-ID AND WS-DUMP-ID > 0
                       MOVE WS-DUMP-BAL TO WS-A-UPD(WS-A)
                       MOVE 'Y' TO WS-A-UPD-OK(WS-A)
                   ELSE
                       CONTINUE
                   END-IF
               END-PERFORM
           ELSE
               CONTINUE
           END-IF.

       REMOVE-CASE-DIR.
           MOVE SPACES TO WS-COMMAND.
           STRING "rm -rf " DELIMITED BY SIZE
                  WS-CASE-DIR DELIMITED BY SPACE
                  INTO WS-COMMAND
           END-STRING.
           CALL "SYSTEM" USING WS-COMMAND.

       WRITE-HEADER.
           MOVE SPACES TO OUTPUT-REC.
           MOVE 1 TO WS-OUT-PTR.
           MOVE 'Y' TO WS-FIRST-COL.
           MOVE "CASE-ID" TO WS-APP-VAL.
           PERFORM APPEND-TEXT.
           MOVE "EXIT-CODE" TO WS-APP-VAL.
           PERFORM APPEND-TEXT.
           PERFORM VARYING WS-A FROM 1 BY 1 UNTIL WS-A > 5
               MOVE WS-A TO WS-IDX
               PERFORM SET-IDX-TXT
               MOVE SPACES TO WS-APP-VAL
               STRING "UPDATED-BAL-" DELIMITED BY SIZE
                      WS-IDX-TXT(1:WS-IDX-LEN) DELIMITED BY SIZE
                      INTO WS-APP-VAL
               END-STRING
               PERFORM APPEND-TEXT
           END-PERFORM.
           MOVE "NUM-TRANSACTIONS" TO WS-APP-VAL.
           PERFORM APPEND-TEXT.
           PERFORM VARYING WS-T FROM 1 BY 1 UNTIL WS-T > 10
               MOVE WS-T TO WS-IDX
               PERFORM SET-IDX-TXT
               PERFORM HEADER-TX-COLUMNS
           END-PERFORM.
           WRITE OUTPUT-REC.

       HEADER-TX-COLUMNS.
           PERFORM VARYING WS-K FROM 1 BY 1 UNTIL WS-K > 9
               MOVE SPACES TO WS-APP-VAL
               EVALUATE WS-K
                   WHEN 1
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN) "-ID"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN 2
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN) "-TYPE"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN 3
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN) "-CAT"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN 4
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN) "-SOURCE"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN 5
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN) "-DESC"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN 6
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN) "-AMT"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN 7
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN)
                              "-CARD-NUM"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN 8
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN)
                              "-ORIG-TS"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
                   WHEN OTHER
                       STRING "TX-" WS-IDX-TXT(1:WS-IDX-LEN)
                              "-PROC-TS"
                           DELIMITED BY SIZE INTO WS-APP-VAL
                       END-STRING
               END-EVALUATE
               PERFORM APPEND-TEXT
           END-PERFORM.

       SET-IDX-TXT.
           MOVE WS-IDX TO WS-IDX-EDIT.
           IF WS-IDX-EDIT(1:1) = SPACE
               MOVE WS-IDX-EDIT(2:1) TO WS-IDX-TXT
               MOVE 1 TO WS-IDX-LEN
           ELSE
               MOVE WS-IDX-EDIT TO WS-IDX-TXT
               MOVE 2 TO WS-IDX-LEN
           END-IF.

       WRITE-OUTPUT-ROW.
           MOVE SPACES TO OUTPUT-REC.
           MOVE 1 TO WS-OUT-PTR.
           MOVE 'Y' TO WS-FIRST-COL.
           MOVE WS-CASE-ID TO WS-APP-VAL.
           PERFORM APPEND-TEXT.
           MOVE WS-EXIT-CODE TO WS-INT-EDIT.
           PERFORM APPEND-INT.
           PERFORM VARYING WS-A FROM 1 BY 1 UNTIL WS-A > 5
               IF WS-ROW-OK = 'Y' AND WS-A-UPD-OK(WS-A) = 'Y'
                   MOVE WS-A-UPD(WS-A) TO WS-NUM
                   PERFORM APPEND-NUM
               ELSE
                   MOVE SPACES TO WS-APP-VAL
                   PERFORM APPEND-TEXT
               END-IF
           END-PERFORM.
           IF WS-ROW-OK = 'Y'
               MOVE WS-TX-COUNT TO WS-INT-EDIT
               PERFORM APPEND-INT
           ELSE
               MOVE SPACES TO WS-APP-VAL
               PERFORM APPEND-TEXT
           END-IF.
           PERFORM VARYING WS-T FROM 1 BY 1 UNTIL WS-T > 10
               PERFORM APPEND-TX-FIELDS
           END-PERFORM.
           WRITE OUTPUT-REC.

       APPEND-TX-FIELDS.
           IF WS-ROW-OK = 'Y' AND WS-T <= WS-TX-COUNT
               MOVE WS-TX-ID(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
               MOVE WS-TX-TYPE(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
               MOVE WS-TX-CAT(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
               MOVE WS-TX-SOURCE(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
               MOVE WS-TX-DESC(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
               MOVE WS-TX-AMT(WS-T) TO WS-NUM
               PERFORM APPEND-NUM
               MOVE WS-TX-CARD(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
               MOVE WS-TX-ORIG(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
               MOVE WS-TX-PROC(WS-T) TO WS-APP-VAL
               PERFORM APPEND-TEXT
           ELSE
               MOVE SPACES TO WS-APP-VAL
               PERFORM VARYING WS-K FROM 1 BY 1 UNTIL WS-K > 9
                   PERFORM APPEND-TEXT
               END-PERFORM
           END-IF.

       APPEND-INT.
      * WS-INT-EDIT holds the value (Z(8)9): append without spaces.
           MOVE SPACES TO WS-APP-VAL.
           MOVE FUNCTION TRIM(WS-INT-EDIT) TO WS-APP-VAL.
           PERFORM APPEND-TEXT.

       APPEND-NUM.
      * WS-NUM as plain signed decimal, scale 2, no leading spaces.
           MOVE WS-NUM TO WS-EDIT.
           MOVE SPACES TO WS-APP-VAL.
           MOVE FUNCTION TRIM(WS-EDIT) TO WS-APP-VAL.
           PERFORM APPEND-TEXT.

       APPEND-TEXT.
      * Append "," (unless first column) and WS-APP-VAL without trailing
      * spaces. An empty value appends nothing but the comma.
           IF WS-FIRST-COL = 'Y'
               MOVE 'N' TO WS-FIRST-COL
           ELSE
               STRING "," DELIMITED BY SIZE
                   INTO OUTPUT-REC WITH POINTER WS-OUT-PTR
               END-STRING
           END-IF.
           MOVE 120 TO WS-L.
           PERFORM UNTIL WS-L = 0 OR WS-APP-VAL(WS-L:1) NOT = SPACE
               SUBTRACT 1 FROM WS-L
           END-PERFORM.
           IF WS-L > 0
               STRING WS-APP-VAL(1:WS-L) DELIMITED BY SIZE
                   INTO OUTPUT-REC WITH POINTER WS-OUT-PTR
               END-STRING
           ELSE
               CONTINUE
           END-IF.
