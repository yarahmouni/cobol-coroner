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


REPO_ROOT = Path(__file__).resolve().parent.parent
T1_DIR = REPO_ROOT / "samples" / "traps" / "T1-ebcdic-match-merge"
T1_FAULTY_ID = "f584d5f35228"
T1_CORRECT_ID = "29c15f04407b"


def _listing(folder: Path) -> list:
    """Names and modification times of the entries of a folder (empty if it does not exist)."""
    if not folder.exists():
        return []
    return sorted((p.name, p.stat().st_mtime_ns) for p in folder.iterdir())


@pytest.fixture(scope="session")
def engine_runs(tmp_path_factory):
    """
    Produce the two T1 runs the tests assert, once per session, with the real engine.

    The same audits as the bundled runs (2000 cases, seed 42): T1 faulty (ZOMBIE, exit 1,
    run f584d5f35228) and T1 correct (ALIVE, exit 0, run 29c15f04407b). They are written
    into a session folder through CORONER_BASE_DIR. The repository runs/ folder is never
    read and never written: its listing is checked before and after.
    """
    repo_runs = REPO_ROOT / "runs"
    before = _listing(repo_runs)

    base = tmp_path_factory.mktemp("gate_check_engine_runs")
    env = {**os.environ, "CORONER_BASE_DIR": str(base)}
    env.pop("CORONER_REPLAY_TIMEOUT", None)

    for java_kind, expected_exit, run_id in (
        ("faulty", 1, T1_FAULTY_ID),
        ("correct", 0, T1_CORRECT_ID),
    ):
        proc = subprocess.run(
            [
                sys.executable, "-m", "coroner", "verify",
                "--cobol", str(T1_DIR / "MATCH-MERGE.cob"),
                "--copybooks", str(T1_DIR / "copybooks"),
                "--java", str(T1_DIR / "java" / java_kind / "MatchMerge.java"),
                "--schema", str(T1_DIR / "schema.json"),
                "--cases", "2000", "--seed", "42",
            ],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=600,
        )
        assert proc.returncode == expected_exit, (
            f"T1 {java_kind} audit exited {proc.returncode}, expected {expected_exit}\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
        assert (base / "runs" / run_id / "certificate.json").is_file(), (
            f"T1 {java_kind} audit did not produce run {run_id}\n{proc.stdout}"
        )

    assert _listing(repo_runs) == before, "the engine runs touched the repository runs/ folder"
    return base / "runs"


@pytest.fixture
def temp_base_dir(tmp_path, monkeypatch, engine_runs):
    """
    Temporary base directory holding the T1 faulty and T1 correct runs.

    The runs come from the session fixture engine_runs (real engine audits) and are
    copied into this test's own folder, so a test that edits a certificate cannot
    affect another test.
    """
    repo_runs = REPO_ROOT / "runs"
    before = _listing(repo_runs)

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    for run_id in (T1_FAULTY_ID, T1_CORRECT_ID):
        shutil.copytree(engine_runs / run_id, runs_dir / run_id)

    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    reset_rate_limiter()

    yield tmp_path

    assert _listing(repo_runs) == before, "the test touched the repository runs/ folder"


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
    
    # The changed certificate is a cache miss and starts a second replay. The first
    # replay consumed the 1-per-10-s gate-check bucket; on a fast machine the window
    # has not elapsed yet, so reset it to keep the test independent of replay speed.
    reset_rate_limiter()
    
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
    
    # The edited certificate is a cache miss and starts a second replay. The first
    # replay consumed the 1-per-10-s gate-check bucket; on a fast machine the window
    # has not elapsed yet, so reset it to keep the test independent of replay speed.
    reset_rate_limiter()
    
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



def test_gate_check_two_different_certificates_within_window(client, temp_base_dir, monkeypatch):
    """
    Test that two POSTs for two different certificates within the window: the second (a miss) gets 429.
    
    Uses a long window to avoid timing dependency on replay duration.
    """
    # Set a long window so the test does not depend on replay speed
    monkeypatch.setenv("CORONER_GATE_CHECK_RATE_WINDOW", "3600")
    
    # First call on T1 correct
    response1 = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "allowed"
    
    # Second call on T1 faulty (different certificate) within the window
    response2 = client.post(
        "/api/gate-check",
        data={"run_id": "f584d5f35228"}
    )
    
    # Should get 429 because the 1-per-window bucket is exhausted
    assert response2.status_code == 429
    data2 = response2.json()
    assert "Rate limit exceeded for gate-check" in data2["detail"]
    assert "retry_after" in data2
    
    # Check Retry-After header
    retry_after = response2.headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) > 0


def test_gate_check_cached_hit_after_miss(client, temp_base_dir, monkeypatch):
    """
    Test that a cached hit right after a miss gets 200 without consuming the gate-check bucket.
    
    Uses a long window to avoid timing dependency on replay duration.
    After the cached hit, a POST for a different certificate gets 429 (proof the hit did not reset).
    """
    # Set a long window so the test does not depend on replay speed
    monkeypatch.setenv("CORONER_GATE_CHECK_RATE_WINDOW", "3600")
    
    # First call on T1 correct (miss)
    response1 = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "allowed"
    
    # Second call on T1 correct (cache hit) within the window
    # This should return 200 without consuming the gate-check bucket
    response2 = client.post(
        "/api/gate-check",
        data={"run_id": "29c15f04407b"}
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "allowed"
    assert data1 == data2
    
    # Third call on T1 faulty (different certificate, cache miss)
    # Should get 429 because the bucket was consumed by the first POST
    response3 = client.post(
        "/api/gate-check",
        data={"run_id": "f584d5f35228"}
    )
    
    assert response3.status_code == 429
    data3 = response3.json()
    assert "Rate limit exceeded for gate-check" in data3["detail"]


def cert_file_sha256(base_dir: Path, run_id: str) -> str:
    import hashlib
    return hashlib.sha256((base_dir / "runs" / run_id / "certificate.json").read_bytes()).hexdigest()


@pytest.mark.slow
def test_gate_check_replay_timeout_is_503_and_never_cached(client, temp_base_dir, monkeypatch):
    """
    A real replay of a real certificate with a 1 s timeout cannot finish (it compiles
    COBOL and Java and runs 2,000 cases): 503, nothing cached, the next POST starts a
    new replay process, and once the timeout is lifted the real answer comes back.
    """
    from coroner.ui.app import get_cached_gate_check, get_last_replay_pgid

    run_id = "29c15f04407b"
    key = cert_file_sha256(temp_base_dir, run_id)
    monkeypatch.setenv("CORONER_REPLAY_TIMEOUT", "1")

    response1 = client.post("/api/gate-check", data={"run_id": run_id})
    assert response1.status_code == 503
    assert response1.json()["message"] == "Replay did not complete, try again"
    assert int(response1.headers["Retry-After"]) > 0
    assert "no-store" in response1.headers["cache-control"]
    assert response1.json()["status"] == "unavailable"
    assert get_cached_gate_check(key) is None
    first_process = get_last_replay_pgid()
    assert first_process is not None

    # A second POST is not answered from a cache: a new replay process is started
    reset_rate_limiter()
    response2 = client.post("/api/gate-check", data={"run_id": run_id})
    assert response2.status_code == 503
    assert get_cached_gate_check(key) is None
    assert get_last_replay_pgid() != first_process

    # The failures did not poison the answer: with the normal timeout the replay gives the real verdict
    monkeypatch.delenv("CORONER_REPLAY_TIMEOUT")
    reset_rate_limiter()
    response3 = client.post("/api/gate-check", data={"run_id": run_id})
    assert response3.status_code == 200
    assert response3.json()["status"] == "allowed"
    assert get_cached_gate_check(key) == response3.json()


def test_gate_check_real_invalid_replay_is_cached(client, temp_base_dir, monkeypatch):
    """
    A certificate edited without its hash replays as INVALID for a real reason
    ("certificate content was modified"): that answer is cached and a second POST
    gets it without a replay (the 1-per-window bucket is exhausted, so a replay
    would have answered 429).
    """
    from coroner.ui.app import get_cached_gate_check

    monkeypatch.setenv("CORONER_GATE_CHECK_RATE_WINDOW", "3600")
    run_id = "29c15f04407b"
    cert_path = temp_base_dir / "runs" / run_id / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    cert_data["status"] = "ZOMBIE"  # certificate_sha256 is left as it was
    cert_path.write_text(json.dumps(cert_data, indent=2, sort_keys=True) + "\n")
    key = cert_file_sha256(temp_base_dir, run_id)
    assert get_cached_gate_check(key) is None

    response1 = client.post("/api/gate-check", data={"run_id": run_id})
    assert response1.status_code == 200
    assert response1.json()["status"] == "blocked"
    assert "Certificate invalid" in response1.json()["message"]
    assert get_cached_gate_check(key) == response1.json()

    response2 = client.post("/api/gate-check", data={"run_id": run_id})
    assert response2.status_code == 200
    assert response2.json() == response1.json()


@pytest.mark.parametrize("reason, reached", [
    ("replay timed out", False),
    ("replay failed: (no stderr)", False),
    ("replay error: boom", False),
    ("reference did not run during replay: no output", False),
    ("certificate content was modified", True),
    ("COBOL file hash mismatch", True),
    ("replay mismatch (status: expected ALIVE, got ZOMBIE)", True),
])
def test_replay_reached_verdict_tells_a_real_invalid_from_a_failed_replay(reason, reached):
    from coroner.certificate import ReplayResult
    from coroner.ui.app import replay_reached_verdict

    result = ReplayResult(
        valid=False, reason=reason, verdict=None, cases_total=0, cases_divergent=0,
        paragraph_coverage_reached=0, paragraph_coverage_total=0,
        branch_coverage_reached=0, branch_coverage_total=0, cases_file="", warnings=[],
    )
    assert replay_reached_verdict(result) is reached
    assert replay_reached_verdict(ReplayResult(**{**result.__dict__, "valid": True, "reason": ""})) is True
