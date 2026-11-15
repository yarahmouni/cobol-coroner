       IDENTIFICATION DIVISION.
       PROGRAM-ID. MATCH-MERGE.
      *>
      *> Trap 1: EBCDIC vs ASCII collating order.
      *> Demonstrates sequential match against a branch table in EBCDIC order.
      *> Java port with ASCII comparison mismatches branches.
      *>
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           ALPHABET EBC IS EBCDIC.
       OBJECT-COMPUTER.
           PROGRAM COLLATING SEQUENCE IS EBC.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO INPUT-FILE-PATH
               ORGANIZATION LINE SEQUENTIAL
               FILE STATUS IS INPUT-FILE-STATUS.
           SELECT OUTPUT-FILE ASSIGN TO OUTPUT-FILE-PATH
               ORGANIZATION LINE SEQUENTIAL
               FILE STATUS IS OUTPUT-FILE-STATUS.
           SELECT SORT-WORK ASSIGN TO "SORTWORK".
       DATA DIVISION.
       FILE SECTION.
       FD INPUT-FILE.
       01 INPUT-RECORD             PIC X(200).
       FD OUTPUT-FILE.
       01 OUTPUT-RECORD            PIC X(200).
       SD SORT-WORK.
       01 SORT-RECORD.
          05 SORT-CASE-ID          PIC X(10).
          05 SORT-BRANCH           PIC X(3).
          05 SORT-AMOUNT           PIC S9(7)V99.
       WORKING-STORAGE SECTION.
       01 INPUT-FILE-PATH          PIC X(200).
       01 OUTPUT-FILE-PATH         PIC X(200).
       01 INPUT-FILE-STATUS        PIC X(2).
       01 OUTPUT-FILE-STATUS       PIC X(2).
       01 IN-CASE-ID               PIC X(10).
       01 IN-BRANCH                PIC X(3).
       01 IN-AMOUNT                PIC X(12).
       01 CURRENT-CASE-ID          PIC X(10).
       01 PREV-CASE-ID             PIC X(10).
       01 BRANCH-TABLE.
          05 BRANCH-ENTRY OCCURS 10 TIMES.
             10 TABLE-CODE         PIC X(3).
             10 TABLE-SUBTOTAL     PIC S9(9)V99.
       01 SUSP-SUBTOTAL            PIC S9(9)V99.
       01 CASE-TOTAL               PIC S9(9)V99.
       01 TABLE-INDEX              PIC 99.
       01 TXN-BRANCH               PIC X(3).
       01 TXN-AMOUNT               PIC S9(7)V99.
       01 OUTPUT-LINE              PIC X(200).
       01 EOF-SW                   PIC 9 VALUE 0.
          88 EOF                   VALUE 1.
       01 OUTPUT-PARTS.
          05 OUT-CASE-ID           PIC X(10).
          05 OUT-COMMA-1           PIC X VALUE ",".
          05 OUT-BRANCH            PIC X(5).
          05 OUT-COMMA-2           PIC X VALUE ",".
          05 OUT-SUBTOTAL          PIC +9(7).99.
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           ACCEPT INPUT-FILE-PATH FROM ENVIRONMENT "INPUT_FILE"
           ACCEPT OUTPUT-FILE-PATH FROM ENVIRONMENT "OUTPUT_FILE"
           
           IF INPUT-FILE-PATH = SPACES OR INPUT-FILE-PATH = LOW-VALUES
              MOVE "input.csv" TO INPUT-FILE-PATH
           ELSE
              CONTINUE
           END-IF
           
           IF OUTPUT-FILE-PATH = SPACES OR OUTPUT-FILE-PATH = LOW-VALUES
              MOVE "output.csv" TO OUTPUT-FILE-PATH
           ELSE
              CONTINUE
           END-IF
           
           MOVE "A01" TO TABLE-CODE(1)
           MOVE "B02" TO TABLE-CODE(2)
           MOVE "C03" TO TABLE-CODE(3)
           MOVE "D04" TO TABLE-CODE(4)
           MOVE "E05" TO TABLE-CODE(5)
           MOVE "F06" TO TABLE-CODE(6)
           MOVE "Z99" TO TABLE-CODE(7)
           MOVE "001" TO TABLE-CODE(8)
           MOVE "9ZZ" TO TABLE-CODE(9)
           MOVE SPACES TO TABLE-CODE(10)
           
           SORT SORT-WORK
               ASCENDING KEY SORT-CASE-ID
               ASCENDING KEY SORT-BRANCH
               COLLATING SEQUENCE IS EBC
               INPUT PROCEDURE IS READ-INPUT-SKIP-HEADER
               OUTPUT PROCEDURE IS PROCESS-SORTED-DATA
           
           STOP RUN.
       
       READ-INPUT-SKIP-HEADER.
           OPEN INPUT INPUT-FILE
           IF INPUT-FILE-STATUS NOT = "00"
              DISPLAY "ERROR: Cannot open input file" UPON SYSERR
              MOVE 2 TO RETURN-CODE
              STOP RUN
           ELSE
              CONTINUE
           END-IF
           
           READ INPUT-FILE
           IF INPUT-FILE-STATUS NOT = "00" 
              AND INPUT-FILE-STATUS NOT = "10"
              DISPLAY "ERROR: Cannot read header" UPON SYSERR
              MOVE 2 TO RETURN-CODE
              STOP RUN
           ELSE
              CONTINUE
           END-IF
           
           PERFORM UNTIL INPUT-FILE-STATUS = "10"
              READ INPUT-FILE
              IF INPUT-FILE-STATUS = "00"
                 UNSTRING INPUT-RECORD DELIMITED BY ","
                    INTO IN-CASE-ID, IN-BRANCH, IN-AMOUNT
                 END-UNSTRING
                 MOVE IN-CASE-ID TO SORT-CASE-ID
                 MOVE IN-BRANCH TO SORT-BRANCH
                 MOVE FUNCTION NUMVAL(IN-AMOUNT) TO SORT-AMOUNT
                 RELEASE SORT-RECORD
              ELSE
                 IF INPUT-FILE-STATUS NOT = "10"
                    DISPLAY "ERROR: Read error" UPON SYSERR
                    MOVE 2 TO RETURN-CODE
                    STOP RUN
                 ELSE
                    CONTINUE
                 END-IF
              END-IF
           END-PERFORM
           
           CLOSE INPUT-FILE.
       
       PROCESS-SORTED-DATA.
           OPEN OUTPUT OUTPUT-FILE
           IF OUTPUT-FILE-STATUS NOT = "00"
              DISPLAY "ERROR: Cannot open output file" UPON SYSERR
              MOVE 2 TO RETURN-CODE
              STOP RUN
           ELSE
              CONTINUE
           END-IF
           
           MOVE "CASE-ID,BRANCH,SUBTOTAL" TO OUTPUT-RECORD
           WRITE OUTPUT-RECORD
           
           MOVE SPACES TO PREV-CASE-ID
           
           RETURN SORT-WORK AT END SET EOF TO TRUE END-RETURN
           PERFORM UNTIL EOF
              MOVE SORT-CASE-ID TO CURRENT-CASE-ID
              MOVE SORT-BRANCH TO TXN-BRANCH
              MOVE SORT-AMOUNT TO TXN-AMOUNT
              
              IF CURRENT-CASE-ID NOT = PREV-CASE-ID
                 IF PREV-CASE-ID NOT = SPACES
                    PERFORM WRITE-CASE-RESULTS
                 ELSE
                    CONTINUE
                 END-IF
                 PERFORM INITIALIZE-CASE-TOTALS
                 MOVE CURRENT-CASE-ID TO PREV-CASE-ID
              ELSE
                 CONTINUE
              END-IF
              
              PERFORM BALANCE-LINE
              
              RETURN SORT-WORK AT END SET EOF TO TRUE END-RETURN
           END-PERFORM
           
           IF PREV-CASE-ID NOT = SPACES
              PERFORM WRITE-CASE-RESULTS
           ELSE
              CONTINUE
           END-IF
           
           CLOSE OUTPUT-FILE.
       
       INITIALIZE-CASE-TOTALS.
           MOVE ZERO TO TABLE-SUBTOTAL(1)
           MOVE ZERO TO TABLE-SUBTOTAL(2)
           MOVE ZERO TO TABLE-SUBTOTAL(3)
           MOVE ZERO TO TABLE-SUBTOTAL(4)
           MOVE ZERO TO TABLE-SUBTOTAL(5)
           MOVE ZERO TO TABLE-SUBTOTAL(6)
           MOVE ZERO TO TABLE-SUBTOTAL(7)
           MOVE ZERO TO TABLE-SUBTOTAL(8)
           MOVE ZERO TO TABLE-SUBTOTAL(9)
           MOVE ZERO TO SUSP-SUBTOTAL
           MOVE ZERO TO CASE-TOTAL.
       
       BALANCE-LINE.
           MOVE 1 TO TABLE-INDEX
           PERFORM UNTIL TABLE-INDEX > 9
              IF TABLE-CODE(TABLE-INDEX) < TXN-BRANCH
                 ADD 1 TO TABLE-INDEX
              ELSE
                 IF TABLE-CODE(TABLE-INDEX) = TXN-BRANCH
                    ADD TXN-AMOUNT TO TABLE-SUBTOTAL(TABLE-INDEX)
                    ADD TXN-AMOUNT TO CASE-TOTAL
                    MOVE 10 TO TABLE-INDEX
                 ELSE
                    ADD TXN-AMOUNT TO SUSP-SUBTOTAL
                    ADD TXN-AMOUNT TO CASE-TOTAL
                    MOVE 10 TO TABLE-INDEX
                 END-IF
              END-IF
           END-PERFORM
           IF TABLE-INDEX = 10
              CONTINUE
           ELSE
              ADD TXN-AMOUNT TO SUSP-SUBTOTAL
              ADD TXN-AMOUNT TO CASE-TOTAL
           END-IF.
       
       WRITE-CASE-RESULTS.
           PERFORM VARYING TABLE-INDEX FROM 1 BY 1 UNTIL TABLE-INDEX > 9
              IF TABLE-SUBTOTAL(TABLE-INDEX) NOT = ZERO
                 MOVE FUNCTION TRIM(PREV-CASE-ID, TRAILING)
                    TO OUT-CASE-ID
                 MOVE FUNCTION TRIM(TABLE-CODE(TABLE-INDEX), TRAILING)
                    TO OUT-BRANCH
                 MOVE TABLE-SUBTOTAL(TABLE-INDEX) TO OUT-SUBTOTAL
                 WRITE OUTPUT-RECORD FROM OUTPUT-PARTS
              ELSE
                 CONTINUE
              END-IF
           END-PERFORM
           IF SUSP-SUBTOTAL NOT = ZERO
              MOVE FUNCTION TRIM(PREV-CASE-ID, TRAILING) TO OUT-CASE-ID
              MOVE "SUSP" TO OUT-BRANCH
              MOVE SUSP-SUBTOTAL TO OUT-SUBTOTAL
              WRITE OUTPUT-RECORD FROM OUTPUT-PARTS
           ELSE
              CONTINUE
           END-IF
           MOVE FUNCTION TRIM(PREV-CASE-ID, TRAILING) TO OUT-CASE-ID
           MOVE "TOTAL" TO OUT-BRANCH
           MOVE CASE-TOTAL TO OUT-SUBTOTAL
           WRITE OUTPUT-RECORD FROM OUTPUT-PARTS.
