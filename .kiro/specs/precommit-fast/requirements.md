# Pre-commit fast mode requirements

## 1. Purpose
A Git pre-commit hook that runs a fast differential check on the demo sample to block commits when the migration is ZOMBIE, preventing broken code from entering the repository.

## 2. Scope
Extends the existing `.githooks/pre-commit` (which already runs `scripts/precommit_guard.py`).

## 3. Hook behavior
**Req 3.1**: The hook runs the guard first (existing behavior), then runs the fast differential check.

**Req 3.2**: The fast check audits the STAGED content, not the working tree. It reads the scope from `.kiro/coroner-scope.json`.

**Req 3.3**: If no scope files (COBOL, copybooks, Java, schema) are staged, the hook prints "Coroner pre-commit: no audited file staged" and allows (exit 0).

**Req 3.4**: If any scope file is staged, the hook exports the staged version of every scope file using `git show :<path>` into a temporary directory, runs `.venv/bin/python -m coroner verify` on those exported files with 500 cases and seed 42, then removes the temporary directory.

**Req 3.5**: For unstaged scope files, the hook uses the index version (also from `git show :<path>`), so the check reflects exactly what will be committed.

**Req 3.6**: Commit allowed when verdict is ALIVE (hook exits 0).

**Req 3.7**: Commit refused when verdict is ZOMBIE or the check errors (hook exits 1), with the message "Commit blocked by Coroner: <verdict line>. See <run dir>/failure_report.json. Fix the Java port, then run run_differential_check again."

**Req 3.8**: On ALIVE, prints "Coroner pre-commit: <verdict line> (Duration: N.N s)".

**Req 3.9**: If `.venv/bin/python` is missing, the hook refuses with a message stating how to create it.

**Req 3.10**: Hook time under 20 s on the dev machine (measured from the Duration line in the verify output).

**Req 3.11**: No bypass variable added. Document Git's own `--no-verify` honestly as the owner's responsibility.

**Req 3.12**: The hook logic lives in `coroner/hooks.py` as a `precommit` command (`.venv/bin/python -m coroner.hooks precommit`). The shell script `.githooks/pre-commit` is a thin wrapper. No duplicated logic between the shell and Python.

## 4. Makefile target
**Req 4.1**: `make precommit` runs the same fast check without committing, for local testing.

**Req 4.2**: The target reads an optional environment variable `CORONER_PRECOMMIT_JAVA` to override the Java file path (default: `samples/credit-fees/java/CreditFees.java`). This allows testing against the HALF_EVEN variant.

## 5. Tests
**Req 5.1**: `tests/test_precommit_fast.py` creates a temporary Git repository with the scope files, stages different versions, and tests the hook.

**Req 5.2**: Test (a): staged HALF_EVEN variant with a correct working tree is blocked (exit 1).

**Req 5.3**: Test (b): staged correct Java with a HALF_EVEN working tree is allowed (exit 0).

**Req 5.4**: Test (c): no scope file staged is allowed without running the check.

**Req 5.5**: Tests use subprocess with timeout 30 s.

**Req 5.6**: Tests marked slow if they take more than 30 s together.

## 6. Constraints
- No new script file in `scripts/` or at the repository root (architecture.md Repository layout rule).
- The hook logic (coroner/hooks.py precommit command) may call git commands to read staged content.
- No file deletion from repository, temporary directories are cleaned up.
- Shell commands run alone (no pipes, no semicolons for command chaining) in the shell wrapper.
- Use `.venv/bin/python` explicitly.
- Shell script uses `set -eu`.

## 7. Documentation
**Req 7.1**: README mentions the Git pre-commit hook as part of "The full chain".

**Req 7.2**: Document `--no-verify` as a bypass available to the owner, with no judgment wording.
