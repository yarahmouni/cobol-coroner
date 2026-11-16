# EBCDIC/control-break demo design

Priority 9 (D-33, D-34, D-45).

## Overview

This spec fixes five engine bugs exposed by T1 (multi-row cases) and adds an integrated demo command that shows the EBCDIC/control-break trap with measured numbers only.

## Design decisions

### Multi-row minimal case reduction (Req 1)

**Problem**: The existing minimal-case selection picks the case with the smallest numeric input values, but for multi-row cases (case_rows in schema.json) it keeps only one row per case. A one-row subset of a control-break case cannot show the divergence.

**Solution**: When case_rows is present and a case diverges, apply delta reduction to the case's input rows:

1. Start with all rows of the divergent case (sorted by case id for determinism).
2. Try removing each row in turn. For each candidate subset, write a temporary CSV, run both programs on it, and compare.
3. If the subset still diverges, keep the removal. Otherwise revert.
4. Stop when no row can be removed.
5. Assert that the final subset diverges (exit status or output difference).
6. If the final subset does not diverge, raise an error: "Minimal case reduction failed: final subset does not diverge".

The failure_report.json gains two fields:
- `original_case_rows`: all rows of the full case (array of row objects with every input column).
- `minimal_case_rows`: the reduced subset (array, may equal original if irreducible).

Existing `minimal_case_input_csv` is written with the minimal subset only. The JUnit test uses the minimal subset.

The reduction runs both programs per candidate, so it has O(N) re-runs where N is the row count of the original case. For T1 with typical batch sizes under 100 rows per case, this is acceptable (under 200 runs). A case with 1000 rows would take longer; document the limitation.

### Row-level divergence description (Req 2)

**Problem**: The comparator treats multi-row outputs as a single "row" field with "present"/"missing" when rows are unequal, losing the output key information.

**Solution**: When output_key is declared in schema.json, the comparator matches rows by output_key value. A divergence is described using the output key and both values exactly as written by the programs.

The comparison already matches rows by output key (since trap-catalog task 1). The bug is in how divergences are reported to failure_report.json and the card. Fix: `coroner/compare.py` must return structured divergences with the output key value and position, not a generic "row" field.

A case diverges if any of its output rows differ (missing, extra or value mismatch). The divergence count (262 for run 92a9f12d2aaa) is the number of cases with at least one divergent row. This count does not change.

### Multi-row Given/When/Then card (Req 3)

**Problem**: The existing card generator assumes one input row per case.

**Solution**: When case_rows is present:

- **Given**: "Case CASE-ID with N input rows: [list each row as a comma-separated line of input values, or a compact table if rows > 5]".
- **When**: "both programs process the batch".
- **Then**: "COBOL returns BRANCH=001 SUBTOTAL=+123.45 and Java returns BRANCH=001 SUBTOTAL=+100.00" (one sentence per divergent output key, up to 3 divergences shown).

COBOL lines involved: for schemas with group_key, include the lines that perform ordering or comparison (IF statements, SORT, EVALUATE on the group key), plus the lines that compute the divergent field (COMPUTE, MOVE, ADD). The existing trace already includes these lines; the card module filters them by relevance to the divergent output column.

### JUnit test verification (Req 4)

**Problem**: The operator found that the generated JUnit test may not compile or may not correctly reproduce the divergence.

**Solution**: The existing JUnit test generation already writes a test that runs the Java main class with a temporary CSV and asserts the output. For multi-row cases, the test CSV contains the minimal subset rows.

Add a verification step to the engine: after writing ZombieRegressionTest.java, compile it with `javac` (classpath: faulty Java classes and JUnit jar), run it with `java org.junit.platform.console.ConsoleLauncher` (must fail), then compile and run against the correct Java classes (must pass). If either behavior is wrong, raise an error: "JUnit test verification failed: expected failure on faulty port but got success" or vice versa.

The verification runs only when both a faulty and correct Java path are known. For a single verify run, the test is generated but not verified (no error). The trap catalog runner provides both paths, so verification happens there. The demo command also provides both paths.

**Note**: This feature is deferred to hardening (Nov 25-27) and not part of priority 9. The demo script will manually compile and run the JUnit test as part of its workflow, which provides equivalent verification without modifying the engine.

### Integrated demo command (Req 5)

A shell script `scripts/demo_ebcdic.sh` orchestrates the demo:

```bash
#!/bin/bash
set -e

BASE_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$BASE_DIR"

TRAP_DIR=samples/traps/T1-ebcdic-match-merge
SCHEMA=$TRAP_DIR/schema.json
COBOL=$TRAP_DIR/ebcdic-match-merge.cob
COPYBOOKS=$TRAP_DIR/copybooks
FAULTY_JAVA=$TRAP_DIR/faulty/EbcdicMatchMerge.java
CORRECT_JAVA=$TRAP_DIR/correct/EbcdicMatchMerge.java

echo "=== Running faulty port (2000 cases, seed 42) ==="
python -m coroner verify --cobol "$COBOL" --copybooks "$COPYBOOKS" \
  --java "$FAULTY_JAVA" --schema "$SCHEMA" --cases 2000 --seed 42 || true

RUN_ID=$(ls -t runs/ | head -1)
CERT=runs/$RUN_ID/certificate.json
JUNIT_TEST=runs/$RUN_ID/ZombieRegressionTest.java
CARD=runs/$RUN_ID/card.txt

if [ ! -f "$CERT" ]; then
  echo "ERROR: No certificate found for faulty run"
  exit 1
fi

# Check verdict is ZOMBIE
VERDICT=$(jq -r .verdict.status "$CERT")
if [ "$VERDICT" != "ZOMBIE" ]; then
  echo "ERROR: Expected ZOMBIE, got $VERDICT"
  exit 1
fi

echo ""
echo "=== Given/When/Then card ==="
cat "$CARD"

echo ""
echo "=== Compiling and running JUnit test against faulty port ==="
FAULTY_BUILD=build/junit_demo_faulty
mkdir -p "$FAULTY_BUILD"
javac -d "$FAULTY_BUILD" "$FAULTY_JAVA"
javac -cp "$FAULTY_BUILD:build/junit/junit-platform-console-standalone-6.1.3.jar" \
  -d "$FAULTY_BUILD" "$JUNIT_TEST"
java -jar build/junit/junit-platform-console-standalone-6.1.3.jar \
  --class-path "$FAULTY_BUILD" --select-class ZombieRegressionTest \
  --fail-if-no-tests || FAULTY_EXIT=$?

if [ "$FAULTY_EXIT" -ne 1 ]; then
  echo "ERROR: JUnit test should fail on faulty port but exited $FAULTY_EXIT"
  exit 1
fi
echo "JUnit test failed as expected on faulty port."

echo ""
echo "=== Compiling and running JUnit test against correct port ==="
CORRECT_BUILD=build/junit_demo_correct
mkdir -p "$CORRECT_BUILD"
javac -d "$CORRECT_BUILD" "$CORRECT_JAVA"
javac -cp "$CORRECT_BUILD:build/junit/junit-platform-console-standalone-6.1.3.jar" \
  -d "$CORRECT_BUILD" "$JUNIT_TEST"
java -jar build/junit/junit-platform-console-standalone-6.1.3.jar \
  --class-path "$CORRECT_BUILD" --select-class ZombieRegressionTest \
  --fail-if-no-tests || CORRECT_EXIT=$?

if [ "$CORRECT_EXIT" -ne 0 ]; then
  echo "ERROR: JUnit test should pass on correct port but exited $CORRECT_EXIT"
  exit 1
fi
echo "JUnit test passed as expected on correct port."

echo ""
echo "=== Replaying certificate ==="
python -m coroner verify "$CERT" | grep "Certificate: VALID" || {
  echo "ERROR: Certificate replay did not show VALID"
  exit 1
}

echo ""
echo "=== Running correct port (2000 cases, seed 42) ==="
python -m coroner verify --cobol "$COBOL" --copybooks "$COPYBOOKS" \
  --java "$CORRECT_JAVA" --schema "$SCHEMA" --cases 2000 --seed 42 || {
  echo "ERROR: Correct port verification failed"
  exit 1
}

CORRECT_RUN_ID=$(ls -t runs/ | head -1)
CORRECT_VERDICT=$(jq -r .verdict.status "runs/$CORRECT_RUN_ID/verdict.json")
if [ "$CORRECT_VERDICT" != "ALIVE" ]; then
  echo "ERROR: Expected ALIVE for correct port, got $CORRECT_VERDICT"
  exit 1
fi

echo ""
echo "=== Demo complete: all steps passed ==="
exit 0
```

Makefile target:

```make
demo-ebcdic:
	bash scripts/demo_ebcdic.sh
```

The script reads the verdict status from certificate.json with `jq`, so jq is a new runtime dependency (already available on macOS and in the Docker image).

### Test coverage (Req 6)

Fast tests:

1. `test_multirow_reduction`: Test the reducer on a real divergent T1 case: extract rows from one divergent case from a small faulty T1 run (200 cases, seed 42), reduce by actually running the T1 COBOL program and the faulty Java port, assert the result diverges on a re-run and that removing any single row of the result makes it stop diverging (1-minimality), assert determinism (same result twice). Also test with a correct-port case (non-divergent input must raise an error).
2. `test_row_divergence_description`: Test comparison with output_key on real T1 outputs, assert divergence message names the output key and values exactly as written by the programs.
3. `test_multirow_card`: Generate a card from a small T1 failure report, assert Given lists the rows, Then names the branch values.

Slow test:

4. `test_demo_ebcdic_integration` (marked slow): Run `make demo-ebcdic` and assert exit 0. Record the measured duration.

### README demo section (Req 7)

Add to README.md after the "Trap catalog" section:

```markdown
## Demo

The EBCDIC/control-break demo shows trap T1 with a faulty Java port, the minimal case, the JUnit regression test, certificate replay, then the correct port:

```bash
make demo-ebcdic
```

(Operator: measured output to be added here after the first run.)
```

The operator runs `make demo-ebcdic` after the spec is built and pastes the verdict blocks, card and pass/fail lines into the placeholder.

## Files changed

### New
- `scripts/demo_ebcdic.sh`: orchestrates the demo sequence.
- `tests/test_multirow_minimal.py`: shrinker, row description, card tests on real T1 cases.
- `tests/test_demo_ebcdic.py`: slow integration test.

### Modified
- `coroner/diag/minimal.py`: add `reduce_multirow_case` function.
- `coroner/diag/failure.py`: call the reducer when case_rows is present, write `original_case_rows` and `minimal_case_rows` to failure_report.json.
- `coroner/diag/card.py`: detect case_rows and generate multi-row Given/Then.
- `coroner/compare.py`: return structured row-level divergences with output_key values.
- `Makefile`: add `demo-ebcdic` target.
- `README.md`: add Demo section.
- `pyproject.toml`: no new dependencies (jq is external, not a Python package).

### Deferred to hardening (Nov 25-27)
- `coroner/diag/junit.py`: add `verify_junit_test` function.
- `coroner/traps.py`: call the JUnit verifier after generating tests.

## Edge cases

- A case with only one row cannot be reduced further: original and minimal are equal.
- A case where every row is necessary: same.
- A case where the reduction produces an empty set: error, never write the report.
- Schema without case_rows: existing minimal-case logic unchanged.
- Schema without output_key: row divergences described by position only, not by key value.

## Limitations

- The reduction is greedy (tries rows in order), not exhaustive. A case with 100 rows and 10 necessary rows may try 90 removals. Documented in the README limitation: "Multi-row minimal case reduction is greedy and may take several minutes for cases with hundreds of rows."
- The JUnit verification requires both faulty and correct Java paths. A standalone `coroner verify` run generates the test but does not verify it.
