"""Tests for UI corrections: currency symbols, divergent counts, exhibit sources."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cli import run_verify


@pytest.fixture(scope="module")
def t1_faulty_run_2000(tmp_path_factory):
    """Create a real T1 faulty run at 2000 cases for testing."""
    tmp_path = tmp_path_factory.mktemp("t1_faulty_2000")
    
    cobol_file = Path("samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob").resolve()
    copybooks = Path("samples/traps/T1-ebcdic-match-merge/copybooks").resolve()
    java_file = Path("samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java").resolve()
    schema_file = Path("samples/traps/T1-ebcdic-match-merge/schema.json").resolve()
    
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
    
    return tmp_path, run_dir.name


def test_no_currency_symbols(t1_faulty_run_2000, monkeypatch):
    """Test correction 1: No currency symbols on the page."""
    tmp_path, run_id = t1_faulty_run_2000
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # No dollar sign anywhere
    assert "$" not in html, "Currency symbol $ found in page"
    
    # No EUR or other currency signs
    assert "EUR" not in html, "EUR currency code found in page"
    assert "€" not in html, "Euro symbol found in page"
    assert "£" not in html, "Pound symbol found in page"
    assert "¥" not in html, "Yen symbol found in page"


def test_divergent_cases_and_rows(t1_faulty_run_2000, monkeypatch):
    """Test correction 2: Both divergent cases and divergent rows are shown."""
    tmp_path, run_id = t1_faulty_run_2000
    run_dir = tmp_path / "runs" / run_id
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    # Compute expected values from comparison_results.json
    comparison_file = run_dir / "comparison_results.json"
    assert comparison_file.exists()
    
    comparison_data = json.loads(comparison_file.read_text())
    
    # Count divergent cases (cases with at least one divergence)
    expected_divergent_cases = 0
    expected_divergent_rows = 0
    for case in comparison_data.get("cases", []):
        if case.get("divergent", False):
            expected_divergent_cases += 1
        divergent_fields = case.get("divergent_fields", [])
        expected_divergent_rows += len(divergent_fields)
    
    # Verify both counts are non-zero for this run
    assert expected_divergent_cases > 0, "Expected some divergent cases"
    assert expected_divergent_rows > 0, "Expected some divergent rows"
    assert expected_divergent_rows > expected_divergent_cases, "Expected more rows than cases"
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Both labels must appear in #technical evidence section
    # Find the technical details section
    technical_start = html.find('id="technical"')
    assert technical_start >= 0, "Technical details section not found"
    technical_section = html[technical_start:]
    
    assert "Divergent cases:" in technical_section, "Label 'Divergent cases:' not found in technical section"
    assert "Divergent rows:" in technical_section, "Label 'Divergent rows:' not found in technical section"
    
    # Both counts must appear in technical section
    assert str(expected_divergent_cases) in technical_section, f"Divergent cases count {expected_divergent_cases} not found in technical section"
    assert str(expected_divergent_rows) in technical_section, f"Divergent rows count {expected_divergent_rows} not found in technical section"
    
    # Count headline figures (class="headline") in #story - should be exactly 3 for T1
    story_start = html.find('id="story"')
    story_end = html.find('</section>', story_start)
    story_section = html[story_start:story_end] if story_start >= 0 and story_end >= 0 else html
    headline_count = story_section.count('class="headline"')
    assert headline_count == 3, f"Found {headline_count} headlines in #story, expected exactly 3"


def test_exhibit_sources(t1_faulty_run_2000, monkeypatch):
    """Test correction 3: Exhibit sources name the correct files."""
    tmp_path, run_id = t1_faulty_run_2000
    run_dir = tmp_path / "runs" / run_id
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Extract all "Source:" lines
    source_pattern = r'<strong>Source:</strong>\s*([^<]+)'
    sources = []
    import re
    for match in re.finditer(source_pattern, html):
        source_text = match.group(1).strip()
        sources.append(source_text)
    
    # Verify each source mentions files that exist
    for source_text in sources:
        # Extract file names from source text
        # Examples:
        # - "verdict.json, comparison_results.json (run abc123)"
        # - "branch_reconciliation.json (run abc123)"
        # - "card.txt, coverage_report.json (run abc123)"
        # - "failure_report.json (run abc123)"
        # - "certificate.json (run abc123)"
        # - "samples/traps/T1-ebcdic-match-merge/trap.json"
        
        if "samples/traps/" in source_text:
            # Trap metadata source
            # Extract path like "samples/traps/T1-ebcdic-match-merge/trap.json"
            trap_path_match = re.search(r'samples/traps/[^/]+/trap\.json', source_text)
            assert trap_path_match, f"Trap source does not specify trap.json path: {source_text}"
            trap_path = trap_path_match.group(0)
            
            # Verify file exists in repository
            repo_root = Path(__file__).resolve().parent.parent
            trap_file = repo_root / trap_path
            assert trap_file.exists(), f"Trap source file does not exist: {trap_path}"
        else:
            # Run file source
            # Extract file names before "(run ...)"
            file_part = source_text.split("(run")[0].strip()
            
            # Split by comma to get individual files
            file_names = [f.strip() for f in file_part.split(",")]
            
            for file_name in file_names:
                # Clean any HTML tags
                file_name = re.sub(r'<[^>]+>', '', file_name).strip()
                
                if not file_name:
                    continue
                
                # Verify file exists in run directory
                run_file = run_dir / file_name
                assert run_file.exists(), f"Source file does not exist in run {run_id}: {file_name}"
                
                # Verify the file contains a value mentioned on the page
                # (at least check it's not empty and is valid JSON if .json)
                if file_name.endswith(".json"):
                    content = json.loads(run_file.read_text())
                    assert content, f"Source file {file_name} is empty"
                elif file_name.endswith(".txt"):
                    content = run_file.read_text()
                    assert content.strip(), f"Source file {file_name} is empty"
    
    # Verify specific sources for known exhibits
    # Exhibit 1 (exposure): verdict.json, comparison_results.json
    if "Unreconciled branch exposure" in html:
        assert any("verdict.json" in s and "comparison_results.json" in s for s in sources), \
            "Exhibit 1 source must reference verdict.json and comparison_results.json"
    
    # Exhibit 2 (chart): branch_reconciliation.json
    if "Branch Reconciliation" in html:
        assert any("branch_reconciliation.json" in s for s in sources), \
            "Exhibit 2 source must reference branch_reconciliation.json"
    
    # Exhibit 4 (example): failure_report.json
    if "Example from Minimal Case" in html:
        assert any("failure_report.json" in s and "(" in s for s in sources), \
            "Exhibit 4 source must reference failure_report.json with run id"
    
    # Exhibit 5 (causes): trap.json
    if "Why This Happened" in html:
        assert any("trap.json" in s for s in sources), \
            "Exhibit 5 source must reference trap.json"
    
    # Exhibit 8 (card): card.txt, coverage_report.json
    if "Given/When/Then" in html or "Technical Details" in html:
        # For ZOMBIE, card.txt should be mentioned
        if "ZOMBIE" in html and "card.txt" in ' '.join(sources):
            assert any("card.txt" in s and "coverage_report.json" in s for s in sources), \
                "Exhibit 8 (ZOMBIE) source must reference card.txt and coverage_report.json"
