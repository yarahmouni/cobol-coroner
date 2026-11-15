"""Tests for coroner/store.py."""
import json
import os
import tempfile
from pathlib import Path
import hashlib

import pytest

from coroner.store import compute_run_id, store_inputs, store_verdict, store_comparison, collect_inputs
from coroner.verdict import Verdict
from coroner.compare import ComparisonResult, CaseResult


def test_compute_run_id_deterministic(tmp_path):
    """Same inputs produce same run_id."""
    inputs = {
        "cobol_source_sha256": "cobol123",
        "java_source_sha256": "java456",
        "schema_sha256": "schema789",
        "copybook_hashes": [
            {"name": "HELPER.cpy", "sha256": "abc123"},
            {"name": "TYPES.cpy", "sha256": "def456"}
        ],
        "seed": 42,
        "case_count": 2000,
        "python_version": "3.12.16",
        "cobc_version": "GnuCOBOL 3.2.0",
        "javac_version": "javac 17.0.21",
        "java_version": "openjdk 17.0.21",
        "coroner_version": "0.1.0"
    }
    
    run_id_1 = compute_run_id(inputs)
    run_id_2 = compute_run_id(inputs)
    
    assert run_id_1 == run_id_2
    assert len(run_id_1) == 12
    assert all(c in "0123456789abcdef" for c in run_id_1)


def test_compute_run_id_changes_with_seed(tmp_path):
    """Changing seed produces different run_id."""
    inputs_1 = {
        "cobol_source_sha256": "cobol123",
        "java_source_sha256": "java456",
        "schema_sha256": "schema789",
        "copybook_hashes": [{"name": "HELPER.cpy", "sha256": "abc123"}],
        "seed": 42,
        "case_count": 2000,
        "python_version": "3.12.16",
        "cobc_version": "GnuCOBOL 3.2.0",
        "javac_version": "javac 17.0.21",
        "java_version": "openjdk 17.0.21",
        "coroner_version": "0.1.0"
    }
    
    inputs_2 = inputs_1.copy()
    inputs_2["seed"] = 99
    
    run_id_1 = compute_run_id(inputs_1)
    run_id_2 = compute_run_id(inputs_2)
    
    assert run_id_1 != run_id_2


def test_compute_run_id_changes_with_case_count(tmp_path):
    """Changing case_count produces different run_id."""
    inputs_1 = {
        "cobol_source_sha256": "cobol123",
        "java_source_sha256": "java456",
        "schema_sha256": "schema789",
        "copybook_hashes": [{"name": "HELPER.cpy", "sha256": "abc123"}],
        "seed": 42,
        "case_count": 2000,
        "python_version": "3.12.16",
        "cobc_version": "GnuCOBOL 3.2.0",
        "javac_version": "javac 17.0.21",
        "java_version": "openjdk 17.0.21",
        "coroner_version": "0.1.0"
    }
    
    inputs_2 = inputs_1.copy()
    inputs_2["case_count"] = 500
    
    run_id_1 = compute_run_id(inputs_1)
    run_id_2 = compute_run_id(inputs_2)
    
    assert run_id_1 != run_id_2


def test_compute_run_id_changes_with_input_hash(tmp_path):
    """Changing any input hash produces different run_id."""
    inputs_1 = {
        "cobol_source_sha256": "cobol123",
        "java_source_sha256": "java456",
        "schema_sha256": "schema789",
        "copybook_hashes": [{"name": "HELPER.cpy", "sha256": "abc123"}],
        "seed": 42,
        "case_count": 2000,
        "python_version": "3.12.16",
        "cobc_version": "GnuCOBOL 3.2.0",
        "javac_version": "javac 17.0.21",
        "java_version": "openjdk 17.0.21",
        "coroner_version": "0.1.0"
    }
    
    inputs_2 = inputs_1.copy()
    inputs_2["cobol_source_sha256"] = "cobol999"
    
    run_id_1 = compute_run_id(inputs_1)
    run_id_2 = compute_run_id(inputs_2)
    
    assert run_id_1 != run_id_2


def test_store_inputs_creates_json(tmp_path):
    """store_inputs writes inputs.json with correct fields."""
    run_dir = tmp_path / "runs" / "abc123def456"
    
    inputs_data = {
        "cobol_source_sha256": "cobol123",
        "java_source_sha256": "java456",
        "schema_sha256": "schema789",
        "copybook_hashes": [{"name": "HELPER.cpy", "sha256": "abc123"}],
        "seed": 42,
        "random_seed": 42,
        "case_count": 2000,
        "cases_file_sha256": "cases123",
        "cases_file_encoding": "utf-8",
        "cases_file_line_ending": "LF",
        "python_version": "3.12.16",
        "cobc_version": "GnuCOBOL 3.2.0",
        "javac_version": "javac 17.0.21",
        "java_version": "openjdk 17.0.21",
        "coroner_version": "0.1.0",
        "comparison_engine_sha256": "engine123",
        "timestamp": "2026-11-15T13:41:40Z"
    }
    
    store_inputs(str(run_dir), inputs_data)
    
    inputs_path = run_dir / "inputs.json"
    assert inputs_path.exists()
    
    with open(inputs_path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    
    assert loaded == inputs_data
    assert loaded["cobol_source_sha256"] == "cobol123"
    assert loaded["seed"] == 42
    assert loaded["random_seed"] == 42
    assert loaded["cases_file_encoding"] == "utf-8"
    assert loaded["cases_file_line_ending"] == "LF"


def test_store_verdict_atomic_write(tmp_path):
    """store_verdict writes atomically with no temp file left."""
    run_dir = tmp_path / "runs" / "abc123def456"
    
    verdict = Verdict(
        status="ALIVE",
        sub_label="PASS: business behavior preserved on 2000 cases",
        cases_total=2000,
        cases_divergent=0,
        run_return_codes=(0, 0)
    )
    
    store_verdict(str(run_dir), verdict)
    
    verdict_path = run_dir / "verdict.json"
    assert verdict_path.exists()
    
    with open(verdict_path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    
    assert loaded["status"] == "ALIVE"
    assert loaded["sub_label"] == "PASS: business behavior preserved on 2000 cases"
    assert loaded["cases_total"] == 2000
    assert loaded["cases_divergent"] == 0
    assert loaded["run_return_codes"] == [0, 0]
    assert loaded["validation_notice"] == "Validated under GnuCOBOL 3.x"
    
    # Check no temp files left
    temp_files = list(run_dir.glob(".verdict_*.json.tmp"))
    assert len(temp_files) == 0


def test_store_verdict_zombie(tmp_path):
    """store_verdict handles ZOMBIE verdicts."""
    run_dir = tmp_path / "runs" / "abc123def456"
    
    verdict = Verdict(
        status="ZOMBIE",
        sub_label="FAIL: business behavior diverged on 75 cases",
        cases_total=2000,
        cases_divergent=75,
        run_return_codes=(0, 0)
    )
    
    store_verdict(str(run_dir), verdict)
    
    verdict_path = run_dir / "verdict.json"
    assert verdict_path.exists()
    
    with open(verdict_path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    
    assert loaded["status"] == "ZOMBIE"
    assert loaded["cases_divergent"] == 75


def test_store_comparison_with_divergences(tmp_path):
    """store_comparison writes comparison results."""
    run_dir = tmp_path / "runs" / "abc123def456"
    
    cases = [
        CaseResult(
            case_id="GEN-00001",
            divergent=False,
            divergent_fields=[]
        ),
        CaseResult(
            case_id="GEN-00002",
            divergent=True,
            divergent_fields=[
                ("FEE", "12.35", "12.36")
            ]
        )
    ]
    
    comparison = ComparisonResult(
        cases=cases,
        run_return_codes=(0, 0),
        row_count_match=True,
        total_divergent=1
    )
    
    store_comparison(str(run_dir), comparison)
    
    comparison_path = run_dir / "comparison_results.json"
    assert comparison_path.exists()
    
    with open(comparison_path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    
    assert loaded["total_divergent"] == 1
    assert loaded["run_return_codes"] == [0, 0]
    assert loaded["row_count_match"] is True
    assert len(loaded["cases"]) == 2
    assert loaded["cases"][0]["case_id"] == "GEN-00001"
    assert loaded["cases"][0]["divergent"] is False
    assert loaded["cases"][1]["case_id"] == "GEN-00002"
    assert loaded["cases"][1]["divergent"] is True
    assert len(loaded["cases"][1]["divergent_fields"]) == 1
    assert loaded["cases"][1]["divergent_fields"][0]["field_name"] == "FEE"
    assert loaded["cases"][1]["divergent_fields"][0]["cobol_value"] == "12.35"
    assert loaded["cases"][1]["divergent_fields"][0]["java_value"] == "12.36"


def test_run_directory_created(tmp_path):
    """Run directory is created when it doesn't exist."""
    run_dir = tmp_path / "runs" / "newrun123456"
    assert not run_dir.exists()
    
    inputs_data = {
        "cobol_source_sha256": "cobol123",
        "seed": 42,
        "case_count": 100
    }
    
    store_inputs(str(run_dir), inputs_data)
    
    assert run_dir.exists()
    assert (run_dir / "inputs.json").exists()


def test_old_runs_not_deleted(tmp_path):
    """Old runs are not deleted when new runs are stored."""
    runs_dir = tmp_path / "runs"
    old_run = runs_dir / "oldrun123456"
    new_run = runs_dir / "newrun789abc"
    
    # Create old run
    inputs_data_old = {
        "cobol_source_sha256": "old123",
        "seed": 1,
        "case_count": 100
    }
    store_inputs(str(old_run), inputs_data_old)
    assert old_run.exists()
    
    # Create new run
    inputs_data_new = {
        "cobol_source_sha256": "new456",
        "seed": 2,
        "case_count": 200
    }
    store_inputs(str(new_run), inputs_data_new)
    
    # Both should exist
    assert old_run.exists()
    assert new_run.exists()
    assert (old_run / "inputs.json").exists()
    assert (new_run / "inputs.json").exists()


def test_collect_inputs_all_fields(tmp_path):
    """collect_inputs returns all required fields."""
    # Create test files
    cobol_source = tmp_path / "test.cob"
    cobol_source.write_text("IDENTIFICATION DIVISION.\n")
    
    java_source = tmp_path / "Test.java"
    java_source.write_text("public class Test {}\n")
    
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"columns":[]}\n')
    
    copybook_dir = tmp_path / "copybooks"
    copybook_dir.mkdir()
    (copybook_dir / "TEST.cpy").write_text("01 TEST-FIELD PIC X(10).\n")
    
    cases_file = tmp_path / "cases.csv"
    cases_file.write_text("CASE_ID\nTEST-001\n", encoding='utf-8')
    
    # Collect inputs
    inputs = collect_inputs(
        cobol_source=str(cobol_source),
        copybook_dir=str(copybook_dir),
        java_source=str(java_source),
        schema_path=str(schema_path),
        cases_file=str(cases_file),
        seed=42,
        case_count=100
    )
    
    # Verify all required fields exist
    assert "cobol_source_sha256" in inputs
    assert "java_source_sha256" in inputs
    assert "schema_sha256" in inputs
    assert "copybook_hashes" in inputs
    assert "seed" in inputs
    assert "random_seed" in inputs
    assert "case_count" in inputs
    assert "cases_file_sha256" in inputs
    assert "cases_file_encoding" in inputs
    assert "cases_file_line_ending" in inputs
    assert "python_version" in inputs
    assert "cobc_version" in inputs
    assert "javac_version" in inputs
    assert "java_version" in inputs
    assert "coroner_version" in inputs
    assert "comparison_engine_sha256" in inputs
    assert "timestamp" in inputs
    
    # Verify values
    assert inputs["seed"] == 42
    assert inputs["random_seed"] == 42
    assert inputs["case_count"] == 100
    assert inputs["cases_file_encoding"] == "utf-8"
    assert inputs["cases_file_line_ending"] == "LF"
    assert len(inputs["copybook_hashes"]) == 1
    assert inputs["copybook_hashes"][0]["name"] == "TEST.cpy"
    
    # Verify timestamp format (ISO 8601 UTC)
    assert inputs["timestamp"].endswith("Z")
    assert "T" in inputs["timestamp"]


def test_collect_inputs_cobol_hash_matches_direct_computation(tmp_path):
    """COBOL hash from collect_inputs equals direct SHA-256."""
    cobol_source = tmp_path / "test.cob"
    cobol_content = "IDENTIFICATION DIVISION.\nPROGRAM-ID. TEST.\n"
    cobol_source.write_text(cobol_content)
    
    java_source = tmp_path / "Test.java"
    java_source.write_text("public class Test {}\n")
    
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"columns":[]}\n')
    
    copybook_dir = tmp_path / "copybooks"
    copybook_dir.mkdir()
    
    cases_file = tmp_path / "cases.csv"
    cases_file.write_text("CASE_ID\nTEST-001\n", encoding='utf-8')
    
    # Collect inputs
    inputs = collect_inputs(
        cobol_source=str(cobol_source),
        copybook_dir=str(copybook_dir),
        java_source=str(java_source),
        schema_path=str(schema_path),
        cases_file=str(cases_file),
        seed=42,
        case_count=100
    )
    
    # Compute hash directly
    expected_hash = hashlib.sha256(cobol_content.encode('utf-8')).hexdigest()
    
    assert inputs["cobol_source_sha256"] == expected_hash


def test_collect_inputs_stable_run_id_despite_different_timestamps(tmp_path):
    """run_id is stable across calls even though timestamps differ."""
    cobol_source = tmp_path / "test.cob"
    cobol_source.write_text("IDENTIFICATION DIVISION.\n")
    
    java_source = tmp_path / "Test.java"
    java_source.write_text("public class Test {}\n")
    
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"columns":[]}\n')
    
    copybook_dir = tmp_path / "copybooks"
    copybook_dir.mkdir()
    
    cases_file = tmp_path / "cases.csv"
    cases_file.write_text("CASE_ID\nTEST-001\n", encoding='utf-8')
    
    # Collect inputs once
    inputs_1 = collect_inputs(
        cobol_source=str(cobol_source),
        copybook_dir=str(copybook_dir),
        java_source=str(java_source),
        schema_path=str(schema_path),
        cases_file=str(cases_file),
        seed=42,
        case_count=100
    )
    
    # Make a copy with a different timestamp
    inputs_2 = inputs_1.copy()
    inputs_2["timestamp"] = "2000-01-01T00:00:00Z"
    
    # run_ids should be the same despite different timestamps
    run_id_1 = compute_run_id(inputs_1)
    run_id_2 = compute_run_id(inputs_2)
    
    assert run_id_1 == run_id_2


def test_collect_inputs_rejects_cr_in_cases_file(tmp_path):
    """collect_inputs raises ValueError if cases file contains CR."""
    cobol_source = tmp_path / "test.cob"
    cobol_source.write_text("IDENTIFICATION DIVISION.\n")
    
    java_source = tmp_path / "Test.java"
    java_source.write_text("public class Test {}\n")
    
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"columns":[]}\n')
    
    copybook_dir = tmp_path / "copybooks"
    copybook_dir.mkdir()
    
    # Create cases file with CRLF
    cases_file = tmp_path / "cases.csv"
    cases_file.write_bytes(b"CASE_ID\r\nTEST-001\r\n")
    
    with pytest.raises(ValueError, match="contains CR"):
        collect_inputs(
            cobol_source=str(cobol_source),
            copybook_dir=str(copybook_dir),
            java_source=str(java_source),
            schema_path=str(schema_path),
            cases_file=str(cases_file),
            seed=42,
            case_count=100
        )


def test_collect_inputs_multiple_copybooks_sorted(tmp_path):
    """Copybooks are sorted by name."""
    cobol_source = tmp_path / "test.cob"
    cobol_source.write_text("IDENTIFICATION DIVISION.\n")
    
    java_source = tmp_path / "Test.java"
    java_source.write_text("public class Test {}\n")
    
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"columns":[]}\n')
    
    copybook_dir = tmp_path / "copybooks"
    copybook_dir.mkdir()
    (copybook_dir / "ZEBRA.cpy").write_text("01 Z PIC X.\n")
    (copybook_dir / "ALPHA.cpy").write_text("01 A PIC X.\n")
    (copybook_dir / "MIDDLE.cpy").write_text("01 M PIC X.\n")
    
    cases_file = tmp_path / "cases.csv"
    cases_file.write_text("CASE_ID\nTEST-001\n", encoding='utf-8')
    
    inputs = collect_inputs(
        cobol_source=str(cobol_source),
        copybook_dir=str(copybook_dir),
        java_source=str(java_source),
        schema_path=str(schema_path),
        cases_file=str(cases_file),
        seed=42,
        case_count=100
    )
    
    names = [cb["name"] for cb in inputs["copybook_hashes"]]
    assert names == ["ALPHA.cpy", "MIDDLE.cpy", "ZEBRA.cpy"]
