# Pre-commit fast mode requirements

## 1. Purpose
A Git pre-commit hook that runs a fast differential check on the demo sample to block commits when the migration is ZOMBIE, preventing broken code from entering the repository.

## 2. Scope
Extends the existing `.githooks/pre-commit` (which already runs `scripts/precommit_guard.py`).

## 3. Hook behavior
**Req 3.1**: The hook runs the guard first (existing behavior), then runs the fast differential check.

**Req 3.2**: The fast check calls `.venv/bin/python -m coroner verify` on the demo sample with 500 cases and seed 42.

**Req 3.3**: Demo sample inputs:
- COBOL: `samples/credit-fees/CREDIT-FEES.cob`
- Copybooks: `samples/credit-fees/copybooks/`
- Java: `samples/credit-fees/java/CreditFees.java`
- Schema: `samples/credit-fees/schema.json`

**Req 3.4**: Commit allowed when verdict is ALIVE (hook exits 0).

**Req 3.5**: Commit refused when verdict is ZOMBIE or the check errors (hook exits 1), with one clear line stating the verdict and the run directory.

**Req 3.6**: If `.venv/bin/python` is missing, the hook refuses with a message stating how to create it.

**Req 3.7**: Hook time under 20 s on the dev machine (measured and printed as "Coroner pre-commit: ALIVE on 500 cases in N.N s" or "ZOMBIE on M cases in N.N s").

**Req 3.8**: No bypass variable added. Document Git's own `--no-verify` honestly as the owner's responsibility.

**Req 3.9**: The fast check uses the same engine code as `make demo`. No duplicated logic.

## 4. Makefile target
**Req 4.1**: `make precommit` runs the same fast check without committing, for local testing.

**Req 4.2**: The target reads an optional environment variable `CORONER_PRECOMMIT_JAVA` to override the Java file path (default: `samples/credit-fees/java/CreditFees.java`). This allows testing against the HALF_EVEN variant.

## 5. Tests
**Req 5.1**: `tests/test_precommit_fast.py` tests the hook by running `make precommit` style command lines through subprocess with a timeout.

**Req 5.2**: Test (a): on the correct Java, exits 0 and prints ALIVE with measured seconds under 20.

**Req 5.3**: Test (b): on the legacy HALF_EVEN variant (via `CORONER_PRECOMMIT_JAVA=build/variants/CreditFees.java`), exits non-zero and prints ZOMBIE.

**Req 5.4**: Tests marked slow only if they take more than 30 s together.

## 6. Constraints
- No new script file in `scripts/` or at the repository root (architecture.md Repository layout rule).
- No Git commands in the hook logic.
- No file deletion.
- Shell commands run alone (no pipes, no semicolons for command chaining).
- Use `.venv/bin/python` explicitly.
- Shell script uses `set -eu`.

## 7. Documentation
**Req 7.1**: README mentions the Git pre-commit hook as part of "The full chain".

**Req 7.2**: Document `--no-verify` as a bypass available to the owner, with no judgment wording.
