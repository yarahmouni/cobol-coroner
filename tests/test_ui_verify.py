"""Test UI certificate verification endpoint."""

import json
import hashlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cli import run_verify


@pytest.fixture
def alive_run_with_cert(tmp_path, monkeypatch):
    """Create a real ALIVE run with certificate at 30 cases."""
    # Set CORONER_BASE_DIR to tmp_path
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
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
        num_cases=30,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    run_id = run_dir.name
    
    run_dir = tmp_path / "runs" / run_id
    
    # Verify the run produced certificate
    assert (run_dir / "certificate.json").exists()
    
    # Verify it's ALIVE
    verdict = json.loads((run_dir / "verdict.json").read_text())
    assert verdict["status"] == "ALIVE"
    
    yield run_id, tmp_path


def test_verify_real_certificate(alive_run_with_cert, monkeypatch):
    """Test verify endpoint returns VALID for a real certificate."""
    run_id, base_dir = alive_run_with_cert
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # POST verify with form data (what htmx sends)
    response = client.post("/api/verify", data={"run_id": run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Check it says VALID
    assert "VALID" in html
    assert "Certificate: VALID" in html
    
    # Check it shows the verdict
    assert "ALIVE" in html
    
    # Check no INVALID
    assert "INVALID" not in html


def test_verify_forged_certificate(alive_run_with_cert, monkeypatch):
    """Test verify endpoint returns INVALID for a forged certificate."""
    run_id, base_dir = alive_run_with_cert
    
    # Forge the certificate by editing cases_divergent and recomputing hash
    run_dir = base_dir / "runs" / run_id
    cert_file = run_dir / "certificate.json"
    
    # Read the certificate
    cert_data = json.loads(cert_file.read_text())
    
    # Remove the hash
    cert_data.pop("certificate_sha256")
    
    # Modify cases_divergent (it should be 0 for ALIVE)
    original_divergent = cert_data["cases_divergent"]
    cert_data["cases_divergent"] = 999
    
    # Recompute hash the way the certificate module does
    canonical_json = json.dumps(cert_data, sort_keys=True, separators=(',', ':'))
    new_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    cert_data["certificate_sha256"] = new_hash
    
    # Write the forged certificate
    with open(cert_file, 'w', encoding='utf-8') as f:
        json.dump(cert_data, f, indent=2, sort_keys=True)
        f.write('\n')
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Also run the CLI on the forged file to get the expected reason
    from coroner.certificate import replay_certificate
    cli_result = replay_certificate(str(cert_file))
    
    assert not cli_result.valid
    expected_reason = cli_result.reason
    
    # POST verify with form data
    response = client.post("/api/verify", data={"run_id": run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Check it says INVALID
    assert "INVALID" in html
    assert "Certificate: INVALID" in html
    
    # Check it shows the reason the CLI prints
    assert expected_reason in html
    
    # Check no standalone VALID (not inside INVALID)
    # "Certificate: VALID" should not appear
    assert "Certificate: VALID" not in html



def test_verify_button_sends_form_data(alive_run_with_cert, monkeypatch):
    """Test that the Verify button sends form data (not JSON), and verify works end-to-end."""
    run_id, base_dir = alive_run_with_cert
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app, reset_rate_limiter
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # 1. Render the run page
    page_response = client.get(f"/run/{run_id}")
    assert page_response.status_code == 200
    html = page_response.text
    
    # 2. Parse the button's hx-post and hx-vals
    # Button is like: <button hx-post="/api/verify" hx-vals='{"run_id": "..."}' ...>
    import re
    
    # Find hx-post
    hx_post_match = re.search(r'hx-post="([^"]+)"', html)
    assert hx_post_match is not None, "hx-post not found in page"
    endpoint = hx_post_match.group(1)
    assert endpoint == "/api/verify"
    
    # Find hx-vals
    hx_vals_match = re.search(r"hx-vals='({[^']+})'", html)
    assert hx_vals_match is not None, "hx-vals not found in page"
    vals_json = hx_vals_match.group(1)
    
    # Parse JSON
    vals = json.loads(vals_json)
    assert "run_id" in vals
    assert vals["run_id"] == run_id
    
    # 3. POST those values as form data (what htmx sends by default)
    response = client.post(endpoint, data=vals)
    assert response.status_code == 200
    
    result_html = response.text
    
    # Check it says VALID
    assert "Certificate: VALID" in result_html
    assert "ALIVE" in result_html
    
    # 4. Test that a forged certificate gives INVALID
    # Create a copy with a changed field
    run_dir = base_dir / "runs" / run_id
    cert_file = run_dir / "certificate.json"
    cert_data = json.loads(cert_file.read_text())
    
    # Create a new run_id (12 hex chars) for the copy
    import secrets
    copy_run_id = secrets.token_hex(6)  # 12 hex chars
    copy_run_dir = base_dir / "runs" / copy_run_id
    copy_run_dir.mkdir(parents=True)
    
    # Copy all files
    for file in run_dir.iterdir():
        if file.is_file():
            import shutil
            shutil.copy2(file, copy_run_dir / file.name)
    
    # Forge the certificate by editing cases_divergent without recomputing hash
    copy_cert_file = copy_run_dir / "certificate.json"
    copy_cert_data = json.loads(copy_cert_file.read_text())
    copy_cert_data["cases_divergent"] = 999
    
    with open(copy_cert_file, 'w', encoding='utf-8') as f:
        json.dump(copy_cert_data, f, indent=2, sort_keys=True)
        f.write('\n')
    
    # Reset rate limiter before second Verify post (the endpoint has 1 per 10s per IP)
    reset_rate_limiter()
    
    # POST verify on the forged copy
    forge_response = client.post("/api/verify", data={"run_id": copy_run_id})
    assert forge_response.status_code == 200
    
    forge_html = forge_response.text
    
    # Should say INVALID
    assert "Certificate: INVALID" in forge_html
    assert "INVALID" in forge_html
    assert "Certificate: VALID" not in forge_html


def test_verify_body_size_limit(alive_run_with_cert, monkeypatch):
    """Test that oversized body to /api/verify is rejected with 413."""
    run_id, base_dir = alive_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Test 1: Body with Content-Length over 16 KB
    # Create form data with massive padding
    padding = "x" * (17 * 1024)
    response = client.post(
        "/api/verify",
        data={"run_id": run_id, "padding": padding}
    )
    
    assert response.status_code == 413
    
    # Test 2: Body under limit is accepted
    response = client.post(
        "/api/verify",
        data={"run_id": run_id}
    )
    
    assert response.status_code == 200



@pytest.mark.slow
def test_verify_does_not_block_event_loop(tmp_path, monkeypatch):
    """
    Test that Verify replay runs off the event loop and does not block the site.
    
    Starts a real uvicorn server, begins a Verify replay (which takes 15-20s at 2000 cases),
    and verifies that GET / answers within 2 seconds while the replay is running.
    """
    import subprocess
    import socket
    import time
    import httpx
    
    # Create a real ZOMBIE run at 2000 cases (replay will be slow)
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    cobol_file = Path("samples/credit-fees/CREDIT-FEES.cob").resolve()
    copybooks = Path("samples/credit-fees/copybooks").resolve()
    
    # Use HALF_EVEN variant for ZOMBIE
    from coroner.catalog.legacy_variant import generate_half_even_variant
    
    java_source_path = Path("samples/credit-fees/java/CreditFees.java").resolve()
    variant_dir = tmp_path / "variant"
    variant_dir.mkdir()
    variant_path = variant_dir / "CreditFees.java"
    generate_half_even_variant(str(java_source_path), str(variant_path))
    
    schema_file = Path("samples/credit-fees/schema.json").resolve()
    
    verdict, run_dir = run_verify(
        cobol_path=str(cobol_file),
        copybooks_dir=str(copybooks),
        java_path=str(variant_path),
        schema_path=str(schema_file),
        num_cases=2000,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    run_id = run_dir.name
    
    # Verify the run produced certificate
    cert_file = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_file.exists()
    
    # Verify it's ZOMBIE
    verdict_file = tmp_path / "runs" / run_id / "verdict.json"
    verdict_data = json.loads(verdict_file.read_text())
    assert verdict_data["status"] == "ZOMBIE"
    
    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    
    # Start uvicorn in a subprocess
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    env["CORONER_ENGINE_MODE"] = "disabled"  # no worker needed
    
    # Use python -m uvicorn with the app factory
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "coroner.ui.app:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "error"
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    try:
        # Wait for server to start (up to 5 seconds)
        base_url = f"http://127.0.0.1:{port}"
        started = False
        for _ in range(50):  # 5 seconds
            try:
                with httpx.Client(timeout=1.0) as client:
                    response = client.get(base_url)
                    if response.status_code == 200:
                        started = True
                        break
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.1)
        
        assert started, "Server did not start within 5 seconds"
        
        # Now POST /api/verify in a background thread (this will take 15-20s)
        import threading
        
        verify_result = {"done": False, "status_code": None}
        
        def post_verify():
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{base_url}/api/verify",
                    data={"run_id": run_id}
                )
                verify_result["status_code"] = response.status_code
                verify_result["done"] = True
        
        verify_thread = threading.Thread(target=post_verify, daemon=True)
        verify_thread.start()
        
        # Wait a moment for the verify request to reach the server
        time.sleep(0.5)
        
        # Now GET / and measure response time
        start_time = time.time()
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(base_url)
        
        elapsed = time.time() - start_time
        
        # Assert GET / responded quickly
        assert response.status_code == 200
        assert elapsed < 2.0, f"GET / took {elapsed:.2f}s, expected < 2.0s (replay blocked the event loop)"
        
        # Verify the page is real
        assert 'id="run-audit-form"' in response.text
        
        # Wait for verify to complete (up to 60 seconds)
        verify_thread.join(timeout=60.0)
        
        # If the thread is still alive, the test setup is wrong
        if verify_thread.is_alive():
            pytest.fail("Verify request did not complete within 60 seconds")
        
        # Check that verify eventually succeeded
        assert verify_result["done"], "Verify thread did not complete"
        assert verify_result["status_code"] == 200
        
    finally:
        # Stop the server
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()



def test_verify_subprocess_real_certificate(tmp_path, monkeypatch):
    """
    Test /api/verify through real subprocess replay on a real run in tmp_path.
    
    This exercises the actual subprocess path with certificate as positional argument.
    """
    # Create a real ALIVE run
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    cobol_file = Path("samples/credit-fees/CREDIT-FEES.cob").resolve()
    copybooks = Path("samples/credit-fees/copybooks").resolve()
    java_file = Path("samples/credit-fees/java/CreditFees.java").resolve()
    schema_file = Path("samples/credit-fees/schema.json").resolve()
    
    verdict, run_dir = run_verify(
        cobol_path=str(cobol_file),
        copybooks_dir=str(copybooks),
        java_path=str(java_file),
        schema_path=str(schema_file),
        num_cases=30,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    run_id = run_dir.name
    
    # Verify certificate exists
    cert_file = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_file.exists()
    
    # Verify it's ALIVE
    verdict_file = tmp_path / "runs" / run_id / "verdict.json"
    verdict_data = json.loads(verdict_file.read_text())
    assert verdict_data["status"] == "ALIVE"
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    
    # POST verify with form data - this goes through real subprocess
    response = client.post("/api/verify", data={"run_id": run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Check it says VALID
    assert "Certificate: VALID" in html
    assert "ALIVE" in html
    
    # Check cases are shown
    assert "30" in html


def test_verify_subprocess_forged_certificate(tmp_path, monkeypatch):
    """
    Test /api/verify through subprocess detects a forged certificate.
    
    This verifies the subprocess returns INVALID with the real reason.
    """
    # Create a real ALIVE run
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    cobol_file = Path("samples/credit-fees/CREDIT-FEES.cob").resolve()
    copybooks = Path("samples/credit-fees/copybooks").resolve()
    java_file = Path("samples/credit-fees/java/CreditFees.java").resolve()
    schema_file = Path("samples/credit-fees/schema.json").resolve()
    
    verdict, run_dir = run_verify(
        cobol_path=str(cobol_file),
        copybooks_dir=str(copybooks),
        java_path=str(java_file),
        schema_path=str(schema_file),
        num_cases=30,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    run_id = run_dir.name
    
    # Forge the certificate
    run_dir_path = tmp_path / "runs" / run_id
    cert_file = run_dir_path / "certificate.json"
    
    # Read and modify
    cert_data = json.loads(cert_file.read_text())
    cert_data.pop("certificate_sha256")
    cert_data["cases_divergent"] = 999
    
    # Recompute hash
    canonical_json = json.dumps(cert_data, sort_keys=True, separators=(',', ':'))
    new_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    cert_data["certificate_sha256"] = new_hash
    
    # Write forged certificate
    with open(cert_file, 'w', encoding='utf-8') as f:
        json.dump(cert_data, f, indent=2, sort_keys=True)
        f.write('\n')
    
    # Set CORONER_BASE_DIR
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    
    # POST verify - subprocess should detect forgery
    response = client.post("/api/verify", data={"run_id": run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Check it says INVALID with the replay mismatch reason
    assert "Certificate: INVALID" in html
    assert "replay mismatch" in html
    assert "cases_divergent" in html


def test_tamper_subprocess_real_certificate(tmp_path, monkeypatch):
    """
    Test /api/tamper through real subprocess on a real run.
    
    This exercises the actual subprocess replay after tamper.
    """
    # Create a real ZOMBIE run
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    # Set CORONER_EXCHANGE_DIR for tamper to write copies
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    cobol_file = Path("samples/credit-fees/CREDIT-FEES.cob").resolve()
    copybooks = Path("samples/credit-fees/copybooks").resolve()
    schema_file = Path("samples/credit-fees/schema.json").resolve()
    
    # Use HALF_EVEN for ZOMBIE
    from coroner.catalog.legacy_variant import generate_half_even_variant
    
    java_source_path = Path("samples/credit-fees/java/CreditFees.java").resolve()
    variant_dir = tmp_path / "variant"
    variant_dir.mkdir()
    variant_path = variant_dir / "CreditFees.java"
    generate_half_even_variant(str(java_source_path), str(variant_path))
    
    verdict, run_dir = run_verify(
        cobol_path=str(cobol_file),
        copybooks_dir=str(copybooks),
        java_path=str(variant_path),
        schema_path=str(schema_file),
        num_cases=30,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    run_id = run_dir.name
    
    # Verify certificate exists and it's ZOMBIE
    cert_file = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_file.exists()
    
    verdict_file = tmp_path / "runs" / run_id / "verdict.json"
    verdict_data = json.loads(verdict_file.read_text())
    assert verdict_data["status"] == "ZOMBIE"
    
    # Set CORONER_BASE_DIR
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    
    # Tamper: change status to ALIVE (should give INVALID)
    response = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ALIVE",
            "cases_total": verdict_data["cases_total"],
            "cases_divergent": 0,  # Changed from actual
            "random_seed": 42,
        }
    )
    assert response.status_code == 200
    
    # /api/tamper returns HTML, not JSON
    html = response.text
    
    # Should be INVALID because replay will detect the mismatch
    assert "Certificate: INVALID" in html
    assert "replay mismatch" in html
    assert "status" in html  # Mentions status field
    
    # Original certificate should still be VALID
    verify_response = client.post("/api/verify", data={"run_id": run_id})
    assert verify_response.status_code == 200
    assert "Certificate: VALID" in verify_response.text
    assert "ZOMBIE" in verify_response.text


