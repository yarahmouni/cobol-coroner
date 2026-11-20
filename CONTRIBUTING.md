# Contributing to COBOL Coroner

## Setup

Prerequisites: GnuCOBOL 3.2, JDK 17, Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Download JUnit jars:

```bash
make junit-jars
```

## Running Tests

Default test suite (fast tests only, under 60 seconds):

```bash
make test
```

All tests including slow ones:

```bash
make test-all
```

Acceptance tests (10-seed differential runs and trap catalog, takes about 10 minutes):

```bash
make acceptance
```

### No-Skip Rule

Tests that skip are not allowed in CI. The CI environment sets `CORONER_NO_SKIP=1`, which makes any skipped test fail instead.

This ensures every test runs in CI and no gap is hidden.

## Development Workflow

COBOL Coroner is built with spec-driven development:

1. Requirements are written in `.kiro/specs/<feature>/requirements.md`
2. Design follows in `design.md`
3. Tasks are listed in `tasks.md`
4. Code is written to implement the tasks
5. Tests verify each task

All specs and code are written by Kiro. The operator (Claude Code) reviews against `.kiro/steering/` and `docs/` before commit.

## Quality Rules

- **Reference outputs come only from running the COBOL program.** A test that compares against a hand-written expected file is rejected. Expected outputs are produced by executing the COBOL reference, never typed by hand.

- **Every commit must pass the pre-commit hook and the gate.** The pre-commit hook (`.githooks/pre-commit`) runs the precommit guard and a fast 500-case audit on the demo sample. The `make coroner-gate` command checks the full audit and certificate validity.

- **Fixed random seed everywhere.** Same inputs give the same verdict. The generator uses `random.Random(seed).random()` only; Hypothesis is for property tests only and never feeds a certificate.

- **No helper or wrapper scripts.** Temporary files go under `build/` and are never committed. A new file at the repository root or in `scripts/` must first be listed in `docs/architecture.md` (Repository layout); the pre-commit guard enforces it.

- **Business logic lives in `coroner/` modules, never in API routes, MCP handlers or the UI.**

## Commit Rules

Before committing:

1. Run `make test` (or `make test-all` if you changed code that affects slow tests)
2. Run `make demo` and `make zombie` to check the demo sample
3. Enable the pre-commit hook (first time only):

   ```bash
   git config core.hooksPath .githooks
   ```

The pre-commit hook:

- Refuses any staged file containing the home directory path
- Refuses any added file at the root or in `scripts/` not listed in `docs/architecture.md`
- Runs `coroner verify` on the demo sample (500 cases, seed 42, under 20 seconds)
- Blocks a ZOMBIE verdict

The hook audits the staged content, not the working tree.

The `git commit --no-verify` bypass is available to the owner under their responsibility.

## CI Gate

The `make coroner-gate` command checks the full audit and certificate validity. It is run in CI and fails builds on ZOMBIE, missing certificate, or invalid certificate.

## Submitting Changes

1. Open a pull request with your changes
2. All tests must pass in CI
3. The gate must pass
4. One reviewer approval required

## Questions

Open a GitHub issue for questions about contributing.
