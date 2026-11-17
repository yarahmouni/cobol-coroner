# Coroner gate requirements

## 1. Purpose
A CI gate that blocks merges when a Java migration is ZOMBIE, missing a certificate, or has an invalid certificate. Coroner is a behavioral regression gate, not a SonarQube replacement.

## 2. Scope
New CLI subcommand `coroner gate`, GitHub Actions workflow, example Jenkinsfile, and supporting tests.

## 3. CLI: coroner gate
**Req 3.1**: New subcommand `python -m coroner gate` with options:
- `--scope PATH` (default `.kiro/coroner-scope.json`): scope file naming the audited migration
- `--java PATH` (optional): override the Java path from scope (for negative tests)
- `--cases N` (default 2000): number of test cases
- `--seed N` (default 42): random seed
- `--certificate PATH` (optional): gate an existing certificate instead of running a new audit
- `--junit PATH` (optional): write a JUnit XML report of the gate result

**Req 3.2**: Without `--certificate`: run a new audit on the scope, write the certificate, then replay it. Exit 0 only if verdict is ALIVE AND replay is VALID.

**Req 3.3**: Exit codes without `--certificate`:
- 0: ALIVE and VALID
- 1: ZOMBIE (print "Gate: ZOMBIE on N of M cases (run <run_id>)")
- 1: certificate missing after audit (print "Gate: certificate missing")
- 1: certificate invalid after audit (print "Gate: certificate invalid (run <run_id>)")
- 2: ERROR verdict, reference did not run (print "Gate: ERROR: reference did not run (run <run_id>)")
- 2: scope file missing or unreadable (print "Gate: scope file error: <reason>")

**Req 3.4**: With `--certificate PATH`: replay the certificate without running a new audit.

**Req 3.5**: Exit codes with `--certificate`:
- 0: verdict ALIVE and replay VALID
- 1: certificate file missing (print "Gate: certificate missing")
- 1: replay not VALID (print "Gate: certificate invalid")
- 1: verdict is ZOMBIE (print "Gate: ZOMBIE on N of M cases")
- 1: certificate file hashes do not match current scope files (print "Gate: certificate does not match the audited files")

**Req 3.6**: Output prints only measured values from the run: verdict line, cases, divergent cases, run id, replay result. No home paths printed; paths are relative to the repository root.

**Req 3.7**: When `--junit PATH` is given, write a JUnit XML report with one test "coroner_gate" that passes (verdict ALIVE and replay VALID) or fails (all other exit codes).

## 4. Makefile target
**Req 4.1**: New variable `PYTHON ?= .venv/bin/python` added to the Makefile (do not change existing targets; use it in the new coroner-gate target only).

**Req 4.2**: New target `coroner-gate:` runs `$(PYTHON) -m coroner gate $(GATE_ARGS)`.

**Req 4.3**: The target allows `make coroner-gate PYTHON=python3` for the Docker image (no venv inside).

**Req 4.4**: Optional variable `GATE_ARGS` can pass additional arguments (for example `GATE_ARGS="--cases 200"`).

## 5. GitHub Actions workflow
**Req 5.1**: New file `.github/workflows/coroner-gate.yml` runs on push and pull_request.

**Req 5.2**: Permissions: `contents: read` only.

**Req 5.3**: Job "gate" builds the Docker image with `--platform linux/amd64` and runs `make coroner-gate PYTHON=python3` inside it.

**Req 5.4**: The container runs with `CORONER_BASE_DIR` pointing to a writable temporary directory (for example `/tmp/coroner-runs`).

**Req 5.5**: Job "block": generates the HALF_EVEN variant inside ONE `docker run ... sh -c` call, runs the gate inside the SAME `docker run` call, and asserts exit code is exactly 1 AND the output contains "ZOMBIE". The variant and gate output are written under `/tmp` in the container (the image runs as user coroner; a bind-mounted build/ may not be writable). An ERROR exit 2 must fail the job.

**Req 5.6**: All `uses:` actions and `docker build / docker run` use `--platform linux/amd64`.

**Req 5.7**: All `uses:` actions are pinned by full 40-hex SHA, copied exactly from `.github/workflows/test.yml`:
- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
- `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0`

**Req 5.8**: No secrets uploaded, no artifact containing run directories.

## 6. Jenkinsfile
**Req 6.1**: New file `Jenkinsfile` at the repository root, declarative Groovy pipeline.

**Req 6.2**: Comment at the top: "Example Jenkinsfile for running Coroner gate in CI. Not executed by this repository's CI."

**Req 6.3**: Stages:
- Build: `docker build --platform linux/amd64 -t coroner:ci .`
- Gate: run the gate container with `--name coroner-gate-${BUILD_NUMBER}` (without `--rm`), write the JUnit file under `/tmp` in the container, then in `post always`: `docker cp` the report out, `docker rm -f` the container.

**Req 6.4**: The shell exit code of the gate is preserved so the build fails on non-zero.

**Req 6.5**: The Jenkinsfile uses standard declarative syntax: `pipeline { agent any; stages { ... } }`.

## 7. Tests
**Req 7.1**: File `tests/test_gate.py` with real runs, no mocks, no unconditional skips.

**Req 7.2**: Test (a): gate on correct credit-fees exits 0. Use 200 cases to keep the test fast (under 5 s).

**Req 7.3**: Test (b): gate with `--java` on the HALF_EVEN variant exits 1 with "ZOMBIE" in output. Mark with `@pytest.mark.slow` (owner rule: default suite tests must take under 5 s).

**Req 7.4**: Test (c): gate with `--certificate` on a missing file exits 1 with "certificate missing" (default run, static test).

**Req 7.5**: Test (d): gate with `--certificate` on a tampered copy of a real certificate exits 1 with "certificate invalid". Mark with `@pytest.mark.slow`.

**Req 7.6**: Test (e): gate with `--certificate` on a certificate whose Java hash differs from the current scope exits 1 with "does not match". Mark with `@pytest.mark.slow`.

**Req 7.7**: Test (f): gate with `--junit` writes a JUnit XML file with one test that passes on ALIVE and fails on ZOMBIE. Mark with `@pytest.mark.slow`.

**Req 7.8**: Static test: every `uses:` line in `.github/workflows/*.yml` is pinned to a 40-character hex SHA (default run).

**Req 7.9**: Static test: `Jenkinsfile` exists, contains `pipeline {`, and contains `junit` (default run).

**Req 7.10**: Add one default-run test that gates a real certificate produced by a module-scoped fixture, asserting the exact first-word output line ("Gate: ALIVE"), if this test completes in under 5 s; otherwise mark it slow and document in tasks.md which test is slow.

**Req 7.11**: All tests use `tmp_path` as `CORONER_BASE_DIR` via environment variable.

**Req 7.12**: All tests use `sys.executable` for Python paths, never `.venv/bin/python`.

**Req 7.13**: Tests never write to the repository's `runs/` directory.

**Req 7.14**: Assert the exact first-word output lines in every test: "Gate: ALIVE", "Gate: ZOMBIE", "Gate: certificate missing", "Gate: certificate invalid", "Gate: certificate does not match the audited files".

## 8. Documentation
**Req 8.1**: README new section "CI gate" (short, after "Demo"):
- What it checks: ALIVE verdict and VALID certificate
- Three exit reasons: ZOMBIE, missing certificate, invalid certificate
- How to run locally: `make coroner-gate`
- D-38 wording: "Coroner is a behavioral regression gate, not a SonarQube replacement."

**Req 8.2**: `docs/architecture.md` mentions the gate in the Modules section: one line for `coroner/gate.py`.

## 9. Constraints
- No new script file in `scripts/` or at the repository root.
- No duplication of certificate replay logic (reuse `coroner/certificate.py` functions).
- Scope loading reuses `coroner/hooks.py` `load_scope()`.
- Docker image already has GnuCOBOL, Java and the package installed; no venv inside the image.
- The Makefile already uses `.venv/bin/python`; introduce `PYTHON` variable to allow override.
- Jenkinsfile syntax is Groovy, not YAML.
