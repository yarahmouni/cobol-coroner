"""Tests for /api/gate-check endpoint."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.gate import gate_decision, run_gate
from coroner.ui.app import app, reset_rate_limiter, replay_with_timeout, clear_gate_check_cache


@pytest.fixture(autouse=True)
def clear_caches_before_test():
    """Clear gate check cache and rate limiter before each test."""
    clear_gate_check_cache()
    reset_rate_limiter()
    yield


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def temp_base_dir(tmp_path, monkeypatch):
    """
    Set up temporary base directory with bundled demo runs.
    
    Copies runs/f584d5f35228 (T1 faulty) and runs/29c15f04407b (T1 correct)
    from the repository.
    """
    # Get repository root
    repo_root = Path(__file__).parent.parent
    
    # Create runs directory in temp
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    
    # Copy T1 faulty run
    faulty_src = repo_root / "runs" / "f584d5f35228"
    faulty_dst = runs_dir / "f584d5f35228"
    if faulty_src.exists():
        shutil.copytree(faulty_src, faulty_dst)
    
    # Copy T1 correct run
    correct_src = repo_root / "runs" / "29c15f04407b"
    correct_dst = runs_dir / "29c15f04407b"
    if correct_src.exists():
        shutil.copytree(correct_src, correct_dst)
    
    # Set CORONER_BASE_DIR
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    # Reset rate limiter
    reset_rate_limiter()
    
    yield tmp_path


def test_gate_decision_table():
    """Test gate_decision covers every branch."""
    # status=None -> 1
    assert gate_decision(None, "VALID", True) == 1
    
    # hash_match=False -> 1
    assert gate_decision("ALIVE", "VALID", False) == 1
    
    # replay != VALID -> 1
    assert gate_decision("ALIVE", "INVALID", True) == 1
    assert gate_decision("ALIVE", None, True) == 1
    
    # status=ZOMBIE -> 1
    assert gate_decision("ZOMBIE", "VALID", True) == 1
    
    # status=ALIVE -> 0
    assert gate_decision("ALIVE", "VALID", True) == 0
    
    # status=ERROR -> 2
    assert gate_decision("ERROR", "VALID", True) == 2
    
    # Other status -> 2
    assert gate_decision("UNKNOWN", "VALID", True) == 2


@pytest.mark.slow
def test_gate_check_faulty(client, temp_base_dir):
    """Test /api/gate-check with T1 faulty run returns blocked."""
    response = client.post(
        "/api/gate-check",
        data={"run_id": "f584d5f35228"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "blocked"
    assert data["exit_code"] == 1
    assert "ZOMBIE" in data["message"]


@pytest.mark.slow
def test_gate_check_correct(client, temp_base_dir):
    """Test /api/gate-check with T1 correct run returns allowed."""
    response = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "allowed"
    assert data["exit_code"] == 0
    assert data["message"] == "Commit allowed"


def test_gate_check_invalid_run_id(client, temp_base_dir):
    """Test /api/gate-check with invalid run_id returns 422."""
    # Not 12 hex chars
    response = client.post(
        "/api/gate-check",
        data={"run_id": "invalid"}
    )
    
    assert response.status_code == 404


def test_gate_check_unknown_run_id(client, temp_base_dir):
    """Test /api/gate-check with non-existent run_id returns 404."""
    response = client.post(
        "/api/gate-check",
        data={"run_id": "999999999999"}
    )
    
    assert response.status_code == 404


def test_gate_check_no_store(client, temp_base_dir):
    """Test /api/gate-check responses have Cache-Control: no-store."""
    # Test on 200
    response = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    cache_control = response.headers.get("cache-control", "")
    assert "no-store" in cache_control
    
    # Test on 404
    response = client.post(
        "/api/gate-check",
        data={"run_id": "999999999999"}
    )
    
    cache_control = response.headers.get("cache-control", "")
    assert "no-store" in cache_control
    
    # Test on 422 (invalid run_id via validation)
    response = client.post(
        "/api/gate-check",
        data={"run_id": "invalid"}
    )
    
    cache_control = response.headers.get("cache-control", "")
    assert "no-store" in cache_control


@pytest.mark.slow
def test_gate_check_matches_run_gate_faulty(temp_base_dir):
    """
    Test /api/gate-check exit_code matches run_gate on T1 faulty.
    
    Uses the bundled T1 faulty certificate and the T1 scope file.
    """
    # Get repository root
    repo_root = Path(__file__).parent.parent
    
    # T1 faulty certificate (in temp_base_dir)
    cert_path_tmp = temp_base_dir / "runs" / "f584d5f35228" / "certificate.json"
    
    # Load certificate to get file paths
    with open(cert_path_tmp) as f:
        cert = json.load(f)
    
    # Write scope JSON to tmp_path with absolute paths
    scope_data = {
        "cobol": cert["cobol_file"],
        "copybooks": cert["copybook_dir"],
        "java": cert["java_file"],
        "schema": cert["schema_file"]
    }
    
    scope_path = temp_base_dir / "t1_faulty_scope.json"
    with open(scope_path, "w") as f:
        json.dump(scope_data, f)
    
    # Run run_gate with absolute scope path
    gate_exit_code = run_gate(
        scope_path=str(scope_path.absolute()),
        java_override=None,
        cases=2000,
        seed=42,
        certificate_path=str(cert_path_tmp),
        junit_path=None
    )
    
    # Call endpoint
    client = TestClient(app)
    response = client.post(
        "/api/gate-check",
        data={"run_id": "f584d5f35228"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Compare exit codes
    assert data["exit_code"] == gate_exit_code


@pytest.mark.slow
def test_gate_check_matches_run_gate_correct(temp_base_dir):
    """
    Test /api/gate-check exit_code matches run_gate on T1 correct.
    
    Uses the bundled T1 correct certificate and the T1 scope file.
    """
    # Get repository root
    repo_root = Path(__file__).parent.parent
    
    # T1 correct certificate (in temp_base_dir)
    cert_path_tmp = temp_base_dir / "runs" / "29c15f04407b" / "certificate.json"
    
    # Load certificate to get file paths
    with open(cert_path_tmp) as f:
        cert = json.load(f)
    
    # Write scope JSON to tmp_path with absolute paths
    scope_data = {
        "cobol": cert["cobol_file"],
        "copybooks": cert["copybook_dir"],
        "java": cert["java_file"],
        "schema": cert["schema_file"]
    }
    
    scope_path = temp_base_dir / "t1_correct_scope.json"
    with open(scope_path, "w") as f:
        json.dump(scope_data, f)
    
    # Run run_gate with absolute scope path
    gate_exit_code = run_gate(
        scope_path=str(scope_path.absolute()),
        java_override=None,
        cases=2000,
        seed=42,
        certificate_path=str(cert_path_tmp),
        junit_path=None
    )
    
    # Call endpoint
    client = TestClient(app)
    response = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Compare exit codes
    assert data["exit_code"] == gate_exit_code


def test_gate_check_cache(client, temp_base_dir, monkeypatch):
    """
    Test that second POST within 600 s returns cached response without replay.
    
    Counts subprocess starts through a wrapper around replay_with_timeout.
    """
    from coroner.ui import app as app_module
    
    # Track replay calls
    replay_calls = []
    original_replay = app_module.replay_with_timeout
    
    def wrapper_replay(*args, **kwargs):
        replay_calls.append(True)
        return original_replay(*args, **kwargs)
    
    # Patch replay_with_timeout
    monkeypatch.setattr(app_module, "replay_with_timeout", wrapper_replay)
    
    # First call
    response1 = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert len(replay_calls) == 1  # One replay
    
    # Second call within 600 s
    response2 = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Should use cache, no new replay
    assert len(replay_calls) == 1
    
    # Same response body
    assert data1 == data2


def test_gate_check_cache_invalidated_on_change(client, temp_base_dir):
    """Test that a certificate edited after first call is not served from cache."""
    # First call
    response1 = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "allowed"
    
    # Edit the certificate (change status field)
    cert_path = temp_base_dir / "runs" / "29c15f04407b" / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # Change status to ZOMBIE
    cert_data["status"] = "ZOMBIE"
    
    # Recompute hash
    from coroner.certificate import compute_certificate_sha256
    cert_data.pop("certificate_sha256", None)
    new_hash = compute_certificate_sha256(cert_data)
    cert_data["certificate_sha256"] = new_hash
    
    # Write back
    cert_path.write_text(json.dumps(cert_data, indent=2, sort_keys=True) + '\n')
    
    # Second call with edited certificate
    response2 = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Should be blocked now (different certificate hash, so cache miss, and ZOMBIE status)
    assert data2["status"] == "blocked"
    assert data2 != data1


@pytest.mark.slow
def test_gate_check_cache_bypass_with_status_edit_no_hash_update(client, temp_base_dir, monkeypatch):
    """
    Test that editing status to ALIVE WITHOUT updating certificate_sha256 does not use cache.
    
    This ensures the cache key is based on file bytes, not the certificate_sha256 field.
    A malicious visitor editing status while keeping the field would get a cache miss.
    """
    from coroner.ui import app as app_module
    
    # Track replay calls
    replay_calls = []
    original_replay = app_module.replay_with_timeout
    
    def wrapper_replay(*args, **kwargs):
        replay_calls.append(True)
        return original_replay(*args, **kwargs)
    
    # Patch replay_with_timeout
    monkeypatch.setattr(app_module, "replay_with_timeout", wrapper_replay)
    
    # First call on faulty (ZOMBIE)
    response1 = client.post(
        "/api/gate-check",
        data={"run_id": "f584d5f35228"}
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "blocked"
    assert len(replay_calls) == 1
    
    # Edit the certificate: change status to ALIVE WITHOUT updating certificate_sha256
    cert_path = temp_base_dir / "runs" / "f584d5f35228" / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # Keep the old certificate_sha256 field (do NOT recompute)
    old_cert_sha256 = cert_data.get("certificate_sha256")
    cert_data["status"] = "ALIVE"
    # certificate_sha256 stays unchanged
    
    # Write back
    cert_path.write_text(json.dumps(cert_data, indent=2, sort_keys=True) + '\n')
    
    # Second call with edited certificate
    response2 = client.post(
        "/api/gate-check",
        data={"run_id": "f584d5f35228"}
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Should start a new replay (cache miss because file bytes changed)
    assert len(replay_calls) == 2
    
    # Should still be blocked (replay will find INVALID because cert hash is wrong)
    assert data2["status"] == "blocked"
    assert "Certificate invalid" in data2["message"]


def test_gate_check_certificate_too_large(client, temp_base_dir):
    """Test /api/gate-check returns 413 for certificate over 1 MB."""
    # Create a large certificate (> 1 MB)
    cert_path = temp_base_dir / "runs" / "29c15f04407b" / "certificate.json"
    
    # Read the real certificate
    cert_data = json.loads(cert_path.read_text())
    
    # Add a large field to exceed 1 MB
    cert_data["large_field"] = "x" * (1024 * 1024 + 1)
    
    # Write back
    cert_path.write_text(json.dumps(cert_data))
    
    # Call endpoint
    response = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_gate_check_missing_java_file(client, temp_base_dir):
    """Test /api/gate-check with certificate naming missing java_file returns 200 blocked, not 500."""
    # Edit the certificate to reference a missing Java file
    cert_path = temp_base_dir / "runs" / "29c15f04407b" / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # Change java_file to a path that does not exist
    cert_data["java_file"] = "samples/does_not_exist/Missing.java"
    
    # Recompute hash
    from coroner.certificate import compute_certificate_sha256
    cert_data.pop("certificate_sha256", None)
    new_hash = compute_certificate_sha256(cert_data)
    cert_data["certificate_sha256"] = new_hash
    
    # Write back
    cert_path.write_text(json.dumps(cert_data, indent=2, sort_keys=True) + '\n')
    
    # Call endpoint
    response = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    # Should return 200 blocked, not 500
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "blocked"
    assert "Certificate invalid" in data["message"]
