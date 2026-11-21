      ******************************************************************
      * Program     : RUN-CBACT04C.CBL
      * Application : CardDemo (COBOL Coroner audit sample)
      * Type        : BATCH COBOL Driver Program
      * Function    : Driver added for the COBOL Coroner audit of
      *               CardDemo CBACT04C. Calls the unchanged CBACT04C
      *               with PARM-DATE from an environment variable.
      * License     : Apache-2.0, as the rest of this repository
      *               (see the repository LICENSE).
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    RUN-CBACT04C.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  EXTERNAL-PARMS.
           05  PARM-LENGTH         PIC S9(04) COMP VALUE 10.
           05  PARM-DATE           PIC X(10).
      *
       PROCEDURE DIVISION.
           ACCEPT PARM-DATE FROM ENVIRONMENT 'CARDDEMO_PARM_DATE'.
           CALL 'CBACT04C' USING EXTERNAL-PARMS.
           STOP RUN.
