"""Tests for multi-row minimal case reduction (trap T1)."""

import csv
from pathlib import Path

import pytest

from coroner.cli import run_verify
from coroner.diag.minimal import reduce_multirow_case
from coroner.parse.schema import load_schema


@pytest.fixture
def t1_paths():
    """Paths for T1 trap."""
    base = Path("samples/traps/T1-ebcdic-match-merge")
    return {
        "cobol": str(base / "MATCH-MERGE.cob"),
        "copybooks": str(base / "copybooks"),
        "java_faulty": str(base / "java" / "faulty" / "MatchMerge.java"),
        "java_correct": str(base / "java" / "correct" / "MatchMerge.java"),
        "schema": str(base / "schema.json")
    }


def test_reduce_multirow_case_real(t1_paths, tmp_path):
    """Test multi-row minimal case reducer on real T1 divergent case.
    
    Uses a small faulty T1 run (200 cases, seed 42), picks a divergent case,
    reduces it, and asserts the result diverges and is 1-minimal.
    """
    # Run a small T1 verification to get a divergent case
    verdict, run_dir = run_verify(
        t1_paths["cobol"],
        t1_paths["java_faulty"],
        t1_paths["schema"],
        t1_paths["copybooks"],
        num_cases=200,
        seed=42,
        base_dir=str(tmp_path)
    )
    
    # Should be ZOMBIE
    assert verdict.status == "ZOMBIE"
    assert verdict.cases_divergent > 0
    
    # Read failure report to get original_case_rows
    failure_path = Path(run_dir) / "failure_report.json"
    assert failure_path.exists(), "failure_report.json must exist for ZOMBIE"
    
    import json
    with open(failure_path) as f:
        failure_data = json.load(f)
    
    assert "original_case_rows" in failure_data
    assert "minimal_case_rows" in failure_data
    original_rows = failure_data["original_case_rows"]
    minimal_rows = failure_data["minimal_case_rows"]
    
    # The reducer should have produced a minimal subset
    assert len(minimal_rows) > 0
    assert len(minimal_rows) <= len(original_rows)
    
    # Read schema
    schema = load_schema(t1_paths["schema"])
    
    # Test that the minimal_rows actually diverge
    # Write them to a test CSV
    test_input = tmp_path / "test_minimal.csv"
    with open(test_input, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[col.name for col in schema.input_columns])
        writer.writeheader()
        for row in minimal_rows:
            writer.writerow(row)
    
    # Re-run verification on just these rows
    from coroner.run import compile_cobol, compile_java, run_cobol, run_java
    from coroner.compare import compare_outputs
    
    # Compile binaries
    cobol_binary = tmp_path / "test_cobol"
    cobc_flags = schema.cobc_flags or []
    compile_cobol(t1_paths["cobol"], t1_paths["copybooks"], str(cobol_binary), cobc_flags, str(tmp_path))
    
    java_classpath = tmp_path / "test_java"
    java_classpath.mkdir(exist_ok=True)
    compile_java(t1_paths["java_faulty"], str(java_classpath), str(tmp_path))
    java_class = Path(t1_paths["java_faulty"]).stem
    
    # Run both
    cobol_output = tmp_path / "cobol_out.csv"
    java_output = tmp_path / "java_out.csv"
    
    cobol_result = run_cobol(str(cobol_binary), str(test_input), str(cobol_output))
    java_result = run_java(java_class, str(java_classpath), str(test_input), str(java_output))
    
    # Compare
    comparison = compare_outputs(
        str(cobol_output),
        str(java_output),
        schema,
        cobol_result.return_code,
        java_result.return_code
    )
    
    # The minimal case must diverge
    assert comparison.total_divergent > 0, "Minimal case must diverge"
    
    # Test 1-minimality: removing any single row should make it non-divergent
    for i in range(len(minimal_rows)):
        candidate = minimal_rows[:i] + minimal_rows[i+1:]
        
        if not candidate:
            # Cannot test removing the last row
            continue
        
        # Write candidate
        candidate_input = tmp_path / f"candidate_{i}.csv"
        with open(candidate_input, 'w', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[col.name for col in schema.input_columns])
            writer.writeheader()
            for row in candidate:
                writer.writerow(row)
        
        # Re-run
        candidate_cobol_out = tmp_path / f"candidate_cobol_{i}.csv"
        candidate_java_out = tmp_path / f"candidate_java_{i}.csv"
        
        cobol_result = run_cobol(str(cobol_binary), str(candidate_input), str(candidate_cobol_out))
        java_result = run_java(java_class, str(java_classpath), str(candidate_input), str(candidate_java_out))
        
        # Compare
        comparison = compare_outputs(
            str(candidate_cobol_out),
            str(candidate_java_out),
            schema,
            cobol_result.return_code,
            java_result.return_code
        )
        
        # Removing this row should make it non-divergent (1-minimality)
        # If minimal has only 1 row, this test is vacuous
        if len(minimal_rows) > 1:
            assert comparison.total_divergent == 0, f"Removing row {i} should make it non-divergent (1-minimality)"


def test_reduce_multirow_case_deterministic(t1_paths, tmp_path):
    """Test that the reducer is deterministic: same result twice."""
    # Run a small T1 verification
    verdict, run_dir = run_verify(
        t1_paths["cobol"],
        t1_paths["java_faulty"],
        t1_paths["schema"],
        t1_paths["copybooks"],
        num_cases=200,
        seed=42,
        base_dir=str(tmp_path)
    )
    
    assert verdict.status == "ZOMBIE"
    
    # Read failure report
    failure_path = Path(run_dir) / "failure_report.json"
    import json
    with open(failure_path) as f:
        failure_data = json.load(f)
    
    original_rows = failure_data["original_case_rows"]
    minimal_rows_1 = failure_data["minimal_case_rows"]
    
    # Run the reducer again on the same input
    schema = load_schema(t1_paths["schema"])
    
    # Need to get the binaries from the run directory
    # The binaries are in build/<run_id>/
    run_id = Path(run_dir).name
    build_dir = tmp_path / "build" / run_id
    cobol_binary = str(build_dir / "MATCH-MERGE")
    java_classpath = str(build_dir / "java")
    
    minimal_rows_2 = reduce_multirow_case(
        t1_paths["cobol"],
        t1_paths["copybooks"],
        t1_paths["java_faulty"],
        schema,
        original_rows,
        str(tmp_path),
        cobol_binary=cobol_binary,
        java_classpath=java_classpath
    )
    
    # Should be identical
    assert minimal_rows_1 == minimal_rows_2, "Reducer must be deterministic"


def test_reduce_multirow_case_correct_port_nondivergent(t1_paths, tmp_path):
    """Test that the reducer raises on non-divergent input (correct port)."""
    # Run T1 with correct Java
    verdict, run_dir = run_verify(
        t1_paths["cobol"],
        t1_paths["java_correct"],
        t1_paths["schema"],
        t1_paths["copybooks"],
        num_cases=200,
        seed=42,
        base_dir=str(tmp_path)
    )
    
    # Should be ALIVE
    assert verdict.status == "ALIVE"
    assert verdict.cases_divergent == 0
    
    # No failure report for ALIVE
    failure_path = Path(run_dir) / "failure_report.json"
    assert not failure_path.exists(), "ALIVE run should have no failure_report.json"
    
    # If we try to reduce a case from the generated_cases, it should not diverge
    # and the reducer should raise
    cases_csv = Path(run_dir) / "generated_cases.csv"
    assert cases_csv.exists()
    
    # Read a case
    with open(cases_csv) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        # Group by CASE-ID to get one multi-row case
        from itertools import groupby
        rows.sort(key=lambda r: r['CASE-ID'])
        groups = {k: list(v) for k, v in groupby(rows, key=lambda r: r['CASE-ID'])}
        first_case = list(groups.values())[0]
    
    # Load schema
    schema = load_schema(t1_paths["schema"])
    
    # Import compile functions
    from coroner.run import compile_cobol, compile_java
    
    # Compile binaries
    cobol_binary = tmp_path / "test_cobol_correct"
    cobc_flags = schema.cobc_flags or []
    compile_cobol(t1_paths["cobol"], t1_paths["copybooks"], str(cobol_binary), cobc_flags, str(tmp_path))
    
    java_classpath = tmp_path / "test_java_correct"
    java_classpath.mkdir(exist_ok=True)
    compile_java(t1_paths["java_correct"], str(java_classpath), str(tmp_path))
    
    # Try to reduce (should raise because the correct port does not diverge)
    with pytest.raises(ValueError, match="final subset does not diverge"):
        reduce_multirow_case(
            t1_paths["cobol"],
            t1_paths["copybooks"],
            t1_paths["java_correct"],
            schema,
            first_case,
            str(tmp_path),
            cobol_binary=str(cobol_binary),
            java_classpath=str(java_classpath)
        )


def test_t1_card_filters_to_balance_line_paragraph(t1_paths, tmp_path):
    """Test that T1 card lists only lines from BALANCE-LINE paragraph.
    
    For group_key schemas, the card must list only executed lines from paragraphs
    that accumulate subtotals (BALANCE-LINE for T1). This test verifies:
    - Every listed line is within BALANCE-LINE (lines 201-219 per the source)
    - Line 204 (the comparison IF) is listed
    """
    # Run a small T1 verification with faulty port
    verdict, run_dir = run_verify(
        t1_paths["cobol"],
        t1_paths["java_faulty"],
        t1_paths["schema"],
        t1_paths["copybooks"],
        num_cases=200,
        seed=42,
        base_dir=str(tmp_path)
    )
    
    assert verdict.status == "ZOMBIE"
    
    # Read the card
    card_path = Path(run_dir) / "card.txt"
    assert card_path.exists(), "card.txt must exist for ZOMBIE"
    
    with open(card_path) as f:
        card_text = f.read()
    
    # Extract COBOL lines from the card
    # The card has a line starting with "COBOL lines involved: "
    # followed by statements like "file:line text"
    assert "COBOL lines involved:" in card_text
    
    lines_section = card_text.split("COBOL lines involved:", 1)[1].split("\n")[0]
    
    # Parse line numbers from the format "file:line statement; ..."
    import re
    line_refs = re.findall(r':(\d+)\s', lines_section)
    line_numbers = [int(n) for n in line_refs]
    
    # BALANCE-LINE paragraph is lines 201-219 per the operator's ground truth
    # (from the trace "Paragraph: BALANCE-LINE" section)
    # Executed lines are 201-210 and 218-219
    balance_line_range = set(range(201, 211)) | {218, 219}
    
    # Every listed line must be in BALANCE-LINE
    for line_num in line_numbers:
        assert line_num in balance_line_range, \
            f"Line {line_num} is not in BALANCE-LINE paragraph (201-210, 218-219)"
    
    # Line 204 (the comparison IF) must be listed
    assert 204 in line_numbers, \
        "Line 204 (IF TABLE-CODE(TABLE-INDEX) < TXN-BRANCH) must be listed"
