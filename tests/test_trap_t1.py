"""Tests for Trap 1: EBCDIC vs ASCII collating order."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


TRAP_DIR = Path("samples/traps/T1-ebcdic-match-merge")
FIXTURES = TRAP_DIR / "fixtures"
BUILD_DIR = Path("build/traps/T1")


@pytest.fixture(scope="module", autouse=True)
def build_programs():
    """Build COBOL and Java programs."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Compile COBOL
    cobol_bin = BUILD_DIR / "MATCH-MERGE"
    result = subprocess.run(
        ["cobc", "-x", "-Wall", str(TRAP_DIR / "MATCH-MERGE.cob"), "-o", str(cobol_bin)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"COBOL compilation failed: {result.stderr}")
    
    # Compile correct Java
    result = subprocess.run(
        ["javac", "-Xlint:all", "-d", str(BUILD_DIR / "correct"), 
         str(TRAP_DIR / "java/correct/MatchMerge.java")],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Correct Java compilation failed: {result.stderr}")
    
    # Compile faulty Java
    result = subprocess.run(
        ["javac", "-Xlint:all", "-d", str(BUILD_DIR / "faulty"), 
         str(TRAP_DIR / "java/faulty/MatchMerge.java")],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Faulty Java compilation failed: {result.stderr}")


def run_cobol(input_file: Path, output_file: Path) -> int:
    """Run COBOL program and return exit code."""
    env = os.environ.copy()
    env["INPUT_FILE"] = str(input_file)
    env["OUTPUT_FILE"] = str(output_file)
    
    result = subprocess.run(
        [str(BUILD_DIR / "MATCH-MERGE")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.returncode


def run_java(variant: str, input_file: Path, output_file: Path) -> int:
    """Run Java program and return exit code."""
    env = os.environ.copy()
    env["INPUT_FILE"] = str(input_file)
    env["OUTPUT_FILE"] = str(output_file)
    
    result = subprocess.run(
        ["java", "-cp", str(BUILD_DIR / variant), "MatchMerge"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.returncode


def test_cobol_compiles_and_runs():
    """COBOL program compiles and runs successfully on fixture."""
    input_file = FIXTURES / "branch-ordering.csv"
    output_file = BUILD_DIR / "cobol-output.csv"
    
    rc = run_cobol(input_file, output_file)
    assert rc == 0, f"COBOL exited with {rc}"
    
    # Check output exists and has data rows
    assert output_file.exists()
    content = output_file.read_text()
    lines = content.strip().split('\n')
    assert len(lines) > 1, "Output has no data rows"
    assert lines[0] == "CASE-ID,BRANCH,SUBTOTAL"


def test_expected_file_equals_cobol_output():
    """Committed expected file equals COBOL output."""
    input_file = FIXTURES / "branch-ordering.csv"
    output_file = BUILD_DIR / "cobol-fresh.csv"
    expected_file = FIXTURES / "branch-ordering-expected.csv"
    
    rc = run_cobol(input_file, output_file)
    assert rc == 0
    
    cobol_output = output_file.read_text()
    expected_output = expected_file.read_text()
    
    assert cobol_output == expected_output, "Expected file diverges from COBOL output"


def test_correct_java_equals_cobol():
    """Correct Java output equals COBOL output byte-for-byte."""
    input_file = FIXTURES / "branch-ordering.csv"
    cobol_output = BUILD_DIR / "cobol-output.csv"
    java_output = BUILD_DIR / "java-correct-output.csv"
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java("correct", input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0
    
    cobol_content = cobol_output.read_text()
    java_content = java_output.read_text()
    
    assert cobol_content == java_content, "Correct Java diverges from COBOL"


def test_faulty_java_diverges_from_cobol():
    """Faulty Java subtotals differ but TOTAL rows match."""
    input_file = FIXTURES / "branch-ordering.csv"
    cobol_output = BUILD_DIR / "cobol-faulty.csv"
    java_output = BUILD_DIR / "java-faulty-output.csv"
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java("faulty", input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0
    
    cobol_lines = cobol_output.read_text().strip().split('\n')
    java_lines = java_output.read_text().strip().split('\n')
    
    # Headers must match
    assert cobol_lines[0] == java_lines[0]
    
    # TOTAL rows must match
    cobol_totals = [line for line in cobol_lines if ',TOTAL,' in line]
    java_totals = [line for line in java_lines if ',TOTAL,' in line]
    assert cobol_totals == java_totals, "TOTAL rows diverged"
    
    # At least one subtotal must differ
    cobol_subtotals = [line for line in cobol_lines if ',TOTAL,' not in line and line != cobol_lines[0]]
    java_subtotals = [line for line in java_lines if ',TOTAL,' not in line and line != java_lines[0]]
    
    assert cobol_subtotals != java_subtotals, "No subtotal divergence found"


@pytest.mark.slow
def test_coroner_correct_java_alive(tmp_path):
    """Coroner verify with correct Java returns ALIVE."""
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "verify",
         "--cobol", str(TRAP_DIR / "MATCH-MERGE.cob"),
         "--copybooks", str(TRAP_DIR / "copybooks"),
         "--java", str(TRAP_DIR / "java/correct/MatchMerge.java"),
         "--schema", str(TRAP_DIR / "schema.json"),
         "--cases", "200",
         "--seed", "42"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 0, f"Coroner exited {result.returncode}: {result.stderr}"
    assert "ALIVE" in result.stdout
    assert "return code differs" not in result.stdout


@pytest.mark.slow
def test_coroner_faulty_java_zombie(tmp_path):
    """Coroner verify with faulty Java returns ZOMBIE with matching grand totals."""
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "verify",
         "--cobol", str(TRAP_DIR / "MATCH-MERGE.cob"),
         "--copybooks", str(TRAP_DIR / "copybooks"),
         "--java", str(TRAP_DIR / "java/faulty/MatchMerge.java"),
         "--schema", str(TRAP_DIR / "schema.json"),
         "--cases", "200",
         "--seed", "42"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 1, f"Expected ZOMBIE (exit 1), got {result.returncode}"
    assert "ZOMBIE" in result.stdout
    assert "grand total matches: yes" in result.stdout.lower() or "FAIL: business behavior diverged" in result.stdout
    assert "return code differs" not in result.stdout


@pytest.mark.slow
def test_exposure_independent_verification():
    """
    Independent verification: run COBOL and Java directly on a real run,
    aggregate per branch with trimmed codes, verify against verdict.json.
    """
    import json
    import re
    import sys
    from decimal import Decimal
    from collections import defaultdict
    
    # Create a run with the T1 faulty port at 2000 cases, seed 42
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", str(TRAP_DIR / "MATCH-MERGE.cob"),
            "--copybooks", str(TRAP_DIR / "copybooks"),
            "--java", str(TRAP_DIR / "java/faulty/MatchMerge.java"),
            "--schema", str(TRAP_DIR / "schema.json"),
            "--cases", "2000",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 1, f"Expected ZOMBIE (exit 1), got {result.returncode}"
    
    # Parse run_id from output
    match = re.search(r'Run: runs/([a-f0-9]+)', result.stdout)
    assert match, f"Could not find 'Run: runs/<id>' in output: {result.stdout}"
    run_id = match.group(1)
    
    # Use exactly that run directory
    run_dir = Path("runs") / run_id
    assert run_dir.exists(), f"Run directory {run_dir} not found"
    
    # Read verdict
    with open(run_dir / "verdict.json") as f:
        verdict = json.load(f)
    
    # Read cases file
    cases_file = run_dir / "generated_cases.csv"
    
    # Run COBOL
    cobol_output = BUILD_DIR / "cobol_independent.csv"
    env = os.environ.copy()
    env["INPUT_FILE"] = str(cases_file)
    env["OUTPUT_FILE"] = str(cobol_output)
    
    result = subprocess.run(
        [str(BUILD_DIR / "MATCH-MERGE")],
        env=env,
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0, f"COBOL failed: {result.stderr}"
    
    # Run faulty Java
    java_output = BUILD_DIR / "java_independent.csv"
    env["OUTPUT_FILE"] = str(java_output)
    
    result = subprocess.run(
        ["java", "-cp", str(BUILD_DIR / "faulty"), "MatchMerge"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0, f"Java failed: {result.stderr}"
    
    # Parse outputs and aggregate by branch
    cobol_lines = cobol_output.read_text().strip().split('\n')
    java_lines = java_output.read_text().strip().split('\n')
    
    # Parse headers
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
        branch = parts[branch_idx].rstrip()  # Trim trailing spaces
        subtotal = Decimal(parts[subtotal_idx])
        
        if branch == "TOTAL":
            cobol_grand_total += subtotal
        else:
            cobol_subtotals[branch] += subtotal
    
    for line in java_lines[1:]:
        parts = line.split(',')
        branch = parts[branch_idx].rstrip()  # Trim trailing spaces
        subtotal = Decimal(parts[subtotal_idx])
        
        if branch == "TOTAL":
            java_grand_total += subtotal
        else:
            java_subtotals[branch] += subtotal
    
    # Compute exposure metrics
    all_branches = set(cobol_subtotals.keys()) | set(java_subtotals.keys())
    differences = []
    suspense_difference = None
    
    for branch in all_branches:
        cobol_val = cobol_subtotals.get(branch, Decimal(0))
        java_val = java_subtotals.get(branch, Decimal(0))
        diff = abs(cobol_val - java_val)
        
        if branch == "SUSP":
            suspense_difference = diff
            continue
        
        if diff > 0:
            differences.append(diff)
    
    exposure_sum = sum(differences) if differences else Decimal(0)
    exposure_max = max(differences) if differences else Decimal(0)
    affected_branches = len(differences)
    grand_total_matches = (cobol_grand_total == java_grand_total)
    
    # Verify against verdict.json
    assert str(exposure_sum) == verdict["exposure_sum"], f"Sum mismatch: computed {exposure_sum}, verdict {verdict['exposure_sum']}"
    assert str(exposure_max) == verdict["exposure_max"], f"Max mismatch: computed {exposure_max}, verdict {verdict['exposure_max']}"
    assert affected_branches == verdict["affected_branches"], f"Branches mismatch: computed {affected_branches}, verdict {verdict['affected_branches']}"
    assert str(suspense_difference) == verdict["suspense_difference"], f"Suspense mismatch: computed {suspense_difference}, verdict {verdict['suspense_difference']}"
    assert grand_total_matches == verdict["grand_total_matches"], f"Grand total match mismatch"



def test_t1_amount_range_and_negative_share():
    """
    T1 generator with amount_range and negative_share produces realistic amounts.
    
    Verifies:
    - Every AMOUNT magnitude is within [0.01, 9999.99] with scale 2
    - Negative share is between 3% and 7% (target 5%)
    - Batch sizes are between 5 and 25 rows per case
    """
    import csv
    from decimal import Decimal
    from coroner.gen import generate_cases
    from coroner.parse.schema import load_schema
    
    # Load T1 schema (with amount_range and negative_share)
    schema = load_schema(str(TRAP_DIR / "schema.json"))
    
    # Generate 2000 cases with seed 42
    cases_file = generate_cases(
        schema=schema,
        cobol_structure={},
        seed=42,
        num_cases=2000,
        tie_share=0.0,
        base_dir="build"
    )
    
    # Read generated cases
    amounts = []
    case_ids = []
    
    with open(cases_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            case_ids.append(row['CASE-ID'])
            amounts.append(Decimal(row['AMOUNT']))
    
    # Check amount_range: every magnitude within [0.01, 9999.99]
    min_val = Decimal("0.01")
    max_val = Decimal("9999.99")
    
    for amount in amounts:
        magnitude = abs(amount)
        assert min_val <= magnitude <= max_val, \
            f"Amount {amount} magnitude {magnitude} outside range [{min_val}, {max_val}]"
    
    # Check negative_share: between 3% and 7% (target 5%)
    negative_count = sum(1 for a in amounts if a < 0)
    negative_share = negative_count / len(amounts)
    
    print(f"T1 generation: negative share = {negative_share:.4f} ({negative_count}/{len(amounts)})")
    
    assert 0.03 <= negative_share <= 0.07, \
        f"Negative share {negative_share:.4f} outside [0.03, 0.07]"
    
    # Check batch sizes: between 5 and 25 per case
    unique_case_ids = list(dict.fromkeys(case_ids))  # Preserve order
    
    for case_id in unique_case_ids:
        batch_size = case_ids.count(case_id)
        assert 5 <= batch_size <= 25, \
            f"Case {case_id} has {batch_size} rows, expected [5, 25]"
    
    print(f"T1 generation: {len(unique_case_ids)} cases with batch sizes 5-25")
