# Trap Catalog Design

## Overview
Six executable banking migration traps that demonstrate silent data corruption patterns: EBCDIC collation breaking control breaks, rounding mode divergence, COMP-3 sign nibble, zoned overpunch, invalid numeric data under REDEFINES, and a reserved slot for the owner's field trap. Each trap includes COBOL, faulty Java, correct Java, schema and fixtures. The catalog runner executes them and builds the Detection Matrix.

## Directory structure
```
samples/traps/
  T1-ebcdic-match-merge/
    MATCH-MERGE.cob
    schema.json
    fixtures/branch-ordering.csv
    java/correct/MatchMerge.java
    java/faulty/MatchMerge.java
  T2-rounding/
    ROUNDING-CALC.cob
    schema.json
    fixtures/ties.csv
    java/correct/RoundingCalc.java
    java/faulty/RoundingCalc.java
  T3-comp3-sign/
    COMP3-SIGN.cob
    schema.json
    fixtures/sign-nibbles.csv
    java/correct/Comp3Sign.java
    java/faulty/Comp3Sign.java
  T4-zoned-overpunch/
    ZONED-OVERPUNCH.cob
    schema.json
    fixtures/zoned-signs.csv
    java/correct/ZonedOverpunch.java
    java/faulty/ZonedOverpunch.java
  T5-redefines-invalid/
    REDEFINES-INVALID.cob
    schema.json
    fixtures/invalid-numerics.csv
    java/correct/RedefinesInvalid.java
    java/faulty/RedefinesInvalid.java
  T6-reserved/
    (placeholder for owner trap)
```

## Trap 1: EBCDIC vs ASCII collating order (lead demo, D-33)

### Problem statement
Banks migrating control-break reports assume the sort order stays unchanged. When the COBOL program sorts with EBCDIC collation and the Java port uses ASCII String.compareTo, the sequential match advances wrongly: transactions are posted to the wrong branch or suspense. Branch subtotals diverge while the grand total still matches (only if unmatched records are counted in the suspense branch), a subtle error that passes balance checks.

A plain grouping by branch (SQL GROUP BY or a Java HashMap) would NOT diverge because subtotals are order independent. The divergence comes from the order-dependent sequential match: the Java code advances to the next branch table entry too early or too late.

Acceptance verification: with measured numbers, the TOTAL rows must be equal while at least one branch subtotal differs.

### COBOL design
- Input: CASE-ID (transaction batch id), BRANCH (3 characters, uppercase letters, digits, space and hyphen only, no lowercase), AMOUNT (signed decimal).
- SORT INPUT-FILE ASCENDING KEY BRANCH COLLATING SEQUENCE IS EBC.
- ALPHABET EBC IS EBCDIC. OBJECT-COMPUTER PROGRAM COLLATING SEQUENCE IS EBC.
- Branch table: hard-coded array of 9 branch codes in EBCDIC order: A01, B02, C03, D04, E05, F06, Z99, 001, 9ZZ. Uppercase-led codes sort in the same relative order under ASCII and EBCDIC (space, uppercase, digits in EBCDIC; space, digits, uppercase in ASCII). Digit-led codes (001, 9ZZ) sort first in ASCII but after uppercase in EBCDIC.
- Match loop: read sorted transaction, advance branch table pointer while BRANCH > TABLE-BRANCH, post to TABLE-BRANCH if equal or "SUSP" if unmatched.
- Output per case: one row per branch with BRANCH, SUBTOTAL (sum of amounts) and one TOTAL row (BRANCH = "TOTAL", SUBTOTAL = grand total).

### Faulty Java design
- Sorts List<Transaction> by branch with String.compareTo (ASCII: space, digits, uppercase).
- Advances wrongly: for a digit-led code like "001", the faulty walk does not advance past A01 (because "001" < "A01" in ASCII but "001" > "A01" in EBCDIC), and posts it to SUSP. Only those amounts move, so branch subtotals diverge but the grand total still matches.
- For batches with only uppercase codes, both programs produce identical output because uppercase codes sort in the same relative order.

### Correct Java design
- Sorts by IBM1047 byte order: Charset ibm1047 = Charset.forName("IBM1047"), convert each branch string to bytes, compare them byte by byte with Byte.compareUnsigned.
- On uppercase letters, digits, space and hyphen this order equals GnuCOBOL's EBCDIC table (evidence file).

### Fixture
At least 3 cases:
- UPPER-01: only uppercase codes (A01, B02, F06), same output for both ports.
- DIGIT-01: digit-led codes (001, 9ZZ) plus Z99, faulty port differs.
- MIXED-01: mix of uppercase and digit-led codes plus X77 (goes to SUSP on both sides).
The expected output comes from running the COBOL program.

### Detection
Measured divergence rate (2000 cases, seed 42): 262 cases (13.1%), exposure sum 666358.16, max 666357.81, 2 branches affected, grand total matches: yes.

### Domain weights
schema.json: A01, B02, C03, D04, E05, F06, Z99 weight 20 each; 001 and 9ZZ weight 2 each; X77 weight 2 (goes to SUSP on both sides). Measured to give 5% to 25% divergence on 2000 cases.

### Engine extension (Req 7, D-34)
- schema.json: "case_rows": {"min": 2, "max": 12}, "output_key": ["CASE-ID", "BRANCH"], "group_key": "BRANCH", "subtotal": "SUBTOTAL", "grand_total_key": "TOTAL".
- Generator: emit 2 to 12 input rows per case with the same CASE-ID, varying BRANCH (drawn from a pool that includes EBCDIC/ASCII divergent codes) and AMOUNT.
- Comparator: index output rows by (CASE-ID, BRANCH), compare row by row. A missing branch on either side is a divergence.
- Verdict extension: sum and max of abs(COBOL_SUBTOTAL - JAVA_SUBTOTAL) per branch, number of affected branches, grand-total match status (compare the TOTAL row). Print "Unreconciled branch exposure: sum $X.XX, max $Y.YY, Z branches affected, grand total matches: yes/no".
- Existing schemas (no case_rows) unchanged.

### Module design
- coroner/gen/cases.py: if schema declares case_rows, emit multiple rows per case; branch pool includes EBCDIC/ASCII divergent codes.
- coroner/compare/normalize.py: if schema declares output_key, index by key instead of line order.
- coroner/verdict.py: compute exposure when group_key is declared.

## Trap 2: Rounding mode divergence

### Problem statement
COBOL ROUNDED defaults to NEAREST-AWAY-FROM-ZERO (HALF_UP in Java). A port that uses HALF_EVEN diverges on ties with an even preceding digit. Truncation without ROUNDED requires DOWN, not HALF_UP.

### COBOL design
- Input: PRINCIPAL, RATE.
- COMPUTE FEE1 = PRINCIPAL * RATE (no ROUNDED, truncates).
- COMPUTE FEE2 ROUNDED = PRINCIPAL * RATE.
- Output: FEE1, FEE2.

### Faulty Java design
- fee1 = principal.multiply(rate).setScale(2, RoundingMode.HALF_UP) (should be DOWN).
- fee2 = principal.multiply(rate).setScale(2, RoundingMode.HALF_EVEN) (should be HALF_UP).

### Correct Java design
- fee1 = principal.multiply(rate).setScale(2, RoundingMode.DOWN).
- fee2 = principal.multiply(rate).setScale(2, RoundingMode.HALF_UP).

### Fixture
At least one tie: 12.345 with even preceding digit 4, and -12.345. Expected output from COBOL.

### Detection
100 percent on cases where the generator produces at least one tie with an even preceding digit (calibrated per task 5 of the engine).

## Trap 3: COMP-3 sign nibble

### Problem statement
Packed decimal sign nibble F is read as positive by GnuCOBOL (evidence file) but may be treated as negative or rejected by a Java port that follows strict BCD rules. Note: GnuCOBOL reads nibble B as positive, while IBM documentation treats B as negative. This is a known GnuCOBOL vs IBM difference.

Generated and certified cases use only the preferred sign nibbles: C for positive, D for negative, and F for unsigned fields. Non-preferred nibbles (B, A, E and others) are excluded from certified cases. This limitation is documented in the README and never claimed to match z/OS behavior.

### COBOL design
- Input: HEX-VALUE (10 characters, hex digits representing 5 packed bytes with amount and 2 decimals).
- WORKING-STORAGE: a field populated with FUNCTION HEX-TO-CHAR(HEX-VALUE), redefined as PIC S9(7)V99 COMP-3, moved to a signed edited output field PIC +9(7).99.
- Output: CASE-ID, DECODED-VALUE.

### Faulty Java design
- Decodes hex to bytes, reads the 5 bytes with 9 digit nibbles and a sign nibble: C positive, D negative, F negative (or rejects).

### Correct Java design
- Decodes the 5 bytes as packed decimal: 9 digit nibbles (high and low nibbles of the first 4.5 bytes) plus the sign nibble (low nibble of the last byte), interpreting the sign nibble: C positive, D negative, F positive, B positive (matches GnuCOBOL; document in a comment that IBM documentation treats B as negative, GnuCOBOL differs, and certified cases use only C, D, F).

### Fixture
At least 3 hex values: one with C, one with D, one with F. Expected output from COBOL.

### Detection
100 percent on cases where the generator emits at least one F sign nibble.

## Trap 4: Zoned decimal overpunch

### Problem statement
Mainframe extract files use the EBCDIC overpunch convention to encode signed zoned decimals: "}" = -0, "J" to "R" = -1 to -9, "{" = +0, "A" to "I" = +1 to +9. A Java port that applies the ASCII convention (or strips the last character) reads the wrong sign or value.

### COBOL design (compiles with -fsign=EBCDIC)
- Input: ZONED-VALUE (6 characters, text form of a signed zoned decimal using EBCDIC overpunch).
- WORKING-STORAGE: PIC X(6) redefined as PIC S9(5), moved to a signed edited output field.
- Output: CASE-ID, DECODED-VALUE.
- Compile flags: `-fsign=EBCDIC` (verified behavior in docs/evidence/gnucobol-encodings.md: "1234}" reads -12340 and "1234M" reads -12344 under -fsign=EBCDIC).

### Engine extension for per-program compile flags
- schema.json declares: "cobc_flags": ["-fsign=EBCDIC"]
- The engine applies these flags to the reference build and the coverage build (in addition to the default `-x -Wall -I`).
- inputs.json records cobc_flags (so they are part of the certificate content, covered by certificate_sha256).
- Certificate replay checks that the recorded flags match the current flags.
- Other traps compile without additional flags (no other non-default flag).

### Faulty Java design
- Applies the ASCII convention (negative last digit + 0x40, for example "1234u" = -12345) or strips the last character.

### Correct Java design
- Applies the EBCDIC overpunch table (evidence file): "}" = -0, "J" = -1, "R" = -9, "{" = +0, "A" = +1, "I" = +9.

### Fixture
At least 2 values: "12345}" (= -12340 in EBCDIC overpunch) and "12345" (= +12345). Expected output from COBOL.

### Detection
100 percent on cases where the generator emits at least one negative value with the EBCDIC convention.

## Trap 5: REDEFINES of invalid numeric data

### Problem statement
GnuCOBOL reads an alphanumeric field with non-digit characters through a REDEFINES as PIC 9(n), using the low nibble of each byte as the digit value (evidence file: "12A45" where A is 0x41, low nibble 1, is read as 12145, so + 1 = 12146 with no abend). A Java port may reject the record or treat it as zero, diverging from the reference behavior.

Wording: Coroner reports the behavior change, it does not judge which side is right (the COBOL behavior is permissive, the Java rejection may be a valid business rule).

### COBOL design
- Input: ALPHA-VALUE (5 characters).
- WORKING-STORAGE: PIC X(5) redefined as PIC 9(5).
- COMPUTE OUTPUT-VALUE = REDEF-NUMERIC + 1.
- Output: CASE-ID, OUTPUT-VALUE.

### Faulty Java design
- Rejects non-digit characters (throws an exception or writes 0).

### Correct Java design
- Reads the low nibble of each byte, matching GnuCOBOL (A=0x41, low nibble 1; J=0x4A, low nibble 10 with carry).

### Fixture
At least 2 values: "12A45" (A is 0x41, low nibble 1, read as 12145, output 12146) and "12345" (output 12346). Expected output from COBOL.

### Detection
100 percent on cases where the generator emits at least one invalid numeric value.

## Trap 6: Reserved for owner field trap

Status: placeholder until the owner provides a real field trap. The catalog runner lists it with status "placeholder: owner field trap pending", not measured, never with numbers.

## Catalog runner

### Module: coroner/traps.py

```python
def run_catalog(seed=42, cases=2000):
    """Run the trap catalog on all built traps, write runs/trap_catalog.json and text."""
    results = []
    for trap_id in ["T1", "T2", "T3", "T4", "T5"]:
        trap_dir = f"samples/traps/{trap_id}-{slug}/"
        if not os.path.exists(trap_dir):
            continue
        # Run on faulty Java
        faulty_verdict = run_verify(cobol=trap_dir + "*.cob", java=trap_dir + "java/faulty/*.java", schema=trap_dir + "schema.json", seed=seed, cases=cases)
        # Run on correct Java
        correct_verdict = run_verify(cobol=trap_dir + "*.cob", java=trap_dir + "java/correct/*.java", schema=trap_dir + "schema.json", seed=seed, cases=cases)
        # Extract fields
        results.append({
            "id": trap_id,
            "title": trap_title,
            "status": "measured",
            "cases_generated": cases,
            "cases_detected": count_divergences(faulty_verdict),
            "detection_rate": detection_rate,
            "minimal_case": faulty_verdict.failure_report.minimal_case if faulty_verdict.status == "ZOMBIE" else None,
            "cobol_lines": faulty_verdict.failure_report.cobol_lines if faulty_verdict.status == "ZOMBIE" else None,
            "probable_cause": probable_cause_from_trap(trap_id),
            "suggested_fix": suggested_fix_from_trap(trap_id),
            "given_when_then": generate_card(faulty_verdict.failure_report.minimal_case),
            "correct_java_verdict": correct_verdict.status,
            "exposure": faulty_verdict.exposure if trap_id == "T1" else None,
        })
    # T6 placeholder
    results.append({"id": "T6", "title": "Reserved for owner field trap", "status": "placeholder: owner field trap pending"})
    # Write JSON and text
    write_json("runs/trap_catalog.json", results)
    write_text("runs/trap_catalog.txt", render_catalog(results))
```

### Probable cause and suggested fix per trap
- T1: "Faulty Java sorts by ASCII String.compareTo instead of EBCDIC byte order. Use IBM1047 Charset or a custom Comparator."
- T2: "Faulty Java uses HALF_EVEN where COBOL has ROUNDED (default HALF_UP). Use RoundingMode.HALF_UP."
- T3: "Faulty Java treats sign nibble F as negative or rejects it. GnuCOBOL reads F as positive."
- T4: "Faulty Java decodes A-I and J-R correctly but forgets the two zero overpunch characters { (+0) and } (-0). Add the two zero overpunch characters to the decoding table: { is +0 and } is -0."
- T5: "Faulty Java rejects invalid numeric data under REDEFINES. GnuCOBOL reads the low nibble of each byte (A=x41 becomes 1, J=x4A becomes 10 with carry)."
- T6: placeholder, no fix.

## Given/When/Then card generation (D-43)

Deterministic template from the minimal case:
```
Given [input field 1 = value 1], [input field 2 = value 2], ...
When [operation from the trap title]
Then COBOL output [field = value]
But Java produced [field = value]
```

Example for T1 minimal case (CASE-ID MIN-01, BRANCH a01, AMOUNT 100.00):
```
Given CASE-ID MIN-01, BRANCH a01, AMOUNT 100.00
When matching transactions with EBCDIC collating sequence
Then COBOL output BRANCH a01, SUBTOTAL 100.00
But Java produced BRANCH SUSP, SUBTOTAL 100.00
```

No LLM. The card is written as a header comment in ZombieRegressionTest.java and shown in the UI.

## MCP tool: get_detection_matrix

Wrapper in coroner/mcp.py:
```python
@server.call_tool()
async def get_detection_matrix(arguments: dict) -> list[TextContent]:
    path = "runs/trap_catalog.json"
    if not os.path.exists(path):
        raise ValueError("Trap catalog not built yet. Run `make traps` first.")
    with open(path) as f:
        catalog = json.load(f)
    # Render as text or structured content
    return [TextContent(type="text", text=json.dumps(catalog, indent=2))]
```

## Documentation updates

### README
After "What Coroner is not":
```
## Six banking migration traps

Coroner demonstrates detection of six banking migration traps that silently corrupt amounts, signs, ordering or control totals:
1. EBCDIC vs ASCII collating sequence breaks control-break subtotals while the grand total matches (lead demo).
2. Rounding mode divergence (ROUNDED ported as HALF_EVEN instead of HALF_UP).
3. COMP-3 sign nibble (F read as positive by GnuCOBOL, may be rejected by Java; generated cases use only preferred nibbles C, D, F).
4. Zoned decimal overpunch (ASCII convention vs EBCDIC table).
5. Invalid numeric data under REDEFINES (GnuCOBOL reads the low nibble of each byte, Java may reject).
6. Reserved for owner field trap.

See samples/traps/ and `make traps`.

These are targeted regression traps within the supported COBOL subset, not general COBOL coverage.

Limitations: COMP-3 sign nibbles B, A, E and other non-preferred nibbles are excluded from certified cases (GnuCOBOL reads B as positive, IBM documentation as negative).
```

### architecture.md
Under "Modules":
```
- `coroner/traps.py`: trap catalog runner, Detection Matrix generation, Given/When/Then cards.
```

Under "Repository layout":
```
### Trap catalog
- `samples/traps/T1-ebcdic-match-merge/`
- `samples/traps/T2-rounding/`
- `samples/traps/T3-comp3-sign/`
- `samples/traps/T4-zoned-overpunch/`
- `samples/traps/T5-redefines-invalid/`
- `samples/traps/T6-reserved/`
```

### Makefile
```makefile
traps:
	python -m coroner traps
```

## Acceptance criteria
1. Every trap T1 to T5 gives ZOMBIE on its faulty Java with at least one detected case (detection_rate > 0) and ALIVE on its correct Java.
2. T1 shows divergent subtotals with a matching TOTAL row and non-zero exposure (verified with measured numbers: TOTAL rows are equal, at least one branch subtotal differs).
3. runs/trap_catalog.json and runs/trap_catalog.txt are written with all required fields.
4. `@coroner/get_detection_matrix` returns the matrix in a Kiro session.
