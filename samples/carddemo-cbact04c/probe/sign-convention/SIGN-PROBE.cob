       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIGN-PROBE.
      * Shows how GnuCOBOL 3.2 reads the upstream signed fields
      * ("0000010000{", "0000005000}", rate "00150{") under the
      * default (ASCII) sign convention and under -fsign=EBCDIC.
      * Same source, compiled twice by "make probe-sign".
      * Reading a field can rewrite its last byte, so every test
      * restores the raw text first and reads the field once.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  RAW-POS       PIC X(11).
       01  BAL-POS       REDEFINES RAW-POS PIC S9(9)V99.
       01  RAW-NEG       PIC X(11).
       01  BAL-NEG       REDEFINES RAW-NEG PIC S9(9)V99.
       01  RAW-RATE      PIC X(6).
       01  RATE          REDEFINES RAW-RATE PIC S9(4)V99.
       01  ACC           PIC S9(9)V99.
       01  INTEREST      PIC S9(9)V99.
       PROCEDURE DIVISION.
           MOVE "0000010000{" TO RAW-POS.
           DISPLAY "DISPLAY 0000010000{       " BAL-POS.
           MOVE "0000005000}" TO RAW-NEG.
           DISPLAY "DISPLAY 0000005000}       " BAL-NEG.
           MOVE "00150{" TO RAW-RATE.
           DISPLAY "DISPLAY 00150{            " RATE.
           MOVE "0000010000{" TO RAW-POS.
           MOVE 0 TO ACC.
           ADD BAL-POS TO ACC.
           DISPLAY "ADD 0000010000{ TO 0      " ACC.
           MOVE "0000005000}" TO RAW-NEG.
           MOVE 0 TO ACC.
           ADD BAL-NEG TO ACC.
           DISPLAY "ADD 0000005000} TO 0      " ACC.
           MOVE "0000010000{" TO RAW-POS.
           MOVE "00150{" TO RAW-RATE.
           COMPUTE INTEREST = (BAL-POS * RATE) / 1200.
           DISPLAY "INTEREST 0000010000{ x 00150{ / 1200 " INTEREST.
           MOVE "0000005000}" TO RAW-NEG.
           MOVE "00150{" TO RAW-RATE.
           COMPUTE INTEREST = (BAL-NEG * RATE) / 1200.
           DISPLAY "INTEREST 0000005000} x 00150{ / 1200 " INTEREST.
           STOP RUN.
