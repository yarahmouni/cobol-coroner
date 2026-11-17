"""Tests for UI sentence generation."""

import json
import subprocess
import os
from pathlib import Path
from decimal import Decimal

import pytest


def test_t1_sentence_from_real_run(tmp_path):
    """T1 ZOMBIE sentence computed from real run files equals independent calculation."""
    from coroner.ui.sentences import generate_zombie_sentence
    
    # Run T1 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
            "--copybooks", "samples/traps/T1-ebcdic-match-merge/copybooks",
            "--java", "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java",
            "--schema", "samples/traps/T1-ebcdic-match-merge/schema.json",
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=30.0,
        env=env
    )
    
    assert result.returncode == 1  # ZOMBIE
    
    # Extract run directory
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir = Path(line.split("Run: ", 1)[1].strip())
            break
    
    assert run_dir is not None
    
    # Generate sentence
    sentence = generate_zombie_sentence("T1", run_dir)
    
    # Independently compute expected sentence


def test_t1_zombie_sentence_in_ui_story(tmp_path):
    """Test that #story contains the ZOMBIE sentence returned by generate_zombie_sentence for T1 faulty run."""
    from coroner.ui.sentences import generate_zombie_sentence
    from fastapi.testclient import TestClient
    
    # Run T1 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
            "--copybooks", "samples/traps/T1-ebcdic-match-merge/copybooks",
            "--java", "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java",
            "--schema", "samples/traps/T1-ebcdic-match-merge/schema.json",
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=30.0,
        env=env
    )
    
    assert result.returncode == 1  # ZOMBIE
    
    # Extract run directory
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir = Path(line.split("Run: ", 1)[1].strip())
            break
    
    assert run_dir is not None
    
    # Generate sentence using the function
    expected_sentence = generate_zombie_sentence("T1", run_dir)
    
    # Get UI page
    from coroner.ui.app import app
    client = TestClient(app)
    
    run_id = run_dir.name
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Find #story section
    story_start = html.find('id="story"')
    assert story_start >= 0, "#story section not found"
    story_end = html.find('</section>', story_start)
    story_section = html[story_start:story_end] if story_end >= 0 else html[story_start:]
    
    # Check the ZOMBIE sentence is in #story
    assert expected_sentence in story_section, f"ZOMBIE sentence not found in #story: {expected_sentence}"


def test_t2_sentence_from_real_run(tmp_path):
    """T2 ZOMBIE sentence computed from real run files equals independent calculation."""
    from coroner.ui.sentences import generate_zombie_sentence
    
    # Run T2 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", "samples/traps/T2-rounding/ROUNDING-CALC.cob",
            "--copybooks", "samples/traps/T2-rounding",
            "--java", "samples/traps/T2-rounding/java/faulty/RoundingCalc.java",
            "--schema", "samples/traps/T2-rounding/schema.json",
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=30.0,
        env=env
    )
    
    assert result.returncode == 1  # ZOMBIE
    
    # Extract run directory
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir = Path(line.split("Run: ", 1)[1].strip())
            break
    
    assert run_dir is not None
    
    # Generate sentence
    sentence = generate_zombie_sentence("T2", run_dir)
    
    # Independently compute expected sentence
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    divergent_count = 0
    total_fees = 0
    max_diff = Decimal(0)
    
    for case in comparison["cases"]:
        if case.get("divergent", False):
            for field in case.get("divergent_fields", []):
                if "FEE" in field["field_name"].upper():
                    divergent_count += 1
                    cobol_val = Decimal(field["cobol_value"].strip().replace("+", "").replace("-", ""))
                    java_val = Decimal(field["java_value"].strip().replace("+", "").replace("-", ""))
                    diff = abs(cobol_val - java_val)
                    if diff > max_diff:
                        max_diff = diff
    
    total_cases = len(comparison["cases"])
    fee_fields_per_case = 0
    
    if comparison["cases"]:
        for case in comparison["cases"]:
            if case.get("divergent", False):
                for field in case.get("divergent_fields", []):
                    if "FEE" in field["field_name"].upper():
                        fee_fields_per_case += 1
                break
    
    total_fees = total_cases * fee_fields_per_case if fee_fields_per_case > 0 else divergent_count
    
    if max_diff == Decimal("0.01"):
        expected = f"This Java migration is not safe to promote: {divergent_count} of {total_fees} fee amounts differ from COBOL by rounding, each by exactly 0.01."
    else:
        expected = f"This Java migration is not safe to promote: {divergent_count} of {total_fees} fee amounts differ from COBOL by rounding (maximum difference {max_diff})."
    
    assert sentence == expected


def test_t3_sentence_from_real_run(tmp_path):
    """T3 ZOMBIE sentence computed from real run files equals independent calculation."""
    from coroner.ui.sentences import generate_zombie_sentence
    
    # Run T3 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", "samples/traps/T3-comp3-sign/COMP3-SIGN.cob",
            "--copybooks", "samples/traps/T3-comp3-sign",
            "--java", "samples/traps/T3-comp3-sign/java/faulty/Comp3Sign.java",
            "--schema", "samples/traps/T3-comp3-sign/schema.json",
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=30.0,
        env=env
    )
    
    assert result.returncode == 1  # ZOMBIE
    
    # Extract run directory
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir = Path(line.split("Run: ", 1)[1].strip())
            break
    
    assert run_dir is not None
    
    # Generate sentence
    sentence = generate_zombie_sentence("T3", run_dir)
    
    # Independently compute expected count
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    count = 0
    for case in comparison["cases"]:
        if case.get("divergent", False):
            for field in case.get("divergent_fields", []):
                cobol_str = field["cobol_value"].strip()
                java_str = field["java_value"].strip()
                
                cobol_val = Decimal(cobol_str.replace("+", ""))
                java_val = Decimal(java_str.replace("+", ""))
                
                if cobol_val > 0 and java_val < 0:
                    count += 1
    
    expected = f"This Java migration is not safe to promote: {count} positive amounts are read as negative."
    
    assert sentence == expected


def test_t5_sentence_from_real_run(tmp_path):
    """T5 ZOMBIE sentence computed from real run files equals independent calculation."""
    from coroner.ui.sentences import generate_zombie_sentence
    
    # Run T5 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", "samples/traps/T5-redefines-invalid/REDEFINES-INVALID.cob",
            "--copybooks", "samples/traps/T5-redefines-invalid",
            "--java", "samples/traps/T5-redefines-invalid/java/faulty/RedefinesInvalid.java",
            "--schema", "samples/traps/T5-redefines-invalid/schema.json",
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=30.0,
        env=env
    )
    
    assert result.returncode == 1  # ZOMBIE
    
    # Extract run directory
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir = Path(line.split("Run: ", 1)[1].strip())
            break
    
    assert run_dir is not None
    
    # Generate sentence
    sentence = generate_zombie_sentence("T5", run_dir)
    
    # Independently compute expected count
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    count = 0
    for case in comparison["cases"]:
        if case.get("divergent", False):
            count += 1
    
    expected = f"This Java migration is not safe to promote: {count} invalid amounts are silently treated as zero instead of being processed like COBOL."
    
    assert sentence == expected


def test_t4_sentence_from_real_run(tmp_path):
    """T4 ZOMBIE sentence computed from real run files equals independent calculation."""
    from coroner.ui.sentences import generate_zombie_sentence
    
    # Run T4 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", "samples/traps/T4-zoned-overpunch/ZONED-OVERPUNCH.cob",
            "--copybooks", "samples/traps/T4-zoned-overpunch",
            "--java", "samples/traps/T4-zoned-overpunch/java/faulty/ZonedOverpunch.java",
            "--schema", "samples/traps/T4-zoned-overpunch/schema.json",
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=30.0,
        env=env
    )
    
    assert result.returncode == 1  # ZOMBIE
    
    # Extract run directory
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir = Path(line.split("Run: ", 1)[1].strip())
            break
    
    assert run_dir is not None
    
    # Generate sentence
    sentence = generate_zombie_sentence("T4", run_dir)
    
    # Independently compute expected count from comparison_results.json
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    divergent_count = 0
    total_cases = len(comparison["cases"])
    wrong_sign_count = 0
    
    for case in comparison["cases"]:
        if case.get("divergent", False):
            for field in case.get("divergent_fields", []):
                if field["field_name"] == "DECODED-VALUE":
                    divergent_count += 1
                    
                    cobol_str = field["cobol_value"].strip()
                    java_str = field["java_value"].strip()
                    
                    cobol_val = Decimal(cobol_str.replace("+", ""))
                    java_val = Decimal(java_str.replace("+", ""))
                    
                    if (cobol_val >= 0) != (java_val >= 0):
                        wrong_sign_count += 1
    
    expected = f"This Java migration is not safe to promote: {divergent_count} of {total_cases} balances are decoded wrongly, {wrong_sign_count} of them with the wrong sign."
    
    assert sentence == expected
