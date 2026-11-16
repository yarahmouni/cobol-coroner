       IDENTIFICATION DIVISION.
       PROGRAM-ID. COMP3-SIGN.
      
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO INPUT_FILE
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS INPUT-STATUS.
           SELECT OUTPUT-FILE ASSIGN TO OUTPUT_FILE
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS OUTPUT-STATUS.
      
       DATA DIVISION.
       FILE SECTION.
       FD INPUT-FILE.
       01 INPUT-RECORD            PIC X(200).
      
       FD OUTPUT-FILE.
       01 OUTPUT-RECORD            PIC X(200).
      
       WORKING-STORAGE SECTION.
       01 INPUT-STATUS             PIC XX.
       01 OUTPUT-STATUS            PIC XX.
       01 EOF-SWITCH               PIC X VALUE 'N'.
       01 FIRST-RECORD             PIC X VALUE 'Y'.
       
       01 IN-CASE-ID              PIC X(10).
       01 IN-HEX-VALUE            PIC X(10).
       
       01 HEADER-LINE.
          05 FILLER               PIC X(10) VALUE 'CASE-ID'.
          05 FILLER               PIC X VALUE ','.
          05 FILLER               PIC X(13) VALUE 'DECODED-VALUE'.
       01 OUTPUT-LINE.
          05 OUT-CASE-ID          PIC X(10).
       
       01 HEX-BYTES                PIC X(5).
       01 COMP3-VALUE REDEFINES HEX-BYTES.
          05 PACKED-FIELD         PIC S9(7)V99 COMP-3.
       
       01 FORMATTED-VALUE.
          05 SIGN-CHAR            PIC X.
          05 INT-PART             PIC 9(7).
          05 FILLER               PIC X VALUE '.'.
          05 DEC-PART             PIC 99.
       
       01 WORK-VALUE              PIC S9(7)V99.
       01 ABS-VALUE               PIC 9(7)V99.
       01 INT-WORK                PIC 9(7).
       01 DEC-WORK                PIC 99.
      
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           OPEN INPUT INPUT-FILE
           OPEN OUTPUT OUTPUT-FILE
           
           IF INPUT-STATUS NOT = '00' OR OUTPUT-STATUS NOT = '00'
               DISPLAY 'Error opening files'
               MOVE 1 TO RETURN-CODE
               STOP RUN
           ELSE
               CONTINUE
           END-IF
           
           WRITE OUTPUT-RECORD FROM HEADER-LINE
           
           PERFORM READ-INPUT
           PERFORM PROCESS-RECORDS UNTIL EOF-SWITCH = 'Y'
           
           CLOSE INPUT-FILE
           CLOSE OUTPUT-FILE
           MOVE 0 TO RETURN-CODE
           STOP RUN.
      
       READ-INPUT.
           READ INPUT-FILE
               AT END MOVE 'Y' TO EOF-SWITCH
               NOT AT END
                   IF FIRST-RECORD = 'Y'
                       MOVE 'N' TO FIRST-RECORD
                       PERFORM READ-INPUT
                   ELSE
                       CONTINUE
                   END-IF
           END-READ.
      
       PROCESS-RECORDS.
           IF EOF-SWITCH = 'N'
               PERFORM PARSE-INPUT
               PERFORM DECODE-HEX
               PERFORM WRITE-OUTPUT
               PERFORM READ-INPUT
           ELSE
               CONTINUE
           END-IF.
       
       PARSE-INPUT.
           UNSTRING INPUT-RECORD DELIMITED BY ','
               INTO IN-CASE-ID, IN-HEX-VALUE
           END-UNSTRING.
      
       DECODE-HEX.
           MOVE FUNCTION HEX-TO-CHAR(IN-HEX-VALUE) TO HEX-BYTES
           MOVE IN-CASE-ID TO OUT-CASE-ID
           MOVE PACKED-FIELD TO WORK-VALUE
           
           IF WORK-VALUE >= 0
               MOVE '+' TO SIGN-CHAR
               MOVE WORK-VALUE TO ABS-VALUE
           ELSE
               MOVE '-' TO SIGN-CHAR
               COMPUTE ABS-VALUE = WORK-VALUE * -1
           END-IF
           
           COMPUTE INT-WORK = FUNCTION INTEGER(ABS-VALUE)
           COMPUTE DEC-WORK ROUNDED = (ABS-VALUE - INT-WORK) * 100
           MOVE INT-WORK TO INT-PART
           MOVE DEC-WORK TO DEC-PART.
      
       WRITE-OUTPUT.
           MOVE SPACES TO OUTPUT-RECORD
           STRING OUT-CASE-ID DELIMITED BY SIZE
                  ',' DELIMITED BY SIZE
                  SIGN-CHAR DELIMITED BY SIZE
                  INT-PART DELIMITED BY SIZE
                  '.' DELIMITED BY SIZE
                  DEC-PART DELIMITED BY SIZE
                  INTO OUTPUT-RECORD
           END-STRING
           WRITE OUTPUT-RECORD.
