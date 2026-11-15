# Pre-commit fast mode implementation summary

## Files created
1. `.kiro/specs/precommit-fast/requirements.md` - Specification requirements
2. `.kiro/specs/precommit-fast/design.md` - Detailed design
3. `.kiro/specs/precommit-fast/tasks.md` - Task breakdown
4. `tests/test_precommit_fast.py` - Test suite

## Files modified
1. `Makefile` - Added `precommit` target
2. `.githooks/pre-commit` - Extended with fast differential check
3. `README.md` - Updated "The full chain" section

## Implementation details

### Makefile target: precommit
- Reads `CORONER_PRECOMMIT_JAVA` environment variable (default: demo Java)
- Runs `coroner verify` with 500 cases, seed 42, on demo sample
- Exits 0 on ALIVE, non-zero on ZOMBIE/error

### Git hook: .githooks/pre-commit
- Keeps existing guard check (runs first)
- Checks `.venv/bin/python` exists
- Runs `make precommit` with timing measurement
- Parses output for verdict (ALIVE/ZOMBIE/error)
- Prints clear message with timing and run_id
- Documents `--no-verify` bypass
- Shell script with `set -eu`, no pipes or semicolons for command chaining

### Tests: tests/test_precommit_fast.py
- Test (a): correct Java exits 0, prints ALIVE, includes "on N cases"
- Test (b): HALF_EVEN variant exits non-zero, prints ZOMBIE
- Uses subprocess with 30 s timeout
- Not marked slow (expected under 30 s combined)

### Documentation: README.md
- Added Git pre-commit hook details to "The full chain"
- Documents 500-case fast check
- Documents `--no-verify` bypass honestly

## No new root files
All implementation follows architecture.md Repository layout:
- No new scripts in `scripts/` or at root
- Hook logic embedded in `.githooks/pre-commit`
- Tests in `tests/`
- Makefile target in existing `Makefile`

## Testing status
Ready to test with:
- `make precommit` (should be ALIVE, under 20 s)
- `CORONER_PRECOMMIT_JAVA=build/variants/CreditFees.java make precommit` (should be ZOMBIE)
- `.venv/bin/pytest -q tests/test_precommit_fast.py`
- `.venv/bin/pytest -q` (full suite)
