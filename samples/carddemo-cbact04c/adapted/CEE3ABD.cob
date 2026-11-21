       IDENTIFICATION DIVISION.
       PROGRAM-ID. CEE3ABD.
      *****************************************************************
      * Stub replacing z/OS Language Environment service CEE3ABD.
      * DISPLAYs the abend code and STOPs RUN with RETURN-CODE.
      *****************************************************************
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ABEND-CODE-DISPLAY     PIC Z(8)9.
       
       LINKAGE SECTION.
       01  ABCODE                    PIC S9(9) BINARY.
       01  TIMING                    PIC S9(9) BINARY.
       
       PROCEDURE DIVISION USING ABCODE TIMING.
           MOVE ABCODE TO WS-ABEND-CODE-DISPLAY
           DISPLAY 'CEE3ABD ABEND CODE ' WS-ABEND-CODE-DISPLAY
           MOVE ABCODE TO RETURN-CODE
           STOP RUN.
