"""Test UI certificate verification endpoint."""

import json
import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cli import run_verify


@pytest.fixture
def alive_run_with_cert(tmp_path):
    """Create a real ALIVE run with certificate at 30 cases."""
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
        
    finally:
        # Restore original CORONER_BASE_DIR
        if original_base is not None:
            os.environ["CORONER_BASE_DIR"] = original_base
        elif "CORONER_BASE_DIR" in os.environ:
            del os.environ["CORONER_BASE_DIR"]


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
