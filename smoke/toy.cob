       IDENTIFICATION DIVISION.
       PROGRAM-ID. TOY.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TEST-VALUE    PIC 9 VALUE 1.
       
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           IF WS-TEST-VALUE = 1
               DISPLAY "BRANCH A: TEST VALUE IS 1"
           ELSE
               DISPLAY "BRANCH B: TEST VALUE IS NOT 1"
           END-IF.
           
           MOVE 0 TO RETURN-CODE.
           STOP RUN.
