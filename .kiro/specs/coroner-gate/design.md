# Coroner gate design

## 1. Overview
The gate runs a differential audit and checks that the result is ALIVE with a VALID certificate. It blocks CI builds when the migration is ZOMBIE, the certificate is missing or invalid, or the reference did not run.

Two modes:
1. **Audit mode** (default): run `coroner verify`, then replay the produced certificate
2. **Certificate mode** (`--certificate PATH`): replay an existing certificate without running a new audit

## 2. Module structure
New file: `coroner/gate.py`

Functions:
- `run_gate(scope_path, java_override, cases, seed, certificate_path, junit_path) -> int`: main entry point, returns exit code
- `run_audit_and_gate(scope, java_path, cases, seed, base_dir) -> tuple[verdict, run_id, replay_result]`: run verify, find certificate, replay
- `gate_certificate(cert_path, scope, base_dir) -> tuple[verdict, replay_result, hash_match]`: check an existing certificate
- `write_junit_report(junit_path, passed, message)`: write JUnit XML

Design choices:
- Reuse `coroner.hooks.load_scope()` for scope loading
- Reuse `coroner.certificate.replay_certificate()` for replay
- Reuse `coroner.hooks.compute_file_hash()` and `compute_directory_hash()` for hash comparison
- New CLI entry point in `coroner/cli.py`: add `gate` subcommand

## 3. Audit mode flow
```
1. Load scope from --scope (default .kiro/coroner-scope.json)
2. Override Java path if --java given
3. Run: python -m coroner verify --cobol <cobol> --copybooks <copybooks> --java <java> --schema <schema> --cases <N> --seed <S>
4. Capture exit code and run_id from output
5. If exit code is 2 (ERROR), print "Gate: ERROR: reference did not run (run <run_id>)" and exit 2
6. Load certificate from runs/<run_id>/certificate.json
7. If certificate missing, print "Gate: certificate missing" and exit 1
8. Replay certificate: python -m coroner verify <cert_path>
9. Parse replay output for VALID/INVALID
10. If replay is not VALID, print "Gate: certificate invalid (run <run_id>)" and exit 1
11. Load verdict from certificate
12. If verdict is ZOMBIE, print "Gate: ZOMBIE on N of M cases (run <run_id>)" and exit 1
13. If verdict is ALIVE and replay VALID, print "Gate: ALIVE on N cases, certificate VALID (run <run_id>)" and exit 0
```

Exit codes:
- 0: ALIVE and VALID
- 1: ZOMBIE, missing certificate, or invalid certificate
- 2: ERROR (reference did not run) or scope file error

## 4. Certificate mode flow
```
1. Load scope from --scope
2. Check certificate file exists; if not, print "Gate: certificate missing" and exit 1
3. Load certificate JSON
4. Compute current file hashes: cobol_file_sha256, java_file_sha256, schema_file_sha256, copybook_hashes (dict: file name -> sha256)
5. Compare with certificate's recorded hashes (exact keys: cobol_file_sha256, java_file_sha256, schema_file_sha256, copybook_hashes)
6. If hashes differ, print "Gate: certificate does not match the audited files" and exit 1
7. Call coroner.certificate.replay_certificate() in-process and use its result fields
8. If replay result is not VALID, print "Gate: certificate invalid" and exit 1
9. Load verdict from certificate
10. If ZOMBIE, print "Gate: ZOMBIE on N of M cases" and exit 1
11. If ALIVE and VALID, print "Gate: ALIVE on N cases, certificate VALID" and exit 0
```

Hash comparison functions:
- Use `coroner.hooks.compute_file_hash(path)` for individual files
- Use `coroner.hooks.compute_directory_hash(directory)` for copybook directories

## 5. CLI integration (coroner/cli.py)
Add `gate` subcommand to the argument parser:
```python
gate_parser = subparsers.add_parser('gate', help='CI gate: check verdict and certificate')
gate_parser.add_argument('--scope', default='.kiro/coroner-scope.json')
gate_parser.add_argument('--java', help='Override Java path from scope')
gate_parser.add_argument('--cases', type=int, default=2000)
gate_parser.add_argument('--seed', type=int, default=42)
gate_parser.add_argument('--certificate', help='Gate an existing certificate')
gate_parser.add_argument('--junit', help='Write JUnit XML report')
```

In the main CLI function:
```python
if args.command == 'gate':
    from coroner.gate import run_gate
    exit_code = run_gate(
        args.scope, args.java, args.cases, args.seed,
        args.certificate, args.junit
    )
    sys.exit(exit_code)
```

## 6. JUnit XML format
When `--junit PATH` is given, write a JUnit XML file with one test:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="coroner" tests="1" failures="0" errors="0">
    <testcase name="coroner_gate" classname="coroner.gate">
      <!-- On success: empty -->
      <!-- On failure: <failure message="ZOMBIE on 86 of 2000 cases">...</failure> -->
    </testcase>
  </testsuite>
</testsuites>
```

Implementation: use Python's `xml.etree.ElementTree` to generate the XML.

## 7. Makefile changes
Add a variable at the top:
```makefile
PYTHON ?= .venv/bin/python
```

Change existing targets to use `$(PYTHON)` instead of `.venv/bin/python`.

Add new target:
```makefile
coroner-gate:
	$(PYTHON) -m coroner gate $(GATE_ARGS)
```

This allows:
- Host: `make coroner-gate` (uses `.venv/bin/python`)
- Docker: `make coroner-gate PYTHON=python3` (uses system python3)
- Custom args: `make coroner-gate GATE_ARGS="--cases 200"`

## 8. GitHub Actions workflow
File: `.github/workflows/coroner-gate.yml`

The workflow calls `python3 -m coroner gate` directly in the Docker image (the image has no `make` and `make` turns every gate exit code into 2).

```yaml
name: Coroner Gate

on: [push, pull_request]

permissions:
  contents: read

jobs:
  gate:
    name: Gate Check
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      
      - name: Build Docker image
        run: docker build --platform linux/amd64 -t coroner:ci .
      
      - name: Run gate (correct Java)
        run: |
          docker run --platform linux/amd64 --rm \
            -e CORONER_BASE_DIR=/tmp/coroner-runs \
            coroner:ci \
            make coroner-gate PYTHON=python3
  
  block:
    name: Gate Blocks ZOMBIE
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      
      - name: Build Docker image
        run: docker build --platform linux/amd64 -t coroner:ci .
      
      - name: Generate HALF_EVEN variant and run gate
        run: |
          docker run --platform linux/amd64 --rm \
            -e CORONER_BASE_DIR=/tmp/coroner-runs \
            coroner:ci \
            sh -c "python3 -m coroner.catalog.legacy_variant samples/credit-fees/java/CreditFees.java /tmp/CreditFees.java && \
                   make coroner-gate PYTHON=python3 GATE_ARGS='--java /tmp/CreditFees.java'"
        id: gate-zombie
      
      - name: Verify gate blocked ZOMBIE
        run: |
          if [ ${{ steps.gate-zombie.outcome }} != 'failure' ]; then
            echo "Gate did not block ZOMBIE (exit code: ${{ steps.gate-zombie.exit-code }})"
            exit 1
          fi
```

Design choices:
- Two jobs: one verifies ALIVE passes, one verifies ZOMBIE blocks
- Build image once per job (parallel jobs)
- Job "block": generate HALF_EVEN variant and run gate inside ONE `docker run ... sh -c` call
- Exit codes: gate exit 1 (ZOMBIE) must fail the step, gate exit 0 (ALIVE) must pass
- All docker commands use `--platform linux/amd64`

## 9. Jenkinsfile
File: `Jenkinsfile` at repository root

The Jenkinsfile calls `python3 -m coroner gate --junit /tmp/gate.xml` as the container command so docker's exit code is the gate's exit code.

```groovy
// Example Jenkinsfile for running Coroner gate in CI.
// Not executed by this repository's CI.

pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                sh 'docker build --platform linux/amd64 -t coroner:ci .'
            }
        }
        
        stage('Gate') {
            steps {
                sh '''
                    docker run --platform linux/amd64 \
                        --name coroner-gate-${BUILD_NUMBER} \
                        -e CORONER_BASE_DIR=/tmp/coroner-runs \
                        coroner:ci \
                        make coroner-gate PYTHON=python3 GATE_ARGS="--junit /tmp/gate.xml"
                '''
            }
        }
    }
    
    post {
        always {
            sh '''
                docker cp coroner-gate-${BUILD_NUMBER}:/tmp/gate.xml ./gate.xml || true
                docker rm -f coroner-gate-${BUILD_NUMBER} || true
            '''
            junit 'gate.xml'
        }
    }
}
```

Design choices:
- Standard declarative pipeline with `agent any`
- Build stage creates the image with `--platform linux/amd64`
- Gate stage: run with `--name` (no `--rm`), write JUnit to `/tmp` in container
- Post always: `docker cp` the report out, `docker rm -f` the container, then publish JUnit
- Shell exit code of the gate is preserved (build fails on non-zero)

## 10. Tests
File: `tests/test_gate.py`

### Test structure
All tests:
- Use `tmp_path` fixture as `CORONER_BASE_DIR`
- Use `sys.executable` for Python
- Run subprocess with timeout
- Assert exit codes and output messages

### Test (a): ALIVE passes
```python
def test_gate_alive(tmp_path):
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "gate", "--cases", "200"],
        capture_output=True, text=True, timeout=60, env=env
    )
    
    assert result.returncode == 0
    assert "ALIVE" in result.stdout
    assert "VALID" in result.stdout
```

### Test (b): ZOMBIE blocks
```python
def test_gate_zombie(tmp_path):
    # Generate HALF_EVEN variant
    variant_path = tmp_path / "CreditFees.java"
    subprocess.run([
        sys.executable, "-m", "coroner.catalog.legacy_variant",
        "samples/credit-fees/java/CreditFees.java",
        str(variant_path)
    ], check=True)
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "gate",
         "--java", str(variant_path), "--cases", "200"],
        capture_output=True, text=True, timeout=60, env=env
    )
    
    assert result.returncode == 1
    assert "ZOMBIE" in result.stdout
```

### Test (c): missing certificate
```python
def test_gate_certificate_missing(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "gate",
         "--certificate", str(tmp_path / "missing.json")],
        capture_output=True, text=True, timeout=5
    )
    
    assert result.returncode == 1
    assert "certificate missing" in result.stdout
```

### Test (d): tampered certificate
```python
def test_gate_certificate_tampered(tmp_path):
    # Run audit to create certificate
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    subprocess.run([
        sys.executable, "-m", "coroner", "verify",
        "--cobol", "samples/credit-fees/CREDIT-FEES.cob",
        "--copybooks", "samples/credit-fees/copybooks",
        "--java", "samples/credit-fees/java/CreditFees.java",
        "--schema", "samples/credit-fees/schema.json",
        "--cases", "50", "--seed", "42"
    ], env=env, check=True)
    
    # Find certificate
    run_dirs = list((tmp_path / "runs").iterdir())
    cert_path = run_dirs[0] / "certificate.json"
    
    # Tamper with status
    with open(cert_path) as f:
        cert = json.load(f)
    cert["status"] = "TAMPERED"
    
    tampered_path = tmp_path / "tampered.json"
    with open(tampered_path, "w") as f:
        json.dump(cert, f)
    
    result = subprocess.run([
        sys.executable, "-m", "coroner", "gate",
        "--certificate", str(tampered_path)
    ], capture_output=True, text=True, timeout=30, env=env)
    
    assert result.returncode == 1
    assert "invalid" in result.stdout
```

### Test (e): hash mismatch
Create a certificate with different Java, then run gate with current scope.

### Test (f): JUnit report
Run gate with `--junit`, load the XML, assert test count and pass/fail status.

### Test (g): actions pinned by SHA
```python
def test_github_actions_pinned():
    workflow_files = glob.glob(".github/workflows/*.yml")
    assert len(workflow_files) > 0
    
    for wf in workflow_files:
        with open(wf) as f:
            content = f.read()
        
        # Find all uses: lines
        uses_lines = [line for line in content.splitlines() if "uses:" in line]
        
        for line in uses_lines:
            # Extract the action reference (after uses:)
            match = re.search(r'uses:\s*([^#\s]+)', line)
            if match:
                ref = match.group(1)
                # Check if pinned by SHA (40 hex chars after @)
                if '@' in ref:
                    sha = ref.split('@')[1].split()[0]  # Handle inline comments
                    assert re.match(r'^[0-9a-f]{40}$', sha), f"Action not pinned by SHA: {line}"
```

### Test (h): Jenkinsfile exists
```python
def test_jenkinsfile_exists():
    assert os.path.exists("Jenkinsfile")
    
    with open("Jenkinsfile") as f:
        content = f.read()
    
    assert "pipeline {" in content
    assert "junit" in content
```

## 11. Documentation updates
### README
Add section after "Demo":

```markdown
## CI gate

The CI gate blocks builds when a Java migration is ZOMBIE, the certificate is missing, or the certificate is invalid.

Run locally:
```bash
make coroner-gate
```

Exit codes:
- 0: ALIVE verdict and VALID certificate
- 1: ZOMBIE verdict, missing certificate, or invalid certificate
- 2: ERROR (reference did not run) or scope file error

Coroner is a behavioral regression gate, not a SonarQube replacement.
```

### docs/architecture.md
Add to "Modules" section:
```
- `coroner/gate.py`: CI gate that checks verdict and certificate validity.
```

## 12. Performance
- Gate runs the full audit (default 2,000 cases): 5 to 15 s measured
- Certificate mode (replay only): under 5 s
- Tests use 200 or 50 cases to stay fast (under 10 s per test)

## 13. Reused code
- `coroner/hooks.py`: `load_scope()`, `compute_file_hash()`, `compute_directory_hash()`, `get_repo_root()`
- `coroner/certificate.py`: `replay_certificate()`
- `coroner/cli.py`: existing `verify` command
- `coroner/catalog/legacy_variant.py`: HALF_EVEN generation for tests

No duplication of certificate replay logic or scope loading.
