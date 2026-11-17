# Trap Catalog Requirements

## Overview
Build a catalog of six banking migration traps that silently corrupt amounts, signs, ordering or control totals. Each trap is an executable COBOL mini-program with a faulty Java port and a correct Java port. The differential engine detects the divergence and reports the minimal case, executed COBOL lines, a deterministic probable cause and a one-sentence suggested fix.

Positioning: targeted regression traps within the supported COBOL subset. Not general COBOL coverage.

## Constraints
- Every trap program: ANSI COBOL, compiles with `cobc -x -Wall`, reads INPUT_FILE and writes OUTPUT_FILE like credit-fees, every IF has an explicit ELSE, every EVALUATE has a WHEN OTHER.
- Default compilation: no other non-default flags. Exception: T4 requires `-fsign=EBCDIC` (see Req 4.1).
- Trap programs are exempt from the 300 to 800 line limit.
- Every encoding rule comes from docs/evidence/gnucobol-encodings.md (operator-verified GnuCOBOL 3.2.0 behavior), never from memory or IBM documentation alone.
- Java: BigDecimal for amounts, Java 17, same file contract as CreditFees.
- One small hand-made fixture per trap whose expected output is produced only by running the COBOL program, never invented.
- Every trap includes schema.json, fixtures/, java/correct/ and java/faulty/.

## Requirements

### 1. Trap 1 (T1-ebcdic-match-merge): EBCDIC vs ASCII collating order (lead demo)
1.1. Input: transactions with CASE-ID, BRANCH and AMOUNT; one case is a batch of 2 to 12 input rows with the same CASE-ID.
1.2. COBOL: SORT ... COLLATING SEQUENCE IS an alphabet declared ALPHABET ... IS EBCDIC, then match transactions sequentially against a branch table held in the program in EBCDIC order; OBJECT-COMPUTER PROGRAM COLLATING SEQUENCE so IF comparisons also use EBCDIC. Unmatched transactions go to a suspense branch "SUSP".
1.3. Output per case: one row per branch with BRANCH, SUBTOTAL and one TOTAL row (BRANCH = "TOTAL") with the grand total.
1.4. Branch codes only use uppercase letters, digits, space and hyphen (the domain where IBM1047 byte order equals GnuCOBOL's EBCDIC table, see the evidence file). No lowercase codes (lowercase codes are not realistic and would cause 100% divergence in ASCII).
1.5. Branch table in EBCDIC order (9 entries): A01, B02, C03, D04, E05, F06, Z99, 001, 9ZZ. Uppercase-led codes sort in the same relative order under ASCII and EBCDIC (space, uppercase, digits in EBCDIC; space, digits, uppercase in ASCII), so batches with only uppercase codes produce identical output. Digit-led codes (001, 9ZZ) sort first in ASCII but after uppercase in EBCDIC; the faulty port with ASCII comparison does not advance past A01 for a digit-led code and posts it to SUSP, so only those amounts move while the TOTAL row still matches.
1.6. Domain weights (schema.json): A01, B02, C03, D04, E05, F06, Z99 weight 20 each; 001 and 9ZZ weight 2 each; X77 weight 2 (goes to SUSP on both sides). Measured divergence rate (2000 cases, seed 42): 262 cases (13.1%), exposure sum 30636924.02, max 26333183.83, 2 branches affected, suspense difference 30636924.02, grand total matches: yes.
1.7. Faulty Java: sorts and compares with String.compareTo (ASCII order), so the sequential match advances wrongly and transactions are posted to the wrong branch or suspense.
1.8. Correct Java: sorts and compares by IBM1047 byte order (the JDK charset IBM1047 provides it).
1.9. Explain in the design: a plain grouping by branch (SQL GROUP BY) would NOT show any divergence because subtotals are order independent. The order-dependent match does diverge.
1.10. Branch subtotals between COBOL and Java diverge while the TOTAL row still matches (the lead evidence of a subtle control-break bug). The TOTAL row matches only if unmatched records are counted (suspense branch).
1.11. The hand fixture covers at least one case with only uppercase codes (same output for both ports) and one case with a digit-led code (faulty differs).
1.12. Acceptance must verify with measured numbers that the TOTAL rows are equal while branch subtotals diverge.

### 2. Trap 2 (T2-rounding): truncation without ROUNDED, and ROUNDED ported as HALF_EVEN
2.1. Input: one or more numeric values.
2.2. COBOL: arithmetic without ROUNDED (truncates) and arithmetic with ROUNDED (HALF_UP).
2.3. Faulty Java: uses HALF_EVEN where COBOL has ROUNDED, HALF_UP where COBOL truncates.
2.4. Correct Java: uses DOWN for truncation, HALF_UP for ROUNDED.
2.5. The hand fixture includes at least one tie that diverges (even preceding digit, positive and negative).

### 3. Trap 3 (T3-comp3-sign): COMP-3 sign nibble
3.1. Input: packed values as hex text (for example "12345D"), representing 5 packed bytes (10 hex digits). Decoded in COBOL with FUNCTION HEX-TO-CHAR into a field redefined as PIC S9(7)V99 COMP-3.
3.2. COBOL rules (evidence file): C positive, D negative, F read as positive, B read as positive (GnuCOBOL rule; IBM treats B as negative).
3.3. Generated and certified cases use only the preferred sign nibbles (C for positive, D for negative, and F for unsigned fields). Non-preferred nibbles (B, A, E and others) are excluded from certified cases.
3.4. Document this as a known GnuCOBOL vs IBM difference (docs/evidence/gnucobol-encodings.md already records it; README limitations gets one line in the documentation task). Never claim the reference matches z/OS for these.
3.5. Faulty Java: treats F as negative or rejects it.
3.6. Correct Java: C positive, D negative, F positive, B positive (matches GnuCOBOL). Decodes the 5 bytes with 9 digit nibbles plus sign nibble, using the low nibble of each byte as the digit value, then interprets the sign nibble (C, D, F positive; D negative).
3.7. The hand fixture includes at least one hex value with F.

### 4. Trap 4 (T4-zoned-overpunch): zoned decimal overpunch sign
4.1. Input: mainframe extract files use the EBCDIC overpunch convention: "}" = -0, "J" to "R" = -1 to -9, "{" = +0, "A" to "I" = +1 to +9 (evidence file).
4.2. COBOL compiles with `-fsign=EBCDIC` (verified behavior in docs/evidence/gnucobol-encodings.md: "1234}" reads -12340 and "1234M" reads -12344 under -fsign=EBCDIC).
4.3. Engine extension: per-program compile flags declared in the trap's schema.json ("cobc_flags": ["-fsign=EBCDIC"]), applied to the reference and the coverage build, recorded in inputs.json and in the certificate (so they are covered by certificate_sha256), and checked on replay.
4.4. Faulty Java: applies the ASCII convention (or strips the last character).
4.5. Correct Java: applies the EBCDIC overpunch table (evidence file).
4.6. The hand fixture includes at least one negative value with the EBCDIC convention.

### 5. Trap 5 (T5-redefines-invalid): numeric field read through REDEFINES of invalid data
5.1. Input: alphanumeric values with non-digit characters.
5.2. COBOL: PIC X(n) input field redefined as PIC 9(n), moved to output, or used in arithmetic (evidence file: "12A45" + 1 = 12146 with no abend, rc 0).
5.3. Faulty Java: rejects the record or treats the value as zero.
5.4. Correct Java: reads the low nibble of each byte as the digit value, matching GnuCOBOL (A=0x41 low nibble 1; J=0x4A low nibble 10 with carry).
5.5. Wording: Coroner reports the behavior change, it does not judge which side is right.
5.6. The hand fixture includes at least one invalid numeric value.

### 6. Trap 6 (T6-reserved): reserved for owner field trap
6.1. Status: placeholder until the owner provides a real field trap.
6.2. The catalog runner lists it with status "placeholder: owner field trap pending", not measured, never with numbers.

### 7. Engine extension for batch input and control breaks (D-34, built with T1)
7.1. schema.json may declare "case_rows": {"min": 2, "max": 12} (the generator emits several input rows per case), "output_key": ["CASE-ID", "BRANCH"] (comparison key of output rows; a case is divergent when any of its rows diverges), "group_key": "BRANCH", "subtotal": "SUBTOTAL", "grand_total_key": "TOTAL" (the value of the group_key field that marks the grand total row).
7.2. The generator: when case_rows is declared, emit 2 to 12 input rows per case with the same CASE-ID, varying the other fields per schema.
7.3. The comparator: when output_key is declared, index output rows by the key fields and compare row by row (a missing row on either side is a divergence).
7.4. The verdict: when group_key, subtotal and grand_total_key are declared, compute "Unreconciled branch exposure": sum of the absolute difference between COBOL and Java subtotals per branch (a missing branch on either side counts as 0), max absolute difference, number of affected branches, and grand-total match status (yes/no).
7.5. Existing schemas (no case_rows, no output_key) keep their behavior unchanged.

### 8. Catalog runner: `python -m coroner traps`
8.1. For each trap T1 to T5 (T6 is a placeholder): run the engine on the faulty Java and on the correct Java (default seed 42, default cases 2000), write runs/trap_catalog.json and a text rendering.
8.2. Per trap: id, title, status, cases_generated, cases_detected, detection_rate, minimal case (deterministic, per the engine rule), COBOL lines (from the failure report), probable cause, suggested fix (one sentence, D-26), Given/When/Then card (D-43, deterministic text from the minimal case, no LLM), correct Java verdict (must be ALIVE), and for T1 the exposure.
8.3. T6: status "placeholder: owner field trap pending", no numbers.
8.4. No global detection rate. Each trap has its own rate.

### 9. Given/When/Then card generation (D-43)
9.1. Deterministic template from the minimal case: "Given [input summary from the minimal case], When [operation from the COBOL program name or title], Then [expected COBOL output field = value], But Java produced [Java output field = value]."
9.2. No LLM. The card is shown in the UI, the report and as a header comment in the JUnit test.

### 10. MCP tool: get_detection_matrix
10.1. Reads runs/trap_catalog.json and returns the matrix as MCP structured content.
10.2. Returns an error if the catalog has not been built yet.

### 11. Documentation
11.1. README: "Six banking migration traps that silently corrupt amounts, signs, ordering or control totals" with the T1 lead example.
11.2. architecture.md: samples/traps/ structure, coroner/traps module.
11.3. Makefile target `traps` runs the catalog.

### 12. Acceptance
12.1. Every trap T1 to T5 gives ZOMBIE on its faulty Java with at least one detected case (detection_rate > 0) and ALIVE on its correct Java.
12.2. T1 shows divergent subtotals with a matching TOTAL row and non-zero exposure (verified with measured numbers: TOTAL rows are equal, at least one branch subtotal differs).
12.3. The catalog JSON and text rendering are written to runs/.
12.4. `@coroner/get_detection_matrix` returns the matrix in a Kiro session.

## Constraints
- Wording: "targeted regression traps within its supported COBOL subset". Never "first", "unique", "novel", "proves", "proven", "guaranteed".
- No S0C7 claim (GnuCOBOL does not raise it, see the evidence file).
- Never use the em dash character in any file.
