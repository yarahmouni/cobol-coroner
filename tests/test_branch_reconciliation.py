"""Tests for branch reconciliation generation."""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest


def test_branch_reconciliation_written_for_t1_faulty(tmp_path):
    """T1 faulty run writes branch_reconciliation.json."""
    import subprocess
    import os
    
    # Run T1 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
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
    
    # Extract run directory from stdout
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir_rel = line.split("Run: ", 1)[1].strip()
            run_dir = tmp_path / run_dir_rel
            break
    
    assert run_dir is not None, "Run directory not found in output"
    assert run_dir.exists()
    
    # branch_reconciliation.json exists
    reconciliation_file = run_dir / "branch_reconciliation.json"
    assert reconciliation_file.exists()
    
    # Read reconciliation
    reconciliation = json.loads(reconciliation_file.read_text())
    
    assert "branches" in reconciliation
    assert "grand_total" in reconciliation
    
    branches = reconciliation["branches"]
    grand_total = reconciliation["grand_total"]
    
    # Branches is a list
    assert isinstance(branches, list)
    assert len(branches) > 0
    
    # Each branch has required fields
    for branch in branches:
        assert "branch" in branch
        assert "cobol_subtotal" in branch
        assert "java_subtotal" in branch
        assert "difference" in branch
        assert "absolute_difference" in branch
        assert "status" in branch
        
        # Status is MATCH or MISMATCH
        assert branch["status"] in ["MATCH", "MISMATCH"]
    
    # Grand total has cobol and java
    assert "cobol" in grand_total
    assert "java" in grand_total


def test_branch_reconciliation_exposure_consistency(tmp_path):
    """
    Sum and max of absolute differences in branch_reconciliation
    equal exposure_sum and exposure_max in verdict.
    """
    import subprocess
    import os
    
    # Run T1 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
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
    
    # Extract run directory from stdout
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir_rel = line.split("Run: ", 1)[1].strip()
            run_dir = tmp_path / run_dir_rel
            break
    
    assert run_dir is not None, "Run directory not found in output"
    
    # Read verdict
    verdict_file = run_dir / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    
    exposure_sum = Decimal(verdict["exposure_sum"])
    exposure_max = Decimal(verdict["exposure_max"])
    affected_branches = verdict["affected_branches"]
    
    # Read reconciliation
    reconciliation_file = run_dir / "branch_reconciliation.json"
    reconciliation = json.loads(reconciliation_file.read_text())
    
    branches = reconciliation["branches"]
    
    # Compute sum and max of absolute differences
    absolute_diffs = []
    mismatch_count = 0
    
    for branch in branches:
        abs_diff = Decimal(branch["absolute_difference"])
        if abs_diff > 0:
            absolute_diffs.append(abs_diff)
            mismatch_count += 1
    
    computed_sum = sum(absolute_diffs) if absolute_diffs else Decimal(0)
    computed_max = max(absolute_diffs) if absolute_diffs else Decimal(0)
    
    # Assert consistency
    assert computed_sum == exposure_sum, f"Sum mismatch: {computed_sum} != {exposure_sum}"
    assert computed_max == exposure_max, f"Max mismatch: {computed_max} != {exposure_max}"
    assert mismatch_count == affected_branches, f"Affected branches mismatch: {mismatch_count} != {affected_branches}"


def test_branch_reconciliation_not_written_for_credit_fees(tmp_path):
    """
    Credit-fees does not have group_key/subtotal, so
    branch_reconciliation.json is not written.
    """
    import subprocess
    import os
    
    # Run credit-fees at 30 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", "samples/credit-fees/CREDIT-FEES.cob",
            "--copybooks", "samples/credit-fees/copybooks",
            "--java", "samples/credit-fees/java/CreditFees.java",
            "--schema", "samples/credit-fees/schema.json",
            "--cases", "30",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=30.0,
        env=env
    )
    
    assert result.returncode == 0  # ALIVE
    
    # Extract run directory from stdout
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir_rel = line.split("Run: ", 1)[1].strip()
            run_dir = tmp_path / run_dir_rel
            break
    
    assert run_dir is not None, "Run directory not found in output"
    
    # branch_reconciliation.json does not exist
    reconciliation_file = run_dir / "branch_reconciliation.json"
    assert not reconciliation_file.exists()


def test_branch_reconciliation_sorted_by_branch(tmp_path):
    """Branches are sorted alphabetically."""
    import subprocess
    import os
    
    # Run T1 faulty
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
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
    
    # Extract run directory from stdout
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir_rel = line.split("Run: ", 1)[1].strip()
            run_dir = tmp_path / run_dir_rel
            break
    
    assert run_dir is not None, "Run directory not found in output"
    
    # Read reconciliation
    reconciliation_file = run_dir / "branch_reconciliation.json"
    reconciliation = json.loads(reconciliation_file.read_text())
    
    branches = reconciliation["branches"]
    branch_codes = [b["branch"] for b in branches]
    
    # Assert sorted
    assert branch_codes == sorted(branch_codes)


def test_branch_reconciliation_aggregates_across_cases(tmp_path):
    """
    Branch reconciliation aggregates sums across all cases,
    matching independent computation by running COBOL and Java on the cases file.
    """
    import subprocess
    import os
    from collections import defaultdict
    
    # Run T1 faulty at 200 cases
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
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
    
    # Extract run directory from stdout
    run_dir = None
    for line in result.stdout.split('\n'):
        if line.startswith("Run: "):
            run_dir_rel = line.split("Run: ", 1)[1].strip()
            run_dir = tmp_path / run_dir_rel
            break
    
    assert run_dir is not None, "Run directory not found in output"
    
    # Read cases file
    cases_file = run_dir / "generated_cases.csv"
    assert cases_file.exists()
    
    # Build T1 programs into tmp_path
    build_dir = tmp_path / "build"
    build_dir.mkdir(exist_ok=True)
    
    # Compile COBOL
    result_cobol = subprocess.run(
        [
            "cobc", "-x", "-Wall",
            "-I", "samples/traps/T1-ebcdic-match-merge/copybooks",
            "-o", str(build_dir / "MATCH-MERGE"),
            "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob"
        ],
        capture_output=True,
        text=True,
        timeout=30.0
    )
    assert result_cobol.returncode == 0, f"COBOL compile failed: {result_cobol.stderr}"
    
    # Compile Java
    java_dir = build_dir / "faulty"
    java_dir.mkdir()
    result_java = subprocess.run(
        [
            "javac", "-d", str(java_dir),
            "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java"
        ],
        capture_output=True,
        text=True,
        timeout=30.0
    )
    assert result_java.returncode == 0, f"Java compile failed: {result_java.stderr}"
    
    # Run COBOL
    cobol_output = build_dir / "cobol_output.csv"
    env_cobol = os.environ.copy()
    env_cobol["INPUT_FILE"] = str(cases_file)
    env_cobol["OUTPUT_FILE"] = str(cobol_output)
    
    result_cobol_run = subprocess.run(
        [str(build_dir / "MATCH-MERGE")],
        env=env_cobol,
        capture_output=True,
        text=True,
        timeout=30.0
    )
    assert result_cobol_run.returncode == 0, f"COBOL run failed: {result_cobol_run.stderr}"
    assert cobol_output.exists()
    
    # Run Java
    java_output = build_dir / "java_output.csv"
    env_java = os.environ.copy()
    env_java["INPUT_FILE"] = str(cases_file)
    env_java["OUTPUT_FILE"] = str(java_output)
    
    result_java_run = subprocess.run(
        ["java", "-cp", str(java_dir), "MatchMerge"],
        env=env_java,
        capture_output=True,
        text=True,
        timeout=30.0
    )
    assert result_java_run.returncode == 0, f"Java run failed: {result_java_run.stderr}"
    assert java_output.exists()
    
    # Parse outputs
    cobol_lines = cobol_output.read_text().strip().split('\n')
    java_lines = java_output.read_text().strip().split('\n')
    
    cobol_header = cobol_lines[0].split(',')
    java_header = java_lines[0].split(',')
    
    branch_idx = cobol_header.index("BRANCH")
    subtotal_idx = cobol_header.index("SUBTOTAL")
    
    # Aggregate subtotals per branch (with trimmed branch codes)
    cobol_subtotals = defaultdict(lambda: Decimal(0))
    java_subtotals = defaultdict(lambda: Decimal(0))
    cobol_grand_total = Decimal(0)
    java_grand_total = Decimal(0)
    
    for line in cobol_lines[1:]:
        parts = line.split(',')
        branch = parts[branch_idx].rstrip()
        subtotal = Decimal(parts[subtotal_idx])
        
        if branch == "TOTAL":
            cobol_grand_total += subtotal
        else:
            cobol_subtotals[branch] += subtotal
    
    for line in java_lines[1:]:
        parts = line.split(',')
        branch = parts[branch_idx].rstrip()
        subtotal = Decimal(parts[subtotal_idx])
        
        if branch == "TOTAL":
            java_grand_total += subtotal
        else:
            java_subtotals[branch] += subtotal
    
    # Read branch_reconciliation.json
    reconciliation_file = run_dir / "branch_reconciliation.json"
    reconciliation = json.loads(reconciliation_file.read_text())
    
    # Verify branch sums (excluding SUSP)
    for branch_entry in reconciliation["branches"]:
        branch = branch_entry["branch"]
        cobol_reported = Decimal(branch_entry["cobol_subtotal"])
        java_reported = Decimal(branch_entry["java_subtotal"])
        
        cobol_computed = cobol_subtotals[branch]
        java_computed = java_subtotals[branch]
        
        assert cobol_reported == cobol_computed, f"Branch {branch}: COBOL {cobol_reported} != {cobol_computed}"
        assert java_reported == java_computed, f"Branch {branch}: Java {java_reported} != {java_computed}"
    
    # Verify suspense if present
    if "suspense" in reconciliation:
        suspense_entry = reconciliation["suspense"]
        cobol_suspense_reported = Decimal(suspense_entry["cobol"])
        java_suspense_reported = Decimal(suspense_entry["java"])
        
        cobol_suspense_computed = cobol_subtotals.get("SUSP", Decimal(0))
        java_suspense_computed = java_subtotals.get("SUSP", Decimal(0))
        
        assert cobol_suspense_reported == cobol_suspense_computed, f"COBOL suspense {cobol_suspense_reported} != {cobol_suspense_computed}"
        assert java_suspense_reported == java_suspense_computed, f"Java suspense {java_suspense_reported} != {java_suspense_computed}"
    
    # Verify grand total
    cobol_grand_reported = Decimal(reconciliation["grand_total"]["cobol"])
    java_grand_reported = Decimal(reconciliation["grand_total"]["java"])
    
    assert cobol_grand_reported == cobol_grand_total, f"COBOL grand {cobol_grand_reported} != {cobol_grand_total}"
    assert java_grand_reported == java_grand_total, f"Java grand {java_grand_reported} != {java_grand_total}"
    
    # Verify verdict.json exposure metrics
    verdict_file = run_dir / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    
    # Compute exposure from aggregated sums (branches only, not SUSP or TOTAL)
    all_branches = set(cobol_subtotals.keys()) | set(java_subtotals.keys())
    differences = []
    suspense_difference = None
    
    for branch in all_branches:
        if branch == "SUSP":
            cobol_val = cobol_subtotals.get(branch, Decimal(0))
            java_val = java_subtotals.get(branch, Decimal(0))
            suspense_difference = abs(cobol_val - java_val)
            continue
        
        cobol_val = cobol_subtotals.get(branch, Decimal(0))
        java_val = java_subtotals.get(branch, Decimal(0))
        diff = abs(cobol_val - java_val)
        if diff > 0:
            differences.append(diff)
    
    computed_sum = sum(differences) if differences else Decimal(0)
    computed_max = max(differences) if differences else Decimal(0)
    
    verdict_sum = Decimal(verdict["exposure_sum"])
    verdict_max = Decimal(verdict["exposure_max"])
    
    assert computed_sum == verdict_sum, f"Exposure sum {computed_sum} != {verdict_sum}"
    assert computed_max == verdict_max, f"Exposure max {computed_max} != {verdict_max}"
    assert str(suspense_difference) == verdict.get("suspense_difference"), f"Suspense difference {suspense_difference} != {verdict.get('suspense_difference')}"



def test_ui_branch_numeric_sort(t1_faulty_run, monkeypatch):
    """Test UI sorts branches numerically by absolute difference, not lexicographically."""
    from decimal import Decimal
    from fastapi.testclient import TestClient
    import re
    
    run_id, tmp_path = t1_faulty_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    from coroner.ui.app import app
    client = TestClient(app)
    
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    assert "Show all branches" in html, "Show all branches section not found"
    
    details_start = html.find("<details")
    assert details_start >= 0, "details element not found"
    details_end = html.find("</details>", details_start)
    assert details_end >= 0, "details close tag not found"
    details_section = html[details_start:details_end]
    
    row_pattern = r'<tr[^>]*>.*?</tr>'
    rows = re.findall(row_pattern, details_section, re.DOTALL)
    
    data_rows = [r for r in rows if '<th' not in r and r.strip()]
    
    absolute_diffs = []
    for row in data_rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) >= 4:
            abs_diff_text = cells[3].strip()
            abs_diff_text = re.sub(r'<[^>]+>', '', abs_diff_text).strip()
            if abs_diff_text:
                absolute_diffs.append(Decimal(abs_diff_text))
    
    assert len(absolute_diffs) >= 2, f"Expected at least 2 branch rows, got {len(absolute_diffs)}"
    
    for i in range(len(absolute_diffs) - 1):
        assert absolute_diffs[i] >= absolute_diffs[i + 1], f"Row {i} value {absolute_diffs[i]} < row {i+1} value {absolute_diffs[i + 1]}: not descending numeric order"
    
    string_sort = sorted([str(d) for d in absolute_diffs])
    numeric_sort = [str(d) for d in sorted(absolute_diffs, reverse=True)]
    
    if string_sort != numeric_sort:
        assert [str(d) for d in absolute_diffs] == numeric_sort, "Order differs from numeric sort when string sort differs"
    else:
        digit_counts = [len(str(d).replace('.', '').replace('-', '')) for d in absolute_diffs]
        assert len(set(digit_counts)) > 1, "Test is meaningful: values have different digit counts"
