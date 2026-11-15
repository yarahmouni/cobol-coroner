      *> Trap 2: Rounding mode divergence
      *> Demonstrates COBOL ROUNDED (HALF_UP) vs truncation (DOWN)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROUNDING-CALC.

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
       01  WS-PRINCIPAL-TXT         PIC X(20).
       01  WS-RATE-TXT              PIC X(20).

      *> Parsed numeric fields
       01  IN-PRINCIPAL             PIC S9(9)V99.
       01  IN-RATE                  PIC V9(5).

      *> Output fields
       01  OUT-CASE-ID              PIC X(10).
       01  OUT-FEE1                 PIC +9(7).99.
       01  OUT-FEE2                 PIC +9(7).99.

      *> Computation fields
       01  WS-FEE1                  PIC S9(7)V99.
       01  WS-FEE2                  PIC S9(7)V99.

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

      *> Read and discard the CSV header row
       READ-HEADER.
           READ INPUT-FILE INTO WS-CSV-LINE
               AT END
                   SET WS-AT-EOF TO TRUE
               NOT AT END
                   CONTINUE
           END-READ.

      *> Write the output CSV header
       WRITE-HEADER.
           MOVE "CASE-ID,FEE1,FEE2" TO OUTPUT-LINE
           WRITE OUTPUT-LINE.

      *> Process one data record: parse, compute, write
       PROCESS-RECORD.
           INITIALIZE WS-CASE-ID-RAW
           INITIALIZE WS-PRINCIPAL-TXT
           INITIALIZE WS-RATE-TXT
           INITIALIZE IN-PRINCIPAL
           INITIALIZE IN-RATE
           INITIALIZE OUT-CASE-ID
           INITIALIZE OUT-FEE1
           INITIALIZE OUT-FEE2
           INITIALIZE WS-FEE1
           INITIALIZE WS-FEE2
           PERFORM PARSE-INPUT
           PERFORM COMPUTE-FEES
           PERFORM WRITE-OUTPUT.

      *> Parse CSV line into work fields
       PARSE-INPUT.
           MOVE ZERO TO WS-FIELD-COUNT
           UNSTRING WS-CSV-LINE DELIMITED BY ","
               INTO WS-CASE-ID-RAW
                    WS-PRINCIPAL-TXT
                    WS-RATE-TXT
               TALLYING IN WS-FIELD-COUNT
           END-UNSTRING.

           MOVE FUNCTION TRIM(WS-CASE-ID-RAW TRAILING) 
               TO OUT-CASE-ID.

           IF FUNCTION TEST-NUMVAL(WS-PRINCIPAL-TXT) = 0
               MOVE FUNCTION NUMVAL(WS-PRINCIPAL-TXT) 
                   TO IN-PRINCIPAL
           ELSE
               CONTINUE
           END-IF.

           IF FUNCTION TEST-NUMVAL(WS-RATE-TXT) = 0
               MOVE FUNCTION NUMVAL(WS-RATE-TXT) 
                   TO IN-RATE
           ELSE
               CONTINUE
           END-IF.

      *> Compute fees: FEE1 without ROUNDED (truncates), FEE2 with ROUNDED
       COMPUTE-FEES.
           COMPUTE WS-FEE1 = IN-PRINCIPAL * IN-RATE
               ON SIZE ERROR
                   MOVE ZERO TO WS-FEE1
               NOT ON SIZE ERROR
                   CONTINUE
           END-COMPUTE.
           
           COMPUTE WS-FEE2 ROUNDED = IN-PRINCIPAL * IN-RATE
               ON SIZE ERROR
                   MOVE ZERO TO WS-FEE2
               NOT ON SIZE ERROR
                   CONTINUE
           END-COMPUTE.
           
           MOVE WS-FEE1 TO OUT-FEE1.
           MOVE WS-FEE2 TO OUT-FEE2.

      *> Write output CSV row
       WRITE-OUTPUT.
           MOVE SPACES TO OUTPUT-LINE
           STRING FUNCTION TRIM(OUT-CASE-ID TRAILING) 
                  DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-FEE1 DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-FEE2 DELIMITED BY SIZE
               INTO OUTPUT-LINE
           END-STRING
           WRITE OUTPUT-LINE.
