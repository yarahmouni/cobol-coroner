# Case 6, The Cursed Modulo (T6): Requirements

## Overview
Case 6 turns the reserved sixth slot of the trap catalog into a real case (owner decision Q1, 2026-11-23). A rotation slot (a weekday slot, 0 to 6) is computed from a signed day offset relative to a reference date. The COBOL program uses `FUNCTION MOD(DAY-OFFSET, 7)`. A faulty Java port uses `%`, which gives a different result for negative offsets.

Positioning: a targeted regression trap within the supported COBOL subset, like T1 to T5.

## Constraints
- The engine is unchanged: no change to coroner/gen, coroner/compare, coroner/run, coroner/verdict.py, coroner/certificate.py, coroner/store.py, coroner/cli.py, coroner/derive.py, coroner/hooks.py. Everything the case needs is in the trap folder and in the case registry.
- ANSI COBOL, fixed format, compiles with `cobc -x -Wall` with no warning, every IF has an explicit ELSE.
- Expected outputs come only from running the COBOL program, never from a hand-written file (steering quality.md, D-51).
- No numeric tolerance. The slot is a code, not an amount, so the output columns are not of type decimal (no money figure is derived for this case).
- Wording: never "proven", "guaranteed", "first", "unique". The measurements come from GnuCOBOL 3.2.0; they do not claim the behaviour of IBM Enterprise COBOL on z/OS beyond what the cited IBM page states.

## Requirements

### 1. The COBOL program (samples/traps/T6-cursed-modulo/ROTATION-SLOT.cob)
1.1. Reads INPUT_FILE (CSV, header, then `CASE-ID,DAY-OFFSET`) and writes OUTPUT_FILE with the header `CASE-ID,DAY-OFFSET,SLOT`.
1.2. DAY-OFFSET is a signed integer from -999 to 999. A negative offset means days before the reference date.
1.3. SLOT is `FUNCTION MOD(DAY-OFFSET, 7)`, always 0 to 6. The offset is written as sign and three digits, the slot as sign and one digit (edited pictures).
1.4. Input validation: wrong field count, empty CASE-ID, a value that is not a number and a value outside -999 to 999 end the run with return code 16 and a message on stderr.
1.5. Measured by the operator on 2026-11-23 (GnuCOBOL 3.2.0, cobc -x -Wall; OpenJDK 17.0.21): `FUNCTION MOD(-11, 7)` = 3; `FUNCTION REM(-11, 7)` = -4; `FUNCTION MOD(-11, 5)` = 4; `FUNCTION MOD(11, -5)` = -4; `DIVIDE -11 BY 7 GIVING Q REMAINDER R` gives Q = -1 and R = -4; Java `-11 % 7` = -4 and `Math.floorMod(-11, 7)` = 3.

### 2. The Java ports
2.1. java/correct/RotationSlot.java uses `Math.floorMod(offset, 7)` and writes byte-identical output to COBOL.
2.2. java/faulty/RotationSlot.java uses `offset % 7`. It differs from COBOL exactly for negative offsets that are not a multiple of 7, where it writes a negative slot (-6 to -1) and COBOL writes 1 to 6.
2.3. Both ports use int arithmetic, write LF line endings, and build the output text without locale dependent formatting.

### 3. Schema and generated cases (samples/traps/T6-cursed-modulo/schema.json)
3.1. Input `DAY-OFFSET` is a decimal column with PIC S9(3) and scale 0, so the existing generator draws signed values (about half negative) without any generator change.
3.2. Output `DAY-OFFSET` and `SLOT` are integer columns, compared as exact text after trimming trailing spaces. A slot is a code, so no amount difference file is written for a T6 run.

### 4. Case text and sources (trap.json, README.md, cases.json)
4.1. samples/traps/cases.json registers T6 as case 6, "The Cursed Modulo", with a subtitle and a detail line (the run page shows the three-line case card, like Case 3).
4.2. trap.json has id, title, business_name, business_cause, probable_cause, technical_cause, business_fix and fix_sentence, each short, because the run page shows these fields verbatim. It also lists the public sources and one line on how the case differs from Case 3.
4.3. The case README names the two public sources with their URLs: the COBOL language reference page for FUNCTION MOD (https://www.ibm.com/docs/en/SS6SG3_6.5/lr/ref/rlinfmod.html, with the table MOD(-11,5) = 4 and MOD(11,-5) = -4) and, for Java, the Java Language Specification section 15.17.3 and SEI CERT rule NUM51-J (https://wiki.sei.cmu.edu/confluence/x/IxRMBQ).
4.4. The text states the twist: `DIVIDE ... REMAINDER` and `FUNCTION REM` behave like Java `%`, so each construct must be mapped separately.
4.5. The text states in one line how Case 6 differs from Case 3: Case 3 loses a sign in storage, Case 6 uses a different mathematical definition of the operation.

### 5. Catalog, UI and MCP
5.1. The catalog runner measures T6 like T1 to T5 (faulty run, correct run, detected, rate, minimal case, card, probable cause, fix sentence). No placeholder entry is written.
5.2. The Detection Matrix, the home selector, the run page, the Run audit endpoint and `get_detection_matrix` treat T6 as a normal case. A catalog written by an older image with a placeholder T6 entry is still shown as "not measured".
5.3. The ZOMBIE sentence of the run page is computed from the run's comparison results: the count of divergent slots, and "Java gives a negative slot where COBOL gives 0 to 6" only when every divergent Java slot is negative.

### 6. Acceptance
6.1. On a catalog run (2000 cases, seed 42, temporary base) the faulty port is ZOMBIE with at least one detected case and the correct port is ALIVE.
6.2. The divergent cases of a faulty run are exactly the negative offsets that are not a multiple of 7, and only those.
6.3. The run ids and counts of T1 to T5 are unchanged.
6.4. A fixture row with offset -11 gives slot 3 in the COBOL output and -4 in the faulty Java output, read from the real runs.
