"""
Trap catalog acceptance tests (task 12).
Marked slow, run with `make acceptance`.
"""

import json
import pytest
from pathlib import Path
from coroner.traps import run_catalog, write_catalog_files


@pytest.mark.slow
def test_trap_catalog_acceptance(tmp_path):
    """
    Run the catalog runner with defaults (2000 cases, seed 42),
    assert measured results for T1 to T6.
    """
    base_dir = tmp_path / "run1"
    base_dir.mkdir()
    
    catalog_result = run_catalog(seed=42, cases=2000, base_dir=str(base_dir))
    write_catalog_files(catalog_result, base_dir=str(base_dir))
    
    catalog_json = base_dir / "runs" / "trap_catalog.json"
    assert catalog_json.exists(), "trap_catalog.json not written"
    
    with open(catalog_json, "r") as f:
        catalog_data = json.load(f)
    
    # The catalog is stored with a "traps" key
    catalog = catalog_data["traps"]
    
    assert len(catalog) == 6, "Expected 6 traps (T1 to T6)"
    
    # T1 to T6: status measured, correct_verdict ALIVE, at least one detected case
    for i in range(6):
        trap = catalog[i]
        trap_id = f"T{i+1}"
        assert trap["id"] == trap_id, f"Expected trap id {trap_id}"
        assert trap["status"] == "measured", f"{trap_id} status should be measured"
        assert trap["correct_verdict"] == "ALIVE", f"{trap_id} correct port should be ALIVE"
        assert trap["cases_detected"] >= 1, f"{trap_id} should detect at least one case"
        
        # Detection rate = cases_detected / cases_generated (stored as string)
        expected_rate = trap["cases_detected"] / trap["cases_generated"]
        actual_rate = float(trap["detection_rate"])
        assert abs(actual_rate - expected_rate) < 0.0001, \
            f"{trap_id} detection_rate should equal cases_detected/cases_generated"
    
    # T1 specific: grand total matches with at least one affected branch
    t1 = catalog[0]
    assert t1["grand_total_matches"] is True, "T1 grand total should match"
    assert t1["affected_branches"] >= 1, "T1 should have at least one affected branch"
    
    # T6: measured like the others, with numeric fields
    t6 = catalog[5]
    assert t6["id"] == "T6", "Expected trap id T6"
    assert t6["status"] == "measured", "T6 status should be measured"
    assert t6["case_name"] == "The Cursed Modulo"
    assert t6["cases_generated"] == 2000
    
    # No global rate field
    for trap in catalog:
        assert "global_rate" not in trap, f"{trap['id']} should not have global_rate"


@pytest.mark.slow
def test_trap_catalog_determinism(tmp_path):
    """
    Run the catalog twice and assert identical JSON except timestamps.
    """
    base_dir1 = tmp_path / "run1"
    base_dir1.mkdir()
    catalog1_result = run_catalog(seed=42, cases=2000, base_dir=str(base_dir1))
    write_catalog_files(catalog1_result, base_dir=str(base_dir1))
    
    base_dir2 = tmp_path / "run2"
    base_dir2.mkdir()
    catalog2_result = run_catalog(seed=42, cases=2000, base_dir=str(base_dir2))
    write_catalog_files(catalog2_result, base_dir=str(base_dir2))
    
    catalog_json1 = base_dir1 / "runs" / "trap_catalog.json"
    catalog_json2 = base_dir2 / "runs" / "trap_catalog.json"
    
    with open(catalog_json1, "r") as f:
        catalog_data1 = json.load(f)
    
    with open(catalog_json2, "r") as f:
        catalog_data2 = json.load(f)
    
    catalog1 = catalog_data1["traps"]
    catalog2 = catalog_data2["traps"]
    
    assert len(catalog1) == len(catalog2), "Both runs should have same number of traps"
    
    for i, (trap1, trap2) in enumerate(zip(catalog1, catalog2)):
        # Remove timestamps and run_ids before comparison (run_ids differ each run)
        trap1_copy = {k: v for k, v in trap1.items() 
                     if k not in ["timestamp", "faulty_run_id", "correct_run_id"]}
        trap2_copy = {k: v for k, v in trap2.items() 
                     if k not in ["timestamp", "faulty_run_id", "correct_run_id"]}
        
        assert trap1_copy == trap2_copy, f"Trap {i} should be identical except timestamp and run_ids"
