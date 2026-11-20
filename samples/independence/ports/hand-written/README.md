# Hand-written port slot

This slot is reserved for a Java port of `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob` written by a person without AI assistance.

The operator and Kiro are language models and do not write code in this slot.

The independence table shows this slot as "pending" until a person provides a hand-written port.

## What would go here

If provided, the hand-written port would follow the same isolation rules as the claude and kiro ports:

- Read only: MATCH-MERGE.cob, copybooks/, schema.json, fixtures/, and coroner/run/__init__.py (for the calling convention)
- Not read: existing Java ports, trap.json, docs/, runs/, any other repository files

The same `coroner verify` audit would be run, and the results would appear in the independence table.
