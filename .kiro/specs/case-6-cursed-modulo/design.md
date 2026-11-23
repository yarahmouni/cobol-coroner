# Case 6, The Cursed Modulo (T6): Design

## Folder

```
samples/traps/T6-cursed-modulo/
  ROTATION-SLOT.cob
  schema.json
  trap.json
  README.md              sources, the twist, the difference from Case 3
  fixtures/offsets.csv
  fixtures/expected-output.csv   output of the COBOL program on offsets.csv
  java/correct/RotationSlot.java
  java/faulty/RotationSlot.java
```

The folder follows T5. The catalog runner, the engine worker and the UI find it through `samples/traps/<id>-*/trap.json`; no list of trap folders has to be extended except the folder name map of coroner/traps.py.

## COBOL program

- Same skeleton as REDEFINES-INVALID.cob: `ASSIGN TO DYNAMIC` paths read from the environment, `READ-HEADER`, `WRITE-HEADER`, `PROCESS-RECORD`, `FILE STATUS` checks, every IF with an ELSE.
- `UNSTRING` splits the line into the case id and the offset text. `FUNCTION TEST-NUMVAL` validates the text. `FUNCTION NUMVAL` converts it into a PIC S9(9) field, the range is checked, then the value is moved into PIC S9(3), so no truncation is possible.
- `COMPUTE WS-SLOT = FUNCTION MOD(WS-OFFSET, 7)` into PIC 9. MOD takes the sign of the divisor, so the slot is 0 to 6.
- Output edited pictures: `+9(3)` for the offset and `+9` for the slot.

## Java ports

Identical code except one line:

```java
int slot = Math.floorMod(offset, SLOTS);   // correct
int slot = offset % SLOTS;                  // faulty
```

Output text is built by hand (sign, zero padded digits) so no `String.format` and no locale are involved.

## Why the generator needs no change

The existing generator draws a `decimal` input column by magnitude (number of digits first, then the digits) with a 50 percent sign when the PIC has an S. PIC S9(3) with scale 0 gives integers from -999 to 999, about half negative. About a quarter of the values are 0 (zero digits drawn), which agree on both sides. The output columns are typed `integer` so that the comparator compares them as exact text and the amount difference code (decimal columns only) writes no figure.

## Catalog and UI changes

- coroner/traps.py: T6 is in the loop of the catalog and in the folder name map; the placeholder function is removed.
- coroner/ui/app.py: T6 in the Run audit sample pattern, in the trap id lists of the run page, and the Detection Matrix shows "not measured" for any entry whose status is not "measured" (an older catalog) instead of testing for the id T6.
- coroner/ui/sentences.py: `_generate_t6_sentence`, from comparison_results.json.
- coroner/cases.py and coroner/ui/story.py: comments only. The guided story and the fool page stay on Case 1 and their three fixed toggles (D-60); Case 6 has no story step.
- samples/traps/cases.json: T6 entry with subtitle and detail.

The engine worker needs no change: it discovers the trap folder from trap.json.

## Sources

The IBM Enterprise COBOL language reference page for FUNCTION MOD, the Java Language Specification section 15.17.3 and SEI CERT rule NUM51-J are cited by name and URL in trap.json (key `sources`) and in the case README. The JLS URL was composed from the section number; it was not fetched when this case was written.
