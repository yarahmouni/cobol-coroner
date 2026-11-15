# Pre-commit fast mode verification checklist

## Requirements coverage

### Req 3.1: Hook runs guard first
✓ `.githooks/pre-commit` line 5: `.venv/bin/python scripts/precommit_guard.py`

### Req 3.2: Fast check with 500 cases, seed 42
✓ `Makefile` precommit target: `--cases 500 --seed 42`

### Req 3.3: Demo sample paths
✓ `Makefile` precommit target uses:
  - `--cobol samples/credit-fees/CREDIT-FEES.cob`
  - `--copybooks samples/credit-fees/copybooks`
  - `--java` (via CORONER_PRECOMMIT_JAVA variable)
  - `--schema samples/credit-fees/schema.json`

### Req 3.4: Allow ALIVE (exit 0)
✓ `.githooks/pre-commit` lines 19-22: exits 0 when EXIT_CODE is 0

### Req 3.5: Block ZOMBIE/error (exit 1)
✓ `.githooks/pre-commit` lines 23-33: exits 1 on ZOMBIE or error, prints verdict and run_id

### Req 3.6: Check .venv/bin/python exists
✓ `.githooks/pre-commit` lines 8-11: checks executable, prints clear error message

### Req 3.7: Under 20 s, print timing
✓ `.githooks/pre-commit` lines 13-16: measures elapsed time
✓ Lines 21, 26: prints "in ${ELAPSED}.0 s"

### Req 3.8: No bypass variable, document --no-verify
✓ No bypass variable added
✓ `.githooks/pre-commit` line 27: documents --no-verify
✓ `README.md` line 84: documents --no-verify as owner's responsibility

### Req 3.9: Same engine code as make demo
✓ Uses `coroner verify` CLI (same as demo)
✓ No duplicated logic

### Req 4.1: make precommit target
✓ `Makefile` lines 30-32: precommit target added to .PHONY and implemented

### Req 4.2: CORONER_PRECOMMIT_JAVA variable
✓ `Makefile` line 31: reads variable with default

### Req 5.1: Test via make precommit
✓ `tests/test_precommit_fast.py` lines 9, 34: uses subprocess.run(["make", "precommit"])

### Req 5.2: Test ALIVE
✓ `tests/test_precommit_fast.py` lines 8-23: test_precommit_alive()

### Req 5.3: Test ZOMBIE
✓ `tests/test_precommit_fast.py` lines 26-48: test_precommit_zombie() with env override

### Req 5.4: Mark slow if needed
✓ Tests use 30 s timeout, not marked slow (expected under 30 s combined)

### Req 7.1: README chain section
✓ `README.md` lines 80-84: describes the full chain

### Req 7.2: Document --no-verify
✓ `README.md` line 84: honest bypass documentation

## Constraints compliance

### No new script files
✓ No files in `scripts/`
✓ No files at repository root (except specs in .kiro/)

### No Git commands in hook logic
✓ Hook runs make precommit, no git commands

### No file deletion
✓ No rm or deletion commands

### Shell commands run alone
✓ Hook uses proper shell variable assignment
✓ Only `2>&1` redirection in subshell
✓ No semicolons for command chaining (only in variable assignment syntax)

### Use .venv/bin/python
✓ All Python invocations use `.venv/bin/python`

### Shell script uses set -eu
✓ `.githooks/pre-commit` line 2: `set -eu`

### No em dash character
✓ All files checked, no em dash

### No "first", "unique", "novel", "proves", "proven", "guaranteed"
✓ All files checked, forbidden words not present

## Test commands to run

1. `make precommit` (should be ALIVE, under 20 s)
2. `CORONER_PRECOMMIT_JAVA=build/variants/CreditFees.java make precommit` (should be ZOMBIE)
3. `.venv/bin/pytest -q tests/test_precommit_fast.py`
4. `.venv/bin/pytest -q` (full suite)

## Expected outputs

### make precommit (ALIVE)
```
ALIVE: PASS: business behavior preserved on 500 cases
Paragraph coverage 12/12
Branch coverage (Coroner definition) 42/70
Validated under GnuCOBOL 3.x
Run: runs/<run_id>
Duration: N.N s
```
Exit code: 0

### make precommit (ZOMBIE)
```
ZOMBIE: FAIL: business behavior diverged on M cases
Paragraph coverage 12/12
Branch coverage (Coroner definition) 42/70
Validated under GnuCOBOL 3.x
Run: runs/<run_id>
Duration: N.N s
```
Exit code: 1

### Hook output (ALIVE)
```
Coroner pre-commit: ALIVE on 500 cases in N.0 s
```

### Hook output (ZOMBIE)
```
Coroner pre-commit: ZOMBIE on M cases in N.0 s (runs/<run_id>)
Commit blocked. Run 'git commit --no-verify' to bypass (owner's responsibility).
```
