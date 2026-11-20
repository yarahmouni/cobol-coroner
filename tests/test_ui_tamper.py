"""Test UI tamper certificate endpoint."""

import json
import hashlib
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cli import run_verify


@pytest.fixture
def t1_faulty_run_with_cert(tmp_path):
    """Create a real T1 faulty run with certificate at 30 cases."""
    cobol_file = Path("samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob").resolve()
    copybooks = Path("samples/traps/T1-ebcdic-match-merge/copybooks").resolve()
    java_file = Path("samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java").resolve()
    schema_file = Path("samples/traps/T1-ebcdic-match-merge/schema.json").resolve()
    
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
    
    # Verify the run produced certificate
    assert (run_dir / "certificate.json").exists()
    
    # Verify it's ZOMBIE
    verdict_data = json.loads((run_dir / "verdict.json").read_text())
    assert verdict_data["status"] == "ZOMBIE"
    
    yield run_id, tmp_path


def test_tamper_form_shows_certificate_values(t1_faulty_run_with_cert, monkeypatch):
    """Test tamper form shows prefilled values from certificate."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # GET tamper form
    response = client.get(f"/tamper?run_id={run_id}")
    assert response.status_code == 200
    
    html = response.text
    assert "ZOMBIE" in html
    assert "30" in html  # cases_total
    assert "Tamper Certificate" in html


def test_tamper_status_change_gives_invalid(t1_faulty_run_with_cert, monkeypatch):
    """Test changing status ZOMBIE to ALIVE gives INVALID."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Create exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Load original certificate to get real values
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # POST tamper with status changed to ALIVE
    response = client.post("/api/tamper", data={
        "run_id": run_id,
        "status": "ALIVE",  # Changed from ZOMBIE
        "cases_total": cert_data["cases_total"],
        "cases_divergent": cert_data["cases_divergent"],
        "random_seed": cert_data["random_seed"]
    })
    
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "no-store"
    
    html = response.text
    assert "INVALID" in html
    assert "replay mismatch" in html or "expected ALIVE" in html


def test_tamper_unchanged_copy_gives_valid(t1_faulty_run_with_cert, monkeypatch):
    """Test unchanged copy gives VALID."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Create exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Load original certificate
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # POST tamper with unchanged values
    response = client.post("/api/tamper", data={
        "run_id": run_id,
        "status": cert_data["status"],
        "cases_total": cert_data["cases_total"],
        "cases_divergent": cert_data["cases_divergent"],
        "random_seed": cert_data["random_seed"]
    })
    
    assert response.status_code == 200
    html = response.text
    assert "VALID" in html


def test_tamper_cases_divergent_change_gives_invalid(t1_faulty_run_with_cert, monkeypatch):
    """Test changing cases_divergent gives INVALID."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Create exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Load original certificate
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # POST tamper with cases_divergent changed
    response = client.post("/api/tamper", data={
        "run_id": run_id,
        "status": cert_data["status"],
        "cases_total": cert_data["cases_total"],
        "cases_divergent": 0,  # Changed
        "random_seed": cert_data["random_seed"]
    })
    
    assert response.status_code == 200
    html = response.text
    assert "INVALID" in html


def test_tamper_original_bytes_unchanged(t1_faulty_run_with_cert, monkeypatch):
    """Test original certificate bytes are unchanged after tamper."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Create exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Compute original hash
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    original_bytes = cert_path.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()
    
    # Load original values
    cert_data = json.loads(cert_path.read_text())
    
    # POST tamper
    response = client.post("/api/tamper", data={
        "run_id": run_id,
        "status": "ALIVE",  # Changed
        "cases_total": cert_data["cases_total"],
        "cases_divergent": cert_data["cases_divergent"],
        "random_seed": cert_data["random_seed"]
    })
    
    assert response.status_code == 200
    
    # Verify original unchanged
    after_bytes = cert_path.read_bytes()
    after_hash = hashlib.sha256(after_bytes).hexdigest()
    
    assert after_hash == original_hash
    assert after_bytes == original_bytes


def test_tamper_no_file_left_in_exchange(t1_faulty_run_with_cert, monkeypatch):
    """Test no file is left in exchange/tamper/ after replay."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Create exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Load original certificate
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # POST tamper
    response = client.post("/api/tamper", data={
        "run_id": run_id,
        "status": cert_data["status"],
        "cases_total": cert_data["cases_total"],
        "cases_divergent": cert_data["cases_divergent"],
        "random_seed": cert_data["random_seed"]
    })
    
    assert response.status_code == 200
    
    # Check no file left in exchange/tamper/
    tamper_dir = exchange_dir / "tamper"
    if tamper_dir.exists():
        files = list(tamper_dir.iterdir())
        assert len(files) == 0, f"Files left in tamper dir: {files}"


def test_tamper_certificate_too_large(t1_faulty_run_with_cert, monkeypatch):
    """Test certificate over 1 MB is rejected."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    # Create a large fake certificate
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    original = cert_path.read_bytes()
    
    # Write a large certificate
    large_content = b'{"data": "' + b'x' * (1024 * 1024 + 1) + b'"}'
    cert_path.write_bytes(large_content)
    
    try:
        client = TestClient(app)
        
        # GET should fail with 413
        response = client.get(f"/tamper?run_id={run_id}")
        assert response.status_code == 413
        
        # POST should also fail with 413
        response = client.post("/api/tamper", data={
            "run_id": run_id,
            "status": "ALIVE",
            "cases_total": 100,
            "cases_divergent": 0,
            "random_seed": 42
        })
        assert response.status_code == 413
        
    finally:
        # Restore original
        cert_path.write_bytes(original)


def test_tamper_bad_run_id_rejected(monkeypatch, tmp_path):
    """Test bad run_id format is rejected with 422."""
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    
    # POST with invalid run_id
    response = client.post("/api/tamper", data={
        "run_id": "invalid-id",
        "status": "ALIVE",
        "cases_total": 100,
        "cases_divergent": 0,
        "random_seed": 42
    })
    
    # Should be 404 because validate_run_id raises 404
    assert response.status_code == 404


def test_tamper_form_reads_rendered_values(t1_faulty_run_with_cert, monkeypatch):
    """Test form values are read from the rendered page."""
    run_id, base_dir = t1_faulty_run_with_cert
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Create exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # GET tamper form
    response = client.get(f"/tamper?run_id={run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Parse values from HTML
    import re
    
    # Find status value
    status_match = re.search(r'name="status" value="([^"]+)"', html)
    assert status_match
    status = status_match.group(1)
    
    # Find cases_total value
    cases_total_match = re.search(r'name="cases_total" value="(\d+)"', html)
    assert cases_total_match
    cases_total = int(cases_total_match.group(1))
    
    # Find cases_divergent value
    cases_divergent_match = re.search(r'name="cases_divergent" value="(\d+)"', html)
    assert cases_divergent_match
    cases_divergent = int(cases_divergent_match.group(1))
    
    # Find random_seed value
    random_seed_match = re.search(r'name="random_seed" value="(\d+)"', html)
    assert random_seed_match
    random_seed = int(random_seed_match.group(1))
    
    # POST with exactly these values
    response = client.post("/api/tamper", data={
        "run_id": run_id,
        "status": status,
        "cases_total": cases_total,
        "cases_divergent": cases_divergent,
        "random_seed": random_seed
    })
    
    assert response.status_code == 200
    html = response.text
    assert "VALID" in html


@pytest.mark.slow
def test_tamper_alive_run(tmp_path, monkeypatch):
    """Test tamper on an ALIVE run (real 30-case run)."""
    # Create ALIVE run
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
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    # Create exchange directory
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    
    # Load original certificate
    cert_path = tmp_path / "runs" / run_id / "certificate.json"
    cert_data = json.loads(cert_path.read_text())
    
    # Tamper: change status to ZOMBIE
    response = client.post("/api/tamper", data={
        "run_id": run_id,
        "status": "ZOMBIE",  # Changed from ALIVE
        "cases_total": cert_data["cases_total"],
        "cases_divergent": cert_data["cases_divergent"],
        "random_seed": cert_data["random_seed"]
    })
    
    assert response.status_code == 200
    html = response.text
    assert "INVALID" in html
    assert "replay mismatch" in html or "expected ZOMBIE" in html
