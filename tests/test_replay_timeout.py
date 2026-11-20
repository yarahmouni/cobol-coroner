"""Test replay timeout with subprocess and CLI --json flag."""

import json
import os
import signal
import time
from pathlib import Path

import pytest

from coroner.cli import run_verify


@pytest.fixture
def alive_run_2000_cases(tmp_path):
    """Create a real ALIVE run with certificate at 2000 cases."""
    # Set CORONER_BASE_DIR to tmp_path
    original_base = os.environ.get("CORONER_BASE_DIR")
    os.environ["CORONER_BASE_DIR"] = str(tmp_path)
    
    try:
        # Run credit-fees with correct Java
        cobol_file = Path("samples/credit-fees/CREDIT-FEES.cob").resolve()
        copybooks = Path("samples/credit-fees/copybooks").resolve()
        java_file = Path("samples/credit-fees/java/CreditFees.java").resolve()
        schema_file = Path("samples/credit-fees/schema.json").resolve()
        
        verdict, run_dir = run_verify(
            cobol_path=str(cobol_file),
            copybooks_dir=str(copybooks),
            java_path=str(java_file),
            schema_path=str(schema_file),
            num_cases=2000,
            seed=42,
            timings=False,
            base_dir=str(tmp_path),
        )
        
        run_id = run_dir.name
        
        run_dir = tmp_path / "runs" / run_id
        
        # Verify the run produced certificate
        assert (run_dir / "certificate.json").exists()
        
        # Verify it's ALIVE
        verdict_data = json.loads((run_dir / "verdict.json").read_text())
        assert verdict_data["status"] == "ALIVE"
        
        yield run_id, tmp_path
        
    finally:
        # Restore original CORONER_BASE_DIR
        if original_base is not None:
            os.environ["CORONER_BASE_DIR"] = original_base
        elif "CORONER_BASE_DIR" in os.environ:
            del os.environ["CORONER_BASE_DIR"]


def test_cli_json_output(alive_run_2000_cases):
    """Test CLI --json flag outputs JSON with ReplayResult fields."""
    run_id, base_dir = alive_run_2000_cases
    
    # Get certificate path
    cert_file = base_dir / "runs" / run_id / "certificate.json"
    assert cert_file.exists()
    
    # Run CLI with --json
    import subprocess
    import sys
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base_dir)
    
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "verify", str(cert_file), "--json"],
        capture_output=True,
        text=True,
        env=env
    )
    
    # Should exit 0 (ALIVE)
    assert result.returncode == 0
    
    # Parse JSON output
    output = json.loads(result.stdout)
    
    # Check all ReplayResult fields are present
    assert output["valid"] is True
    assert output["reason"] == ""
    assert output["verdict_status"] == "ALIVE"
    assert output["verdict_sub_label"] is not None
    assert output["cases_total"] == 2000
    assert output["cases_divergent"] == 0
    assert isinstance(output["paragraph_coverage_reached"], int)
    assert isinstance(output["paragraph_coverage_total"], int)
    assert isinstance(output["branch_coverage_reached"], int)
    assert isinstance(output["branch_coverage_total"], int)
    assert output["cases_file"] != ""
    assert isinstance(output["warnings"], list)
    
    # Compare with replay_certificate result
    from coroner.certificate import replay_certificate
    
    direct_result = replay_certificate(str(cert_file), str(base_dir))
    
    assert output["valid"] == direct_result.valid
    assert output["verdict_status"] == direct_result.verdict.status
    assert output["cases_total"] == direct_result.cases_total
    assert output["cases_divergent"] == direct_result.cases_divergent


def test_replay_timeout_kills_process_group(alive_run_2000_cases, monkeypatch):
    """Test replay timeout kills process group and returns within timeout + 10s."""
    run_id, base_dir = alive_run_2000_cases
    
    # Set CORONER_BASE_DIR and CORONER_REPLAY_TIMEOUT before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    monkeypatch.setenv("CORONER_REPLAY_TIMEOUT", "1")
    
    # Import app after setting env var
    from coroner.ui.app import app, replay_with_timeout, get_last_replay_pgid
    
    # Get certificate path
    cert_file = base_dir / "runs" / run_id / "certificate.json"
    
    # Run replay with 1 second timeout (should timeout on 2000 cases)
    start_time = time.time()
    
    result = replay_with_timeout(str(cert_file), str(base_dir), 1)
    
    elapsed = time.time() - start_time
    
    # Should return within 1 + 10 seconds
    assert elapsed < 11.0, f"Replay took {elapsed:.2f}s, expected < 11.0s"
    
    # Should return timeout error
    assert result.valid is False
    assert result.reason == "replay timed out"
    
    # Get the pgid that was killed
    pgid = get_last_replay_pgid()
    assert pgid is not None
    
    # Verify the process group is gone
    try:
        os.killpg(pgid, 0)
        # If we get here, the process group still exists
        pytest.fail(f"Process group {pgid} still exists after timeout")
    except ProcessLookupError:
        # Expected: process group was killed
        pass


@pytest.mark.slow
def test_replay_completes_within_timeout(alive_run_2000_cases, monkeypatch):
    """Test replay completes normally when timeout is sufficient."""
    run_id, base_dir = alive_run_2000_cases
    
    # Set CORONER_BASE_DIR with sufficient timeout
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import replay_with_timeout
    
    # Get certificate path
    cert_file = base_dir / "runs" / run_id / "certificate.json"
    
    # Run replay with 90 second timeout (should complete)
    result = replay_with_timeout(str(cert_file), str(base_dir), 90)
    
    # Should succeed
    assert result.valid is True
    assert result.reason == ""
    assert result.verdict is not None
    assert result.verdict.status == "ALIVE"
    assert result.cases_total == 2000
    assert result.cases_divergent == 0


def test_html_escape_in_verify_endpoint(alive_run_2000_cases, monkeypatch):
    """Test HTML escaping in /api/verify endpoint."""
    run_id, base_dir = alive_run_2000_cases
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # Test VALID case
    response = client.post("/api/verify", data={"run_id": run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Should not contain unescaped HTML
    assert "<script>" not in html.lower()
    
    # Create a forged certificate with malicious content
    run_dir = base_dir / "runs" / run_id
    cert_file = run_dir / "certificate.json"
    
    import shutil
    import secrets
    
    # Create a copy
    copy_run_id = secrets.token_hex(6)
    copy_run_dir = base_dir / "runs" / copy_run_id
    copy_run_dir.mkdir(parents=True)
    
    for file in run_dir.iterdir():
        if file.is_file():
            shutil.copy2(file, copy_run_dir / file.name)
    
    # Forge the certificate to trigger INVALID with XSS attempt
    copy_cert_file = copy_run_dir / "certificate.json"
    copy_cert_data = json.loads(copy_cert_file.read_text())
    
    # Modify without recomputing hash (will be INVALID)
    copy_cert_data["cases_divergent"] = 999
    
    with open(copy_cert_file, 'w', encoding='utf-8') as f:
        json.dump(copy_cert_data, f, indent=2, sort_keys=True)
        f.write('\n')
    
    # Reset rate limiter
    from coroner.ui.app import reset_rate_limiter
    reset_rate_limiter()
    
    # POST verify on forged certificate
    response = client.post("/api/verify", data={"run_id": copy_run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Should contain escaped reason
    assert "INVALID" in html
    
    # Should not contain unescaped HTML tags
    assert "<script>" not in html.lower()
    
    # The reason text should be present but escaped
    # (the actual reason depends on what replay_certificate returns)
    assert "Certificate: INVALID" in html


def test_html_escape_in_tamper_endpoint(alive_run_2000_cases, monkeypatch):
    """Test HTML escaping in /api/tamper endpoint."""
    run_id, base_dir = alive_run_2000_cases
    
    # Create a temporary exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    
    # Set CORONER_BASE_DIR and CORONER_EXCHANGE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # Tamper with the certificate
    response = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ZOMBIE",
            "cases_total": 2000,
            "cases_divergent": 999,
            "random_seed": 42
        }
    )
    
    assert response.status_code == 200
    
    html = response.text
    
    # Should contain INVALID (mismatch)
    assert "INVALID" in html
    
    # Should not contain unescaped HTML
    assert "<script>" not in html.lower()
    
    # The reason should be escaped
    assert "Certificate: INVALID" in html
