"""Test UI run page with real engine runs."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cli import run_verify


@pytest.fixture
def alive_run(tmp_path):
    """Create a real ALIVE run using the engine at 30 cases."""
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
        
        # Verify the run produced expected files
        assert (run_dir / "verdict.json").exists()
        assert (run_dir / "inputs.json").exists()
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


def test_alive_run_page(alive_run, monkeypatch):
    """Test ALIVE run page renders with all required fields from real files."""
    run_id, base_dir = alive_run
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Read the actual run files to get expected values
    run_dir = base_dir / "runs" / run_id
    verdict_data = json.loads((run_dir / "verdict.json").read_text())
    coverage_data = json.loads((run_dir / "coverage_report.json").read_text())
    
    # Expected values from real files
    status = verdict_data["status"]
    sub_label = verdict_data["sub_label"]
    cases_total = verdict_data["cases_total"]
    cases_divergent = verdict_data["cases_divergent"]
    
    paragraph_covered = coverage_data["paragraphs_covered"]
    paragraph_total = coverage_data["paragraphs_total"]
    branch_covered = coverage_data["branches_covered"]
    branch_total = coverage_data["branches_total"]
    
    # Request the run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check verdict status and sub_label appear
    assert status in html
    assert sub_label in html
    
    # Check cases count appears with correct value
    assert str(cases_total) in html
    
    # Check divergences (exact value)
    assert str(cases_divergent) in html
    
    # Check paragraph coverage (exact formatted value)
    paragraph_coverage = f"{paragraph_covered}/{paragraph_total}"
    assert paragraph_coverage in html
    
    # Check branch coverage (exact formatted value)
    branch_coverage = f"{branch_covered}/{branch_total}"
    assert branch_coverage in html
    
    # Check GnuCOBOL validation notice
    assert "Validated under GnuCOBOL 3.x" in html
    
    # Check certificate panel
    assert "Certificate" in html
    assert "Verify" in html
    
    # Read certificate data
    cert_data = json.loads((run_dir / "certificate.json").read_text())
    cert_status = cert_data.get("status")
    if cert_status:
        assert cert_status in html
    
    # Check no home directory in response
    home_dir = str(Path.home())
    assert home_dir not in html
    
    # Check no tmp base path in response
    assert str(base_dir) not in html


def test_missing_coverage_shows_not_recorded(alive_run, monkeypatch):
    """Test that missing coverage_report.json shows 'not recorded'."""
    run_id, base_dir = alive_run
    
    # Delete coverage_report.json
    run_dir = base_dir / "runs" / run_id
    coverage_file = run_dir / "coverage_report.json"
    coverage_file.unlink()
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Request the run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check "not recorded" appears for coverage
    assert "not recorded" in html


def test_index_lists_run(alive_run, monkeypatch):
    """Test that the index page lists the ALIVE run."""
    run_id, base_dir = alive_run
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Request the index page
    response = client.get("/")
    assert response.status_code == 200
    
    html = response.text
    
    # Check the run is listed
    assert f"runs/{run_id}" in html
    assert "ALIVE" in html
    
    # Check tagline
    assert "independent regression auditor" in html or "The independent" in html
    
    # Check Detection Matrix link
    assert "/matrix" in html or "Detection Matrix" in html
    
    # Check no home directory in response
    home_dir = str(Path.home())
    assert home_dir not in html
    
    # Check no tmp base path in response
    assert str(base_dir) not in html



@pytest.fixture
def t1_faulty_run(t1_faulty_200):
    """The shared real ZOMBIE run of the T1 faulty port at 200 cases (tests/conftest.py), read only: (run id, base)."""
    assert (t1_faulty_200.run_dir / "failure_report.json").exists()
    verdict = json.loads((t1_faulty_200.run_dir / "verdict.json").read_text())
    assert verdict["status"] == "ZOMBIE"
    return t1_faulty_200.run_id, t1_faulty_200.base


def test_t1_exhibit_4_and_divergence_count(t1_faulty_run, monkeypatch):
    """Test that T1 ZOMBIE run page shows exhibit 4 with correct sentence and divergence count."""
    run_id, base_dir = t1_faulty_run
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Read the actual run files to compute expected values
    run_dir = base_dir / "runs" / run_id
    verdict_data = json.loads((run_dir / "verdict.json").read_text())
    failure_data = json.loads((run_dir / "failure_report.json").read_text())
    trap_data = json.loads(Path("samples/traps/T1-ebcdic-match-merge/trap.json").read_text())
    
    # Compute expected example sentence from failure_report.json
    divergent_fields = failure_data.get("divergent_fields", [])
    suspense_code = trap_data["suspense_code"]
    suspense_label = trap_data["suspense_label"]
    
    expected_sentence = None
    # Find the missing_in_cobol entry (Java posted to suspense)
    java_suspense_entry = None
    for div in divergent_fields:
        if div.get("kind") == "missing_in_cobol":
            output_key = div.get("output_key", {})
            branch = output_key.get("BRANCH", "").strip()
            if branch == suspense_code:
                java_suspense_entry = div
                break
    
    if java_suspense_entry:
        java_values = java_suspense_entry.get("java_values", {})
        subtotal = java_values.get("SUBTOTAL", "")
        
        # Find the missing_in_java entry with the same SUBTOTAL
        for div in divergent_fields:
            if div.get("kind") == "missing_in_java":
                cobol_values = div.get("cobol_values", {})
                cobol_subtotal = cobol_values.get("SUBTOTAL", "")
                
                if cobol_subtotal == subtotal:
                    output_key = div.get("output_key", {})
                    cobol_branch = output_key.get("BRANCH", "").strip()
                    
                    # Parse with Decimal, quantize to column scale (2 decimals), absolute value
                    from decimal import Decimal
                    amount = Decimal(subtotal.strip())
                    amount_quantized = amount.quantize(Decimal("0.01"))
                    amount_str = f"{abs(amount_quantized):.2f}"
                    # New format: "<amount> was posted to <suspense_label> instead of branch <code>."
                    expected_sentence = f"{amount_str} was posted to {suspense_label} instead of branch {cobol_branch}."
                    break
    
    assert expected_sentence is not None, "Could not compute expected sentence from failure_report.json"
    
    # Get expected divergence count from verdict.json
    cases_divergent = verdict_data["cases_divergent"]
    
    # Request the run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check example sentence is in #story (not labeled as "Exhibit 4")
    story_start = html.find('id="story"')
    story_end = html.find('</section>', story_start) if story_start >= 0 else -1
    story_section = html[story_start:story_end] if story_start >= 0 and story_end >= 0 else ""
    
    assert expected_sentence in story_section, f"Expected sentence not found in #story: {expected_sentence}"
    
    # Check divergence count appears in #technical
    technical_start = html.find('id="technical"')
    technical_section = html[technical_start:] if technical_start >= 0 else html
    
    assert str(cases_divergent) in technical_section, f"Divergent cases count {cases_divergent} not found in technical section"
    
    # Check "Divergences []" does not appear
    assert "Divergences []" not in html
    
    # Check no home directory in response
    home_dir = str(Path.home())
    assert home_dir not in html
    
    # Check no tmp base path in response
    assert str(base_dir) not in html
