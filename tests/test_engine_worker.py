"""Tests for engine worker."""
import json
import os
import time
from pathlib import Path

import pytest

from coroner.engine_worker import (
    discover_trap_folders,
    execute_job,
    find_oldest_queued_job,
    resolve_sample_paths,
    update_status,
    validate_job_id,
)


def test_validate_job_id():
    """Test job_id validation."""
    # Valid
    assert validate_job_id("a26c32ac9519")
    assert validate_job_id("000000000000")
    assert validate_job_id("ffffffffffff")
    
    # Invalid
    assert not validate_job_id("A26C32AC9519")  # uppercase
    assert not validate_job_id("a26c32ac951")  # too short
    assert not validate_job_id("a26c32ac95199")  # too long
    assert not validate_job_id("g26c32ac9519")  # invalid char
    assert not validate_job_id("a26c32ac951g")  # invalid char
    assert not validate_job_id("")
    assert not validate_job_id("../etc/passwd")


def test_update_status(tmp_path):
    """Test status.json update."""
    job_dir = tmp_path / "test_job"
    job_dir.mkdir()
    
    # Initial write
    update_status(job_dir, "queued", queued_at=100)
    
    status_file = job_dir / "status.json"
    assert status_file.exists()
    
    data = json.loads(status_file.read_text())
    assert data["status"] == "queued"
    assert data["queued_at"] == 100
    
    # Update
    update_status(job_dir, "running", started_at=200)
    
    data = json.loads(status_file.read_text())
    assert data["status"] == "running"
    assert data["queued_at"] == 100  # preserved
    assert data["started_at"] == 200


def test_find_oldest_queued_job(tmp_path, monkeypatch):
    """Test finding oldest queued job."""
    # Set CORONER_EXCHANGE_DIR
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    
    # No jobs yet
    assert find_oldest_queued_job() is None
    
    # Create jobs with different timestamps
    job1_dir = jobs_dir / "a26c32ac9511"
    job1_dir.mkdir()
    update_status(job1_dir, "queued", queued_at=300)
    
    job2_dir = jobs_dir / "a26c32ac9512"
    job2_dir.mkdir()
    update_status(job2_dir, "queued", queued_at=100)  # oldest
    
    job3_dir = jobs_dir / "a26c32ac9513"
    job3_dir.mkdir()
    update_status(job3_dir, "queued", queued_at=200)
    
    # Create a non-queued job
    job4_dir = jobs_dir / "a26c32ac9514"
    job4_dir.mkdir()
    update_status(job4_dir, "running", queued_at=50)
    
    # Should return job2 (oldest queued)
    oldest = find_oldest_queued_job()
    assert oldest == job2_dir
    
    # Mark job2 as running
    update_status(job2_dir, "running")
    
    # Should return job3 now
    oldest = find_oldest_queued_job()
    assert oldest == job3_dir


def test_discover_trap_folders():
    """Test trap folder discovery."""
    trap_map = discover_trap_folders()
    
    # Should find T1 through T6
    assert "T1" in trap_map
    assert "T2" in trap_map
    assert "T3" in trap_map
    assert "T4" in trap_map
    assert "T5" in trap_map
    assert "T6" in trap_map
    
    # Check that paths are valid directories
    for trap_id, folder in trap_map.items():
        assert folder.exists()
        assert folder.is_dir()
        assert (folder / "trap.json").exists()


def test_resolve_sample_paths_credit_fees(tmp_path):
    """Test resolving paths for credit-fees sample."""
    # Correct port
    cobol_path, java_path, schema_path, copybooks_path = resolve_sample_paths("credit-fees", "correct", tmp_path)
    
    assert Path(cobol_path).name == "CREDIT-FEES.cob"
    assert Path(java_path).name == "CreditFees.java"
    assert Path(schema_path).name == "schema.json"
    assert Path(copybooks_path).name == "copybooks"
    
    # All exist
    assert Path(cobol_path).exists()
    assert Path(java_path).exists()
    assert Path(schema_path).exists()
    assert Path(copybooks_path).exists()
    
    # Faulty port: the worker generates the HALF_EVEN variant in CORONER_VARIANTS_DIR (the test
    # session sets it to a temp folder, see tests/conftest.py; the default is build/variants)
    cobol_path2, java_path2, schema_path2, copybooks_path2 = resolve_sample_paths("credit-fees", "faulty", tmp_path)
    
    # COBOL, schema and copybooks should be the same
    assert cobol_path2 == cobol_path
    assert schema_path2 == schema_path
    assert copybooks_path2 == copybooks_path
    
    from coroner.engine_worker import get_repo_root
    expected_variant = Path(os.environ["CORONER_VARIANTS_DIR"]) / "CreditFees.java"
    assert expected_variant.parent != get_repo_root() / "build" / "variants"
    
    assert Path(java_path2) == expected_variant, f"Expected {expected_variant}, got {java_path2}"
    assert Path(java_path2).exists(), f"Variant not found at {java_path2}"
    assert not list(expected_variant.parent.glob(".*tmp")), "temporary file left behind"
    
    # Verify it's the HALF_EVEN variant
    content = Path(java_path2).read_text()
    assert "RoundingMode.HALF_EVEN" in content
    assert "RoundingMode.HALF_UP" not in content


def test_resolve_sample_paths_traps(tmp_path):
    """Test resolving paths for all trap samples."""
    for trap_id in ["T1", "T2", "T3", "T4", "T5", "T6"]:
        # Correct port
        cobol_path, java_path, schema_path, copybooks_path = resolve_sample_paths(trap_id, "correct", tmp_path)
        
        assert Path(cobol_path).suffix == ".cob"
        assert Path(java_path).suffix == ".java"
        assert Path(schema_path).name == "schema.json"
        
        # All exist
        assert Path(cobol_path).exists(), f"{trap_id} COBOL not found: {cobol_path}"
        assert Path(java_path).exists(), f"{trap_id} Java not found: {java_path}"
        assert Path(schema_path).exists(), f"{trap_id} schema not found: {schema_path}"
        assert Path(copybooks_path).exists(), f"{trap_id} copybooks not found: {copybooks_path}"
        
        # Faulty port
        cobol_path2, java_path2, schema_path2, copybooks_path2 = resolve_sample_paths(trap_id, "faulty", tmp_path)
        
        # COBOL, schema and copybooks should be the same
        assert cobol_path2 == cobol_path
        assert schema_path2 == schema_path
        assert copybooks_path2 == copybooks_path
        
        # Java should exist
        assert Path(java_path2).exists(), f"{trap_id} faulty Java not found: {java_path2}"


def test_resolve_sample_paths_unknown_sample(tmp_path):
    """Test that unknown sample raises ValueError."""
    with pytest.raises(ValueError, match="unknown sample"):
        resolve_sample_paths("unknown", "correct", tmp_path)


def test_resolve_sample_paths_invalid_port(tmp_path):
    """Test that invalid port raises ValueError."""
    with pytest.raises(ValueError, match="unknown port"):
        resolve_sample_paths("credit-fees", "invalid", tmp_path)


def test_execute_job_invalid_job_id(tmp_path, monkeypatch):
    """Test execute_job with invalid job_id."""
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    job_dir = tmp_path / "invalid_id"
    job_dir.mkdir()
    
    request_data = {
        "sample": "credit-fees",
        "port": "correct",
        "seed": 42,
        "cases": 30
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    execute_job(job_dir)
    
    # Should be error
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "error"
    assert "invalid job_id format" in status_data["reason"]


def test_execute_job_missing_request(tmp_path, monkeypatch):
    """Test execute_job with missing request.json."""
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    job_dir = tmp_path / "a26c32ac9519"
    job_dir.mkdir()
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    execute_job(job_dir)
    
    # Should be error
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "error"
    assert "request.json not found" in status_data["reason"]


def test_execute_job_invalid_seed(tmp_path, monkeypatch):
    """Test execute_job with seed out of bounds."""
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    job_dir = tmp_path / "a26c32ac9519"
    job_dir.mkdir()
    
    # Seed too large
    request_data = {
        "sample": "credit-fees",
        "port": "correct",
        "seed": 2000000,
        "cases": 30
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    execute_job(job_dir)
    
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "error"
    assert "seed must be an integer between 0 and 1000000" in status_data["reason"]


def test_execute_job_invalid_cases(tmp_path, monkeypatch):
    """Test execute_job with cases out of bounds."""
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    job_dir = tmp_path / "b26c32ac9519"
    job_dir.mkdir()
    
    # Cases too small
    request_data = {
        "sample": "credit-fees",
        "port": "correct",
        "seed": 42,
        "cases": 5
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    execute_job(job_dir)
    
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "error"
    assert "cases must be an integer between 10 and 2000" in status_data["reason"]


def test_execute_job_unknown_sample(tmp_path, monkeypatch):
    """Test execute_job with unknown sample."""
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    job_dir = tmp_path / "c26c32ac9519"
    job_dir.mkdir()
    
    request_data = {
        "sample": "unknown",
        "port": "correct",
        "seed": 42,
        "cases": 30
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    execute_job(job_dir)
    
    # Should be error
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "error"
    assert "unknown sample" in status_data["reason"]


@pytest.mark.slow
def test_execute_job_credit_fees_correct(tmp_path, monkeypatch):
    """
    Test execute_job with credit-fees correct port.
    
    Compares worker result with direct run_verify call.
    """
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    job_dir = tmp_path / "a26c32ac9519"
    job_dir.mkdir()
    
    request_data = {
        "sample": "credit-fees",
        "port": "correct",
        "seed": 42,
        "cases": 30
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    # Execute
    execute_job(job_dir)
    
    # Check status
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "done"
    assert "completed_at" in status_data
    assert "run_id" in status_data
    
    # Check result.json
    result_file = job_dir / "result.json"
    assert result_file.exists()
    
    result_data = json.loads(result_file.read_text())
    assert result_data["exit_code"] == 0  # ALIVE
    assert result_data["verdict"] == "ALIVE"
    assert "run_id" in result_data
    
    # Check that runs/ directory was created inside job_dir
    runs_dir = job_dir / "runs"
    assert runs_dir.exists()
    
    # Check the run directory exists
    run_id = result_data["run_id"]
    run_dir = runs_dir / run_id
    assert run_dir.exists()
    
    # Check verdict.json exists
    verdict_file = run_dir / "verdict.json"
    assert verdict_file.exists()
    
    verdict_data = json.loads(verdict_file.read_text())
    assert verdict_data["status"] == "ALIVE"
    
    # Compare with direct run_verify in another tmp directory
    from coroner.cli import run_verify
    
    direct_tmp = tmp_path / "direct"
    direct_tmp.mkdir()
    
    cobol_path, java_path, schema_path, copybooks_path = resolve_sample_paths("credit-fees", "correct", direct_tmp)
    
    direct_verdict, direct_run_dir = run_verify(
        cobol_path=cobol_path,
        java_path=java_path,
        schema_path=schema_path,
        copybooks_dir=copybooks_path,
        num_cases=30,
        seed=42,
        timings=False,
        base_dir=str(direct_tmp)
    )
    
    # Should have the same run_id and verdict
    assert result_data["run_id"] == direct_run_dir.name
    assert result_data["verdict"] == direct_verdict.status


@pytest.mark.slow
def test_execute_job_t1_faulty_zombie(tmp_path, monkeypatch):
    """
    Test execute_job with T1 faulty port (ZOMBIE).
    
    Uses a small case count (30) for speed.
    """
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    
    job_dir = tmp_path / "e26c32ac9519"
    job_dir.mkdir()
    
    request_data = {
        "sample": "T1",
        "port": "faulty",
        "seed": 42,
        "cases": 30
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    # Execute
    execute_job(job_dir)
    
    # Check status
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "done"
    
    # Check result.json
    result_file = job_dir / "result.json"
    assert result_file.exists()
    
    result_data = json.loads(result_file.read_text())
    assert result_data["exit_code"] == 1  # ZOMBIE
    assert result_data["verdict"] == "ZOMBIE"
    
    # Compare with direct run_verify
    from coroner.cli import run_verify
    
    direct_tmp = tmp_path / "direct_t1"
    direct_tmp.mkdir()
    
    cobol_path, java_path, schema_path, copybooks_path = resolve_sample_paths("T1", "faulty", direct_tmp)
    
    direct_verdict, direct_run_dir = run_verify(
        cobol_path=cobol_path,
        java_path=java_path,
        schema_path=schema_path,
        copybooks_dir=copybooks_path,
        num_cases=30,
        seed=42,
        timings=False,
        base_dir=str(direct_tmp)
    )
    
    # Should have the same run_id and verdict
    assert result_data["run_id"] == direct_run_dir.name
    assert result_data["verdict"] == direct_verdict.status


@pytest.mark.slow
def test_execute_job_timeout(tmp_path, monkeypatch):
    """
    Test that job timeout is enforced.
    
    Sets a very short timeout (1 second) and runs T1 at 2000 cases,
    which should take longer than 1 second. The subprocess timeout
    kills the process group.
    """
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_JOB_TIMEOUT", "1")  # 1 second timeout
    
    job_dir = tmp_path / "d26c32ac9519"
    job_dir.mkdir()
    
    request_data = {
        "sample": "T1",
        "port": "correct",
        "seed": 42,
        "cases": 2000  # This will take more than 1 second
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    update_status(job_dir, "queued", queued_at=time.time())
    
    # Measure execution time
    start_time = time.monotonic()
    
    # Execute (should timeout)
    execute_job(job_dir)
    
    end_time = time.monotonic()
    elapsed = end_time - start_time
    
    # Check status
    status_data = json.loads((job_dir / "status.json").read_text())
    assert status_data["status"] == "error"
    assert status_data["reason"] == "timeout"
    
    # Job should end within timeout + 10 seconds
    timeout_seconds = int(os.environ["CORONER_JOB_TIMEOUT"])
    assert elapsed < timeout_seconds + 10, f"Job took {elapsed}s, expected < {timeout_seconds + 10}s"
    
    # Verify the process group is gone
    # Read pgid from status.json
    pgid = status_data.get("pgid")
    assert pgid is not None, "pgid not recorded in status.json"
    
    # Verify process group no longer exists
    # os.killpg with signal 0 checks existence without killing
    try:
        os.killpg(pgid, 0)
        # If we get here, the process group still exists
        assert False, f"Process group {pgid} still exists after timeout"
    except ProcessLookupError:
        # Expected: process group is gone
        pass
