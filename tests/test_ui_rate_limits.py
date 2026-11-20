"""Tests for UI rate limits and validation (Task 15)."""
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.ui.app import app


@pytest.fixture
def client(tmp_path):
    """Test client with temporary base directory."""
    os.environ["CORONER_BASE_DIR"] = str(tmp_path)
    os.environ["CORONER_EXCHANGE_DIR"] = str(tmp_path / "exchange")
    yield TestClient(app)
    os.environ.pop("CORONER_BASE_DIR", None)
    os.environ.pop("CORONER_EXCHANGE_DIR", None)


@pytest.mark.slow
def test_api_run_rate_limit_endpoint_specific(client, tmp_path):
    """Test /api/run endpoint-specific rate limit (5/min per IP)."""
    # Reset rate limiter to ensure clean state
    from coroner.ui.app import reset_rate_limiter
    reset_rate_limiter()
    
    # Create exchange and base directories
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    
    # Point to temp directories
    os.environ["CORONER_EXCHANGE_DIR"] = str(exchange_dir)
    os.environ["CORONER_BASE_DIR"] = str(base_dir)
    
    try:
        # Make 5 requests with different seeds, running each job to completion
        # so the client has no active audit when sending the next one
        from coroner import engine_worker
        
        for i in range(5):
            response = client.post(
                "/api/run",
                data={
                    "sample": "credit-fees",
                    "port": "correct",
                    "seed": str(i + 1000),
                    "cases": "10"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            assert response.status_code == 202, f"Request {i+1} failed with {response.status_code}"
            
            # Extract job_id from Location header
            location = response.headers.get("location", "")
            job_id = location.split("/")[-2] if "/status" in location else None
            assert job_id, f"No job_id in Location: {location}"
            
            # Execute the job
            job_dir = exchange_dir / "jobs" / job_id
            assert job_dir.exists(), f"Job directory {job_dir} does not exist"
            engine_worker.execute_job(job_dir)
            
            # Poll until done
            max_polls = 60
            for _ in range(max_polls):
                status_response = client.get(f"/api/job/{job_id}/status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get("status") in ["done", "error"]:
                        break
                time.sleep(0.5)
        
        # 6th request should be rate-limited by the /api/run endpoint limit (5/min)
        response = client.post(
            "/api/run",
            data={
                "sample": "credit-fees",
                "port": "correct",
                "seed": "9999",
                "cases": "10"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 429
        assert "retry-after" in response.headers
        retry_after = int(response.headers["retry-after"])
        assert retry_after > 0
        
        # Verify it's the endpoint limit, not the one-active-audit limit
        data = response.json()
        assert data["detail"] == "Rate limit exceeded for this endpoint"
        
        # Check Cache-Control
        assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    finally:
        os.environ.pop("CORONER_EXCHANGE_DIR", None)
        os.environ.pop("CORONER_BASE_DIR", None)


def test_rate_limiter_unit():
    """Test the rate limiter directly (fast unit test)."""
    from coroner.ui.app import check_rate_limit, reset_rate_limiter
    
    reset_rate_limiter()
    
    client1 = "192.168.1.1"
    client2 = "192.168.1.2"
    endpoint_key = "/api/run"
    limit = 5
    window = 60
    
    # Client 1: 5 requests allowed
    for i in range(5):
        key = f"{endpoint_key}:{client1}"
        retry_after = check_rate_limit(key, limit, window)
        assert retry_after is None, f"Request {i+1} was denied"
    
    # Client 1: 6th request denied
    key = f"{endpoint_key}:{client1}"
    retry_after = check_rate_limit(key, limit, window)
    assert retry_after is not None, "6th request should be denied"
    assert retry_after > 0, "Retry-after should be positive"
    
    # Client 2: still allowed (separate limit)
    key = f"{endpoint_key}:{client2}"
    retry_after = check_rate_limit(key, limit, window)
    assert retry_after is None, "Client 2 should be allowed"


def test_api_verify_rate_limit_short_window(client, tmp_path):
    """Test /api/verify rate limit (1 per window, configurable for test)."""
    # Use short window for test
    os.environ["CORONER_VERIFY_RATE_WINDOW"] = "1"
    
    # Create a run with certificate
    run_id = "aabbccddeeff"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    
    # Minimal certificate
    cert_data = {
        "run_id": run_id,
        "status": "ALIVE",
        "cases_total": 10,
        "cases_divergent": 0,
        "random_seed": 42,
        "certificate_sha256": "dummy"
    }
    
    import json
    (run_dir / "certificate.json").write_text(json.dumps(cert_data))
    
    # First request should succeed or fail (depends on replay), but not be rate-limited
    response1 = client.post(
        "/api/verify",
        data={"run_id": run_id},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response1.status_code in [200, 500]  # May fail replay but not rate-limited
    
    # Second request within 1 second should be rate-limited
    response2 = client.post(
        "/api/verify",
        data={"run_id": run_id},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response2.status_code == 429
    assert "retry-after" in response2.headers
    retry_after = int(response2.headers["retry-after"])
    assert retry_after > 0
    
    # Check Cache-Control on 429
    assert response2.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    
    # Wait for window to pass
    time.sleep(1.5)
    
    # Third request after window should succeed (or fail replay, but not rate-limited)
    response3 = client.post(
        "/api/verify",
        data={"run_id": run_id},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response3.status_code in [200, 500]  # Not 429
    
    os.environ.pop("CORONER_VERIFY_RATE_WINDOW", None)


def test_api_tamper_rate_limit_short_window(client, tmp_path):
    """Test /api/tamper rate limit (1 per window, configurable for test)."""
    # Use short window for test
    os.environ["CORONER_TAMPER_RATE_WINDOW"] = "1"
    
    # Create exchange dir
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    # Create a run with certificate
    run_id = "112233445566"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    
    # Minimal certificate
    cert_data = {
        "run_id": run_id,
        "status": "ALIVE",
        "cases_total": 10,
        "cases_divergent": 0,
        "random_seed": 42,
        "certificate_sha256": "dummy"
    }
    
    import json
    (run_dir / "certificate.json").write_text(json.dumps(cert_data))
    
    # First request should succeed or fail (depends on replay), but not be rate-limited
    response1 = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ZOMBIE",
            "cases_total": "10",
            "cases_divergent": "5",
            "random_seed": "42"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response1.status_code in [200, 500]  # May fail replay but not rate-limited
    
    # Second request within 1 second should be rate-limited
    response2 = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ZOMBIE",
            "cases_total": "10",
            "cases_divergent": "5",
            "random_seed": "42"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response2.status_code == 429
    assert "retry-after" in response2.headers
    retry_after = int(response2.headers["retry-after"])
    assert retry_after > 0
    
    # Check Cache-Control on 429
    assert response2.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    
    # Wait for window to pass
    time.sleep(1.5)
    
    # Third request after window should succeed (or fail replay, but not rate-limited)
    response3 = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ZOMBIE",
            "cases_total": "10",
            "cases_divergent": "5",
            "random_seed": "42"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response3.status_code in [200, 500]  # Not 429
    
    os.environ.pop("CORONER_TAMPER_RATE_WINDOW", None)


def test_queue_full_has_retry_after(client, tmp_path):
    """Test queue full response includes Retry-After."""
    # Set very small queue
    os.environ["CORONER_MAX_QUEUE_LENGTH"] = "0"
    
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    # Try to submit audit with full queue
    response = client.post(
        "/api/run",
        data={
            "sample": "credit-fees",
            "port": "correct",
            "seed": "42",
            "cases": "10"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 429
    assert "retry-after" in response.headers
    assert response.headers["retry-after"] == "30"
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    
    os.environ.pop("CORONER_MAX_QUEUE_LENGTH", None)


def test_cache_control_api_run_success(client, tmp_path):
    """Test Cache-Control on /api/run success responses."""
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    response = client.post(
        "/api/run",
        data={
            "sample": "credit-fees",
            "port": "correct",
            "seed": "42",
            "cases": "10"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code in [200, 202]
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_cache_control_api_run_validation_error(client, tmp_path):
    """Test Cache-Control on /api/run validation error (422)."""
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    response = client.post(
        "/api/run",
        data={
            "sample": "invalid-sample",
            "port": "correct",
            "seed": "42",
            "cases": "10"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_cache_control_api_run_body_too_large(client, tmp_path):
    """Test Cache-Control on 413 response from body size limit."""
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    # Send very large body (> 16 KB)
    large_data = "x" * 20000
    
    response = client.post(
        "/api/run",
        data=large_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_cache_control_api_job_status(client, tmp_path):
    """Test Cache-Control on /api/job/{job_id}/status."""
    response = client.get("/api/job/aabbccddeeff/status")
    
    # Will be 404 (job not found), but should have Cache-Control
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_cache_control_api_verify_error(client, tmp_path):
    """Test Cache-Control on /api/verify error responses."""
    # 404 run not found
    response = client.post(
        "/api/verify",
        data={"run_id": "aabbccddeeff"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_cache_control_api_tamper_error(client, tmp_path):
    """Test Cache-Control on /api/tamper error responses."""
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    # 404 run not found
    response = client.post(
        "/api/tamper",
        data={
            "run_id": "aabbccddeeff",
            "status": "ALIVE",
            "cases_total": "10",
            "cases_divergent": "0",
            "random_seed": "42"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_cache_control_api_tamper_validation_error(client, tmp_path):
    """Test Cache-Control on /api/tamper validation error (422)."""
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    # Create a run
    run_id = "112233445566"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    
    import json
    cert_data = {"run_id": run_id}
    (run_dir / "certificate.json").write_text(json.dumps(cert_data))
    
    # Invalid status
    response = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "INVALID_STATUS",
            "cases_total": "10",
            "cases_divergent": "0",
            "random_seed": "42"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_cache_control_static_files(client):
    """Test Cache-Control on static files."""
    # Create a test static file
    static_dir = Path(__file__).parent.parent / "coroner" / "ui" / "static"
    test_file = static_dir / "test.txt"
    
    if not static_dir.exists():
        pytest.skip("Static directory does not exist")
    
    try:
        test_file.write_text("test content")
        
        response = client.get("/static/test.txt")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=86400"
    finally:
        if test_file.exists():
            test_file.unlink()


def test_verify_and_tamper_separate_limits(client, tmp_path):
    """Test that /api/verify and /api/tamper have separate rate limit keys."""
    # Use short window for test
    os.environ["CORONER_VERIFY_RATE_WINDOW"] = "2"
    os.environ["CORONER_TAMPER_RATE_WINDOW"] = "2"
    
    # Create exchange dir and run
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    run_id = "aabbccddeeff"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    
    import json
    cert_data = {
        "run_id": run_id,
        "status": "ALIVE",
        "cases_total": 10,
        "cases_divergent": 0,
        "random_seed": 42,
        "certificate_sha256": "dummy"
    }
    (run_dir / "certificate.json").write_text(json.dumps(cert_data))
    
    # First verify request
    response1 = client.post(
        "/api/verify",
        data={"run_id": run_id},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response1.status_code in [200, 500]  # Not rate-limited
    
    # First tamper request (should succeed because separate limit)
    response2 = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ZOMBIE",
            "cases_total": "10",
            "cases_divergent": "5",
            "random_seed": "42"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response2.status_code in [200, 500]  # Not rate-limited (separate key)
    
    # Second verify request (should be rate-limited)
    response3 = client.post(
        "/api/verify",
        data={"run_id": run_id},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response3.status_code == 429
    
    # Second tamper request (should be rate-limited)
    response4 = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ZOMBIE",
            "cases_total": "10",
            "cases_divergent": "5",
            "random_seed": "42"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response4.status_code == 429
    
    os.environ.pop("CORONER_VERIFY_RATE_WINDOW", None)
    os.environ.pop("CORONER_TAMPER_RATE_WINDOW", None)
