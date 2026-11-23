      *> Trap 6: FUNCTION MOD with a negative day offset
      *> A rotation slot (weekday slot 0 to 6) is computed from a signed
      *> day offset relative to a reference date. A negative offset
      *> means days before the reference date.
      *> FUNCTION MOD returns a result with the sign of the divisor,
      *> so MOD(-11, 7) is 3. Java % keeps the sign of the dividend.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROTATION-SLOT.

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
       01  WS-OFFSET-RAW            PIC X(20).

      *> Parsed fields
       01  IN-CASE-ID               PIC X(10).
       01  WS-OFFSET-WIDE           PIC S9(9).
       01  WS-OFFSET                PIC S9(3).

      *> Rotation slot, 0 to 6
       01  WS-SLOT                  PIC 9.

      *> Output fields
       01  OUT-CASE-ID              PIC X(10).
       01  OUT-OFFSET               PIC +9(3).
       01  OUT-SLOT                 PIC +9.

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
           MOVE "CASE-ID,DAY-OFFSET,SLOT" TO OUTPUT-LINE
           WRITE OUTPUT-LINE.

       PROCESS-RECORD.
           INITIALIZE WS-CASE-ID-RAW
           INITIALIZE WS-OFFSET-RAW
           INITIALIZE IN-CASE-ID

      *> Parse CSV: CASE-ID,DAY-OFFSET
           MOVE 0 TO WS-FIELD-COUNT
           UNSTRING WS-CSV-LINE DELIMITED BY ","
               INTO WS-CASE-ID-RAW
                    WS-OFFSET-RAW
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

           MOVE FUNCTION TRIM(WS-CASE-ID-RAW TRAILING) TO IN-CASE-ID

      *> Validate CASE-ID
           IF IN-CASE-ID = SPACES
               DISPLAY "ERROR: CASE-ID is empty"
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF

      *> Validate the offset text
           IF FUNCTION TEST-NUMVAL(WS-OFFSET-RAW) NOT = 0
               DISPLAY "ERROR: DAY-OFFSET is not a number"
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF

      *> Validate the offset range, so that the move below is exact
           COMPUTE WS-OFFSET-WIDE = FUNCTION NUMVAL(WS-OFFSET-RAW)
           IF WS-OFFSET-WIDE > 999 OR WS-OFFSET-WIDE < -999
               DISPLAY "ERROR: DAY-OFFSET out of range"
                   UPON SYSERR
               MOVE 16 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF
           MOVE WS-OFFSET-WIDE TO WS-OFFSET

      *> Rotation slot: MOD takes the sign of the divisor
           COMPUTE WS-SLOT = FUNCTION MOD(WS-OFFSET, 7)

      *> Format output
           MOVE IN-CASE-ID TO OUT-CASE-ID
           MOVE WS-OFFSET TO OUT-OFFSET
           MOVE WS-SLOT TO OUT-SLOT

      *> Build output CSV
           INITIALIZE OUTPUT-LINE
           STRING OUT-CASE-ID DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-OFFSET DELIMITED BY SIZE
                  "," DELIMITED BY SIZE
                  OUT-SLOT DELIMITED BY SIZE
               INTO OUTPUT-LINE
           END-STRING

           WRITE OUTPUT-LINE.
