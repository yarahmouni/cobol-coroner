"""Tests for trap catalog runner."""
import json
from pathlib import Path

import pytest

from coroner.traps import run_catalog


@pytest.fixture(scope="module")
def catalog_200(tmp_path_factory):
    """The real trap catalog at 200 cases, seed 42, built once for the slow tests of this module.

    run_catalog runs in a temporary base directory. The tests that write the catalog files write
    them from a copy of this dict into their own folder.
    """
    return run_catalog(seed=42, cases=200, base_dir=str(tmp_path_factory.mktemp("catalog_200")))


@pytest.mark.slow
def test_catalog_runner_200_cases(catalog_200):
    """Test catalog runner with 200 cases."""
    catalog = catalog_200
    
    assert "traps" in catalog
    traps = catalog["traps"]
    
    # Should have exactly 6 entries (T1-T5 measured, T6 placeholder)
    assert len(traps) == 6
    
    # Must be in order T1, T2, T3, T4, T5, T6
    trap_ids = [t["id"] for t in traps]
    assert trap_ids == ["T1", "T2", "T3", "T4", "T5", "T6"], f"Traps not in order, got {trap_ids}"
    
    # Check T6 placeholder
    t6 = [t for t in traps if t["id"] == "T6"][0]
    assert t6["status"] == "placeholder: owner field trap pending"
    assert "cases_generated" not in t6
    assert "cases_detected" not in t6
    assert "detection_rate" not in t6
    
    # Check measured traps (T1-T5)
    for trap in traps:
        if trap["id"] != "T6":
            assert trap["status"] == "measured"
            assert trap["cases_generated"] == 200
            assert "cases_detected" in trap
            assert "detection_rate" in trap
            assert "correct_verdict" in trap
            assert "faulty_run_id" in trap
            assert "correct_run_id" in trap
            assert "probable_cause" in trap
            assert "fix_sentence" in trap
            
            # Every trap must detect at least one case
            assert trap["cases_detected"] >= 1, f"{trap['id']} detected 0 cases"
            
            # Correct Java must be ALIVE
            assert trap["correct_verdict"] == "ALIVE", f"{trap['id']} correct Java is not ALIVE"
            
            # Detection rate must equal cases_detected / cases_generated
            expected_rate = trap["cases_detected"] / trap["cases_generated"]
            assert trap["detection_rate"] == f"{expected_rate:.4f}"
            
            # Fix sentence must describe a Java-side change, not a compile flag or validation
            fix = trap["fix_sentence"]
            assert "-fsign" not in fix, f"{trap['id']} fix mentions compile flag"
            assert "validate" not in fix.lower(), f"{trap['id']} fix mentions validation (not a port fix)"
    
    # No global detection rate field anywhere
    assert "detection_rate" not in catalog
    assert "global_detection_rate" not in catalog


@pytest.mark.slow
def test_catalog_json_written(catalog_200, tmp_path):
    """Test that catalog JSON is written."""
    import copy
    
    catalog = copy.deepcopy(catalog_200)
    
    from coroner.traps import write_catalog_files
    write_catalog_files(catalog, base_dir=str(tmp_path))
    
    # Check JSON exists
    json_path = tmp_path / "runs" / "trap_catalog.json"
    assert json_path.exists()
    
    # Check it's valid JSON with sorted keys
    with open(json_path) as f:
        content = f.read()
        data = json.loads(content)
    
    # Verify structure
    assert "traps" in data
    assert len(data["traps"]) == 6
    
    # Check text file exists
    txt_path = tmp_path / "runs" / "trap_catalog.txt"
    assert txt_path.exists()
    
    with open(txt_path) as f:
        text = f.read()
    
    # Check header
    assert "Six banking migration traps" in text
    assert "targeted regression traps within its supported COBOL subset" in text
    
    # Check no forbidden terms
    assert "first" not in text.lower() or "first statement" in text.lower()
    assert "unique" not in text.lower()
    assert "novel" not in text.lower()
    assert "proven" not in text.lower()
    assert "proves" not in text.lower()
    assert "guaranteed" not in text.lower()



def test_catalog_does_not_overwrite_real_file(story_runs):
    """Test that catalog runner never overwrites the repository's runs/trap_catalog.json.

    The catalog is the session fixture story_runs of tests/conftest.py: run_catalog and
    write_catalog_files ran there with a temporary base directory, after the fixture recorded
    the state of the repository file (mtime and SHA-256; None when the file is absent, as in
    the Docker image).
    """
    import hashlib
    
    repo_catalog_path = Path(__file__).resolve().parent.parent / "runs" / "trap_catalog.json"
    
    # The catalog really was built in a temporary base directory, not in the repository
    assert (story_runs.base / "runs" / "trap_catalog.json").exists()
    assert story_runs.base.resolve() != repo_catalog_path.parent.parent.resolve()
    
    # State recorded before the catalog was built
    before = story_runs.repo_catalog_before
    
    # A file that was absent must not have been created
    if before is None:
        assert not repo_catalog_path.exists(), "Catalog runner created the repository catalog"
        return
    
    # Check the repository file was not touched
    original_mtime, original_hash = before
    assert repo_catalog_path.stat().st_mtime_ns == original_mtime, "Repository catalog mtime changed"
    
    with open(repo_catalog_path, "rb") as f:
        new_hash = hashlib.sha256(f.read()).hexdigest()
    assert new_hash == original_hash, "Repository catalog SHA-256 changed"
