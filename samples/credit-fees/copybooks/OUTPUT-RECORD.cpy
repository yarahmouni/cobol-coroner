      *> OUTPUT-RECORD.cpy
      *> Output record structure for CSV writing
       01  OUTPUT-RECORD.
           05  OUT-CASE-ID              PIC X(10).
           05  OUT-FEE-AMOUNT           PIC +9(7).99.
           05  OUT-ELIGIBLE             PIC X(1).
           05  OUT-REASON-CODE          PIC X(3).
