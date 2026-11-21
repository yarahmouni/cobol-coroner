       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOAD-FILES.
      * Loads CardDemo data from text files into indexed files
      * for GnuCOBOL execution
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
      * Input text files
           SELECT TCATBAL-TEXT ASSIGN TO TCATBALTEXT
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS TEXT-STATUS.

           SELECT XREF-TEXT ASSIGN TO XREFTEXT
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS TEXT-STATUS.

           SELECT ACCT-TEXT ASSIGN TO ACCTTEXT
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS TEXT-STATUS.

           SELECT DISCGRP-TEXT ASSIGN TO DISCGRPTEXT
                  ORGANIZATION IS LINE SEQUENTIAL
                  FILE STATUS IS TEXT-STATUS.

      * Output INDEXED files
           SELECT TCATBAL-IDX ASSIGN TO TCATBALF
                  ORGANIZATION IS INDEXED
                  ACCESS MODE  IS DYNAMIC
                  RECORD KEY   IS IDX-TCAT-KEY
                  FILE STATUS  IS IDX-STATUS.

           SELECT XREF-IDX ASSIGN TO XREFFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE  IS DYNAMIC
                  RECORD KEY   IS IDX-XREF-CARD-NUM
                  ALTERNATE RECORD KEY IS IDX-XREF-ACCT-ID
                     WITH DUPLICATES
                  FILE STATUS  IS IDX-STATUS.

           SELECT ACCT-IDX ASSIGN TO ACCTFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE  IS DYNAMIC
                  RECORD KEY   IS ACCT-ID
                  FILE STATUS  IS IDX-STATUS.

           SELECT DISCGRP-IDX ASSIGN TO DISCGRP
                  ORGANIZATION IS INDEXED
                  ACCESS MODE  IS DYNAMIC
                  RECORD KEY   IS IDX-DISCGRP-KEY
                  FILE STATUS  IS IDX-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  TCATBAL-TEXT.
       01  TEXT-TCAT-REC                PIC X(200).

       FD  XREF-TEXT.
       01  TEXT-XREF-REC                PIC X(200).

       FD  ACCT-TEXT.
       01  TEXT-ACCT-REC                PIC X(500).

       FD  DISCGRP-TEXT.
       01  TEXT-DISCGRP-REC             PIC X(200).

       FD  TCATBAL-IDX.
       01  IDX-TCAT-REC.
           05 IDX-TCAT-KEY.
              10 IDX-TRANCAT-ACCT-ID    PIC 9(11).
              10 IDX-TRANCAT-TYPE-CD    PIC X(02).
              10 IDX-TRANCAT-CD         PIC 9(04).
           05 IDX-TCAT-DATA             PIC X(33).

       FD  XREF-IDX.
       01  IDX-XREF-REC.
           05 IDX-XREF-CARD-NUM         PIC X(16).
           05 IDX-XREF-CUST-NUM         PIC 9(09).
           05 IDX-XREF-ACCT-ID          PIC 9(11).
           05 IDX-XREF-FILLER           PIC X(14).

       FD  ACCT-IDX.
       COPY CVACT01Y.

       FD  DISCGRP-IDX.
       01  IDX-DISCGRP-REC.
           05 IDX-DISCGRP-KEY.
              10 IDX-DIS-ACCT-GROUP-ID  PIC X(10).
              10 IDX-DIS-TRAN-TYPE-CD   PIC X(02).
              10 IDX-DIS-TRAN-CAT-CD    PIC 9(04).
           05 IDX-DISCGRP-DATA          PIC X(34).

       WORKING-STORAGE SECTION.
       01  TEXT-STATUS                  PIC XX.
       01  IDX-STATUS                   PIC XX.
       01  WS-EOF                       PIC X VALUE 'N'.
       01  WS-RECORD-COUNT              PIC 9(8) VALUE 0.
       01  WS-TEXT-REC                  PIC X(500).
       01  WS-I                         PIC 9(4).
       01  WS-LEN                       PIC 9(4).

       PROCEDURE DIVISION.
           DISPLAY 'Starting file load...'.

           DISPLAY 'Loading TCATBAL...'.
           MOVE 'N' TO WS-EOF.

           OPEN INPUT TCATBAL-TEXT.
           IF TEXT-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot open TCATBAL text file'
               DISPLAY 'File status: ' TEXT-STATUS
               STOP RUN
           END-IF.

           OPEN OUTPUT TCATBAL-IDX.
           IF IDX-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot create TCATBAL indexed file'
               DISPLAY 'File status: ' IDX-STATUS
               STOP RUN
           END-IF.

           PERFORM UNTIL WS-EOF = 'Y'
               READ TCATBAL-TEXT INTO WS-TEXT-REC
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       PERFORM TRIM-LINE
                       MOVE WS-TEXT-REC(1:50) TO IDX-TCAT-REC
                       WRITE IDX-TCAT-REC
                       IF IDX-STATUS NOT = '00'
                           DISPLAY 'ERROR writing TCATBAL record'
                           DISPLAY 'File status: ' IDX-STATUS
                           STOP RUN
                       END-IF
                       ADD 1 TO WS-RECORD-COUNT
               END-READ
           END-PERFORM.

           CLOSE TCATBAL-TEXT.
           CLOSE TCATBAL-IDX.
           DISPLAY 'TCATBAL loaded: ' WS-RECORD-COUNT ' records'.

           DISPLAY 'Loading XREF...'.
           MOVE ZERO TO WS-RECORD-COUNT.
           MOVE 'N' TO WS-EOF.

           OPEN INPUT XREF-TEXT.
           IF TEXT-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot open XREF text file'
               DISPLAY 'File status: ' TEXT-STATUS
               STOP RUN
           END-IF.

           OPEN OUTPUT XREF-IDX.
           IF IDX-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot create XREF indexed file'
               DISPLAY 'File status: ' IDX-STATUS
               STOP RUN
           END-IF.

           PERFORM UNTIL WS-EOF = 'Y'
               READ XREF-TEXT INTO WS-TEXT-REC
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       PERFORM TRIM-LINE
                       MOVE WS-TEXT-REC(1:50) TO IDX-XREF-REC
                       WRITE IDX-XREF-REC
                       IF IDX-STATUS NOT = '00'
                           DISPLAY 'ERROR writing XREF record'
                           DISPLAY 'File status: ' IDX-STATUS
                           STOP RUN
                       END-IF
                       ADD 1 TO WS-RECORD-COUNT
               END-READ
           END-PERFORM.

           CLOSE XREF-TEXT.
           CLOSE XREF-IDX.
           DISPLAY 'XREF loaded: ' WS-RECORD-COUNT ' records'.

           DISPLAY 'Loading ACCT...'.
           MOVE ZERO TO WS-RECORD-COUNT.
           MOVE 'N' TO WS-EOF.

           OPEN INPUT ACCT-TEXT.
           IF TEXT-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot open ACCT text file'
               DISPLAY 'File status: ' TEXT-STATUS
               STOP RUN
           END-IF.

           OPEN OUTPUT ACCT-IDX.
           IF IDX-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot create ACCT indexed file'
               DISPLAY 'File status: ' IDX-STATUS
               STOP RUN
           END-IF.

           PERFORM UNTIL WS-EOF = 'Y'
               READ ACCT-TEXT INTO WS-TEXT-REC
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       PERFORM TRIM-LINE
      * Build ACCOUNT-RECORD field by field because the upstream
      * ASCII text omits ACCT-ADDR-ZIP (10 bytes between
      * ACCT-CURR-CYC-DEBIT and ACCT-GROUP-ID)
                       MOVE WS-TEXT-REC(1:102)
                            TO ACCOUNT-RECORD(1:102)
                       MOVE SPACES TO ACCT-ADDR-ZIP
                       MOVE WS-TEXT-REC(103:188)
                            TO ACCOUNT-RECORD(113:188)
                       WRITE ACCOUNT-RECORD
                       IF IDX-STATUS NOT = '00'
                           DISPLAY 'ERROR writing ACCT record'
                           DISPLAY 'File status: ' IDX-STATUS
                           STOP RUN
                       END-IF
                       ADD 1 TO WS-RECORD-COUNT
               END-READ
           END-PERFORM.

           CLOSE ACCT-TEXT.
           CLOSE ACCT-IDX.
           DISPLAY 'ACCT loaded: ' WS-RECORD-COUNT ' records'.

           DISPLAY 'Loading DISCGRP...'.
           MOVE ZERO TO WS-RECORD-COUNT.
           MOVE 'N' TO WS-EOF.

           OPEN INPUT DISCGRP-TEXT.
           IF TEXT-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot open DISCGRP text file'
               DISPLAY 'File status: ' TEXT-STATUS
               STOP RUN
           END-IF.

           OPEN OUTPUT DISCGRP-IDX.
           IF IDX-STATUS NOT = '00'
               DISPLAY 'ERROR: Cannot create DISCGRP indexed file'
               DISPLAY 'File status: ' IDX-STATUS
               STOP RUN
           END-IF.

           PERFORM UNTIL WS-EOF = 'Y'
               READ DISCGRP-TEXT INTO WS-TEXT-REC
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       PERFORM TRIM-LINE
                       MOVE WS-TEXT-REC(1:50) TO IDX-DISCGRP-REC
                       WRITE IDX-DISCGRP-REC
                       IF IDX-STATUS NOT = '00'
                           DISPLAY 'ERROR writing DISCGRP record'
                           DISPLAY 'File status: ' IDX-STATUS
                           STOP RUN
                       END-IF
                       ADD 1 TO WS-RECORD-COUNT
               END-READ
           END-PERFORM.

           CLOSE DISCGRP-TEXT.
           CLOSE DISCGRP-IDX.
           DISPLAY 'DISCGRP loaded: ' WS-RECORD-COUNT ' records'.

           DISPLAY 'All files loaded successfully.'.
           STOP RUN.

       TRIM-LINE.
      * Remove trailing CR, LF, and spaces from text record
           MOVE 500 TO WS-LEN.
           PERFORM VARYING WS-I FROM 500 BY -1
               UNTIL WS-I < 1 OR WS-TEXT-REC(WS-I:1) NOT = X'20'
                  AND WS-TEXT-REC(WS-I:1) NOT = X'0D'
                  AND WS-TEXT-REC(WS-I:1) NOT = X'0A'
               MOVE WS-I TO WS-LEN
               IF WS-I = 1
                   EXIT PERFORM
               END-IF
           END-PERFORM.
