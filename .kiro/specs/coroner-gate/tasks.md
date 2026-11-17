# Coroner gate tasks

## Task 1: Module coroner/gate.py (audit mode)
**Requirements**: 3.1, 3.2, 3.3, 3.6

Create `coroner/gate.py` with functions:
- `run_gate(scope_path, java_override, cases, seed, certificate_path, junit_path) -> int`: main entry point
- `run_audit_and_gate(scope, java_path, cases, seed, base_dir) -> tuple`: run verify as subprocess, parse run_id from output, load certificate from `runs/<run_id>/certificate.json`, replay certificate, return verdict, run_id, replay_result
- Handle exit code 2 from verify (ERROR: reference did not run)
- Print measured values only: "Gate: ALIVE on N cases, certificate VALID (run <run_id>)" or failure messages
- Print paths relative to repo root, no home paths

Reuse:
- `coroner.hooks.load_scope()` for scope loading
- `coroner.certificate.replay_certificate()` for replay
- `coroner.hooks.get_repo_root()` for path resolution

**Done when**: `python -m coroner.gate` (as a module) runs audit mode and returns correct exit codes for ALIVE/ZOMBIE/ERROR.

## Task 2: Module coroner/gate.py (certificate mode)
**Requirements**: 3.4, 3.5, 3.6

Add to `coroner/gate.py`:
- `gate_certificate(cert_path, scope, base_dir) -> tuple`: load certificate JSON, compute current file hashes for scope files, compare with certificate's recorded hashes, replay certificate, return verdict, replay_result, hash_match
- Handle missing certificate file (exit 1 "certificate missing")
- Handle hash mismatch (exit 1 "certificate does not match the audited files")
- Handle invalid replay (exit 1 "certificate invalid")
- Handle ZOMBIE verdict (exit 1 "ZOMBIE on N of M cases")

Reuse:
- `coroner.hooks.compute_file_hash()` and `compute_directory_hash()` for hash comparison
- `coroner.certificate.replay_certificate()` for replay

**Done when**: `python -m coroner.gate --certificate <path>` gates existing certificates correctly.

## Task 3: JUnit XML report
**Requirements**: 3.7

Add to `coroner/gate.py`:
- `write_junit_report(junit_path, passed, message)`: write JUnit XML with one test "coroner_gate" in testsuite "coroner"
- Use `xml.etree.ElementTree` to generate the XML
- On pass: empty testcase
- On fail: `<failure message="...">...</failure>` inside testcase

**Done when**: `python -m coroner.gate --junit report.xml` writes a valid JUnit XML file.

## Task 4: CLI integration (coroner/cli.py)
**Requirements**: 3.1

Add `gate` subcommand to `coroner/cli.py`:
- Parser with options: `--scope` (default `.kiro/coroner-scope.json`), `--java`, `--cases` (default 2000), `--seed` (default 42), `--certificate`, `--junit`
- Call `coroner.gate.run_gate()` with parsed arguments
- Exit with the returned exit code

**Done when**: `python -m coroner gate --help` shows the gate options; `python -m coroner gate` runs without errors.

## Task 5: Makefile changes
**Requirements**: 4.1, 4.2, 4.3, 4.4

Modify `Makefile`:
- Add variable `PYTHON ?= .venv/bin/python` at the top
- DO NOT change existing targets; use `$(PYTHON)` in the new coroner-gate target only
- Add target `coroner-gate:` that runs `$(PYTHON) -m coroner gate $(GATE_ARGS)`

**Done when**: `make coroner-gate` runs with `.venv/bin/python`; `make coroner-gate PYTHON=python3` uses system python3; existing targets unchanged.

## Task 6: GitHub Actions workflow
**Requirements**: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8

Create `.github/workflows/coroner-gate.yml`:
- Job "gate": builds Docker image with `--platform linux/amd64`, runs `python3 -m coroner gate` inside container with `CORONER_BASE_DIR=/tmp/coroner-runs` (the image has no `make`)
- Job "block": builds image with `--platform linux/amd64`, runs ONE `docker run --platform linux/amd64 ... sh -c` call that generates HALF_EVEN variant and runs `python3 -m coroner gate --java /tmp/CreditFees.java` (both under `/tmp` in the container; the image runs as user coroner, a bind-mounted build/ may not be writable), asserts exit code is exactly 1 AND output contains "ZOMBIE" (an ERROR exit 2 must fail the job)
- Permissions: `contents: read`
- Pin actions by SHA (copy from `.github/workflows/test.yml`):
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
  - `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0` (if needed)
- All docker build and run commands use `--platform linux/amd64`
- No secrets uploaded, no artifacts

**Done when**: Workflow file is valid YAML; jobs defined with correct steps; block job captures gate exit code correctly.

## Task 7: Jenkinsfile
**Requirements**: 6.1, 6.2, 6.3, 6.4, 6.5

Create `Jenkinsfile` at repository root:
- Comment: "Example Jenkinsfile for running Coroner gate in CI. Not executed by this repository's CI."
- Declarative pipeline: `pipeline { agent any; stages { ... } }`
- Stage "Build": `docker build --platform linux/amd64 -t coroner:ci .`
- Stage "Gate": run `python3 -m coroner gate --junit /tmp/gate.xml` as the container command so docker's exit code is the gate's exit code; use `--name coroner-gate-${BUILD_NUMBER}` (without `--rm`)
- Post always: `docker cp` the report from container to host, `docker rm -f` the container, then publish JUnit with `junit` step
- Shell exit code of the gate is preserved (build fails on non-zero)

**Done when**: `Jenkinsfile` exists with valid Groovy syntax; contains `pipeline {` and `junit`; post section copies and removes container.

## Task 8: Tests (basic gate behavior)
**Requirements**: 7.1, 7.2, 7.3, 7.11, 7.12, 7.13, 7.14

Create `tests/test_gate.py`:
- Test (a): gate on correct credit-fees exits 0, output first-word line is "Gate:" and contains "ALIVE" and "VALID" (use 200 cases, under 5 s, default run)
- Test (b): gate with `--java` on HALF_EVEN variant exits 1, output first-word line is "Gate:" and contains "ZOMBIE" (mark `@pytest.mark.slow`)
- All tests use `tmp_path` as `CORONER_BASE_DIR` via environment variable
- All tests use `sys.executable` for Python
- All tests run subprocess with timeout
- No writes to repository's `runs/` directory
- Assert exact first-word output lines: "Gate: ALIVE", "Gate: ZOMBIE"

**Done when**: `pytest tests/test_gate.py::test_gate_alive tests/test_gate.py::test_gate_zombie_slow -v` passes.

## Task 9: Tests (certificate mode)
**Requirements**: 7.4, 7.5, 7.6, 7.11, 7.12, 7.13, 7.14

Add to `tests/test_gate.py`:
- Test (c): gate with `--certificate` on missing file exits 1, output first-word line is "Gate: certificate missing" (default run, static test)
- Test (d): gate with `--certificate` on tampered certificate (status edited without rehash) exits 1, output first-word line is "Gate: certificate invalid" (mark `@pytest.mark.slow`)
- Test (e): gate with `--certificate` on a certificate whose Java hash differs from current scope exits 1, output first-word line is "Gate: certificate does not match the audited files" (mark `@pytest.mark.slow`)
- All use `tmp_path`, `sys.executable`, subprocess with timeout
- Assert exact first-word output lines: "Gate: certificate missing", "Gate: certificate invalid", "Gate: certificate does not match the audited files"

**Done when**: `pytest tests/test_gate.py -k certificate -v` passes.

## Task 10: Tests (JUnit, module-scoped fixture, and static checks)
**Requirements**: 7.7, 7.8, 7.9, 7.10, 7.11, 7.13, 7.14

Add to `tests/test_gate.py`:
- Create a module-scoped fixture `real_cert_run` that runs one audit (200 cases, seed 42) and returns the certificate path
- Test (f): gate with `--junit` on ALIVE writes XML with one passing test; gate on ZOMBIE writes XML with one failing test (mark `@pytest.mark.slow`); load XML with `xml.etree.ElementTree` and assert test count, pass/fail status
- Test (g): static check that every `uses:` line in `.github/workflows/*.yml` is pinned to a 40-character hex SHA (default run)
- Test (h): static check that `Jenkinsfile` exists, contains `pipeline {` and `junit` (default run)
- Test (i): default-run test using the module-scoped fixture that gates a real certificate, asserts output first-word line is "Gate: ALIVE", if this completes in under 5 s; otherwise mark `@pytest.mark.slow` and document in tasks.md which test is slow

**Exact output lines to assert** (all test first words and exact substring matches):
- "Gate: ALIVE" (on ALIVE verdict)
- "Gate: ZOMBIE" (on ZOMBIE verdict)
- "Gate: certificate missing" (missing cert file)
- "Gate: certificate invalid" (invalid cert or failed replay)
- "Gate: certificate does not match the audited files" (hash mismatch)

**Done when**: `pytest tests/test_gate.py -v` runs test_gate_alive, test_gate_certificate_real (fast or slow as documented), test_github_actions_pinned, test_jenkinsfile_exists; `pytest tests/test_gate.py -m slow` runs all slow tests and passes.

## Task 11: Documentation
**Requirements**: 8.1, 8.2

Update README:
- Add section "CI gate" after "Demo" with what it checks, exit codes, how to run, D-38 wording

Update `docs/architecture.md`:
- Add one line in "Modules" section: `coroner/gate.py: CI gate that checks verdict and certificate validity.`

**Done when**: README and architecture.md mention the gate.

## Task 12: Time budget and verification
**Requirements**: 7.2, 7.3

Add to tasks.md:

**Time budget**: The gate on 2000 cases must finish in under 120 s in the Docker image (to be measured during real implementation and test verification, not assumed).

**Done when**: 
- `make coroner-gate` exits 0 on correct Java (2000 cases), finishes in under 120 s inside the image
- `make coroner-gate GATE_ARGS="--java <HALF_EVEN>"` exits 1 with "ZOMBIE" in output (2000 cases), finishes in under 120 s inside the image
- `pytest tests/test_gate.py -q` all tests pass
- Check workflow YAML is valid: `cat .github/workflows/coroner-gate.yml`
- Check Jenkinsfile exists and is valid: `cat Jenkinsfile`
- Slow test marker: document in tasks.md if test_gate_certificate_real runs slow (over 5 s)

---

## Coverage

| Requirement | Task |
|-------------|------|
| 3.1 CLI options | 4 |
| 3.2 Audit mode: run and replay | 1 |
| 3.3 Exit codes audit mode | 1 |
| 3.4 Certificate mode | 2 |
| 3.5 Exit codes certificate mode | 2 |
| 3.6 Output format | 1, 2 |
| 3.7 JUnit report | 3 |
| 4.1 PYTHON variable | 5 |
| 4.2 coroner-gate target | 5 |
| 4.3 Docker override | 5 |
| 4.4 GATE_ARGS | 5 |
| 5.1 to 5.7 GitHub Actions | 6 |
| 6.1 to 6.5 Jenkinsfile | 7 |
| 7.1 Test file | 8 |
| 7.2 Test ALIVE | 8 |
| 7.3 Test ZOMBIE | 8 |
| 7.4 Test missing cert | 9 |
| 7.5 Test tampered cert | 9 |
| 7.6 Test hash mismatch | 9 |
| 7.7 Test JUnit | 10 |
| 7.8 Test actions pinned | 10 |
| 7.9 Test Jenkinsfile | 10 |
| 7.10 to 7.12 Test constraints | 8, 9, 10 |
| 8.1 README | 11 |
| 8.2 architecture.md | 11 |
