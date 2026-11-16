      *> Trap 5: REDEFINES of invalid numeric data
      *> Demonstrates GnuCOBOL low-nibble rule for invalid numeric data
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REDEFINES-INVALID.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO DYNAMIC INPUT-FILE-PATH
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.
           SELECT OUTPUT-FILE ASSIGN TO DYNAMIC OUTPUT-FILE-PATH
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-FILE-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  INPUT-FILE.
       01  INPUT-LINE               PIC X(200).

       FD  OUTPUT-FILE.
       01  OUTPUT-LINE              PIC X(200).

       WORKING-STORAGE SECTION.
       01  INPUT-FILE-PATH          PIC X(256).
       01  OUTPUT-FILE-PATH         PIC X(256).
       01  WS-CSV-LINE              PIC X(200).
       01  WS-FILE-STATUS           PIC XX.

       01  WS-EOF                   PIC X VALUE "N".
           88 WS-AT-EOF             VALUE "Y".

       01  WS-FIELD-COUNT           PIC 9 VALUE 0.

      *> Input fields (alphanumeric work fields)
       01  WS-CASE-ID-RAW           PIC X(20).
       01  WS-AMOUNT-TEXT-RAW       PIC X(20).

      *> Parsed fields
       01  IN-CASE-ID               PIC X(10).
       01  IN-AMOUNT-TEXT           PIC X(7).

      *> REDEFINES for reading invalid numeric data
       01  WS-AMOUNT-WORK.
           05 WS-AMOUNT-ALPHA       PIC X(7).
           05 WS-AMOUNT-NUMERIC REDEFINES WS-AMOUNT-ALPHA
                                    PIC 9(5)V99.

      *> Computation field
       01  WS-FIXED-FEE             PIC 9V99 VALUE 1.00.
       01  WS-COMPUTED              PIC S9(7)V99.

      *> Output fields
       01  OUT-CASE-ID              PIC X(10).
       01  OUT-AMOUNT               PIC +9(7).99.
       01  OUT-NUMERIC-OK           PIC X VALUE "N".

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           ACCEPT INPUT-FILE-PATH FROM ENVIRONMENT "INPUT_FILE"
           ACCEPT OUTPUT-FILE-PATH FROM ENVIRONMENT "OUTPUT_FILE"

           IF INPUT-FILE-PATH = SPACES OR OUTPUT-FILE-PATH = SPACES
               DISPLAY "ERROR: INPUT_FILE or OUTPUT_FILE not set"
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF

           OPEN INPUT INPUT-FILE
           IF WS-FILE-STATUS NOT = "00"
               DISPLAY "ERROR: Cannot open input file " 
                   INPUT-FILE-PATH
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF

           OPEN OUTPUT OUTPUT-FILE
           IF WS-FILE-STATUS NOT = "00"
               DISPLAY "ERROR: Cannot open output file " 
                   OUTPUT-FILE-PATH
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF

           PERFORM READ-HEADER
           PERFORM WRITE-HEADER

      *> Process records
           PERFORM UNTIL WS-AT-EOF
               READ INPUT-FILE INTO WS-CSV-LINE
                   AT END
                       SET WS-AT-EOF TO TRUE
                   NOT AT END
                       PERFORM PROCESS-RECORD
               END-READ
           END-PERFORM

           CLOSE INPUT-FILE
           CLOSE OUTPUT-FILE
           MOVE 0 TO RETURN-CODE
           STOP RUN.

       READ-HEADER.
           READ INPUT-FILE INTO WS-CSV-LINE
               AT END
                   SET WS-AT-EOF TO TRUE
               NOT AT END
                   CONTINUE
           END-READ.

       WRITE-HEADER.
           MOVE "CASE-ID,AMOUNT,NUMERIC-OK" TO OUTPUT-LINE
           WRITE OUTPUT-LINE.

       PROCESS-RECORD.
           INITIALIZE WS-CASE-ID-RAW
           INITIALIZE WS-AMOUNT-TEXT-RAW
           INITIALIZE IN-CASE-ID
           INITIALIZE IN-AMOUNT-TEXT
           INITIALIZE WS-AMOUNT-WORK
           MOVE "N" TO OUT-NUMERIC-OK

      *> Parse CSV: CASE-ID,AMOUNT-TEXT
           MOVE 0 TO WS-FIELD-COUNT
           UNSTRING WS-CSV-LINE DELIMITED BY ","
               INTO WS-CASE-ID-RAW
                    WS-AMOUNT-TEXT-RAW
               TALLYING WS-FIELD-COUNT
           END-UNSTRING

      *> Validate field count
           IF WS-FIELD-COUNT NOT = 2
               DISPLAY "ERROR: Invalid CSV row (expected 2 fields)"
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF

      *> Copy and trim
           MOVE FUNCTION TRIM(WS-CASE-ID-RAW TRAILING) TO IN-CASE-ID
           MOVE FUNCTION TRIM(WS-AMOUNT-TEXT-RAW TRAILING)
               TO IN-AMOUNT-TEXT

      *> Validate CASE-ID
           IF IN-CASE-ID = SPACES
               DISPLAY "ERROR: CASE-ID is empty"
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF

      *> Move the potentially invalid text to the REDEFINES field
           MOVE IN-AMOUNT-TEXT TO WS-AMOUNT-ALPHA

      *> Check if the redefined numeric field passes IS NUMERIC
           IF WS-AMOUNT-NUMERIC IS NUMERIC
               MOVE "Y" TO OUT-NUMERIC-OK
           ELSE
               MOVE "N" TO OUT-NUMERIC-OK
           END-IF

      *> Compute using the redefined numeric value
      *> GnuCOBOL uses the low nibble of each byte as the digit
           COMPUTE WS-COMPUTED = WS-AMOUNT-NUMERIC + WS-FIXED-FEE

      *> Format output
           MOVE IN-CASE-ID TO OUT-CASE-ID
           MOVE WS-COMPUTED TO OUT-AMOUNT

      *> Build output CSV
           INITIALIZE OUTPUT-LINE
           STRING OUT-CASE-ID DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-AMOUNT DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-NUMERIC-OK DELIMITED BY SIZE
               INTO OUTPUT-LINE
           END-STRING

           WRITE OUTPUT-LINE.
