      *> INPUT-WORK-FIELDS.cpy
      *> Alphanumeric work fields for CSV parsing and validation
       01  INPUT-WORK-FIELDS.
           05  WS-IN-CASE-ID-RAW        PIC X(20).
           05  WS-IN-PRINCIPAL-TXT      PIC X(20).
           05  WS-IN-FEE-RATE-TXT       PIC X(20).
           05  WS-IN-DURATION-TXT       PIC X(20).
           05  WS-IN-SEGMENT-TXT        PIC X(20).
           05  WS-IN-INCOME-TXT         PIC X(20).
           05  WS-FIELD-COUNT           PIC 9 VALUE 0.

       01  INPUT-NUMERIC-FIELDS.
           05  IN-PRINCIPAL             PIC S9(9)V99.
           05  IN-FEE-RATE              PIC V9(5).
           05  IN-DURATION-MONTHS       PIC 9(3).
           05  IN-CUSTOMER-SEGMENT      PIC X(1).
           05  IN-INCOME                PIC 9(9)V99.
