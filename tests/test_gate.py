"""Tests for the gate module."""

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
T1_FAULTY_ID = "f584d5f35228"
CREDIT_FEES_CORRECT_ID = "df4d7929ce44"


@pytest.fixture(scope="session")
def gate_engine_runs(t1_faulty_2000, credit_fees_2000):
    """
    The two runs the certificate-matching tests rely on, made by the real engine.

    T1 faulty (ZOMBIE, exit 1, run f584d5f35228) and credit-fees correct (ALIVE, exit 0, run
    df4d7929ce44), 2000 cases, seed 42. Both are the session fixtures of tests/conftest.py (one
    temporary base shared with the other test files; the run ids are asserted there, and the
    repository runs/ folder is checked there). These tests only read the certificates.
    """
    assert t1_faulty_2000.base == credit_fees_2000.base
    return t1_faulty_2000.base / "runs"


@pytest.fixture(scope="module")
def real_cert_run(tmp_path_factory):
    """Create a real certificate run for fast tests."""
    tmp_path = tmp_path_factory.mktemp("cert_run")
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    # Run audit to create certificate
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", "samples/credit-fees/CREDIT-FEES.cob",
            "--copybooks", "samples/credit-fees/copybooks",
            "--java", "samples/credit-fees/java/CreditFees.java",
            "--schema", "samples/credit-fees/schema.json",
            "--cases", "200", "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 0, f"Setup failed: {result.stderr}"
    
    # Parse run_id from output
    run_id = None
    for line in result.stdout.splitlines():
        if line.startswith("Run: "):
            value = line.split("Run: ", 1)[1].strip()
            run_id = Path(value).name
            break
    
    assert run_id is not None, f"No run_id found in output: {result.stdout}"
    cert_path = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_path.exists(), f"Certificate not found at {cert_path}"
    
    return cert_path, tmp_path


@pytest.mark.slow
def test_gate_alive(tmp_path):
    """Test gate on correct credit-fees exits 0."""
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "gate", "--cases", "200"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert result.stdout.startswith("Gate: ALIVE")
    assert "VALID" in result.stdout
    assert "200 cases" in result.stdout


@pytest.mark.slow
def test_gate_zombie(tmp_path):
    """Test gate with HALF_EVEN variant exits 1."""
    # Generate HALF_EVEN variant
    variant_path = tmp_path / "CreditFees.java"
    subprocess.run(
        [
            sys.executable, "-m", "coroner.catalog.legacy_variant",
            "samples/credit-fees/java/CreditFees.java",
            str(variant_path)
        ],
        check=True,
        timeout=10
    )
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--java", str(variant_path),
            "--cases", "200"
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert result.stdout.startswith("Gate: ZOMBIE")
    assert " of 200 cases" in result.stdout
    
    # Load certificate and verify numbers
    import re
    match = re.search(r"run (\w+)\)", result.stdout)
    assert match, f"No run_id in output: {result.stdout}"
    run_id = match.group(1)
    
    cert_path = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_path.exists()
    
    with open(cert_path) as f:
        cert = json.load(f)
    
    cases_divergent = cert["cases_divergent"]
    cases_total = cert["cases_total"]
    
    assert cases_total == 200
    assert cases_divergent >= 1
    assert f"{cases_divergent} of {cases_total} cases" in result.stdout


def test_gate_certificate_missing(tmp_path):
    """Test gate with missing certificate exits 1."""
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--certificate", str(tmp_path / "missing.json")
        ],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    assert result.returncode == 1
    assert result.stdout.startswith("Gate: certificate missing")


@pytest.mark.slow
def test_gate_certificate_tampered(tmp_path):
    """Test gate with tampered certificate exits 1."""
    # Run audit to create certificate
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", "samples/credit-fees/CREDIT-FEES.cob",
            "--copybooks", "samples/credit-fees/copybooks",
            "--java", "samples/credit-fees/java/CreditFees.java",
            "--schema", "samples/credit-fees/schema.json",
            "--cases", "50", "--seed", "42"
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60
    )
    
    assert result.returncode == 0, f"Setup failed: {result.stderr}"
    
    # Parse run_id from output
    run_id = None
    for line in result.stdout.splitlines():
        if line.startswith("Run: "):
            value = line.split("Run: ", 1)[1].strip()
            run_id = Path(value).name
            break
    
    assert run_id is not None, f"No run_id found in output: {result.stdout}"
    cert_path = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_path.exists(), f"Certificate not found at {cert_path}"
    
    # Tamper with status
    with open(cert_path) as f:
        cert = json.load(f)
    cert["status"] = "TAMPERED"
    
    tampered_path = tmp_path / "tampered.json"
    with open(tampered_path, "w") as f:
        json.dump(cert, f)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--certificate", str(tampered_path)
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env
    )
    
    assert result.returncode == 1
    assert result.stdout.startswith("Gate: certificate invalid")


@pytest.mark.slow
def test_gate_certificate_hash_mismatch(tmp_path):
    """Test gate with certificate hash mismatch exits 1."""
    # Run audit to create certificate
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", "samples/credit-fees/CREDIT-FEES.cob",
            "--copybooks", "samples/credit-fees/copybooks",
            "--java", "samples/credit-fees/java/CreditFees.java",
            "--schema", "samples/credit-fees/schema.json",
            "--cases", "50", "--seed", "42"
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60
    )
    
    assert result.returncode == 0, f"Setup failed: {result.stderr}"
    
    # Parse run_id from output
    run_id = None
    for line in result.stdout.splitlines():
        if line.startswith("Run: "):
            value = line.split("Run: ", 1)[1].strip()
            run_id = Path(value).name
            break
    
    assert run_id is not None, f"No run_id found in output: {result.stdout}"
    cert_path = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_path.exists(), f"Certificate not found at {cert_path}"
    
    # Change Java hash
    with open(cert_path) as f:
        cert = json.load(f)
    cert["java_file_sha256"] = "0" * 64
    
    # Recompute certificate hash
    import hashlib
    cert_copy = {k: v for k, v in cert.items() if k != "certificate_sha256"}
    cert_json = json.dumps(cert_copy, sort_keys=True, indent=2)
    new_hash = hashlib.sha256(cert_json.encode()).hexdigest()
    cert["certificate_sha256"] = new_hash
    
    modified_path = tmp_path / "modified.json"
    with open(modified_path, "w") as f:
        json.dump(cert, f)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--certificate", str(modified_path)
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env
    )
    
    assert result.returncode == 1
    assert result.stdout.startswith("Gate: certificate does not match the audited files")


@pytest.mark.slow
def test_gate_junit(tmp_path):
    """Test gate with --junit writes XML."""
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    junit_path = tmp_path / "gate.xml"
    
    # Test ALIVE writes passing test
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--cases", "200",
            "--junit", str(junit_path)
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 0
    assert junit_path.exists()
    
    # Parse XML
    tree = ET.parse(junit_path)
    root = tree.getroot()
    testsuites = root.findall(".//testsuite")
    assert len(testsuites) == 1
    
    testsuite = testsuites[0]
    assert testsuite.get("tests") == "1"
    assert testsuite.get("failures") == "0"
    
    # Test ZOMBIE writes failing test
    variant_path = tmp_path / "CreditFees.java"
    subprocess.run(
        [
            sys.executable, "-m", "coroner.catalog.legacy_variant",
            "samples/credit-fees/java/CreditFees.java",
            str(variant_path)
        ],
        check=True,
        timeout=10
    )
    
    junit_path2 = tmp_path / "gate2.xml"
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--java", str(variant_path),
            "--cases", "200",
            "--junit", str(junit_path2)
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 1
    assert junit_path2.exists()
    
    # Parse XML
    tree = ET.parse(junit_path2)
    root = tree.getroot()
    testsuites = root.findall(".//testsuite")
    assert len(testsuites) == 1
    
    testsuite = testsuites[0]
    assert testsuite.get("tests") == "1"
    assert testsuite.get("failures") == "1"


def test_github_actions_pinned():
    """Test that all GitHub Actions uses are pinned by SHA."""
    import glob
    
    workflow_files = glob.glob(".github/workflows/*.yml")
    assert len(workflow_files) > 0, "No workflow files found"
    
    for wf in workflow_files:
        with open(wf) as f:
            content = f.read()
        
        # Find all uses: lines
        for line in content.splitlines():
            if "uses:" in line:
                # Extract the action reference (after uses:)
                match = re.search(r'uses:\s*([^#\s]+)', line)
                if match:
                    ref = match.group(1)
                    # Check if pinned by SHA (40 hex chars after @)
                    if '@' in ref:
                        sha = ref.split('@')[1].split()[0]  # Handle inline comments
                        assert re.match(r'^[0-9a-f]{40}$', sha), \
                            f"Action not pinned by 40-char SHA in {wf}: {line}"


def test_publish_workflow_safety():
    """Test that publish-image workflow has required safety constraints."""
    import yaml
    
    workflow_path = ".github/workflows/publish-image.yml"
    assert os.path.exists(workflow_path), "publish-image.yml not found"
    
    with open(workflow_path) as f:
        workflow = yaml.safe_load(f)
    
    # Must trigger only on workflow_dispatch
    # Note: PyYAML (YAML 1.1) loads 'on' as the boolean True
    triggers = workflow.get("on", workflow.get(True))
    assert triggers == {"workflow_dispatch": None}, \
        f"Expected only workflow_dispatch trigger, got {triggers}"
    
    # Must have packages write permission
    assert "permissions" in workflow, "No permissions defined"
    perms = workflow["permissions"]
    assert perms.get("packages") == "write", \
        f"Expected packages: write, got {perms.get('packages')}"
    
    # Read workflow content to check for latest tag
    with open(workflow_path) as f:
        content = f.read()
    
    # Must not push latest tag
    assert ":latest" not in content, "Workflow must not push 'latest' tag"


def test_jenkinsfile_exists():
    """Test that Jenkinsfile exists and has required content."""
    assert os.path.exists("Jenkinsfile"), "Jenkinsfile not found"
    
    with open("Jenkinsfile") as f:
        content = f.read()
    
    assert "pipeline {" in content, "Jenkinsfile does not contain 'pipeline {'"
    assert "junit" in content, "Jenkinsfile does not contain 'junit'"
    
    # Check that docker run has --init
    if "docker run" in content:
        # Find docker run lines
        docker_run_lines = [line for line in content.splitlines() if "docker run" in line]
        assert len(docker_run_lines) > 0, "Jenkinsfile has 'docker run' but no matching lines"
        
        for line in docker_run_lines:
            if "coroner:ci" in line or "coroner" in line:
                assert "--init" in line, (
                    f"docker run in Jenkinsfile missing --init flag: {line}"
                )


def test_gate_certificate_real(real_cert_run):
    """Test gate with real certificate from fixture."""
    cert_path, base_dir = real_cert_run
    
    # Load certificate to get expected numbers
    with open(cert_path) as f:
        cert = json.load(f)
    
    cases_total = cert["cases_total"]
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base_dir)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--certificate", str(cert_path)
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env
    )
    
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert result.stdout.startswith("Gate: ALIVE")
    assert f"{cases_total} cases" in result.stdout


def test_gate_certificate_missing_keys(real_cert_run):
    """Test gate with certificate missing cases_total key exits 1."""
    cert_path, base_dir = real_cert_run
    
    # Load and tamper certificate
    with open(cert_path) as f:
        cert = json.load(f)
    
    # Remove cases_total key
    del cert["cases_total"]
    
    tampered_path = Path(str(cert_path).replace("certificate.json", "tampered_missing_key.json"))
    with open(tampered_path, "w") as f:
        json.dump(cert, f)
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base_dir)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "gate",
            "--certificate", str(tampered_path)
        ],
        capture_output=True,
        text=True,
        timeout=5,
        env=env
    )
    
    assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert result.stdout.strip() == "Gate: certificate invalid"


def test_certificate_matches_bundled_t1_run(gate_engine_runs):
    """Test that the T1 faulty certificate made by the engine matches its files."""
    from coroner.gate import certificate_matches_files
    from coroner.hooks import get_repo_root
    
    cert_path = gate_engine_runs / T1_FAULTY_ID / "certificate.json"
    assert cert_path.exists(), f"T1 run not found at {cert_path}"
    
    with open(cert_path) as f:
        cert = json.load(f)
    
    repo_root = get_repo_root()
    
    # Build scope from certificate fields
    scope = {
        "cobol": cert["cobol_file"],
        "copybooks": cert["copybook_dir"],
        "java": cert["java_file"],
        "schema": cert["schema_file"]
    }
    
    assert certificate_matches_files(cert, scope, repo_root), \
        "Bundled T1 certificate should match its files"


def test_certificate_matches_bundled_credit_fees_run(gate_engine_runs):
    """Test that the credit-fees certificate made by the engine matches its files."""
    from coroner.gate import certificate_matches_files
    from coroner.hooks import get_repo_root
    
    cert_path = gate_engine_runs / CREDIT_FEES_CORRECT_ID / "certificate.json"
    assert cert_path.exists(), f"credit-fees run not found at {cert_path}"
    
    with open(cert_path) as f:
        cert = json.load(f)
    
    repo_root = get_repo_root()
    
    # Build scope from certificate fields
    scope = {
        "cobol": cert["cobol_file"],
        "copybooks": cert["copybook_dir"],
        "java": cert["java_file"],
        "schema": cert["schema_file"]
    }
    
    assert certificate_matches_files(cert, scope, repo_root), \
        "Bundled credit-fees certificate should match its files"


def test_certificate_no_match_after_copybook_edit(tmp_path, gate_engine_runs):
    """Test that certificate does not match after a copybook is edited."""
    from coroner.gate import certificate_matches_files
    from coroner.hooks import get_repo_root
    import shutil
    
    # Use credit-fees which has real copybooks
    cert_path = gate_engine_runs / CREDIT_FEES_CORRECT_ID / "certificate.json"
    assert cert_path.exists()
    
    with open(cert_path) as f:
        cert = json.load(f)
    
    # Copy repository structure to tmp
    repo_root_real = get_repo_root()
    tmp_repo = tmp_path / "repo"
    tmp_repo.mkdir()
    
    # Copy the relevant files
    cobol_src = repo_root_real / "samples/credit-fees"
    cobol_dst = tmp_repo / "samples/credit-fees"
    shutil.copytree(cobol_src, cobol_dst)
    
    # Build scope from certificate fields
    scope = {
        "cobol": cert["cobol_file"],
        "copybooks": cert["copybook_dir"],
        "java": cert["java_file"],
        "schema": cert["schema_file"]
    }
    
    # Should match before edit
    assert certificate_matches_files(cert, scope, tmp_repo), \
        "Certificate should match before edit"
    
    # Edit one copybook (CONSTANTS.cpy instead of non-existent WORKING-STORAGE.cpy)
    copybook = tmp_repo / "samples/credit-fees/copybooks/CONSTANTS.cpy"
    assert copybook.exists()
    with open(copybook, "a") as f:
        f.write("\n      * Modified\n")
    
    # Should not match after edit
    assert not certificate_matches_files(cert, scope, tmp_repo), \
        "Certificate should not match after copybook edit"


def test_certificate_matches_with_stray_non_copybook_file(tmp_path, gate_engine_runs):
    """Test that stray non-copybook files do not affect matching."""
    from coroner.gate import certificate_matches_files
    from coroner.hooks import get_repo_root
    import shutil
    
    # Use credit-fees which has real copybooks
    cert_path = gate_engine_runs / CREDIT_FEES_CORRECT_ID / "certificate.json"
    assert cert_path.exists()
    
    with open(cert_path) as f:
        cert = json.load(f)
    
    # Copy repository structure to tmp
    repo_root_real = get_repo_root()
    tmp_repo = tmp_path / "repo"
    tmp_repo.mkdir()
    
    # Copy the relevant files
    cobol_src = repo_root_real / "samples/credit-fees"
    cobol_dst = tmp_repo / "samples/credit-fees"
    shutil.copytree(cobol_src, cobol_dst)
    
    # Build scope from certificate fields
    scope = {
        "cobol": cert["cobol_file"],
        "copybooks": cert["copybook_dir"],
        "java": cert["java_file"],
        "schema": cert["schema_file"]
    }
    
    # Should match before adding stray file
    assert certificate_matches_files(cert, scope, tmp_repo), \
        "Certificate should match before adding stray file"
    
    # Add a stray non-copybook file
    copybook_dir = tmp_repo / "samples/credit-fees/copybooks"
    stray_file = copybook_dir / "notes.txt"
    with open(stray_file, "w") as f:
        f.write("This is a stray file\n")
    
    # Should still match (only *.cpy and *.cbl are hashed)
    assert certificate_matches_files(cert, scope, tmp_repo), \
        "Certificate should still match with stray non-copybook file"
    
    # Also test with .gitkeep
    gitkeep = copybook_dir / ".gitkeep"
    gitkeep.touch()
    
    # Should still match
    assert certificate_matches_files(cert, scope, tmp_repo), \
        "Certificate should still match with .gitkeep"
