# Pre-commit fast mode tasks

## Task 1: Makefile target `precommit`
**Requirements**: 4.1, 4.2

Add the `precommit` target to `Makefile`:
- Reads `CORONER_PRECOMMIT_JAVA` (default `samples/credit-fees/java/CreditFees.java`)
- Calls `.venv/bin/python -m coroner verify` with demo sample paths, 500 cases, seed 42
- Uses the same engine code as `make demo`

**Done when**: `make precommit` runs and exits 0 on correct Java, non-zero on HALF_EVEN variant.

## Task 2: Hook script (.githooks/pre-commit)
**Requirements**: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9

Extend `.githooks/pre-commit`:
- Keep the guard check first
- Check `.venv/bin/python` exists
- Run `make precommit` with timing
- Parse output for verdict (ALIVE, ZOMBIE, error)
- Exit 0 on ALIVE, 1 on ZOMBIE or error
- Print "Coroner pre-commit: ALIVE/ZOMBIE on N cases in M.M s"
- On ZOMBIE, print run_id and document `--no-verify`
- Shell script with `set -eu`, no pipes, no semicolons for command chaining

**Done when**: Hook runs in under 20 s on the dev machine; allows ALIVE, blocks ZOMBIE.

## Task 3: Tests (tests/test_precommit_fast.py)
**Requirements**: 5.1, 5.2, 5.3, 5.4

Write tests:
- Test (a): `make precommit` with correct Java exits 0, prints ALIVE, under 20 s
- Test (b): `make precommit` with `CORONER_PRECOMMIT_JAVA=build/variants/CreditFees.java` exits non-zero, prints ZOMBIE
- Subprocess with timeout 30 s
- Mark slow if combined time exceeds 30 s

**Done when**: `pytest tests/test_precommit_fast.py` passes; both tests run in under 30 s combined.

## Task 4: Documentation
**Requirements**: 7.1, 7.2

Update README:
- Add Git pre-commit hook to "The full chain" section
- Mention 500-case fast check, blocks ZOMBIE
- Document `--no-verify` bypass honestly

**Done when**: README shows the hook as part of the chain with honest bypass documentation.

## Task 5: Verification
Run:
- `make precommit` on correct Java: ALIVE, under 20 s
- `CORONER_PRECOMMIT_JAVA=build/variants/CreditFees.java make precommit`: ZOMBIE
- `.venv/bin/pytest -q tests/test_precommit_fast.py`
- Full test suite: `.venv/bin/pytest -q`

**Done when**: All tests pass, hook timing measured under 20 s.

---

## Coverage

| Requirement | Task |
|-------------|------|
| 3.1 Guard first | 2 |
| 3.2 500 cases, seed 42 | 1, 2 |
| 3.3 Demo sample paths | 1 |
| 3.4 Allow ALIVE | 2 |
| 3.5 Block ZOMBIE/error | 2 |
| 3.6 Missing venv check | 2 |
| 3.7 Under 20 s, print timing | 2 |
| 3.8 No bypass variable, document --no-verify | 2, 4 |
| 3.9 Same engine code | 1 |
| 4.1 make precommit | 1 |
| 4.2 CORONER_PRECOMMIT_JAVA | 1 |
| 5.1 Test via make precommit | 3 |
| 5.2 Test ALIVE | 3 |
| 5.3 Test ZOMBIE | 3 |
| 5.4 Mark slow if needed | 3 |
| 7.1 README chain | 4 |
| 7.2 Document --no-verify | 4 |
