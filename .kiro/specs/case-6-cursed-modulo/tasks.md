# Case 6, The Cursed Modulo (T6): Tasks

- [x] 1. Phase A: check that no frozen engine file needs a change
  _Requirements: Constraints._
  Done when:
  - T1 to T5 wiring, the T6 placeholder code, the generator and the comparator were read; the generator draws signed scale 0 decimal input columns and the comparator compares non-decimal columns as exact text, so no frozen file changes.

- [x] 2. COBOL program, schema and fixtures
  _Requirements: 1, 3._
  Done when:
  - samples/traps/T6-cursed-modulo/ROTATION-SLOT.cob compiles with `cobc -x -Wall` with empty stderr.
  - fixtures/offsets.csv holds fixed offsets including -11; fixtures/expected-output.csv is a copy of the output of the COBOL program on it.
  - The COBOL output for -11 has slot +3.

- [x] 3. Java ports
  _Requirements: 2._
  Done when:
  - java/correct/RotationSlot.java uses Math.floorMod and its output equals the COBOL output on the fixture byte for byte.
  - java/faulty/RotationSlot.java uses `%`; on the fixture it differs from COBOL exactly for negative offsets that are not multiples of 7; offset -11 gives slot -4.

- [x] 4. Case text, sources and registry
  _Requirements: 4._
  Done when:
  - trap.json, README.md and the cases.json entry exist; the README names both public sources with their URLs, the twist and the difference from Case 3.
  - The old samples/traps/T6-reserved folder is gone and every reference to it is updated.

- [x] 5. Remove the T6 placeholder code
  _Requirements: 5._
  Done when:
  - coroner/traps.py measures T6 in the catalog; coroner/ui/app.py, coroner/ui/sentences.py accept T6; the matrix shows "not measured" for any non-measured entry.
  - No frozen engine file changed.

- [x] 6. Tests
  _Requirements: 6._
  Done when:
  - tests/test_trap_t6.py, written like tests/test_trap_t5.py: real runs in a temporary base, faulty ZOMBIE, divergent cases exactly the negative offsets that are not multiples of 7, correct ALIVE, the -11 fixture from the COBOL run, the run page and the sentence.
  - The tests that asserted "Case 6 reserved", "not measured" or five measured cases assert the real case.

- [x] 7. Measured figures and documentation
  _Requirements: 6.1, 6.3._
  Done when:
  - A catalog run (2000 cases, seed 42, temporary base) gives T6 faulty ZOMBIE and T6 correct ALIVE, with the run ids and counts recorded in the README, docs/judge-guide.md and CHANGELOG.md; T1 to T5 run ids are unchanged.
  - The README "Try it in 60 seconds" step 5 is left unchanged until the next image is live.
