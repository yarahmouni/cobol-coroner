      *> ZONED-OVERPUNCH.cob: Read zoned decimal with EBCDIC overpunch
      *> convention (requires -fsign=EBCDIC).
      *> Input: CASE-ID, ZONED-VALUE (9 characters, text form of PIC
      *> S9(7)V99 zoned field with EBCDIC overpunch sign in last char).
      *> Output: CASE-ID, DECODED-VALUE (edited as +9(7).99).
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ZONED-OVERPUNCH.
       
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO DYNAMIC INPUT-FILE-NAME
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS INPUT-STATUS.
           SELECT OUTPUT-FILE ASSIGN TO DYNAMIC OUTPUT-FILE-NAME
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS OUTPUT-STATUS.
       
       DATA DIVISION.
       FILE SECTION.
       FD  INPUT-FILE.
       01  INPUT-RECORD.
           05  INPUT-LINE          PIC X(200).
       
       FD  OUTPUT-FILE.
       01  OUTPUT-RECORD           PIC X(200).
       
       WORKING-STORAGE SECTION.
       01  INPUT-FILE-NAME         PIC X(256).
       01  OUTPUT-FILE-NAME        PIC X(256).
       01  INPUT-STATUS            PIC XX.
       01  OUTPUT-STATUS           PIC XX.
       01  EOF-SWITCH              PIC 9 VALUE 0.
       01  HEADER-SWITCH           PIC 9 VALUE 0.
       
      *> CSV line buffer
       01  WS-CSV-LINE             PIC X(200).
       
      *> Input fields from CSV
       01  IN-CASE-ID              PIC X(20).
       01  IN-ZONED-VALUE          PIC X(20).
       
      *> Working fields
       01  ZONED-TEXT              PIC X(9).
       01  ZONED-FIELD             REDEFINES ZONED-TEXT
                                   PIC S9(7)V99.
       01  DECODED-VALUE           PIC +9(7).99.
       
      *> Output line construction
       01  OUTPUT-LINE             PIC X(200).
       
       01  FIELD-COUNT             PIC 9.
       
       PROCEDURE DIVISION.
       MAIN-PROCEDURE.
           ACCEPT INPUT-FILE-NAME FROM ENVIRONMENT "INPUT_FILE"
           ACCEPT OUTPUT-FILE-NAME FROM ENVIRONMENT "OUTPUT_FILE"
           
           OPEN INPUT INPUT-FILE
           OPEN OUTPUT OUTPUT-FILE
           
           IF INPUT-STATUS NOT = "00" THEN
               DISPLAY "Error opening input file"
               STOP RUN
           END-IF
           
           IF OUTPUT-STATUS NOT = "00" THEN
               DISPLAY "Error opening output file"
               STOP RUN
           END-IF
           
           PERFORM READ-HEADER
           PERFORM WRITE-HEADER
           PERFORM PROCESS-RECORDS UNTIL EOF-SWITCH = 1
           
           CLOSE INPUT-FILE
           CLOSE OUTPUT-FILE
           STOP RUN.
       
       READ-HEADER.
           READ INPUT-FILE INTO WS-CSV-LINE
               AT END
                   MOVE 1 TO EOF-SWITCH
           END-READ
           MOVE 1 TO HEADER-SWITCH.
       
       WRITE-HEADER.
           MOVE "CASE-ID,DECODED-VALUE" TO OUTPUT-RECORD
           WRITE OUTPUT-RECORD.
       
       PROCESS-RECORDS.
           READ INPUT-FILE INTO WS-CSV-LINE
               AT END
                   MOVE 1 TO EOF-SWITCH
               NOT AT END
                   PERFORM PARSE-CSV-LINE
                   PERFORM DECODE-ZONED
                   PERFORM WRITE-OUTPUT
           END-READ.
       
       PARSE-CSV-LINE.
           INITIALIZE IN-CASE-ID
           INITIALIZE IN-ZONED-VALUE
           MOVE 0 TO FIELD-COUNT
           
           UNSTRING WS-CSV-LINE DELIMITED BY ","
               INTO IN-CASE-ID
                    IN-ZONED-VALUE
               TALLYING IN FIELD-COUNT
           END-UNSTRING.
       
       DECODE-ZONED.
      *> Move the zoned text (9 characters) to ZONED-TEXT
      *> which is redefined as PIC S9(7)V99.
      *> The EBCDIC overpunch convention in the last character
      *> will be interpreted by GnuCOBOL compiled with -fsign=EBCDIC.
           MOVE IN-ZONED-VALUE(1:9) TO ZONED-TEXT
           MOVE ZONED-FIELD TO DECODED-VALUE.
       
       WRITE-OUTPUT.
           INITIALIZE OUTPUT-LINE
           STRING
               FUNCTION TRIM(IN-CASE-ID TRAILING) DELIMITED BY SIZE
               "," DELIMITED BY SIZE
               DECODED-VALUE DELIMITED BY SIZE
               INTO OUTPUT-LINE
           END-STRING
           
           WRITE OUTPUT-RECORD FROM OUTPUT-LINE.
