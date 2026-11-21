       IDENTIFICATION DIVISION.
       PROGRAM-ID. DUMP-ACCT.
      * Dumps account file records to text for verification
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCT-IDX ASSIGN TO ACCTFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE  IS SEQUENTIAL
                  RECORD KEY   IS ACCT-ID
                  FILE STATUS  IS IDX-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  ACCT-IDX.
       COPY CVACT01Y.

       WORKING-STORAGE SECTION.
       01  IDX-STATUS          PIC XX.
       01  REC-COUNT           PIC 9(5) VALUE 0.

       PROCEDURE DIVISION.
           OPEN INPUT ACCT-IDX.
           IF IDX-STATUS NOT = '00'
               DISPLAY 'Error opening ACCT file: ' IDX-STATUS
               STOP RUN
           END-IF.

           PERFORM UNTIL IDX-STATUS NOT = '00'
               READ ACCT-IDX
                   AT END
                       CONTINUE
                   NOT AT END
                       ADD 1 TO REC-COUNT
                       DISPLAY ACCT-ID ' ' ACCT-CURR-BAL
               END-READ
           END-PERFORM.

           CLOSE ACCT-IDX.
           DISPLAY 'Total records: ' REC-COUNT.
           STOP RUN.
