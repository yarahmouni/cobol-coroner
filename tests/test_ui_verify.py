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
    
    # POST verify
    response = client.post("/api/verify", json={"run_id": run_id})
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
    
    # POST verify
    response = client.post("/api/verify", json={"run_id": run_id})
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
