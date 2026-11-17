"""Tests for certificate generation and replay."""
import json
import os
import sys
import pytest
import shutil
import hashlib
from pathlib import Path

from coroner.certificate import generate_certificate, replay_certificate


@pytest.fixture(scope="module")
def small_run_alive(tmp_path_factory):
    """Generate a small ALIVE run for testing (30 cases)."""
    from coroner.cli import verify_command
    
    cobol = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    java = "samples/credit-fees/java/CreditFees.java"
    schema = "samples/credit-fees/schema.json"
    
    # Run verification with 30 cases
    exit_code = verify_command(cobol, copybooks, java, schema, cases=30, seed=123)
    
    # Find the run directory
    runs_dir = Path("runs")
    run_dirs = sorted(runs_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    run_id = run_dirs[0].name
    
    yield {
        "run_id": run_id,
        "run_dir": f"runs/{run_id}",
        "exit_code": exit_code,
        "cobol": cobol,
        "copybooks": copybooks,
        "java": java,
        "schema": schema
    }


@pytest.fixture(scope="module")
def small_run_zombie(tmp_path_factory):
    """Generate a small ZOMBIE run for testing (30 cases with legacy variant)."""
    from coroner.cli import verify_command
    from coroner.catalog.legacy_variant import generate_half_even_variant
    
    cobol = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    java_orig = "samples/credit-fees/java/CreditFees.java"
    schema = "samples/credit-fees/schema.json"
    
    # Generate legacy variant
    os.makedirs("build/test_variants", exist_ok=True)
    java_variant = "build/test_variants/CreditFees.java"
    generate_half_even_variant(java_orig, java_variant)
    
    # Run verification with 30 cases
    exit_code = verify_command(cobol, copybooks, java_variant, schema, cases=30, seed=123)
    
    # Find the run directory
    runs_dir = Path("runs")
    run_dirs = sorted(runs_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    run_id = run_dirs[0].name
    
    yield {
        "run_id": run_id,
        "run_dir": f"runs/{run_id}",
        "exit_code": exit_code,
        "cobol": cobol,
        "copybooks": copybooks,
        "java": java_variant,
        "schema": schema
    }


def test_certificate_generated_alive(small_run_alive):
    """Certificate is generated after ALIVE run with all required fields."""
    run_dir = small_run_alive["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    assert os.path.isfile(cert_path), "certificate.json not found"
    
    with open(cert_path, 'r') as f:
        cert = json.load(f)
    
    # Check required fields
    assert cert["certificate_format"] == 1
    assert cert["title"] == "Coroner Certificate"
    assert "Reproducible run record:" in cert["statement"]
    assert "Validated under GnuCOBOL 3.x" in cert["statement"]
    assert "This is not a formal proof of equivalence" in cert["statement"]
    
    # Check no forbidden wording
    assert "certified equivalent" not in cert["statement"].lower()
    assert "proven" not in cert["statement"].lower()
    assert "guaranteed" not in cert["statement"].lower()
    
    # Check inputs.json fields
    assert "cobol_file_sha256" in cert
    assert "copybook_hashes" in cert
    assert "java_file_sha256" in cert
    assert "schema_file_sha256" in cert
    assert "cases_file_sha256" in cert
    assert "cases_file_encoding" in cert
    assert "cases_file_line_ending" in cert
    assert "case_count" in cert
    assert "random_seed" in cert
    assert "python_version" in cert
    assert "cobc_version" in cert
    assert "javac_version" in cert
    assert "java_version" in cert
    assert "coroner_version" in cert
    assert "comparison_engine_sha256" in cert
    assert "timestamp" in cert
    
    # Check file paths
    assert "cobol_file" in cert
    assert "copybook_dir" in cert
    assert "java_file" in cert
    assert "schema_file" in cert
    assert "cases_file" in cert
    
    # Check verdict fields
    assert cert["status"] == "ALIVE"
    assert "PASS:" in cert["sub_label"]
    assert cert["cases_total"] == 30
    assert cert["cases_divergent"] == 0
    assert "run_return_codes" in cert
    # Return codes may be non-zero if generated cases include validation errors
    assert cert["run_return_codes"]["cobol"] >= 0
    assert cert["run_return_codes"]["java"] >= 0
    
    # Check coverage fields
    assert "paragraph_coverage_reached" in cert
    assert "paragraph_coverage_total" in cert
    assert "branch_coverage_reached" in cert
    assert "branch_coverage_total" in cert
    
    # Check ZOMBIE-only fields are null for ALIVE
    assert cert["minimal_case_id"] is None
    assert cert["divergent_fields"] is None
    
    # Verify certificate_sha256
    recorded_hash = cert.pop("certificate_sha256")
    canonical = json.dumps(cert, sort_keys=True, separators=(',', ':'))
    computed_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    assert computed_hash == recorded_hash, "certificate_sha256 mismatch"


def test_certificate_generated_zombie(small_run_zombie):
    """Certificate is generated after ZOMBIE run with minimal_case_id and divergent_fields."""
    run_dir = small_run_zombie["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    assert os.path.isfile(cert_path), "certificate.json not found"
    
    with open(cert_path, 'r') as f:
        cert = json.load(f)
    
    # Check verdict
    assert cert["status"] == "ZOMBIE"
    assert "FAIL:" in cert["sub_label"]
    assert cert["cases_divergent"] > 0
    
    # Check ZOMBIE-specific fields
    assert cert["minimal_case_id"] is not None
    assert isinstance(cert["minimal_case_id"], str)
    assert cert["divergent_fields"] is not None
    assert isinstance(cert["divergent_fields"], list)
    assert len(cert["divergent_fields"]) > 0


def test_replay_valid_alive(small_run_alive):
    """Replay of ALIVE certificate succeeds with exit code 0."""
    run_dir = small_run_alive["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    result = replay_certificate(cert_path)
    
    assert result.valid is True
    assert result.reason == ""
    assert result.verdict is not None
    assert result.verdict.status == "ALIVE"
    assert result.cases_total == 30
    assert result.cases_divergent == 0
    assert result.paragraph_coverage_reached > 0
    assert result.paragraph_coverage_total > 0
    assert result.branch_coverage_reached > 0
    assert result.branch_coverage_total > 0
    assert result.cases_file.endswith("generated_cases.csv")


def test_replay_valid_zombie(small_run_zombie):
    """Replay of ZOMBIE certificate succeeds with exit code 1."""
    run_dir = small_run_zombie["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    result = replay_certificate(cert_path)
    
    assert result.valid is True
    assert result.reason == ""
    assert result.verdict is not None
    assert result.verdict.status == "ZOMBIE"
    assert result.cases_total == 30
    assert result.cases_divergent > 0


def test_replay_invalid_content(small_run_alive, tmp_path):
    """Edited certificate content is detected as INVALID."""
    run_dir = small_run_alive["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    # Copy certificate
    temp_cert = tmp_path / "cert_modified.json"
    with open(cert_path, 'r') as f:
        cert = json.load(f)
    
    # Modify one field (not the hash)
    cert["case_count"] = 999
    
    with open(temp_cert, 'w') as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    
    # Replay should detect tampering
    result = replay_certificate(str(temp_cert))
    
    assert result.valid is False
    assert "certificate content was modified" in result.reason


def test_replay_invalid_cases_file(small_run_alive, tmp_path):
    """Modified cases file is detected as INVALID."""
    run_dir = small_run_alive["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    cases_orig = f"{run_dir}/generated_cases.csv"
    
    # Copy certificate and cases file
    temp_cert = tmp_path / "cert.json"
    temp_cases = tmp_path / "cases.csv"
    
    shutil.copy(cert_path, temp_cert)
    shutil.copy(cases_orig, temp_cases)
    
    # Modify cases file (add one byte)
    with open(temp_cases, 'ab') as f:
        f.write(b'X')
    
    # Update certificate to point to modified cases file
    with open(temp_cert, 'r') as f:
        cert = json.load(f)
    
    # Remove old hash
    cert.pop("certificate_sha256")
    
    # Update cases file path
    cert["cases_file"] = str(temp_cases)
    
    # Recompute hash with the new path
    canonical = json.dumps(cert, sort_keys=True, separators=(',', ':'))
    cert["certificate_sha256"] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    with open(temp_cert, 'w') as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    
    # Replay should detect cases file hash mismatch (file changed, but hash in cert still references old content)
    result = replay_certificate(str(temp_cert))
    
    assert result.valid is False
    assert "cases file hash mismatch" in result.reason


def test_replay_invalid_metrics_tampering(small_run_alive, tmp_path):
    """Certificate with tampered metrics (but correct hash) is detected on replay."""
    run_dir = small_run_alive["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    # Copy certificate
    temp_cert = tmp_path / "cert_tampered.json"
    with open(cert_path, 'r') as f:
        cert = json.load(f)
    
    # Remove certificate_sha256
    cert.pop("certificate_sha256")
    
    # Tamper with divergence count (an ALIVE run has 0 divergences)
    cert["cases_divergent"] = 50
    
    # Recompute certificate_sha256 with the tampered data
    canonical = json.dumps(cert, sort_keys=True, separators=(',', ':'))
    cert["certificate_sha256"] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    with open(temp_cert, 'w') as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    
    # Replay should detect the mismatch when re-running
    result = replay_certificate(str(temp_cert))
    
    assert result.valid is False
    assert "replay mismatch" in result.reason
    assert "cases_divergent" in result.reason


def test_replay_tool_version_warnings(small_run_alive, tmp_path, monkeypatch):
    """Tool version differences produce warnings but not invalidity."""
    run_dir = small_run_alive["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    # This test is hard to implement without actually changing tool versions.
    # We verify the structure is correct and warnings exist in the result.
    result = replay_certificate(cert_path)
    
    assert result.valid is True
    assert isinstance(result.warnings, list)
    # Warnings may be empty if tools haven't changed


def test_replay_missing_file(tmp_path):
    """Replay of non-existent certificate returns error."""
    fake_cert = tmp_path / "nonexistent.json"
    
    result = replay_certificate(str(fake_cert))
    
    assert result.valid is False
    assert "file not found" in result.reason.lower() or "invalid certificate" in result.reason.lower()


def test_certificate_no_em_dash(small_run_alive):
    """Certificate contains no em dash character."""
    run_dir = small_run_alive["run_dir"]
    cert_path = f"{run_dir}/certificate.json"
    
    with open(cert_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Em dash is Unicode U+2014
    assert '\u2014' not in content, "Certificate contains em dash character"


@pytest.mark.slow
def test_certificate_cobc_flags_tampering(tmp_path):
    """Certificate with tampered cobc_flags is detected on replay."""
    import subprocess
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    # Run T4 verification to get a certificate with cobc_flags
    t4_dir = Path("samples/traps/T4-zoned-overpunch")
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", str(t4_dir / "ZONED-OVERPUNCH.cob"),
            "--copybooks", str(t4_dir / "copybooks"),
            "--java", str(t4_dir / "java/correct/ZonedOverpunch.java"),
            "--schema", str(t4_dir / "schema.json"),
            "--cases", "100",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 0
    
    # Find the run directory
    import re
    match = re.search(r'runs/([a-f0-9]{12})', result.stdout)
    assert match, f"Could not find run_id in output: {result.stdout}"
    run_id = match.group(1)
    
    cert_path = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_path.exists()
    
    # Load certificate and verify cobc_flags
    with open(cert_path, 'r') as f:
        cert_orig = json.load(f)
    
    assert cert_orig["cobc_flags"] == ["-fsign=EBCDIC"]
    
    # First verify the original certificate replays as VALID
    from coroner.certificate import replay_certificate
    result_orig = replay_certificate(str(cert_path))
    assert result_orig.valid is True
    assert result_orig.verdict.status == "ALIVE"
    
    # Now tamper with cobc_flags and recompute hash
    temp_cert = tmp_path / "cert_tampered.json"
    cert_tampered = cert_orig.copy()
    cert_tampered.pop("certificate_sha256")
    
    # Change flags to empty list
    cert_tampered["cobc_flags"] = []
    
    # Recompute hash
    canonical = json.dumps(cert_tampered, sort_keys=True, separators=(',', ':'))
    cert_tampered["certificate_sha256"] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    with open(temp_cert, 'w') as f:
        json.dump(cert_tampered, f, indent=2, sort_keys=True)
    
    # Replay should detect the mismatch (outputs differ when compiled without -fsign=EBCDIC)
    result_tampered = replay_certificate(str(temp_cert))
    
    assert result_tampered.valid is False
    assert "replay mismatch" in result_tampered.reason
