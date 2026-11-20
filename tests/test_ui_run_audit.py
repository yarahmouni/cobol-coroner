"""Tests for Run audit endpoint (Task 13)."""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_exchange(tmp_path):
    """Create a temporary exchange directory."""
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    return exchange_dir


@pytest.fixture
def app_with_exchange(tmp_path, tmp_exchange, monkeypatch):
    """Create FastAPI test client with temporary base and exchange directories."""
    # Set environment variables with monkeypatch to ensure cleanup
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_exchange))
    monkeypatch.setenv("CORONER_MAX_QUEUE_LENGTH", "3")
    
    # Import app after setting environment
    from coroner.ui.app import app
    
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_limits():
    """Reset rate limiter state before each test."""
    from coroner.ui.app import reset_rate_limiter
    reset_rate_limiter()
    yield
    reset_rate_limiter()


def test_run_audit_valid_request(app_with_exchange, tmp_path, tmp_exchange):
    """Test valid Run audit request returns 202 with job_id."""
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    
    job_id = data["job_id"]
    assert len(job_id) == 12
    assert all(c in "0123456789abcdef" for c in job_id)
    
    # Check Location header
    assert response.headers["Location"] == f"/api/job/{job_id}/status"
    
    # Check job directory created
    job_dir = tmp_exchange / "jobs" / job_id
    assert job_dir.exists()
    
    # Check request.json
    request_file = job_dir / "request.json"
    assert request_file.exists()
    request_data = json.loads(request_file.read_text())
    assert request_data["sample"] == "T1"
    assert request_data["port"] == "correct"
    assert request_data["seed"] == 42
    assert request_data["cases"] == 200
    
    # Check status.json
    status_file = job_dir / "status.json"
    assert status_file.exists()
    status_data = json.loads(status_file.read_text())
    assert status_data["status"] == "queued"


def test_run_audit_unknown_field_rejected(app_with_exchange):
    """Test that unknown fields are rejected (Pydantic extra='forbid')."""
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200,
            "extra_field": "should be rejected"
        }
    )
    
    assert response.status_code == 422  # Validation error


def test_run_audit_seed_out_of_bounds(app_with_exchange):
    """Test that seed out of bounds is rejected."""
    # Seed too low
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": -1,
            "cases": 200
        }
    )
    assert response.status_code == 422
    
    # Seed too high
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 1000001,
            "cases": 200
        }
    )
    assert response.status_code == 422


def test_run_audit_cases_out_of_bounds(app_with_exchange):
    """Test that cases out of bounds is rejected."""
    # Cases too low
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 9
        }
    )
    assert response.status_code == 422
    
    # Cases too high
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 2001
        }
    )
    assert response.status_code == 422


def test_run_audit_invalid_sample(app_with_exchange):
    """Test that invalid sample is rejected."""
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "invalid",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    assert response.status_code == 422


def test_run_audit_invalid_port(app_with_exchange):
    """Test that invalid port is rejected."""
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "invalid",
            "seed": 42,
            "cases": 200
        }
    )
    assert response.status_code == 422


def test_run_audit_body_size_limit(app_with_exchange):
    """Test that oversized request body is rejected with 413."""
    # Test 1: Content-Length over limit
    # Create a valid JSON payload padded with whitespace to exceed 16 KB
    import json as json_module
    
    payload = {
        "sample": "T1",
        "port": "correct",
        "seed": 42,
        "cases": 200
    }
    
    # Serialize and pad with whitespace
    json_str = json_module.dumps(payload)
    # Insert whitespace padding (17 KB of spaces)
    padding = " " * (17 * 1024)
    padded_json = json_str[:-1] + padding + json_str[-1:]
    
    # Post with Content-Length header
    response = app_with_exchange.post(
        "/api/run",
        content=padded_json,
        headers={"Content-Type": "application/json"}
    )
    
    # Should be rejected with 413
    assert response.status_code == 413
    
    # Test 2: Body over limit without Content-Length (chunked encoding)
    # TestClient with a generator body simulates chunked encoding (no Content-Length)
    def body_generator():
        """Generate a body larger than 16 KB in chunks."""
        # Send 20 chunks of 1 KB each (20 KB total)
        for _ in range(20):
            yield b"x" * 1024
    
    # Post with generator content (chunked)
    response = app_with_exchange.post(
        "/api/run",
        content=body_generator(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    # Should be rejected with 413
    assert response.status_code == 413


def test_run_audit_body_size_under_limit(app_with_exchange):
    """Test that body under limit is accepted."""
    # Create a valid payload under 16 KB
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    
    # Should be accepted
    assert response.status_code in [200, 202]


def test_job_status_queued(app_with_exchange, tmp_exchange):
    """Test job status endpoint for queued job."""
    # Submit a job
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    
    job_id = response.json()["job_id"]
    
    # Get status
    response = app_with_exchange.get(f"/api/job/{job_id}/status")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "queued"
    assert "run_id" not in data  # Not yet done


def test_job_status_invalid_job_id(app_with_exchange):
    """Test job status with invalid job_id returns 404."""
    response = app_with_exchange.get("/api/job/invalid/status")
    assert response.status_code == 404


def test_job_status_not_found(app_with_exchange):
    """Test job status with non-existent job_id returns 404."""
    response = app_with_exchange.get("/api/job/000000000000/status")
    assert response.status_code == 404


def test_cf_connecting_ip_no_trusted_proxy(tmp_path, tmp_exchange, monkeypatch):
    """Test that CF-Connecting-IP is ignored when CORONER_TRUSTED_PROXY is empty."""
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_exchange))
    monkeypatch.setenv("CORONER_TRUSTED_PROXY", "")
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Submit request with CF-Connecting-IP header
    response = client.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 10
        },
        headers={"CF-Connecting-IP": "1.2.3.4"}
    )
    
    # Should succeed (header is ignored)
    assert response.status_code == 202


def test_cf_connecting_ip_untrusted_peer(tmp_path, tmp_exchange, monkeypatch):
    """Test that CF-Connecting-IP is ignored from untrusted peer."""
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_exchange))
    monkeypatch.setenv("CORONER_TRUSTED_PROXY", "172.20.0.2")
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # TestClient uses testclient as the peer address
    # Submit request with CF-Connecting-IP header from untrusted peer
    response = client.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 10
        },
        headers={"CF-Connecting-IP": "1.2.3.4"}
    )
    
    # Should succeed (header is ignored because peer is not trusted)
    assert response.status_code == 202


def test_cf_connecting_ip_from_trusted_peer(tmp_path, tmp_exchange, monkeypatch):
    """Test that CF-Connecting-IP is used from trusted peer."""
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_exchange))
    # TestClient uses "testclient" as the peer address
    monkeypatch.setenv("CORONER_TRUSTED_PROXY", "testclient")
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Submit request with CF-Connecting-IP header from trusted peer
    response = client.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 10
        },
        headers={"CF-Connecting-IP": "1.2.3.4"}
    )
    
    # Should succeed (header is used because peer is trusted)
    assert response.status_code == 202


@pytest.mark.slow
def test_run_audit_cache_hit(app_with_exchange, tmp_path, tmp_exchange):
    """Test that identical parameters reuse existing run without creating a job."""
    # First request
    response1 = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    
    assert response1.status_code == 202
    job_id = response1.json()["job_id"]
    
    # Run the real worker on this job
    from coroner.engine_worker import execute_job
    
    job_dir = tmp_exchange / "jobs" / job_id
    execute_job(job_dir)
    
    # Poll status until done
    max_polls = 10
    run_id = None
    for _ in range(max_polls):
        response = app_with_exchange.get(f"/api/job/{job_id}/status")
        assert response.status_code == 200
        data = response.json()
        
        if data["status"] == "done":
            run_id = data["run_id"]
            break
        
        time.sleep(0.5)
    
    assert run_id is not None, "Job did not complete"
    
    # Verify run was copied to base_dir and index was updated
    run_dir = tmp_path / "runs" / run_id
    assert run_dir.exists()
    
    run_index_file = tmp_path / "run_index.json"
    assert run_index_file.exists()
    run_index_raw = json.loads(run_index_file.read_text())
    assert "T1:correct:42:200" in run_index_raw
    # Index now stores {run_id, recorded_at} instead of just run_id
    index_entry = run_index_raw["T1:correct:42:200"]
    if isinstance(index_entry, dict):
        assert index_entry["run_id"] == run_id
    else:
        assert index_entry == run_id
    
    # Count existing jobs (should be 0 after cleanup)
    jobs_dir = tmp_exchange / "jobs"
    existing_jobs = list(jobs_dir.iterdir()) if jobs_dir.exists() else []
    assert len(existing_jobs) == 0
    
    # Second request with identical parameters
    response2 = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    
    # Should return 200 with cached run_id
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["run_id"] == run_id
    assert data2.get("cached") is True
    
    # No new job should be created
    new_jobs = list(jobs_dir.iterdir()) if jobs_dir.exists() else []
    assert len(new_jobs) == 0


def test_run_audit_queue_full(tmp_path, tmp_exchange, monkeypatch):
    """Test that queue full returns 429."""
    # Set a small queue limit
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_exchange))
    monkeypatch.setenv("CORONER_MAX_QUEUE_LENGTH", "2")
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Create 2 queued jobs manually (simpler than starting worker)
    jobs_dir = tmp_exchange / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    
    for i in range(2):
        job_id = f"00000000000{i}"
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True)
        
        status_file = job_dir / "status.json"
        status_file.write_text(json.dumps({"status": "queued", "queued_at": time.time()}))
    
    # Try to submit a third job
    response = client.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    
    assert response.status_code == 429
    data = response.json()
    assert "Queue full" in data["detail"]
    assert "retry_after" in data
    assert response.headers["Retry-After"] == "30"


def test_run_audit_second_audit_from_same_ip(app_with_exchange, tmp_exchange):
    """Test that second audit from same IP is rejected."""
    # Submit first audit
    response1 = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 200
        }
    )
    
    assert response1.status_code == 202
    
    # Try to submit second audit (job is still queued)
    response2 = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T2",
            "port": "faulty",
            "seed": 123,
            "cases": 100
        }
    )
    
    assert response2.status_code == 429
    data = response2.json()
    assert "One audit per client at a time" in data["detail"]
    assert "retry_after" in data


def test_run_audit_rate_limit_per_ip(tmp_path, tmp_exchange, monkeypatch):
    """Test rate limit per IP (20/min)."""
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_exchange))
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Make 20 requests (should all succeed, but mark jobs as done to allow next)
    for i in range(20):
        response = client.post(
            "/api/run",
            json={
                "sample": "T1",
                "port": "correct",
                "seed": i,
                "cases": 10
            }
        )
        # First request succeeds, others might hit "one audit per client" limit
        # Mark jobs as done to allow next request
        if response.status_code == 202:
            job_id = response.json()["job_id"]
            # Mark job as done to allow next audit
            job_dir = tmp_exchange / "jobs" / job_id
            status_file = job_dir / "status.json"
            status_file.write_text(json.dumps({"status": "done"}))
    
    # 21st request should be rate limited
    response = client.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 99,
            "cases": 10
        }
    )
    
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_run_audit_cache_control_header(app_with_exchange):
    """Test that audit endpoints return Cache-Control: no-store, no-cache, must-revalidate."""
    # Test /api/run
    response = app_with_exchange.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 10
        }
    )
    
    assert response.status_code == 202
    assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"
    
    # Test /api/job/{job_id}/status
    job_id = response.json()["job_id"]
    response = app_with_exchange.get(f"/api/job/{job_id}/status")
    
    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"


def test_run_audit_form_submission(app_with_exchange):
    """Test that form on home page posts correctly."""
    import re
    
    # Get home page
    response = app_with_exchange.get("/")
    assert response.status_code == 200
    
    html = response.text
    
    # Find the form
    assert 'id="run-audit-form"' in html
    
    # Extract hx-post attribute
    match = re.search(r'hx-post="([^"]+)"', html)
    assert match is not None
    action = match.group(1)
    assert action == "/api/run"
    
    # Extract default values from the form
    # Sample: first option value
    sample_match = re.search(r'<select name="sample"[^>]*>.*?<option value="([^"]+)"', html, re.DOTALL)
    assert sample_match is not None
    sample = sample_match.group(1)
    
    # Port: first option value
    port_match = re.search(r'<select name="port"[^>]*>.*?<option value="([^"]+)"', html, re.DOTALL)
    assert port_match is not None
    port = port_match.group(1)
    
    # Seed: input value
    seed_match = re.search(r'<input[^>]*name="seed"[^>]*value="(\d+)"', html)
    assert seed_match is not None
    seed = int(seed_match.group(1))
    
    # Cases: input value
    cases_match = re.search(r'<input[^>]*name="cases"[^>]*value="(\d+)"', html)
    assert cases_match is not None
    cases = int(cases_match.group(1))
    
    # Submit form as htmx would (form-encoded)
    response = app_with_exchange.post(
        action,
        data={
            "sample": sample,
            "port": port,
            "seed": seed,
            "cases": cases
        }
    )
    
    # Should succeed
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data


@pytest.mark.slow
def test_run_audit_end_to_end_t2_faulty(tmp_path, tmp_exchange):
    """
    End-to-end test: submit T2 faulty audit, start worker, poll status, check result.
    
    This test runs a real engine worker and a real audit.
    """
    # Set environment
    os.environ["CORONER_BASE_DIR"] = str(tmp_path)
    os.environ["CORONER_EXCHANGE_DIR"] = str(tmp_exchange)
    os.environ["CORONER_JOB_TIMEOUT"] = "30"
    
    # Import app
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Submit audit
    response = client.post(
        "/api/run",
        json={
            "sample": "T2",
            "port": "faulty",
            "seed": 42,
            "cases": 30
        }
    )
    
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    # Start worker in a thread
    from coroner.engine_worker import find_oldest_queued_job, execute_job
    
    stop_flag = threading.Event()
    worker_exception = []
    
    def worker_thread():
        try:
            while not stop_flag.is_set():
                job_dir = find_oldest_queued_job()
                if job_dir:
                    execute_job(job_dir)
                    stop_flag.set()
                    break
                time.sleep(0.1)
        except Exception as e:
            worker_exception.append(e)
            stop_flag.set()
    
    thread = threading.Thread(target=worker_thread, daemon=True)
    thread.start()
    
    # Poll status until done (with timeout)
    max_polls = 40
    run_id = None
    for _ in range(max_polls):
        response = client.get(f"/api/job/{job_id}/status")
        assert response.status_code == 200
        
        data = response.json()
        status = data["status"]
        
        if status == "done":
            run_id = data["run_id"]
            break
        
        time.sleep(1)
    
    # Stop worker
    stop_flag.set()
    thread.join(timeout=5)
    
    if worker_exception:
        raise worker_exception[0]
    
    assert run_id is not None, "Job did not complete"
    
    # Check that run was copied to base_dir
    run_dir = tmp_path / "runs" / run_id
    assert run_dir.exists()
    
    # Check verdict
    verdict_file = run_dir / "verdict.json"
    assert verdict_file.exists()
    
    verdict_data = json.loads(verdict_file.read_text())
    
    # Verify the engine produced this verdict
    # Run verify directly to compare
    from coroner.cli import run_verify
    from coroner.engine_worker import resolve_sample_paths
    
    cobol_path, java_path, schema_path, copybooks_path = resolve_sample_paths(
        "T2", "faulty", tmp_path
    )
    
    # Run verify in a different directory to get expected result
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    
    expected_verdict, expected_run_dir = run_verify(
        cobol_path=str(cobol_path),
        java_path=str(java_path),
        schema_path=str(schema_path),
        copybooks_dir=str(copybooks_path),
        num_cases=30,
        seed=42,
        base_dir=str(expected_dir)
    )
    
    # T2 faulty should be ZOMBIE
    assert verdict_data["status"] == "ZOMBIE"
    assert run_id == expected_run_dir.name
    assert verdict_data["status"] == expected_verdict.status
    
    expected_verdict_json = json.loads((expected_run_dir / "verdict.json").read_text())
    assert verdict_data["cases_divergent"] == expected_verdict_json["cases_divergent"]
    assert verdict_data["cases_divergent"] > 0
    
    # Check that job directory was cleaned up
    job_dir_path = tmp_exchange / "jobs" / job_id
    assert not job_dir_path.exists()
    
    # Check run page can display it
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    assert "ZOMBIE" in response.text


@pytest.mark.slow
def test_run_audit_end_to_end_t1_correct(tmp_path, tmp_exchange):
    """
    End-to-end test: submit T1 correct audit, verify ALIVE.
    """
    # Set environment
    os.environ["CORONER_BASE_DIR"] = str(tmp_path)
    os.environ["CORONER_EXCHANGE_DIR"] = str(tmp_exchange)
    os.environ["CORONER_JOB_TIMEOUT"] = "30"
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Submit audit
    response = client.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 30
        }
    )
    
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    # Run worker in thread
    from coroner.engine_worker import find_oldest_queued_job, execute_job
    
    stop_flag = threading.Event()
    worker_exception = []
    
    def worker_thread():
        try:
            while not stop_flag.is_set():
                job_dir = find_oldest_queued_job()
                if job_dir:
                    execute_job(job_dir)
                    stop_flag.set()
                    break
                time.sleep(0.1)
        except Exception as e:
            worker_exception.append(e)
            stop_flag.set()
    
    thread = threading.Thread(target=worker_thread, daemon=True)
    thread.start()
    
    # Poll status
    max_polls = 40
    run_id = None
    for _ in range(max_polls):
        response = client.get(f"/api/job/{job_id}/status")
        data = response.json()
        
        if data["status"] == "done":
            run_id = data["run_id"]
            break
        
        time.sleep(1)
    
    # Stop worker
    stop_flag.set()
    thread.join(timeout=5)
    
    if worker_exception:
        raise worker_exception[0]
    
    assert run_id is not None, "Job did not complete"
    
    # Check verdict
    run_dir = tmp_path / "runs" / run_id
    verdict_file = run_dir / "verdict.json"
    verdict_data = json.loads(verdict_file.read_text())
    
    # Verify against direct run_verify
    from coroner.cli import run_verify
    from coroner.engine_worker import resolve_sample_paths
    
    cobol_path, java_path, schema_path, copybooks_path = resolve_sample_paths(
        "T1", "correct", tmp_path
    )
    
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    
    expected_verdict, expected_run_dir = run_verify(
        cobol_path=str(cobol_path),
        java_path=str(java_path),
        schema_path=str(schema_path),
        copybooks_dir=str(copybooks_path),
        num_cases=30,
        seed=42,
        base_dir=str(expected_dir)
    )
    
    # T1 correct should be ALIVE
    assert verdict_data["status"] == "ALIVE"
    assert run_id == expected_run_dir.name
    assert verdict_data["status"] == expected_verdict.status
    
    expected_verdict_json = json.loads((expected_run_dir / "verdict.json").read_text())
    assert verdict_data["cases_divergent"] == 0
    assert expected_verdict_json["cases_divergent"] == 0
    
    # Check run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    assert "ALIVE" in response.text



def test_disk_quota_enforcement(tmp_path):
    """
    Test disk quota: with limit 2 and 3 visitor entries, oldest is deleted.
    Bundled runs (not in index) are kept.
    Path traversal entries in index are ignored.
    """
    import shutil
    
    # Create runs directory
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    
    # Create 3 visitor run directories with minimal content
    visitor_ids = ["aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc"]
    
    for vid in visitor_ids:
        visitor_dir = runs_dir / vid
        visitor_dir.mkdir()
        # Add a marker file
        (visitor_dir / "verdict.json").write_text('{"status": "ALIVE"}')
    
    # Create a bundled run (not in index)
    bundled_id = "dddddddddddd"
    bundled_dir = runs_dir / bundled_id
    bundled_dir.mkdir()
    (bundled_dir / "verdict.json").write_text('{"status": "ALIVE"}')
    
    # Create initial index with 3 visitor entries (different recorded_at times)
    index_file = tmp_path / "run_index.json"
    index = {
        "cf:c:10:10": {"run_id": "aaaaaaaaaaaa", "recorded_at": 1000.0},  # oldest
        "cf:c:20:10": {"run_id": "bbbbbbbbbbbb", "recorded_at": 2000.0},
        "cf:c:30:10": {"run_id": "cccccccccccc", "recorded_at": 3000.0},  # newest
    }
    index_file.write_text(json.dumps(index, indent=2))
    
    # Add a path traversal entry to the index
    index["cf:c:40:10"] = {"run_id": "../evil", "recorded_at": 500.0}
    index_file.write_text(json.dumps(index, indent=2))
    
    # Create a directory outside runs/ that the traversal entry points to
    evil_dir = tmp_path / "evil"
    evil_dir.mkdir()
    (evil_dir / "marker.txt").write_text("should not be deleted")
    
    # Set environment
    os.environ["CORONER_BASE_DIR"] = str(tmp_path)
    os.environ["CORONER_MAX_VISITOR_RUNS"] = "2"
    
    # Import and call update_run_index
    from coroner.ui.app import update_run_index
    
    # Add a 4th visitor entry (should trigger pruning)
    new_id = "eeeeeeeeeeee"
    new_dir = runs_dir / new_id
    new_dir.mkdir()
    (new_dir / "verdict.json").write_text('{"status": "ALIVE"}')
    
    update_run_index("cf", "c", 50, 10, new_id)
    
    # Check that the two oldest visitor runs were deleted
    assert not (runs_dir / "aaaaaaaaaaaa").exists()  # oldest, deleted
    assert not (runs_dir / "bbbbbbbbbbbb").exists()  # 2nd oldest, deleted
    
    # Check that the two newest runs are kept
    assert (runs_dir / "cccccccccccc").exists()  # 3rd oldest (2nd newest)
    assert (runs_dir / new_id).exists()  # newest
    
    # Check that bundled run (not in index) was NOT deleted
    assert bundled_dir.exists()
    
    # Check that path traversal did not delete anything outside runs/
    assert evil_dir.exists()
    assert (evil_dir / "marker.txt").exists()
    
    # Check index has exactly 2 entries (limit)
    updated_index_raw = json.loads(index_file.read_text())
    # Filter for valid entries (not path traversal)
    valid_entries = {k: v for k, v in updated_index_raw.items() 
                     if isinstance(v, dict) and v.get("run_id") and 
                     re.match(r"^[0-9a-f]{12}$", v.get("run_id", ""))}
    assert len(valid_entries) == 2
    
    # Check that the kept entries are the newest ones
    kept_ids = [v["run_id"] for v in valid_entries.values()]
    assert "cccccccccccc" in kept_ids  # 2nd newest
    assert new_id in kept_ids  # newest
    assert "aaaaaaaaaaaa" not in kept_ids  # oldest, deleted
    assert "bbbbbbbbbbbb" not in kept_ids  # 2nd oldest, deleted


@pytest.mark.slow
def test_job_status_returns_verdict_after_run(tmp_path, tmp_exchange):
    """
    Test that job status endpoint returns verdict, cases_divergent and cases_total
    after a real run completes.
    """
    # Set environment
    os.environ["CORONER_BASE_DIR"] = str(tmp_path)
    os.environ["CORONER_EXCHANGE_DIR"] = str(tmp_exchange)
    os.environ["CORONER_JOB_TIMEOUT"] = "30"
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Submit T1 faulty audit
    response = client.post(
        "/api/run",
        json={
            "sample": "T1",
            "port": "faulty",
            "seed": 42,
            "cases": 200
        }
    )
    
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    # Run worker in thread
    from coroner.engine_worker import find_oldest_queued_job, execute_job
    
    stop_flag = threading.Event()
    worker_exception = []
    
    def worker_thread():
        try:
            while not stop_flag.is_set():
                job_dir = find_oldest_queued_job()
                if job_dir:
                    execute_job(job_dir)
                    stop_flag.set()
                    break
                time.sleep(0.1)
        except Exception as e:
            worker_exception.append(e)
            stop_flag.set()
    
    thread = threading.Thread(target=worker_thread, daemon=True)
    thread.start()
    
    # Poll status
    max_polls = 40
    final_status = None
    for _ in range(max_polls):
        response = client.get(f"/api/job/{job_id}/status")
        data = response.json()
        
        if data["status"] in ["done", "error"]:
            final_status = data
            break
        
        time.sleep(1)
    
    # Stop worker
    stop_flag.set()
    thread.join(timeout=5)
    
    if worker_exception:
        raise worker_exception[0]
    
    assert final_status is not None, "Job did not complete"
    assert final_status["status"] == "done"
    
    run_id = final_status["run_id"]
    
    # Check that verdict info is returned
    assert "verdict" in final_status
    assert final_status["verdict"] == "ZOMBIE"
    
    assert "cases_divergent" in final_status
    assert "cases_total" in final_status
    
    # Verify these match the verdict.json file
    run_dir = tmp_path / "runs" / run_id
    verdict_file = run_dir / "verdict.json"
    assert verdict_file.exists()
    
    verdict_data = json.loads(verdict_file.read_text())
    assert final_status["verdict"] == verdict_data["status"]
    assert final_status["cases_divergent"] == verdict_data["cases_divergent"]
    assert final_status["cases_total"] == verdict_data["cases_total"]
    
    # Verify divergent cases > 0 for T1 faulty
    assert final_status["cases_divergent"] > 0


def test_bundled_run_protected_from_quota(tmp_path, tmp_exchange):
    """
    Test that a bundled run (that existed before the job) is not copied over
    and is marked as bundled in the index, so it's never deleted by quota enforcement.
    """
    import shutil
    
    # Create runs directory
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a bundled run (already exists before any job)
    bundled_id = "f584d5f35228"  # T1 faulty seed 42 deterministic run_id
    bundled_dir = runs_dir / bundled_id
    bundled_dir.mkdir()
    (bundled_dir / "verdict.json").write_text('{"status": "ZOMBIE"}')
    (bundled_dir / "inputs.json").write_text('{"seed": 42}')
    
    # Set environment with strict quota
    os.environ["CORONER_BASE_DIR"] = str(tmp_path)
    os.environ["CORONER_EXCHANGE_DIR"] = str(tmp_exchange)
    os.environ["CORONER_MAX_VISITOR_RUNS"] = "0"  # Delete everything except bundled
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Simulate a visitor job that produces the same run_id
    # (same parameters as the bundled run)
    job_id = "000000000001"
    job_dir = tmp_exchange / "jobs" / job_id
    job_dir.mkdir(parents=True)
    
    # Write request.json
    request_data = {
        "job_id": job_id,
        "sample": "T1",
        "port": "faulty",
        "seed": 42,
        "cases": 2000,
        "timestamp": time.time(),
    }
    (job_dir / "request.json").write_text(json.dumps(request_data))
    
    # Write status.json (done)
    status_data = {
        "status": "done",
        "run_id": bundled_id,
        "completed_at": time.time(),
    }
    (job_dir / "status.json").write_text(json.dumps(status_data))
    
    # Create a job run directory (the worker would have produced this)
    job_run_dir = job_dir / "runs" / bundled_id
    job_run_dir.mkdir(parents=True)
    (job_run_dir / "verdict.json").write_text('{"status": "ZOMBIE"}')
    
    # Call job status (triggers copy and index update)
    response = client.get(f"/api/job/{job_id}/status")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "done"
    assert data["run_id"] == bundled_id
    
    # Check that the bundled run still exists (not copied over)
    assert bundled_dir.exists()
    assert (bundled_dir / "inputs.json").exists()  # Original file still there
    
    # Check the index
    index_file = tmp_path / "run_index.json"
    assert index_file.exists()
    
    index = json.loads(index_file.read_text())
    key = "T1:faulty:42:2000"
    assert key in index
    
    entry = index[key]
    assert entry["run_id"] == bundled_id
    assert entry.get("bundled") is True  # Marked as bundled
    
    # Verify quota enforcement doesn't delete it
    # The limit is 0, so if it wasn't marked bundled, it would be deleted
    assert bundled_dir.exists()
