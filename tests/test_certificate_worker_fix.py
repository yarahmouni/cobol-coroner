"""
Tests for certificate replay with worker-generated runs.

Verifies the fix for relative cases_file paths and HALF_EVEN variant.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from coroner.certificate import generate_certificate, replay_certificate
from coroner.engine_worker import execute_job
from coroner.ui.app import get_base_dir


def test_certificate_relative_cases_file(tmp_path):
    """
    Test that new certificates record cases_file as relative path.
    
    Verifies that generate_certificate writes "runs/<run_id>/generated_cases.csv"
    instead of an absolute path, so the certificate can be replayed from
    any base directory.
    """
    # Create a test run structure in tmp_path
    run_id = "test12345678"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    
    # Create minimal required files
    inputs = {
        "cobol_source_sha256": "abc123",
        "copybook_hashes": [],
        "java_source_sha256": "def456",
        "schema_sha256": "ghi789",
        "cases_file_sha256": "jkl012",
        "cases_file_encoding": "utf-8",
        "cases_file_line_ending": "LF",
        "case_count": 10,
        "random_seed": 42,
        "python_version": "3.12.0",
        "cobc_version": "3.2.0",
        "javac_version": "17.0.0",
        "java_version": "17.0.0",
        "coroner_version": "1.0.0",
        "comparison_engine_sha256": "mno345",
        "timestamp": "2026-11-20T00:00:00Z"
    }
    (run_dir / "inputs.json").write_text(json.dumps(inputs))
    
    verdict = {
        "status": "ALIVE",
        "sub_label": "PASS: business behavior preserved on 10 cases",
        "cases_total": 10,
        "cases_divergent": 0,
        "run_return_codes": [0, 0]
    }
    (run_dir / "verdict.json").write_text(json.dumps(verdict))
    
    coverage = {
        "paragraphs_covered": 5,
        "paragraphs_total": 5,
        "branches_covered": 10,
        "branches_total": 10
    }
    (run_dir / "coverage_report.json").write_text(json.dumps(coverage))
    
    # Create dummy files for the certificate
    cobol_file = tmp_path / "test.cob"
    cobol_file.write_text("IDENTIFICATION DIVISION.\n")
    
    copybook_dir = tmp_path / "copybooks"
    copybook_dir.mkdir()
    
    java_file = tmp_path / "Test.java"
    java_file.write_text("public class Test {}\n")
    
    schema_file = tmp_path / "schema.json"
    schema_file.write_text("{}")
    
    cases_file = run_dir / "generated_cases.csv"
    cases_file.write_text("CASE-ID\n001\n")
    
    # Generate certificate
    generate_certificate(
        run_id=run_id,
        cobol_file=str(cobol_file),
        copybook_dir=str(copybook_dir),
        java_file=str(java_file),
        schema_file=str(schema_file),
        base_dir=str(tmp_path)
    )
    
    # Read generated certificate
    cert_file = run_dir / "certificate.json"
    assert cert_file.exists()
    
    cert_data = json.loads(cert_file.read_text())
    
    # Verify cases_file is relative
    assert cert_data["cases_file"] == f"runs/{run_id}/generated_cases.csv"
    assert not os.path.isabs(cert_data["cases_file"])


def test_certificate_replay_from_worker_run(tmp_path):
    """
    Test that a certificate from a worker run can be replayed.
    
    Simulates the scenario where:
    1. Worker runs audit with CORONER_BASE_DIR=/tmp/job_abc123
    2. API copies run to /data/runs/<run_id>
    3. Verify/Tamper replay the certificate with base_dir=/data
    
    The cases_file should be resolved relative to the replay base_dir.
    """
    # Simulate the job directory where worker ran
    job_dir = tmp_path / "jobs" / "abc123456789"
    job_dir.mkdir(parents=True)
    
    # Simulate the API data directory
    api_base = tmp_path / "data"
    api_base.mkdir()
    
    run_id = "test87654321"
    
    # Create run in job directory (simulates worker execution)
    job_run_dir = job_dir / "runs" / run_id
    job_run_dir.mkdir(parents=True)
    
    # Create minimal files
    cases_file = job_run_dir / "generated_cases.csv"
    cases_file.write_text("CASE-ID\n001\n")
    
    # Create certificate with relative cases_file
    cert = {
        "certificate_format": 1,
        "title": "Coroner Certificate",
        "statement": "Test",
        "cobol_file_sha256": "abc",
        "copybook_hashes": {},
        "java_file_sha256": "def",
        "schema_file_sha256": "ghi",
        "cases_file_sha256": "jkl",
        "cases_file": f"runs/{run_id}/generated_cases.csv",  # Relative!
        "cases_file_encoding": "utf-8",
        "cases_file_line_ending": "LF",
        "case_count": 1,
        "random_seed": 42,
        "cobc_flags": [],
        "python_version": "3.12.0",
        "cobc_version": "3.2.0",
        "javac_version": "17.0.0",
        "java_version": "17.0.0",
        "coroner_version": "1.0.0",
        "comparison_engine_sha256": "mno",
        "timestamp": "2026-11-20T00:00:00Z",
        "status": "ALIVE",
        "sub_label": "PASS",
        "cases_total": 1,
        "cases_divergent": 0,
        "run_return_codes": {"cobol": 0, "java": 0},
        "paragraph_coverage_reached": 1,
        "paragraph_coverage_total": 1,
        "branch_coverage_reached": 1,
        "branch_coverage_total": 1,
        "minimal_case_id": None,
        "divergent_fields": None
    }
    
    # Compute certificate_sha256 (would use compute_certificate_sha256)
    cert_copy = cert.copy()
    from coroner.certificate import compute_certificate_sha256
    cert["certificate_sha256"] = compute_certificate_sha256(cert_copy)
    
    cert_file = job_run_dir / "certificate.json"
    cert_file.write_text(json.dumps(cert, indent=2))
    
    # Simulate API copying the run
    api_run_dir = api_base / "runs" / run_id
    api_run_dir.mkdir(parents=True)
    
    # Copy cases file and certificate
    import shutil
    shutil.copy(cases_file, api_run_dir / "generated_cases.csv")
    shutil.copy(cert_file, api_run_dir / "certificate.json")
    
    # Now try to replay from the API's perspective
    # The certificate should find cases_file relative to api_base
    result = replay_certificate(
        str(api_run_dir / "certificate.json"),
        base_dir=str(api_base)
    )
    
    # The replay should find the cases file
    # (It will fail at later steps because we don't have COBOL/Java files,
    # but it should NOT fail with "cases file not found")
    assert "cases file not found" not in result.reason.lower()


def test_old_certificate_with_absolute_path_still_works(tmp_path):
    """
    Test that old certificates with absolute cases_file still replay.
    
    Ensures backward compatibility: existing certificates in runs/
    that record absolute paths should still work.
    """
    run_id = "old12345678"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    
    # Create cases file at an absolute path (simulates old certificate)
    cases_file = run_dir / "generated_cases.csv"
    cases_file.write_text("CASE-ID\n001\n")
    
    # Old certificate with absolute path
    cert = {
        "certificate_format": 1,
        "title": "Coroner Certificate",
        "statement": "Test",
        "cobol_file_sha256": "abc",
        "copybook_hashes": {},
        "java_file_sha256": "def",
        "schema_file_sha256": "ghi",
        "cases_file_sha256": "jkl",
        "cases_file": str(cases_file),  # Absolute path!
        "cases_file_encoding": "utf-8",
        "cases_file_line_ending": "LF",
        "case_count": 1,
        "random_seed": 42,
        "cobc_flags": [],
        "python_version": "3.12.0",
        "cobc_version": "3.2.0",
        "javac_version": "17.0.0",
        "java_version": "17.0.0",
        "coroner_version": "1.0.0",
        "comparison_engine_sha256": "mno",
        "timestamp": "2026-11-20T00:00:00Z",
        "status": "ALIVE",
        "sub_label": "PASS",
        "cases_total": 1,
        "cases_divergent": 0,
        "run_return_codes": {"cobol": 0, "java": 0},
        "paragraph_coverage_reached": 1,
        "paragraph_coverage_total": 1,
        "branch_coverage_reached": 1,
        "branch_coverage_total": 1,
        "minimal_case_id": None,
        "divergent_fields": None
    }
    
    from coroner.certificate import compute_certificate_sha256
    cert["certificate_sha256"] = compute_certificate_sha256(cert.copy())
    
    cert_file = run_dir / "certificate.json"
    cert_file.write_text(json.dumps(cert, indent=2))
    
    # Replay should find the cases file via the absolute path
    result = replay_certificate(str(cert_file), base_dir=str(tmp_path))
    
    # Should not fail with "cases file not found"
    assert "cases file not found" not in result.reason.lower()


def test_certificate_no_absolute_path_in_content(tmp_path):
    """
    Test that generated certificates don't expose absolute paths.
    
    Verifies the security/privacy fix: certificates should not contain
    internal absolute paths like /tmp/jobs/abc123/...
    """
    from coroner.cli import run_verify
    
    cobol = Path("samples/credit-fees/CREDIT-FEES.cob").resolve()
    copybooks = Path("samples/credit-fees/copybooks").resolve()
    java = Path("samples/credit-fees/java/CreditFees.java").resolve()
    schema = Path("samples/credit-fees/schema.json").resolve()
    
    # Run verification with tmp_path as base
    verdict, run_dir = run_verify(
        cobol_path=str(cobol),
        copybooks_dir=str(copybooks),
        java_path=str(java),
        schema_path=str(schema),
        num_cases=10,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    # Read certificate content
    cert_file = run_dir / "certificate.json"
    cert_data = json.loads(cert_file.read_text())
    
    # Verify no path field is absolute
    path_fields = ["cobol_file", "copybook_dir", "java_file", "schema_file", "cases_file"]
    for field in path_fields:
        value = cert_data.get(field)
        if value:
            assert not os.path.isabs(value), (
                f"Certificate field '{field}' contains absolute path: {value}"
            )


@pytest.mark.slow
def test_half_even_variant_path(tmp_path, monkeypatch):
    """
    The worker looks for the HALF_EVEN variant where scripts/init_demo_runs.sh puts it.

    This test only reads the repository: it never creates build/variants/CreditFees.java, a file
    shared with the init script and make zombie. The default location is checked as a path, the
    worker's generation is checked in a folder of the test's own, and the generated file is read.
    """
    from coroner.engine_worker import get_repo_root, get_variants_dir, resolve_sample_paths

    repo_root = Path(__file__).parents[1]
    assert get_repo_root() == repo_root

    # Default location, the one the init script uses
    monkeypatch.delenv("CORONER_VARIANTS_DIR", raising=False)
    default_path = get_variants_dir() / "CreditFees.java"
    assert default_path == repo_root / "build" / "variants" / "CreditFees.java"
    init_script = (repo_root / "scripts" / "init_demo_runs.sh").read_text()
    assert str(default_path.relative_to(repo_root)) in init_script

    # The worker generates the variant into the folder named by CORONER_VARIANTS_DIR
    own_dir = tmp_path / "build" / "variants"
    monkeypatch.setenv("CORONER_VARIANTS_DIR", str(own_dir))
    _, java_path, _, _ = resolve_sample_paths("credit-fees", "faulty", tmp_path)
    variant_path = Path(java_path)
    assert variant_path == own_dir / "CreditFees.java"
    assert not list(own_dir.glob(".*tmp")), "temporary file left behind"
    
    # Verify it's a valid Java file
    content = variant_path.read_text()
    assert "class CreditFees" in content
    assert "RoundingMode.HALF_EVEN" in content
    assert "RoundingMode.HALF_UP" not in content


@pytest.mark.slow
def test_worker_run_certificate_replay_integration(tmp_path, monkeypatch):
    """
    Integration test: worker executes job, API copies run, Verify replays certificate.
    
    This is the real flow that was broken before the fix.
    """
    from coroner.engine_worker import execute_job
    import time
    
    # Create exchange directory structure
    exchange_dir = tmp_path / "exchange"
    jobs_dir = exchange_dir / "jobs"
    jobs_dir.mkdir(parents=True)
    
    # Create job
    job_id = "abc123456789"  # Exactly 12 lowercase hex characters
    job_dir = jobs_dir / job_id
    job_dir.mkdir()
    
    # Write request
    request = {
        "sample": "credit-fees",
        "port": "correct",
        "seed": 42,
        "cases": 10  # Small for speed
    }
    (job_dir / "request.json").write_text(json.dumps(request))
    
    # Write initial status
    status = {
        "status": "queued",
        "queued_at": time.time()
    }
    (job_dir / "status.json").write_text(json.dumps(status))
    
    # Set environment for worker
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    monkeypatch.setenv("CORONER_JOB_TIMEOUT", "60")
    
    # Execute job
    execute_job(job_dir)
    
    # Check job completed
    status_file = job_dir / "status.json"
    assert status_file.exists()
    status_data = json.loads(status_file.read_text())
    assert status_data["status"] == "done", f"Job failed: {status_data}"
    
    # Get run_id
    run_id = status_data["run_id"]
    
    # Simulate API copying run to its base directory
    api_base = tmp_path / "api_data"
    api_base.mkdir()
    
    job_run_dir = job_dir / "runs" / run_id
    api_run_dir = api_base / "runs" / run_id
    api_run_dir.parent.mkdir(parents=True)
    
    import shutil
    shutil.copytree(job_run_dir, api_run_dir)
    
    # Now replay certificate from API's perspective
    cert_path = api_run_dir / "certificate.json"
    assert cert_path.exists()
    
    # Check that no path field in the certificate is absolute
    cert_data = json.loads(cert_path.read_text())
    path_fields = ["cobol_file", "copybook_dir", "java_file", "schema_file", "cases_file"]
    for field in path_fields:
        value = cert_data.get(field)
        if value:
            assert not os.path.isabs(value), (
                f"Certificate field '{field}' contains absolute path: {value}"
            )
    
    # This should NOT fail with "cases file not found"
    result = replay_certificate(str(cert_path), str(api_base))
    
    # It may fail at later steps (COBOL/Java files), but NOT at cases file
    if not result.valid:
        assert "cases file not found" not in result.reason.lower(), (
            f"Certificate replay failed to find cases file: {result.reason}"
        )
    
    # If it got past the cases file check, that's success
    # (The full replay may fail because COBOL/Java paths are relative to job_dir)
    print(f"Certificate replay result: valid={result.valid}, reason={result.reason}")

