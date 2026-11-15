      *> CREDIT-FEES.cob
      *> Synthetic credit file fee computation with eligibility check
      *> Computes fees with COBOL ROUNDED (nearest away from zero)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CREDIT-FEES.

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
       COPY INPUT-WORK-FIELDS.
       COPY OUTPUT-RECORD.
       COPY CONSTANTS.

       01  INPUT-FILE-PATH          PIC X(256).
       01  OUTPUT-FILE-PATH         PIC X(256).
       01  WS-CSV-LINE              PIC X(200).
       01  WS-ERROR-FLAG            PIC 9 VALUE 0.
       01  WS-FILE-STATUS           PIC XX.

       01  WS-EOF                   PIC X VALUE "N".
           88 WS-AT-EOF             VALUE "Y".

       01  WS-FEE-AMOUNT            PIC S9(7)V99 COMP-3.
       01  WS-DISCOUNT-RATE         PIC V9(3) COMP-3.
       01  WS-DISCOUNTED-FEE        PIC S9(7)V99 COMP-3.
       01  WS-BASE-FEE              PIC S9(7)V99 COMP-3.

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

           IF WS-ERROR-FLAG = 1
               MOVE 4 TO RETURN-CODE
           ELSE
               MOVE 0 TO RETURN-CODE
           END-IF

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
           MOVE "CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE" 
               TO OUTPUT-LINE
           WRITE OUTPUT-LINE.

      *> Process one data record: parse, validate, compute, write
       PROCESS-RECORD.
           INITIALIZE INPUT-WORK-FIELDS
           INITIALIZE INPUT-NUMERIC-FIELDS
           INITIALIZE OUTPUT-RECORD
           INITIALIZE WS-FEE-AMOUNT
           INITIALIZE WS-DISCOUNT-RATE
           INITIALIZE WS-DISCOUNTED-FEE
           INITIALIZE WS-BASE-FEE
           PERFORM PARSE-INPUT
           PERFORM VALIDATE-INPUT
           IF OUT-REASON-CODE = "E01"
               PERFORM REJECT-RECORD
           ELSE
               PERFORM COMPUTE-FEE
               IF OUT-REASON-CODE = "E01"
                   PERFORM REJECT-RECORD
               ELSE
                   PERFORM CHECK-ELIGIBILITY
                   PERFORM WRITE-OUTPUT
               END-IF
           END-IF.

      *> Parse CSV line into alphanumeric work fields
       PARSE-INPUT.
           MOVE ZERO TO WS-FIELD-COUNT
           UNSTRING WS-CSV-LINE DELIMITED BY ","
               INTO WS-IN-CASE-ID-RAW
                    WS-IN-PRINCIPAL-TXT
                    WS-IN-FEE-RATE-TXT
                    WS-IN-DURATION-TXT
                    WS-IN-SEGMENT-TXT
                    WS-IN-INCOME-TXT
               TALLYING IN WS-FIELD-COUNT
               ON OVERFLOW
                   MOVE "E01" TO OUT-REASON-CODE
               NOT ON OVERFLOW
                   CONTINUE
           END-UNSTRING.

      *> Validate field count, CASE-ID, and call numeric validation
       VALIDATE-INPUT.
           IF OUT-REASON-CODE = "E01"
               MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) 
                   TO OUT-CASE-ID
           ELSE
               IF WS-FIELD-COUNT NOT = 6
                   MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) 
                       TO OUT-CASE-ID
                   MOVE "E01" TO OUT-REASON-CODE
               ELSE
                   IF WS-IN-CASE-ID-RAW = SPACES
                       MOVE FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING) 
                           TO OUT-CASE-ID
                       MOVE "E01" TO OUT-REASON-CODE
                   ELSE
                       IF FUNCTION LENGTH(
                          FUNCTION TRIM(WS-IN-CASE-ID-RAW TRAILING)) 
                          > 10
                           MOVE FUNCTION TRIM(
                               WS-IN-CASE-ID-RAW TRAILING) 
                               TO OUT-CASE-ID
                           MOVE "E01" TO OUT-REASON-CODE
                       ELSE
                           MOVE FUNCTION TRIM(
                               WS-IN-CASE-ID-RAW TRAILING) 
                               TO OUT-CASE-ID
                           PERFORM VALIDATE-NUMERIC-FIELDS
                       END-IF
                   END-IF
               END-IF
           END-IF.

      *> Validate all numeric fields with TEST-NUMVAL and NUMVAL
       VALIDATE-NUMERIC-FIELDS.
      *> PRINCIPAL validation
           IF WS-IN-PRINCIPAL-TXT = SPACES
               MOVE "E01" TO OUT-REASON-CODE
           ELSE
               IF FUNCTION TEST-NUMVAL(WS-IN-PRINCIPAL-TXT) NOT = 0
                   MOVE "E01" TO OUT-REASON-CODE
               ELSE
                   MOVE FUNCTION NUMVAL(WS-IN-PRINCIPAL-TXT) 
                       TO IN-PRINCIPAL
                   IF IN-PRINCIPAL NOT = 
                      FUNCTION NUMVAL(WS-IN-PRINCIPAL-TXT)
                       MOVE "E01" TO OUT-REASON-CODE
                   ELSE
                       CONTINUE
                   END-IF
               END-IF
           END-IF

      *> FEE-RATE validation
           IF OUT-REASON-CODE = SPACES
               IF WS-IN-FEE-RATE-TXT = SPACES
                   MOVE "E01" TO OUT-REASON-CODE
               ELSE
                   IF FUNCTION TEST-NUMVAL(WS-IN-FEE-RATE-TXT) 
                      NOT = 0
                       MOVE "E01" TO OUT-REASON-CODE
                   ELSE
                       MOVE FUNCTION NUMVAL(WS-IN-FEE-RATE-TXT) 
                           TO IN-FEE-RATE
                       IF IN-FEE-RATE NOT = 
                          FUNCTION NUMVAL(WS-IN-FEE-RATE-TXT)
                           MOVE "E01" TO OUT-REASON-CODE
                       ELSE
                           CONTINUE
                       END-IF
                   END-IF
               END-IF
           ELSE
               CONTINUE
           END-IF

      *> DURATION-MONTHS validation
           IF OUT-REASON-CODE = SPACES
               IF WS-IN-DURATION-TXT = SPACES
                   MOVE "E01" TO OUT-REASON-CODE
               ELSE
                   IF FUNCTION TEST-NUMVAL(WS-IN-DURATION-TXT) 
                      NOT = 0
                       MOVE "E01" TO OUT-REASON-CODE
                   ELSE
                       MOVE FUNCTION NUMVAL(WS-IN-DURATION-TXT) 
                           TO IN-DURATION-MONTHS
                       IF IN-DURATION-MONTHS NOT = 
                          FUNCTION NUMVAL(WS-IN-DURATION-TXT)
                           MOVE "E01" TO OUT-REASON-CODE
                       ELSE
                           CONTINUE
                       END-IF
                   END-IF
               END-IF
           ELSE
               CONTINUE
           END-IF

      *> CUSTOMER-SEGMENT validation
           IF OUT-REASON-CODE = SPACES
               IF FUNCTION LENGTH(
                  FUNCTION TRIM(WS-IN-SEGMENT-TXT TRAILING)) > 1
                   MOVE "E01" TO OUT-REASON-CODE
               ELSE
                   MOVE WS-IN-SEGMENT-TXT TO IN-CUSTOMER-SEGMENT
               END-IF
           ELSE
               CONTINUE
           END-IF

      *> INCOME validation
           IF OUT-REASON-CODE = SPACES
               IF WS-IN-INCOME-TXT = SPACES
                   MOVE "E01" TO OUT-REASON-CODE
               ELSE
                   IF FUNCTION TEST-NUMVAL(WS-IN-INCOME-TXT) NOT = 0
                       MOVE "E01" TO OUT-REASON-CODE
                   ELSE
                       MOVE FUNCTION NUMVAL(WS-IN-INCOME-TXT) 
                           TO IN-INCOME
                       IF IN-INCOME NOT = 
                          FUNCTION NUMVAL(WS-IN-INCOME-TXT)
                           MOVE "E01" TO OUT-REASON-CODE
                       ELSE
                           CONTINUE
                       END-IF
                   END-IF
               END-IF
           ELSE
               CONTINUE
           END-IF.

      *> Compute base fee and apply segment discount
       COMPUTE-FEE.
           COMPUTE WS-BASE-FEE ROUNDED = 
               IN-PRINCIPAL * IN-FEE-RATE
               ON SIZE ERROR
                   MOVE "E01" TO OUT-REASON-CODE
                   MOVE 1 TO WS-ERROR-FLAG
               NOT ON SIZE ERROR
                   CONTINUE
           END-COMPUTE

           IF OUT-REASON-CODE NOT = "E01"
               MOVE WS-BASE-FEE TO WS-FEE-AMOUNT
               PERFORM APPLY-SEGMENT-DISCOUNT

               IF OUT-REASON-CODE NOT = "E01"
                   IF WS-DISCOUNTED-FEE > ZERO 
                      AND WS-DISCOUNTED-FEE < WS-MIN-FEE
                       MOVE WS-MIN-FEE TO WS-DISCOUNTED-FEE
                       MOVE "A01" TO OUT-REASON-CODE
                   ELSE
                       IF OUT-REASON-CODE = SPACES
                           MOVE "A00" TO OUT-REASON-CODE
                       ELSE
                           CONTINUE
                       END-IF
                   END-IF

                   MOVE WS-DISCOUNTED-FEE TO OUT-FEE-AMOUNT
               ELSE
                   CONTINUE
               END-IF
           ELSE
               CONTINUE
           END-IF.

      *> Apply discount based on customer segment
       APPLY-SEGMENT-DISCOUNT.
           EVALUATE IN-CUSTOMER-SEGMENT
               WHEN 'P'
                   MOVE 0.10 TO WS-DISCOUNT-RATE
                   COMPUTE WS-DISCOUNTED-FEE ROUNDED = 
                       WS-FEE-AMOUNT * (1 - WS-DISCOUNT-RATE)
                       ON SIZE ERROR
                           MOVE "E01" TO OUT-REASON-CODE
                           MOVE 1 TO WS-ERROR-FLAG
                       NOT ON SIZE ERROR
                           CONTINUE
                   END-COMPUTE
               WHEN 'S'
                   MOVE 0.05 TO WS-DISCOUNT-RATE
                   COMPUTE WS-DISCOUNTED-FEE ROUNDED = 
                       WS-FEE-AMOUNT * (1 - WS-DISCOUNT-RATE)
                       ON SIZE ERROR
                           MOVE "E01" TO OUT-REASON-CODE
                           MOVE 1 TO WS-ERROR-FLAG
                       NOT ON SIZE ERROR
                           CONTINUE
                   END-COMPUTE
               WHEN 'B'
                   MOVE WS-FEE-AMOUNT TO WS-DISCOUNTED-FEE
               WHEN OTHER
                   MOVE WS-FEE-AMOUNT TO WS-DISCOUNTED-FEE
           END-EVALUATE.

      *> Check income and duration eligibility rules
       CHECK-ELIGIBILITY.
           IF IN-INCOME < WS-MIN-INCOME
               MOVE "N" TO OUT-ELIGIBLE
               MOVE "R01" TO OUT-REASON-CODE
           ELSE
               IF IN-DURATION-MONTHS < WS-MIN-DURATION
                   MOVE "N" TO OUT-ELIGIBLE
                   MOVE "R02" TO OUT-REASON-CODE
               ELSE
                   MOVE "Y" TO OUT-ELIGIBLE
               END-IF
           END-IF.

      *> Handle validation or overflow errors
       REJECT-RECORD.
           MOVE 1 TO WS-ERROR-FLAG
           MOVE ZERO TO OUT-FEE-AMOUNT
           MOVE "N" TO OUT-ELIGIBLE
           PERFORM WRITE-OUTPUT.

      *> Write output record as CSV line
       WRITE-OUTPUT.
           MOVE SPACES TO OUTPUT-LINE
           STRING FUNCTION TRIM(OUT-CASE-ID TRAILING) 
                  DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-FEE-AMOUNT DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-ELIGIBLE DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-REASON-CODE DELIMITED BY SIZE
               INTO OUTPUT-LINE
           END-STRING
           WRITE OUTPUT-LINE.
