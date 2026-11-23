"""Test UI Detection Matrix page."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def matrix_catalog(story_runs):
    """The real trap catalog of the session (fixture story_runs of tests/conftest.py), read only.

    story_runs ran run_catalog and write_catalog_files once in a temporary base directory (9 cases,
    seed 42, faulty and correct port of T1 to T6). The page only reads the catalog file.
    """
    tmp_path = story_runs.base
    
    # Verify catalog was written
    catalog_file = tmp_path / "runs" / "trap_catalog.json"
    assert catalog_file.exists()
    
    catalog_data = json.loads(catalog_file.read_text())
    
    # Convert traps list to dict keyed by id for easier lookup
    traps_by_id = {trap["id"]: trap for trap in catalog_data["traps"]}
    
    return traps_by_id, tmp_path


def test_matrix_page_with_catalog(matrix_catalog, monkeypatch):
    """Test Detection Matrix page with a real catalog."""
    catalog_data, base_dir = matrix_catalog
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = base_dir
    
    client = TestClient(app)
    
    # Request the matrix page
    response = client.get("/matrix")
    assert response.status_code == 200
    
    html = response.text
    
    # Check the title
    assert "Detection Matrix" in html
    
    # Check the header
    assert "Six banking migration traps" in html
    
    # Check table columns
    assert "Trap" in html
    assert "Description" in html
    assert "Detected" in html
    assert "Rate" in html
    assert "Correct port" in html
    
    # Check each trap from the real catalog
    for trap_id in ["T1", "T2", "T3", "T4", "T5", "T6"]:
        assert trap_id in html
        
        trap_data = catalog_data[trap_id]
        
        # Check description (title)
        title = trap_data.get("title", "")
        if title:
            assert title in html
        
        # Check detected (exact format from real data)
        detected = trap_data.get("cases_detected")
        total = trap_data.get("cases_generated")
        if detected is not None and total is not None:
            detected_text = f"{detected} of {total}"
            assert detected_text in html
        
        # Check rate (exact format - it's already a string in the data)
        rate = trap_data.get("detection_rate")
        if rate is not None:
            assert rate in html
        
        # Check correct port verdict
        correct_verdict = trap_data.get("correct_verdict")
        if correct_verdict:
            assert correct_verdict in html
    
    # T6 is measured like the others: its row shows the numbers of the catalog
    assert "T6" in html
    t6_index = html.find(">T6<")
    assert t6_index > 0, "T6 not found in HTML"
    t6_row = html[t6_index:html.find("</tr>", t6_index)]
    trap_t6 = catalog_data["T6"]
    assert trap_t6["title"] in html
    assert f"{trap_t6['cases_detected']} of {trap_t6['cases_generated']}" in t6_row
    assert trap_t6["detection_rate"] in t6_row
    assert trap_t6["correct_verdict"] in t6_row
    assert "not measured" not in t6_row
    assert "Case 6 The Cursed Modulo" in html
    
    # Check no "not available yet" message
    assert "not available yet" not in html


def test_matrix_page_shows_an_unmeasured_entry_without_numbers(matrix_catalog, tmp_path, monkeypatch):
    """An entry of an older catalog that is not measured (a placeholder) is shown as "not measured"."""
    catalog_data, base_dir = matrix_catalog
    traps = [dict(trap) for trap in catalog_data.values()]
    for trap in traps:
        if trap["id"] == "T6":
            for key in ("cases_generated", "cases_detected", "detection_rate", "correct_verdict",
                        "faulty_run_id", "correct_run_id"):
                trap.pop(key, None)
            trap["status"] = "placeholder: owner field trap pending"
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "trap_catalog.json").write_text(json.dumps({"traps": traps}))
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))

    from coroner.ui.app import app

    html = TestClient(app).get("/matrix").text
    t6_index = html.find(">T6<")
    t6_row = html[t6_index:html.find("</tr>", t6_index)]
    assert t6_row.count("not measured") == 3
    t1_index = html.find(">T1<")
    assert "not measured" not in html[t1_index:html.find("</tr>", t1_index)]


def test_matrix_page_without_catalog(tmp_path, monkeypatch):
    """Test Detection Matrix page when catalog file is absent."""
    # Set CORONER_BASE_DIR to tmp_path (no catalog created)
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    # Import app after setting env var
    from coroner.ui.app import app
    
    # Override BASE_DIR directly
    import coroner.ui.app as app_module
    app_module.BASE_DIR = tmp_path
    
    client = TestClient(app)
    
    # Request the matrix page
    response = client.get("/matrix")
    assert response.status_code == 200
    
    html = response.text
    
    # Check the title
    assert "Detection Matrix" in html
    
    # Check the "not available yet" message
    assert "Detection Matrix not available yet: run make traps" in html
    
    # Check no table
    assert "<table" not in html
    assert "Trap" not in html or "Trap" in "Detection Matrix"  # "Trap" might be in "Detection Matrix" in title
