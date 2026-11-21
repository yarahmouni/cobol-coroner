# CardDemo CBACT04C Tasks

## Task 1: Verify Harness Requirements Against Probes

**Requirements**: Check that the harness design can replicate the three probe outputs before any code is written.

**Done when**: For each of the three probe datasets (upstream-sample, probe-nonzero, missing-default), the harness contract (one input row with accounts, catbals, rates) can produce the same:
- Interest amounts (from probe/*/transact.txt)
- Updated balances (from probe/*/acctdata-after.txt)
- Exit code (from probe/*/exit-code.txt or 0 when not present)

**Measurable**: Compare the probe outputs line by line with what the harness will extract.

---

## Task 2: Write adapted/HARNESS-CBACT04C.cob

**Requirements**: Write the harness program that wraps CBACT04C for differential testing.

**Done when**:
- adapted/HARNESS-CBACT04C.cob exists
- Compiles with `cobc -x -Wall -Iupstream/cpy -o build/carddemo/HARNESS-CBACT04C adapted/HARNESS-CBACT04C.cob`
- The helper programs (LOAD-FILES, RUN-CBACT04C, DUMP-ACCT) are already built in build/carddemo/ by the Makefile
- Accepts INPUT_FILE and OUTPUT_FILE environment variables (the engine's standard interface)
- Reads one input CSV row per case (CASE-ID, PARM-DATE, 5 accounts x 7 fields, 10 catbals x 4 fields, 20 rates x 4 fields; no EXIT-CODE-EXPECTED)
- Writes text files (tcatbal.txt, cardxref.txt, acctdata.txt, discgrp.txt) to a temporary directory under TMPDIR or the current directory (not fixed /tmp/cbact04c-<CASE-ID>/)
- Calls LOAD-FILES, RUN-CBACT04C, DUMP-ACCT through CALL "SYSTEM" with correct environment variables and paths
- Reads transact.txt (350-byte records) and DUMP-ACCT output
- Writes one output CSV row (CASE-ID, EXIT-CODE, 5 updated balances x 3 fields, 10 transactions x 9 fields, NUM-TRANSACTIONS)
- Cleans up the temporary directory after each case

**Measurable**: `INPUT_FILE=test-one-case.csv OUTPUT_FILE=harness-output.csv build/carddemo/HARNESS-CBACT04C` exits and harness-output.csv contains header and one data row with all fields.

---

## Task 3: Check Harness Against Probe Outputs

**Requirements**: Run the harness on two probe datasets and verify it gives the same results as the recorded probe outputs.

**Done when**:
- Two test input CSV files (one row each) written: harness-check/probe-nonzero.csv and harness-check/missing-default.csv under samples/carddemo-cbact04c/
- Each row built from the text files in datasets/probe-nonzero/ and datasets/missing-default/
- Harness run on each: `INPUT_FILE=harness-check/<probe>.csv OUTPUT_FILE=harness-check/<probe>-harness.csv build/carddemo/HARNESS-CBACT04C`
- For probe-nonzero: exit code 0, 7 transactions, amounts and balances match probe/probe-nonzero/transact.txt and probe/probe-nonzero/acctdata-after.txt
- For missing-default: exit code 231 (from probe/missing-default/exit-code.txt), 0 transactions

**Measurable**: The extracted amounts, balances and exit codes match the recorded probe outputs (comparison by eye or a check script; timestamps are deterministic from PARM-DATE).

---

## Task 4: Write schema.json

**Requirements**: Write schema.json with generator_script pointing to samples/carddemo-cbact04c/generator.py.

**Done when**:
- samples/carddemo-cbact04c/schema.json exists
- Contains program "CBACT04C", description, generator_script path
- Input columns: CASE-ID, PARM-DATE, ACCT-ID-1 to ACCT-ID-5, ACCT-GROUP-ID-1 to 5, ACCT-CURR-BAL-1 to 5, ACCT-CURR-CYC-CREDIT-1 to 5, ACCT-CURR-CYC-DEBIT-1 to 5, XREF-CARD-NUM-1 to 5, XREF-EXISTS-1 to 5, CATBAL-ACCT-INDEX-1 to 10, CATBAL-TYPE-1 to 10, CATBAL-CAT-1 to 10, CATBAL-BAL-1 to 10, RATE-GROUP-1 to 20, RATE-TYPE-1 to 20, RATE-CAT-1 to 20, RATE-VALUE-1 to 20
- Output columns: CASE-ID, EXIT-CODE, UPDATED-BAL-1 to 5, UPDATED-CYC-CREDIT-1 to 5, UPDATED-CYC-DEBIT-1 to 5, TX-1-ID to TX-10-ID, TX-1-TYPE to TX-10-TYPE, TX-1-CAT to TX-10-CAT, TX-1-SOURCE to TX-10-SOURCE, TX-1-DESC to TX-10-DESC, TX-1-AMT to TX-10-AMT, TX-1-CARD-NUM to TX-10-CARD-NUM, TX-1-ORIG-TS to TX-10-ORIG-TS, TX-1-PROC-TS to TX-10-PROC-TS, NUM-TRANSACTIONS
- Each column has type (string, decimal, integer), pic, description

**Measurable**: `python3 -c "from coroner.parse.schema import load_schema; s = load_schema('samples/carddemo-cbact04c/schema.json'); print(s.program)"` prints "CBACT04C".

---

## Task 5: Write generator.py

**Requirements**: Write the generator script that produces CardDemo test cases with edge cases.

**Done when**:
- samples/carddemo-cbact04c/generator.py exists
- Defines `def generate_cases(schema, rng: random.Random, num_cases: int) -> list[dict]:`
- Generates num_cases rows, each with:
  - 1 to 5 accounts with IDs 10000000001 to 10000000005, groups drawn from ['GROUP01', 'GROUP02', 'DEFAULT'], balances drawn by magnitude (negative, zero, positive), cycle credit/debit drawn by magnitude, card numbers 16 digits, XREF-EXISTS 90% 'Y', 10% 'N'
  - 1 to 10 category balances, CATBAL-ACCT-INDEX 1 to num_accounts (the actual count), type '01', category 0001 to 0010, balance drawn by magnitude (signed)
  - 5 to 20 rates, RATE-GROUP including DEFAULT for 70% of cases, type '01', category 0001 to 0010, value 0.00 to 25.00
- Uses only rng.random() for draws (per D-30)
- Does not compute or fill EXIT-CODE-EXPECTED (expected results come only from running the COBOL)

**Measurable**: `python3 -c "from samples.carddemo_cbact04c.generator import generate_cases; import random; cases = generate_cases(None, random.Random(42), 10); print(len(cases), cases[0]['CASE-ID'])"` prints "10 GEN-000001".

---

## Task 6: Extend Engine for generator_script

**Requirements**: Extend coroner/gen/__init__.py to call an external generator script when schema.generator_script is present.

**Done when**:
- coroner/gen/__init__.py generate_cases checks `if hasattr(schema, 'generator_script') and schema.generator_script:`
- If true, verifies the script path resolves (after resolving symlinks) inside the directory containing schema.json, else raises RuntimeError with ERROR verdict
- If verified, imports the script module and calls its generate_cases(schema, rng, num_cases)
- If false, uses existing generate_cases logic
- schema.py Schema dataclass gains `generator_script: str | None = None` and `file_path: str` (to know the schema directory)
- load_schema reads the optional "generator_script" key from JSON and records the schema file path

**Measurable**: With schema.json pointing to generator.py, the engine calls the script and generates cases.

**Test**: tests/test_generator_script_security.py creates a schema.json with generator_script pointing to /tmp/evil.py and asserts the run fails with RuntimeError.

---

## Task 7: Kiro Agent Generates Java Port

**Requirements**: A Kiro agent ports adapted/CBACT04C.cob to Java 17.

**Done when**:
- Prompt written (I/O contract from schema.json, Java 17, BigDecimal for money, RoundingMode explicit; no hint about the formula or rounding)
- Full spec .kiro/specs/carddemo-cbact04c/ given to the agent
- Agent produces samples/carddemo-cbact04c/java/Cbact04cInterest.java (or similar name)
- Java compiles with `javac -d build/carddemo samples/carddemo-cbact04c/java/*.java`
- Java reads INPUT_FILE and OUTPUT_FILE from environment
- Java implements the same CSV contract as the harness (one row in, one row out)
- Prompt, spec and full transcript saved in docs/evidence/carddemo-cbact04c-port.txt

**Measurable**: `INPUT_FILE=test-one-case.csv OUTPUT_FILE=java-output.csv java -cp build/carddemo Cbact04cInterest` exits 0 and java-output.csv contains one data row.

---

## Task 8: Run Differential Audit at 200 Cases

**Requirements**: Run `coroner verify` with the harness and the Kiro-generated Java on 200 generated cases.

**Done when**:
- Generator produces 200 cases (seed 42) into samples/carddemo-cbact04c/datasets/audit-200/generated_cases.csv
- Harness compiles and runs with HARNESS_INPUT=generated_cases.csv, HARNESS_OUTPUT=cobol_output.csv
- Java compiles and runs with INPUT_FILE=generated_cases.csv, OUTPUT_FILE=java_output.csv
- `python3 -m coroner verify --cobol adapted/HARNESS-CBACT04C.cob --copybooks upstream/cpy --java java/Cbact04cInterest.java --schema schema.json --cases 200 --seed 42` completes
- Verdict is ALIVE or ZOMBIE (no ERROR)
- Exit code 0 (ALIVE) or 1 (ZOMBIE)
- runs/<run_id>/verdict.json contains status, cases_total 200, cases_divergent (0 for ALIVE, >0 for ZOMBIE)

**Measurable**: Command output shows "ALIVE: PASS: business behavior preserved on 200 cases" or "ZOMBIE: FAIL: business behavior diverged on M cases" (M >= 1).

**Measured per-case time**: The probe runs one case in well under a second. A 200-case audit should complete in under 2 minutes.

---

## Task 9: Update CHANGES.md and README

**Requirements**: Document the harness and audit.

**Done when**:
- samples/carddemo-cbact04c/CHANGES.md gains a "5. HARNESS-CBACT04C.cob: Audit harness for differential testing" line under "Additions"
- samples/carddemo-cbact04c/README.md includes the required public wording verbatim:
  - "Uses AWS's open-source CardDemo sample (Apache 2.0). Not affiliated with or endorsed by AWS."
  - "This preserves the business logic under audit; it does not emulate z/OS VSAM."
  - Verdict wording: "no behavioral difference across the tested scenarios; not a certification for all inputs."
- Never claims "audits CardDemo" or "all programs"

**Measurable**: `grep "Uses AWS" samples/carddemo-cbact04c/README.md` finds the required sentence.

---

## Task 10: tests/test_carddemo_audit.py

**Requirements**: Write a test that runs the 200-case audit and checks the verdict.

**Done when**:
- tests/test_carddemo_audit.py exists
- Test compiles the harness and Java, generates 200 cases (seed 42), runs both, compares outputs
- Asserts verdict is ALIVE or ZOMBIE (not ERROR)
- Asserts cases_total == 200
- If ZOMBIE, asserts cases_divergent > 0 and failure_report.json exists

**Measurable**: `pytest tests/test_carddemo_audit.py -v` shows 1 passed.
