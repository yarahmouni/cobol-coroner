# Pre-commit fast mode design

## 1. Overview
Extend `.githooks/pre-commit` to run a fast 500-case differential check on the demo sample after the guard passes. Block commits when ZOMBIE, allow when ALIVE, refuse when errored.

## 2. Hook structure
The hook runs two checks in sequence:

1. **Guard check** (existing): `python scripts/precommit_guard.py`
   - Blocks files with home paths and unlisted root/script files
   - Already exits 1 on failure

2. **Fast differential check** (new): calls the engine via a Makefile target
   - 500 cases, seed 42, demo sample
   - Under 20 s
   - Exits 0 on ALIVE, 1 on ZOMBIE or error

Both checks must pass for the commit to proceed.

## 3. Makefile target: precommit
```makefile
precommit:
	JAVA_FILE=$${CORONER_PRECOMMIT_JAVA:-samples/credit-fees/java/CreditFees.java}; \
	.venv/bin/python -m coroner verify \
		--cobol samples/credit-fees/CREDIT-FEES.cob \
		--copybooks samples/credit-fees/copybooks \
		--java "$$JAVA_FILE" \
		--schema samples/credit-fees/schema.json \
		--cases 500 \
		--seed 42
```

- Default Java: `samples/credit-fees/java/CreditFees.java`
- Override via `CORONER_PRECOMMIT_JAVA` (for testing against variants)
- Uses the same `coroner verify` CLI as `make demo`

## 4. Hook script (.githooks/pre-commit)
Shell structure:
```bash
#!/bin/bash
set -eu

# Check 1: Guard
python scripts/precommit_guard.py
if [ $? -ne 0 ]; then
  exit 1
fi

# Check 2: Fast differential
if [ ! -x .venv/bin/python ]; then
  echo "Error: .venv/bin/python not found. Run: python3.12 -m venv .venv && .venv/bin/pip install -e \".[dev]\""
  exit 1
fi

START_TIME=$(date +%s)
OUTPUT=$(make precommit 2>&1)
EXIT_CODE=$?
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

RUN_ID=$(echo "$OUTPUT" | grep -o 'run [a-f0-9]*' | head -1)

if [ $EXIT_CODE -eq 0 ]; then
  # ALIVE
  CASES=$(echo "$OUTPUT" | grep -o 'on [0-9]* cases' | head -1)
  echo "Coroner pre-commit: ALIVE $CASES in $ELAPSED.0 s"
  exit 0
elif echo "$OUTPUT" | grep -q "ZOMBIE"; then
  # ZOMBIE
  CASES=$(echo "$OUTPUT" | grep -o 'on [0-9]* cases' | head -1)
  echo "Coroner pre-commit: ZOMBIE $CASES in $ELAPSED.0 s ($RUN_ID)"
  echo "Commit blocked. Run 'git commit --no-verify' to bypass (owner's responsibility)."
  exit 1
else
  # Error
  echo "Coroner pre-commit: check errored in $ELAPSED.0 s"
  echo "$OUTPUT"
  exit 1
fi
```

Design choices:
- Capture both stdout and stderr with `2>&1` to parse verdict
- Extract run_id with grep
- Print clear verdict message with timing
- Document `--no-verify` bypass without judgment
- No command chaining (each command on its own line, only variable assignment uses `;` within shell variable syntax)

## 5. Tests
File: `tests/test_precommit_fast.py`

### Test (a): correct Java, ALIVE
```python
def test_precommit_alive():
    result = subprocess.run(
        ["make", "precommit"],
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "ALIVE" in output
    # Extract timing
    match = re.search(r'(\d+\.\d+) s', output)
    if match:
        elapsed = float(match.group(1))
        assert elapsed < 20.0
```

### Test (b): HALF_EVEN variant, ZOMBIE
```python
def test_precommit_zombie():
    env = os.environ.copy()
    env["CORONER_PRECOMMIT_JAVA"] = "build/variants/CreditFees.java"
    result = subprocess.run(
        ["make", "precommit"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "ZOMBIE" in output
```

If combined test time exceeds 30 s, mark with `@pytest.mark.slow`.

## 6. No new files
- No new script in `scripts/`
- No helper script at the root
- Hook logic embedded in `.githooks/pre-commit` (shell)
- Makefile target added to existing `Makefile`

## 7. Documentation updates
### README
Add to "The full chain" section (already has the tagline):
```markdown
The Git pre-commit hook runs a fast 500-case check on the demo sample and blocks ZOMBIE commits. Use `git commit --no-verify` to bypass (owner's responsibility).
```

### Makefile help (if it exists)
Add `precommit` to the target list.

## 8. Integration with existing engine
No code duplication:
- Uses `coroner verify` CLI (entry point: `coroner/cli.py`)
- Same engine modules: parse, gen, run, compare, verdict, store, diag
- Same fixed seed and case count as acceptance tests
- Output format already includes verdict and run_id

## 9. Performance target
Measured on the dev machine (macOS, S1 acceptance timing):
- Correct Java: 4 to 6 s for 2,000 cases
- 500 cases: under 3 s expected
- Guard: under 0.5 s
- Total: under 20 s (requirement met with margin)

## 10. Error handling
- `.venv/bin/python` missing: clear message, exit 1
- Engine error (schema missing, compilation failure): print output, exit 1
- Parsing failure: treated as error, exit 1
