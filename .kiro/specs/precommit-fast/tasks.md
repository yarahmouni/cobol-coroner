# Pre-commit fast mode tasks

## Task 1: Makefile target `precommit`
**Requirements**: 4.1, 4.2

Add the `precommit` target to `Makefile`:
- Reads `CORONER_PRECOMMIT_JAVA` (default `samples/credit-fees/java/CreditFees.java`)
- Calls `.venv/bin/python -m coroner verify` with demo sample paths, 500 cases, seed 42
- Uses the same engine code as `make demo`

**Done when**: `make precommit` runs and exits 0 on correct Java, non-zero on HALF_EVEN variant.

## Task 2: Hook logic (coroner/hooks.py precommit command)
**Requirements**: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.12

Add `precommit` command to `coroner/hooks.py`:
- Load scope from `.kiro/coroner-scope.json`
- Get staged files using `git diff --cached --name-only`
- If no scope files staged, print "Coroner pre-commit: no audited file staged" and exit 0
- Create temporary directory under `build/precommit/`
- Export staged versions of all scope files using `git show :<path>` (copybooks directory exported file by file)
- Run verify with 500 cases, seed 42 on exported files
- Clean up temporary directory
- Parse verdict and duration from verify output
- Exit 0 on ALIVE with message, exit 1 on ZOMBIE with block message

**Done when**: `python -m coroner.hooks precommit` runs the staged-content check correctly.

## Task 3: Shell wrapper (.githooks/pre-commit)
**Requirements**: 3.1, 3.9, 3.11

Update `.githooks/pre-commit`:
- Keep the guard check first
- Check `.venv/bin/python` exists
- Call `.venv/bin/python -m coroner.hooks precommit` instead of `make precommit`
- Exit with the status from the Python command
- Shell script with `set -eu`, no output parsing

**Done when**: Hook runs, allows ALIVE, blocks ZOMBIE on staged content.

## Task 4: Tests (tests/test_precommit_fast.py)
**Requirements**: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6

Write tests:
- Create a temporary Git repository with scope files committed
- Test (a): stage HALF_EVEN variant, working tree has correct Java, hook blocks (exit 1)
- Test (b): stage correct Java, working tree has HALF_EVEN variant, hook allowed (exit 0)
- Test (c): no scope file staged, hook allowed without running check
- Subprocess with timeout 30 s
- Mark slow if combined time exceeds 30 s

**Done when**: `pytest tests/test_precommit_fast.py` passes; all tests verify staged vs working-tree behavior.

## Task 5: Documentation
**Requirements**: 7.1, 7.2

Update README:
- Add Git pre-commit hook to "The full chain" section
- Mention 500-case fast check on staged content, blocks ZOMBIE
- Document `--no-verify` bypass honestly

**Done when**: README shows the hook as part of the chain with honest bypass documentation.

## Task 6: Verification
Run:
- Create a test commit with staged HALF_EVEN: blocked
- Create a test commit with staged correct Java: allowed
- `.venv/bin/pytest -q tests/test_precommit_fast.py tests/test_hooks.py`
- Full test suite: `.venv/bin/pytest -q`

**Done when**: All tests pass, hook verifies staged content correctly.

---

## Coverage

| Requirement | Task |
|-------------|------|
| 3.1 Guard first | 3 |
| 3.2 Staged content | 2 |
| 3.3 No scope file staged | 2 |
| 3.4 Export staged files | 2 |
| 3.5 Index version for unstaged | 2 |
| 3.6 Allow ALIVE | 2 |
| 3.7 Block ZOMBIE/error | 2 |
| 3.8 ALIVE message | 2 |
| 3.9 Missing venv check | 3 |
| 3.10 Under 20 s | 2, 6 |
| 3.11 No bypass variable, document --no-verify | 5 |
| 3.12 Python logic, thin shell wrapper | 2, 3 |
| 4.1 make precommit | 1 |
| 4.2 CORONER_PRECOMMIT_JAVA | 1 |
| 5.1 Test with temp Git repo | 4 |
| 5.2 Test staged HALF_EVEN blocked | 4 |
| 5.3 Test staged correct allowed | 4 |
| 5.4 Test no scope staged allowed | 4 |
| 5.5 Subprocess timeout | 4 |
| 5.6 Mark slow if needed | 4 |
| 7.1 README chain | 5 |
| 7.2 Document --no-verify | 5 |
