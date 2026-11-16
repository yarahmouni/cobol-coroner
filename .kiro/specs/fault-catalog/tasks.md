# Trap Catalog Tasks

- [x] 1. Engine extension for batch input and control breaks

_Requirements: Req 7, D-34. Schema.json may declare case_rows (emit multiple input rows per case), output_key (comparison key for output rows), group_key, subtotal and grand_total_key (compute Unreconciled branch exposure)._

Done when:
- coroner/parse/schema.py: parse_schema reads case_rows (optional dict with min and max), output_key (optional list of field names), group_key, subtotal, grand_total_key (all optional strings), and cobc_flags (optional list of strings for per-program compile flags).
- coroner/gen/cases.py: when case_rows is declared, generate 2 to 12 input rows per case with the same CASE-ID (drawn with random.Random(seed).random() between min and max), varying the other fields per schema.
- coroner/compare/normalize.py: when output_key is declared, index output rows by the key fields (tuple of values) instead of line order; a missing row on either side is a divergence (the comparator loops over the union of COBOL and Java keys).
- coroner/verdict.py: when group_key, subtotal and grand_total_key are declared, compute exposure = sum of abs(cobol_subtotal - java_subtotal) per group (excluding the grand total row), max_exposure = max of those differences, affected_branches = count of groups with non-zero difference, grand_total_matches = whether the grand total row values are equal; add these fields to the Verdict dataclass; print "Unreconciled branch exposure: sum $X.XX, max $Y.YY, Z branches affected, grand total matches: yes/no" after the coverage lines.
- coroner/run/cobol.py: when schema declares cobc_flags, apply them to the reference build and the coverage build (in addition to the default `-x -Wall -I`).
- coroner/store.py: inputs.json records cobc_flags when declared.
- coroner/certificate.py: certificate includes cobc_flags (so they are covered by certificate_sha256); replay checks that the recorded flags match the current flags.
- Existing schemas (no case_rows, no output_key, no cobc_flags) keep their behavior unchanged (unit tests for both cases).
- pytest passes.

- [x] 2. Trap 1 (T1-ebcdic-match-merge)

_Requirements: Req 1. COBOL program sorts transactions with EBCDIC collating sequence and matches them sequentially against a branch table in EBCDIC order; faulty Java sorts and compares with ASCII String.compareTo; correct Java uses IBM1047 byte order; branch subtotals diverge while the TOTAL row matches (only if unmatched records are counted in the suspense branch)._

Done when:
- samples/traps/T1-ebcdic-match-merge/ created with MATCH-MERGE.cob, schema.json (with case_rows, output_key, group_key, subtotal, grand_total_key), fixtures/branch-ordering.csv (at least 4 transactions covering EBCDIC/ASCII divergence), java/correct/MatchMerge.java and java/faulty/MatchMerge.java.
- MATCH-MERGE.cob: reads INPUT-FILE, SORT ... COLLATING SEQUENCE IS EBC, ALPHABET EBC IS EBCDIC, OBJECT-COMPUTER PROGRAM COLLATING SEQUENCE IS EBC, hard-coded branch table in EBCDIC order (for example "A01", "A02", "Z99", "a01"), sequential match, unmatched to "SUSP", outputs one row per branch with SUBTOTAL and one TOTAL row.
- Branch codes only use letters, digits, space and hyphen.
- Compiles with `cobc -x -Wall`, every IF has ELSE, every EVALUATE has WHEN OTHER.
- Faulty Java: sorts by String.compareTo (ASCII), advances wrongly.
- Correct Java: sorts by IBM1047 byte order (Charset.forName("IBM1047"), convert to bytes, compare).
- fixtures/branch-ordering.csv: at least one branch that appears before "Z99" in EBCDIC but after it in ASCII (for example "a01"), expected output produced only by running MATCH-MERGE.cob.
- Run the engine on the fixture (--cases 0 to use the fixture only): faulty Java ZOMBIE with divergent BRANCH rows and a matching TOTAL row (verified with measured numbers: TOTAL rows are equal, at least one branch subtotal differs), non-zero exposure; correct Java ALIVE.
- pytest passes.

- [x] 3. Trap 2 (T2-rounding)

_Requirements: Req 2. COBOL program computes with and without ROUNDED; faulty Java uses HALF_EVEN where COBOL has ROUNDED and HALF_UP where COBOL truncates; correct Java uses DOWN for truncation and HALF_UP for ROUNDED._

Done when:
- samples/traps/T2-rounding/ created with ROUNDING-CALC.cob, schema.json, fixtures/ties.csv, java/correct/RoundingCalc.java and java/faulty/RoundingCalc.java.
- ROUNDING-CALC.cob: reads INPUT-FILE (CASE-ID, PRINCIPAL, RATE), COMPUTE FEE1 = PRINCIPAL * RATE (no ROUNDED), COMPUTE FEE2 ROUNDED = PRINCIPAL * RATE, writes OUTPUT-FILE (CASE-ID, FEE1, FEE2).
- Compiles with `cobc -x -Wall`, every IF has ELSE.
- Faulty Java: fee1 with HALF_UP (should be DOWN), fee2 with HALF_EVEN (should be HALF_UP).
- Correct Java: fee1 with DOWN, fee2 with HALF_UP.
- fixtures/ties.csv: at least one tie with even preceding digit (12.345, -12.345), expected output from COBOL.
- Run the engine on the fixture: faulty Java ZOMBIE with divergent FEE1 or FEE2; correct Java ALIVE.
- pytest passes.

- [ ] 4. Trap 3 (T3-comp3-sign)

_Requirements: Req 3. COBOL decodes hex text to COMP-3 with FUNCTION HEX-TO-CHAR and REDEFINES; sign nibble F is read as positive by GnuCOBOL (evidence file); faulty Java treats F as negative or rejects it. Generated and certified cases use only preferred sign nibbles (C, D, F); non-preferred nibbles (B, A, E, others) are excluded._

Done when:
- samples/traps/T3-comp3-sign/ created with COMP3-SIGN.cob, schema.json, fixtures/sign-nibbles.csv, java/correct/Comp3Sign.java and java/faulty/Comp3Sign.java.
- COMP3-SIGN.cob: reads INPUT-FILE (CASE-ID, HEX-VALUE), WORKING-STORAGE field populated with FUNCTION HEX-TO-CHAR(HEX-VALUE), redefined as PIC S9(7)V99 COMP-3 (5 bytes, 10 hex digits), moved to a signed edited output field PIC +9(7).99, writes OUTPUT-FILE (CASE-ID, DECODED-VALUE).
- Compiles with `cobc -x -Wall`, every IF has ELSE.
- Faulty Java: decodes hex to bytes, reads sign nibble C positive, D negative, F negative (or rejects).
- Correct Java: decodes the 5 bytes with 9 digit nibbles plus a sign nibble, using the low nibble of each byte as the digit value, interprets sign nibble C positive, D negative, F positive, B positive (matches GnuCOBOL; comment states that IBM documentation treats B as negative, GnuCOBOL differs, and certified cases use only C, D, F).
- Case generator: when HEX-VALUE is generated, use only sign nibbles C (positive), D (negative), and F (unsigned); never generate B, A, E or other non-preferred nibbles.
- fixtures/sign-nibbles.csv: at least 3 hex values (one with C, one with D, one with F), expected output from COBOL.
- Run the engine on the fixture: faulty Java ZOMBIE with divergent DECODED-VALUE on F; correct Java ALIVE.
- pytest passes.

- [ ] 5. Trap 4 (T4-zoned-overpunch)

_Requirements: Req 4. COBOL reads mainframe extract files with EBCDIC overpunch convention ("}" = -0, "J" to "R" = -1 to -9, "{" = +0, "A" to "I" = +1 to +9); COBOL compiles with -fsign=EBCDIC (verified behavior in docs/evidence/gnucobol-encodings.md); faulty Java applies the ASCII convention or strips the last character. Engine extension: per-program compile flags in schema.json._

Done when:
- samples/traps/T4-zoned-overpunch/ created with ZONED-OVERPUNCH.cob, schema.json (with "cobc_flags": ["-fsign=EBCDIC"]), fixtures/zoned-signs.csv, java/correct/ZonedOverpunch.java and java/faulty/ZonedOverpunch.java.
- ZONED-OVERPUNCH.cob: reads INPUT-FILE (CASE-ID, ZONED-VALUE), WORKING-STORAGE PIC X(6) redefined as PIC S9(5), moved to a signed edited output field, writes OUTPUT-FILE (CASE-ID, DECODED-VALUE).
- Compiles with `cobc -x -Wall -fsign=EBCDIC`, every IF has ELSE.
- Faulty Java: applies the ASCII convention (negative last digit + 0x40, for example "1234u" = -12345) or strips the last character.
- Correct Java: applies the EBCDIC overpunch table (evidence file): "}" = -0, "J" = -1, "R" = -9, "{" = +0, "A" = +1, "I" = +9.
- fixtures/zoned-signs.csv: at least 2 values ("12345}" = -12340 in EBCDIC overpunch, "12345" = +12345), expected output from COBOL.
- Run the engine on the fixture: faulty Java ZOMBIE with divergent DECODED-VALUE; correct Java ALIVE.
- pytest passes.

- [ ] 6. Trap 5 (T5-redefines-invalid)

_Requirements: Req 5. COBOL reads an alphanumeric field with non-digit characters through a REDEFINES as PIC 9(n), using the low nibble of each byte as the digit value (evidence file: "12A45" where A is 0x41, low nibble 1, is read as 12145, so + 1 = 12146 with no abend); faulty Java rejects or treats it as zero._

Done when:
- samples/traps/T5-redefines-invalid/ created with REDEFINES-INVALID.cob, schema.json, fixtures/invalid-numerics.csv, java/correct/RedefinesInvalid.java and java/faulty/RedefinesInvalid.java.
- REDEFINES-INVALID.cob: reads INPUT-FILE (CASE-ID, ALPHA-VALUE), WORKING-STORAGE PIC X(5) redefined as PIC 9(5), COMPUTE OUTPUT-VALUE = REDEF-NUMERIC + 1, writes OUTPUT-FILE (CASE-ID, OUTPUT-VALUE).
- Compiles with `cobc -x -Wall`, every IF has ELSE.
- Faulty Java: rejects non-digit characters (throws an exception or writes 0).
- Correct Java: reads the low nibble of each byte (A=0x41 becomes 1, J=0x4A becomes 10 with carry), matching GnuCOBOL.
- fixtures/invalid-numerics.csv: at least 2 values ("12A45" (low nibble reads as 12145, output 12146) and "12345" (output 12346)), expected output from COBOL.
- Run the engine on the fixture: faulty Java ZOMBIE with divergent OUTPUT-VALUE on "12A45"; correct Java ALIVE.
- pytest passes.

- [x] 7. Trap 6 (T6-reserved) placeholder

_Requirements: Req 6. Reserved slot for the owner's real field trap._

Done when:
- samples/traps/T6-reserved/ directory created with a README.md stating "Placeholder for owner field trap".
- The catalog runner lists T6 with status "placeholder: owner field trap pending", not measured, no numbers.

- [ ] 8. Given/When/Then card generation

_Requirements: Req 9, D-43. Deterministic template from the minimal case, no LLM._

Done when:
- coroner/traps.py: generate_card(minimal_case, trap_title) returns a string with the format "Given [input field 1 = value 1], [input field 2 = value 2], ... / When [operation from trap_title] / Then COBOL output [field = value] / But Java produced [field = value]".
- The card is written as a header comment in ZombieRegressionTest.java (coroner/diag/junit.py: prepend the card as a block comment).
- Unit test: generate_card with a known minimal case returns the expected card text.
- pytest passes.

- [ ] 9. Catalog runner

_Requirements: Req 8. `python -m coroner traps` runs the engine on all built traps (T1 to T5), writes runs/trap_catalog.json and runs/trap_catalog.txt._

Done when:
- coroner/traps.py: run_catalog(seed=42, cases=2000) loops over T1 to T5, runs the engine on faulty Java and correct Java, collects id, title, status, cases_generated, cases_detected, detection_rate, minimal_case, cobol_lines, probable_cause, suggested_fix, given_when_then, correct_java_verdict, and for T1 the exposure.
- Probable cause and suggested fix per trap (one sentence each): T1 "Faulty Java sorts by ASCII String.compareTo instead of EBCDIC byte order. Use IBM1047 Charset or a custom Comparator.", T2 "Faulty Java uses HALF_EVEN where COBOL has ROUNDED (default HALF_UP). Use RoundingMode.HALF_UP.", T3 "Faulty Java treats sign nibble F as negative or rejects it. GnuCOBOL reads F as positive.", T4 "Faulty Java applies the ASCII convention (or strips the last character) to EBCDIC-encoded data. Use the EBCDIC overpunch table (compile the reference with -fsign=EBCDIC).", T5 "Faulty Java rejects invalid numeric data under REDEFINES. GnuCOBOL reads the low nibble of each byte."
- T6: {"id": "T6", "title": "Reserved for owner field trap", "status": "placeholder: owner field trap pending"}.
- Writes runs/trap_catalog.json (JSON array of trap results) and runs/trap_catalog.txt (human-readable rendering).
- CLI entry point: python -m coroner traps calls run_catalog.
- pytest passes.

- [ ] 10. MCP tool get_detection_matrix

_Requirements: Req 10. Reads runs/trap_catalog.json and returns the matrix; error if the catalog has not been built yet._

Done when:
- coroner/mcp.py: @server.call_tool() async def get_detection_matrix(arguments: dict) reads runs/trap_catalog.json, returns the JSON as TextContent; raises ToolError("Trap catalog not built yet. Run `make traps` first.") if the file does not exist.
- tests/test_mcp_server.py: test_get_detection_matrix_success (with a real trap_catalog.json) and test_get_detection_matrix_not_built (missing file, assert is_error).
- pytest passes.

- [x] 11. Documentation

_Requirements: Req 11. README, architecture.md, Makefile target._

Done when:
- README.md: after "What Coroner is not", add "## Six banking migration traps" with the list (EBCDIC collation lead, rounding, COMP-3 sign with preferred nibbles only, zoned overpunch, REDEFINES, reserved) and the wording "targeted regression traps within its supported COBOL subset, not general COBOL coverage". Add under limitations: "COMP-3 sign nibbles B, A, E and other non-preferred nibbles are excluded from certified cases (GnuCOBOL reads B as positive, IBM documentation as negative)."
- architecture.md: under "Modules" add coroner/traps.py, under "Repository layout" add samples/traps/T1-ebcdic-match-merge/ to T6-reserved/.
- Makefile: target `traps` runs `python -m coroner traps`.

- [x] 12. Acceptance

_Requirements: Req 12. Every trap T1 to T5 gives ZOMBIE on its faulty Java with at least one detected case and ALIVE on its correct Java; T1 shows divergent subtotals with a matching TOTAL row (verified with measured numbers) and non-zero exposure; catalog JSON and text are written; MCP tool returns the matrix._

Done when:
- Run `make traps`: T1 to T5 each show ZOMBIE on faulty Java with detection_rate > 0 and ALIVE on correct Java.
- T1 faulty Java verdict: at least one case with divergent branch subtotals and a matching TOTAL row (measured verification: COBOL TOTAL row value equals Java TOTAL row value, at least one branch subtotal differs), exposure sum > 0, max > 0, affected_branches > 0, grand_total_matches = true.
- runs/trap_catalog.json exists and contains 6 entries (T1 to T5 measured, T6 placeholder).
- runs/trap_catalog.txt exists and is human-readable.
- Real Kiro session: `@coroner/get_detection_matrix` returns the matrix (6 traps listed).
- pytest passes (all trap tests, MCP test).

## Coverage

| Criterion | Tasks |
|---|---|
| Req 1 (T1 EBCDIC match-merge) | 1, 2 |
| Req 2 (T2 rounding) | 3 |
| Req 3 (T3 COMP-3 sign) | 4 |
| Req 4 (T4 zoned overpunch) | 1, 5 |
| Req 5 (T5 REDEFINES invalid) | 6 |
| Req 6 (T6 reserved) | 7 |
| Req 7 (engine extension) | 1 |
| Req 8 (catalog runner) | 9 |
| Req 9 (Given/When/Then card) | 8 |
| Req 10 (MCP tool) | 10 |
| Req 11 (documentation) | 11 |
| Req 12 (acceptance) | 12 |
