       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRACE-TWO-SOURCE.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COUNTER           PIC 9(3) VALUE 0.
       
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "Start main".
           PERFORM HELPER-PARA.
           DISPLAY "End main".
           DISPLAY "Final counter: " WS-COUNTER.
           STOP RUN.
           
       HELPER-PARA.
           COPY HELPER.
