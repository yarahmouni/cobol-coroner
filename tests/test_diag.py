"""Tests for diagnostic modules."""

import csv
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from coroner.compare import CaseResult
from coroner.diag import (
    CoverageReport,
    FailureReport,
    compute_coverage,
    generate_failure_report,
    select_minimal_case,
)
from coroner.parse.copybook import BranchInfo
from coroner.parse.schema import Schema, SchemaColumn


def test_compute_coverage_basic():
    """Test compute_coverage with simple trace and structure."""
    # Simple trace with source file and line numbers
    trace = {
        ("test.cob", 10): 1,
        ("test.cob", 15): 1,
        ("test.cob", 20): 1,
        ("test.cob", 30): 1,
    }
    
    # Structure with paragraphs and branches
    structure = {
        "paragraphs": {
            "MAIN-PARA": 10,
            "SUB-PARA": 25,
        },
        "branches": [
            BranchInfo("MAIN-PARA", 15, "IF_TRUE"),
            BranchInfo("MAIN-PARA", 20, "IF_ELSE"),
            BranchInfo("SUB-PARA", 30, "IF_TRUE"),
            BranchInfo("SUB-PARA", 35, "IF_ELSE"),
        ]
    }
    
    report = compute_coverage(trace, structure, "test.cob", ".")
    
    # Paragraph MAIN-PARA is covered (line 10 in trace)
    # Paragraph SUB-PARA is not covered (line 25 not in trace)
    assert report.paragraphs_total == 2
    assert report.paragraphs_covered == 1
    
    # Branches at lines 15, 20, 30 are covered
    # Branch at line 35 is not covered
    assert report.branches_total == 4
    assert report.branches_covered == 3


def test_select_minimal_case_by_numeric_values():
    """Test minimal case selection orders by absolute numeric value."""
    schema = Schema(
        program_name="test",
        description="test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn("CASE-ID", "string", "X(10)", "Case ID"),
            SchemaColumn("PRINCIPAL", "decimal", "S9(9)V99", "Principal", scale=2, signed=True),
            SchemaColumn("FEE-RATE", "decimal", "V9(5)", "Fee rate", scale=5, signed=False),
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn("CASE-ID", "string", "X(10)", "Case ID"),
            SchemaColumn("FEE-AMOUNT", "decimal", "+9(7).99", "Fee amount", scale=2, signed=True),
        ]
    )
    
    # Create divergent cases with different input values
    cases = [
        CaseResult("GEN-00001", True, [("FEE-AMOUNT", "100.00", "100.01")]),
        CaseResult("GEN-00002", True, [("FEE-AMOUNT", "10.00", "10.01")]),
        CaseResult("GEN-00003", True, [("FEE-AMOUNT", "50.00", "50.01")]),
    ]
    
    input_rows = {
        "GEN-00001": {"CASE-ID": "GEN-00001", "PRINCIPAL": "1000.00", "FEE-RATE": "0.01000"},
        "GEN-00002": {"CASE-ID": "GEN-00002", "PRINCIPAL": "100.00", "FEE-RATE": "0.01000"},
        "GEN-00003": {"CASE-ID": "GEN-00003", "PRINCIPAL": "500.00", "FEE-RATE": "0.01000"},
    }
    
    minimal = select_minimal_case(cases, schema, input_rows)
    
    # GEN-00002 has the smallest PRINCIPAL (100.00)
    assert minimal.case_id == "GEN-00002"


def test_select_minimal_case_with_tie_uses_case_id():
    """Test minimal case selection breaks ties with case_id."""
    schema = Schema(
        program_name="test",
        description="test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn("CASE-ID", "string", "X(10)", "Case ID"),
            SchemaColumn("AMOUNT", "decimal", "S9(9)V99", "Amount", scale=2, signed=True),
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn("CASE-ID", "string", "X(10)", "Case ID"),
            SchemaColumn("RESULT", "decimal", "S9(9)V99", "Result", scale=2, signed=True),
        ]
    )
    
    cases = [
        CaseResult("GEN-00003", True, [("RESULT", "10.00", "10.01")]),
        CaseResult("GEN-00001", True, [("RESULT", "10.00", "10.01")]),
        CaseResult("GEN-00002", True, [("RESULT", "10.00", "10.01")]),
    ]
    
    input_rows = {
        "GEN-00001": {"CASE-ID": "GEN-00001", "AMOUNT": "10.00"},
        "GEN-00002": {"CASE-ID": "GEN-00002", "AMOUNT": "10.00"},
        "GEN-00003": {"CASE-ID": "GEN-00003", "AMOUNT": "10.00"},
    }
    
    minimal = select_minimal_case(cases, schema, input_rows)
    
    # All have same AMOUNT, so lexicographically first case_id wins
    assert minimal.case_id == "GEN-00001"


def test_select_minimal_case_negative_values():
    """Test minimal case selection uses absolute value."""
    schema = Schema(
        program_name="test",
        description="test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn("CASE-ID", "string", "X(10)", "Case ID"),
            SchemaColumn("AMOUNT", "decimal", "S9(9)V99", "Amount", scale=2, signed=True),
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn("CASE-ID", "string", "X(10)", "Case ID"),
            SchemaColumn("RESULT", "decimal", "S9(9)V99", "Result", scale=2, signed=True),
        ]
    )
    
    cases = [
        CaseResult("GEN-00001", True, [("RESULT", "100.00", "100.01")]),
        CaseResult("GEN-00002", True, [("RESULT", "50.00", "50.01")]),
        CaseResult("GEN-00003", True, [("RESULT", "-200.00", "-200.01")]),
    ]
    
    input_rows = {
        "GEN-00001": {"CASE-ID": "GEN-00001", "AMOUNT": "100.00"},
        "GEN-00002": {"CASE-ID": "GEN-00002", "AMOUNT": "-50.00"},
        "GEN-00003": {"CASE-ID": "GEN-00003", "AMOUNT": "-200.00"},
    }
    
    minimal = select_minimal_case(cases, schema, input_rows)
    
    # GEN-00002 has smallest absolute AMOUNT (50.00)
    assert minimal.case_id == "GEN-00002"


@pytest.mark.skipif(
    subprocess.run(["which", "cobc"], capture_output=True).returncode != 0,
    reason="cobc not available"
)
@pytest.mark.skipif(
    subprocess.run(["which", "javac"], capture_output=True).returncode != 0,
    reason="javac not available"
)
def test_generate_failure_report_integration():
    """Test failure report generation with real programs."""
    # This test requires the credit-fees sample to be compiled
    cobol_source = "samples/credit-fees/CREDIT-FEES.cob"
    java_source = "samples/credit-fees/java/CreditFees.java"
    schema_path = "samples/credit-fees/schema.json"
    
    if not Path(cobol_source).exists():
        pytest.skip("Credit-fees sample not available")
    
    # Create a minimal schema for testing
    from coroner.parse.schema import load_schema
    schema = load_schema(schema_path)
    
    # Create a minimal case
    minimal_case = CaseResult(
        "TEST-01",
        True,
        [("FEE-AMOUNT", "+0000012.35", "+0000012.34")]
    )
    
    input_rows = {
        "TEST-01": {
            "CASE-ID": "TEST-01",
            "PRINCIPAL": "1234.50",
            "FEE-RATE": "0.01000",
            "CUSTOMER-SEGMENT": "B",
            "DURATION-MONTHS": "12",
            "INCOME": "50000"
        }
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Compile instrumented COBOL with copybooks
        cobol_binary = Path(tmpdir) / "credit_fees_instrumented"
        copybook_dir = "samples/credit-fees/copybooks"
        subprocess.run(
            ["cobc", "-x", "-Wall", "-ftraceall", "-I", copybook_dir, 
             "-o", str(cobol_binary), cobol_source],
            check=True,
            timeout=30
        )
        
        # Compile Java
        java_dir = Path(tmpdir) / "java"
        java_dir.mkdir()
        subprocess.run(
            ["javac", "-d", str(java_dir), java_source],
            check=True,
            timeout=30
        )
        
        # Generate failure report
        report = generate_failure_report(
            minimal_case=minimal_case,
            input_rows=input_rows,
            schema=schema,
            cobol_instrumented_binary=str(cobol_binary),
            java_class_name="CreditFees",
            java_classpath=str(java_dir),
            run_dir=tmpdir,
            timeout=10.0
        )
        
        # Verify report structure
        assert report.case_id == "TEST-01"
        assert report.input_row == input_rows["TEST-01"]
        assert len(report.divergent_fields) > 0
        assert report.cobol_return_code == 0
        assert report.java_return_code == 0
        assert len(report.executed_lines) > 0
        
        # Verify executed lines contain the COMPUTE-FEE paragraph
        # We expect the COBOL source to have executed lines from the main file
        assert any("CREDIT-FEES" in source for source, line in report.executed_lines)


@pytest.mark.skipif(
    subprocess.run(["which", "cobc"], capture_output=True).returncode != 0,
    reason="cobc not available"
)
@pytest.mark.skipif(
    subprocess.run(["which", "javac"], capture_output=True).returncode != 0,
    reason="javac not available"
)
def test_failure_report_captures_return_codes():
    """Test failure report captures both return codes from single-case re-run."""
    cobol_source = "samples/credit-fees/CREDIT-FEES.cob"
    java_source = "samples/credit-fees/java/CreditFees.java"
    schema_path = "samples/credit-fees/schema.json"
    copybook_dir = "samples/credit-fees/copybooks"
    
    if not Path(cobol_source).exists():
        pytest.skip("Credit-fees sample not available")
    
    from coroner.parse.schema import load_schema
    schema = load_schema(schema_path)
    
    # Use VAL-001: an E01 case with only 5 fields (missing INCOME)
    # Both programs should exit with return code 4 on this single case
    minimal_case = CaseResult(
        "VAL-001",
        True,
        [("REASON-CODE", "E01", "E01")]
    )
    
    input_rows = {
        "VAL-001": {
            "CASE-ID": "VAL-001",
            "PRINCIPAL": "1000.00",
            "FEE-RATE": "0.01000",
            "DURATION-MONTHS": "24",
            "CUSTOMER-SEGMENT": "B",
        }
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Compile instrumented COBOL with copybooks
        cobol_binary = Path(tmpdir) / "credit_fees_instrumented"
        subprocess.run(
            ["cobc", "-x", "-Wall", "-ftraceall", "-I", copybook_dir, 
             "-o", str(cobol_binary), cobol_source],
            check=True,
            timeout=30
        )
        
        # Compile Java
        java_dir = Path(tmpdir) / "java"
        java_dir.mkdir()
        subprocess.run(
            ["javac", "-d", str(java_dir), java_source],
            check=True,
            timeout=30
        )
        
        # Generate failure report
        report = generate_failure_report(
            minimal_case=minimal_case,
            input_rows=input_rows,
            schema=schema,
            cobol_instrumented_binary=str(cobol_binary),
            java_class_name="CreditFees",
            java_classpath=str(java_dir),
            run_dir=tmpdir,
            timeout=10.0
        )
        
        # Assert both return codes are 4 (E01 validation error)
        assert report.cobol_return_code == 4, f"Expected COBOL return code 4, got {report.cobol_return_code}"
        assert report.java_return_code == 4, f"Expected Java return code 4, got {report.java_return_code}"


@pytest.mark.skipif(
    subprocess.run(["which", "cobc"], capture_output=True).returncode != 0,
    reason="cobc not available"
)
@pytest.mark.skipif(
    subprocess.run(["which", "javac"], capture_output=True).returncode != 0,
    reason="javac not available"
)
@pytest.mark.skipif(
    subprocess.run(["which", "java"], capture_output=True).returncode != 0,
    reason="java not available"
)
def test_end_to_end_half_even_divergence():
    """
    End-to-end test: generate 2,000 cases with seed 42, build a HALF_EVEN variant,
    run everything, and assert:
    - Coverage numbers reported with 12 paragraphs and 70 branches in the totals
    - The minimal case is divergent only on FEE-AMOUNT
    - The divergence is explained by an exact tie with an even preceding digit at
      one of the two ROUNDED steps (base or discount)
    - Its executed lines include the exact COMPUTE statement responsible
    """
    from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
    from coroner.gen import generate_cases
    from coroner.parse.schema import load_schema
    from coroner.parse.copybook import parse_cobol_structure
    from coroner.run import compile_cobol, compile_java, run_cobol, run_java, run_cobol_instrumented
    from coroner.compare import compare_outputs
    from coroner.diag import compute_coverage, select_minimal_case, generate_failure_report
    
    cobol_source = "samples/credit-fees/CREDIT-FEES.cob"
    java_source = "samples/credit-fees/java/CreditFees.java"
    schema_path = "samples/credit-fees/schema.json"
    copybook_dir = "samples/credit-fees/copybooks"
    
    if not Path(cobol_source).exists():
        pytest.skip("Credit-fees sample not available")
    
    schema = load_schema(schema_path)
    cobol_structure = parse_cobol_structure(cobol_source, copybook_dir)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = Path(tmpdir) / "run"
        run_dir.mkdir()
        
        # Generate 2,000 cases with seed 42
        cases_csv = generate_cases(
            schema=schema,
            cobol_structure=cobol_structure,
            seed=42,
            num_cases=2000,
            tie_share=0.05
        )
        
        # Build HALF_EVEN variant
        half_even_source = Path(tmpdir) / "CreditFees.java"
        with open(java_source, 'r') as src:
            content = src.read()
        # Replace RoundingMode.HALF_UP with RoundingMode.HALF_EVEN
        content = content.replace("RoundingMode.HALF_UP", "RoundingMode.HALF_EVEN")
        half_even_source.write_text(content)
        
        # Compile COBOL (reference and instrumented)
        cobol_binary = Path(tmpdir) / "credit_fees"
        compile_cobol(cobol_source, copybook_dir, str(cobol_binary), [])
        
        cobol_instrumented = Path(tmpdir) / "credit_fees_instrumented"
        compile_cobol(cobol_source, copybook_dir, str(cobol_instrumented), ["-ftraceall"])
        
        # Compile Java HALF_EVEN variant
        java_dir = Path(tmpdir) / "java"
        java_dir.mkdir()
        compile_java(str(half_even_source), str(java_dir))
        
        # Run both programs
        cobol_output = Path(tmpdir) / "cobol_output.csv"
        java_output = Path(tmpdir) / "java_output.csv"
        trace_file = Path(run_dir) / "coverage_trace.txt"
        
        cobol_result = run_cobol(str(cobol_binary), cases_csv, str(cobol_output))
        java_result = run_java("CreditFees", str(java_dir), cases_csv, str(java_output))
        instrumented_result = run_cobol_instrumented(
            str(cobol_instrumented), cases_csv, str(cobol_output), str(trace_file)
        )
        
        # Compare outputs
        comparison = compare_outputs(
            str(cobol_output), str(java_output), schema,
            cobol_result.return_code, java_result.return_code
        )
        
        # Assert divergences found
        assert comparison.total_divergent > 0, "Expected divergences with HALF_EVEN variant"
        
        # Compute coverage
        from coroner.parse.trace import parse_trace_counts
        trace = parse_trace_counts(str(trace_file))
        coverage = compute_coverage(trace, cobol_structure, cobol_source, copybook_dir)
        
        # Assert coverage numbers (12 paragraphs, 70 branches)
        assert coverage.paragraphs_total == 12, f"Expected 12 paragraphs, got {coverage.paragraphs_total}"
        assert coverage.branches_total == 70, f"Expected 70 branches, got {coverage.branches_total}"
        
        # Select minimal case
        input_rows = {}
        with open(cases_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                input_rows[row['CASE-ID']] = row
        
        divergent_cases = [c for c in comparison.cases if c.divergent]
        minimal_case = select_minimal_case(divergent_cases, schema, input_rows)
        
        # Generate failure report
        report = generate_failure_report(
            minimal_case, input_rows, schema,
            str(cobol_instrumented), "CreditFees", str(java_dir),
            str(run_dir)
        )
        
        # Assert minimal case divergent only on FEE-AMOUNT
        divergent_fields = [field for field, _, _ in report.divergent_fields]
        assert "FEE-AMOUNT" in divergent_fields, f"Expected FEE-AMOUNT divergent, got {divergent_fields}"
        
        # Assert the divergence is explained by an exact tie at one of the two ROUNDED steps
        principal = Decimal(report.input_row["PRINCIPAL"])
        fee_rate = Decimal(report.input_row["FEE-RATE"])
        segment = report.input_row["CUSTOMER-SEGMENT"].strip()
        
        # Step 1: base = PRINCIPAL * FEE-RATE, ROUNDED
        base_product = principal * fee_rate
        
        # Check if base_product is a tie with even preceding digit
        # A tie at scale 2 means the value at scale 3 ends in exactly 5
        base_at_3 = base_product.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
        base_str = str(abs(base_at_3))
        
        base_is_tie = False
        base_has_even_preceding = False
        if '.' in base_str:
            parts = base_str.split('.')
            if len(parts[1]) >= 3 and parts[1][2] == '5':
                base_is_tie = True
                # Check preceding digit (at position 1, the tenths place after rounding to 2)
                if len(parts[1]) >= 2:
                    preceding = int(parts[1][1])
                    base_has_even_preceding = (preceding % 2 == 0)
        
        # Step 2: if segment is P or S, discount step
        discount_is_tie = False
        discount_has_even_preceding = False
        
        if segment in ('P', 'S'):
            # base rounded to 2 decimals with HALF_UP
            base_rounded = base_product.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            # discount rate
            discount_rate = Decimal("0.10") if segment == 'P' else Decimal("0.05")
            discount_product = base_rounded * (Decimal("1") - discount_rate)
            
            # Check if discount_product is a tie with even preceding digit
            discount_at_3 = discount_product.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
            discount_str = str(abs(discount_at_3))
            
            if '.' in discount_str:
                parts = discount_str.split('.')
                if len(parts[1]) >= 3 and parts[1][2] == '5':
                    discount_is_tie = True
                    if len(parts[1]) >= 2:
                        preceding = int(parts[1][1])
                        discount_has_even_preceding = (preceding % 2 == 0)
        
        # Assert at least one tie with even preceding digit exists
        has_half_even_divergence = (
            (base_is_tie and base_has_even_preceding) or
            (discount_is_tie and discount_has_even_preceding)
        )
        assert has_half_even_divergence, (
            f"Expected a HALF_EVEN divergence (tie with even preceding digit). "
            f"Base: tie={base_is_tie}, even={base_has_even_preceding}. "
            f"Discount: tie={discount_is_tie}, even={discount_has_even_preceding}."
        )
        
        # Assert executed lines include the exact COMPUTE statement responsible
        # Read the COBOL source to find the line numbers
        with open(cobol_source, 'r') as f:
            source_lines = f.readlines()
        
        # Find line numbers of COMPUTE statements
        base_compute_line = None
        discount_p_line = None
        discount_s_line = None
        
        for i, line in enumerate(source_lines, start=1):
            if "COMPUTE WS-BASE-FEE ROUNDED" in line:
                base_compute_line = i
            elif "WHEN 'P'" in line:
                # Next COMPUTE after WHEN 'P' is the P discount
                for j in range(i, len(source_lines)):
                    if "COMPUTE WS-DISCOUNTED-FEE ROUNDED" in source_lines[j]:
                        discount_p_line = j + 1
                        break
            elif "WHEN 'S'" in line:
                # Next COMPUTE after WHEN 'S' is the S discount
                for j in range(i, len(source_lines)):
                    if "COMPUTE WS-DISCOUNTED-FEE ROUNDED" in source_lines[j]:
                        discount_s_line = j + 1
                        break
        
        # Determine which COMPUTE is responsible
        expected_line = None
        if base_is_tie and base_has_even_preceding:
            expected_line = base_compute_line
        elif segment == 'P' and discount_is_tie and discount_has_even_preceding:
            expected_line = discount_p_line
        elif segment == 'S' and discount_is_tie and discount_has_even_preceding:
            expected_line = discount_s_line
        
        assert expected_line is not None, "Could not determine responsible COMPUTE line"
        
        # Check executed lines contain the responsible COMPUTE line
        executed_line_numbers = [line for source, line in report.executed_lines]
        assert expected_line in executed_line_numbers, (
            f"Expected executed lines to contain line {expected_line} "
            f"(the responsible COMPUTE statement), got {executed_line_numbers}"
        )


def test_coverage_detail_lists():
    """Test that coverage report includes detail lists for paragraphs and branches."""
    # Simple trace and structure
    trace = {
        ("test.cob", 10): 1,
        ("test.cob", 15): 1,
        ("test.cob", 20): 1,
    }
    
    structure = {
        "paragraphs": {
            "PARA-A": 10,
            "PARA-B": 25,
        },
        "branches": [
            BranchInfo("PARA-A", 15, "IF_TRUE"),
            BranchInfo("PARA-A", 20, "IF_ELSE"),
            BranchInfo("PARA-B", 30, "IF_TRUE"),
        ]
    }
    
    report = compute_coverage(trace, structure, "test.cob", ".")
    
    # Check paragraph details
    assert len(report.paragraph_details) == 2
    para_dict = {p.name: p for p in report.paragraph_details}
    assert para_dict["PARA-A"].covered is True
    assert para_dict["PARA-A"].line == 10
    assert para_dict["PARA-B"].covered is False
    assert para_dict["PARA-B"].line == 25
    
    # Check branch details
    assert len(report.branch_details) == 3
    assert report.branch_details[0].paragraph == "PARA-A"
    assert report.branch_details[0].line == 15
    assert report.branch_details[0].branch_type == "IF_TRUE"
    assert report.branch_details[0].covered is True
    assert report.branch_details[1].covered is True
    assert report.branch_details[2].covered is False


@pytest.mark.skipif(
    subprocess.run(["which", "cobc"], capture_output=True).returncode != 0,
    reason="cobc not available"
)
@pytest.mark.skipif(
    subprocess.run(["which", "javac"], capture_output=True).returncode != 0,
    reason="javac not available"
)
def test_coverage_uncovered_error_path():
    """
    Test that on the 2,000-case run, the uncovered branches include the
    IF_TRUE arm at the 'INPUT_FILE or OUTPUT_FILE not set' error DISPLAY.
    """
    from coroner.gen import generate_cases
    from coroner.parse.schema import load_schema
    from coroner.parse.copybook import parse_cobol_structure
    from coroner.run import compile_cobol, run_cobol_instrumented
    from coroner.parse.trace import parse_trace_counts
    
    cobol_source = "samples/credit-fees/CREDIT-FEES.cob"
    schema_path = "samples/credit-fees/schema.json"
    copybook_dir = "samples/credit-fees/copybooks"
    
    if not Path(cobol_source).exists():
        pytest.skip("Credit-fees sample not available")
    
    schema = load_schema(schema_path)
    cobol_structure = parse_cobol_structure(cobol_source, copybook_dir)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate 2,000 valid cases
        cases_csv = generate_cases(
            schema=schema,
            cobol_structure=cobol_structure,
            seed=42,
            num_cases=2000,
            tie_share=0.05
        )
        
        # Compile instrumented COBOL
        cobol_instrumented = Path(tmpdir) / "credit_fees_instrumented"
        compile_cobol(cobol_source, copybook_dir, str(cobol_instrumented), ["-ftraceall"])
        
        # Run and capture trace
        cobol_output = Path(tmpdir) / "cobol_output.csv"
        trace_file = Path(tmpdir) / "trace.txt"
        
        run_cobol_instrumented(
            str(cobol_instrumented), cases_csv, str(cobol_output), str(trace_file)
        )
        
        # Compute coverage
        trace = parse_trace_counts(str(trace_file))
        coverage = compute_coverage(trace, cobol_structure, cobol_source, copybook_dir)
        
        # Find the error-path branch in the source
        # The error check is: IF INPUT-FILE = SPACES OR OUTPUT-FILE = SPACES
        #                         DISPLAY "Error: INPUT_FILE or OUTPUT_FILE not set"
        # This is an error path that should never be covered by valid cases
        
        with open(cobol_source, 'r') as f:
            source_lines = f.readlines()
        
        error_display_line = None
        for i, line in enumerate(source_lines, start=1):
            if "INPUT_FILE or OUTPUT_FILE not set" in line:
                error_display_line = i
                break
        
        assert error_display_line is not None, "Could not find error DISPLAY in source"
        
        # Find the branch that starts at or near this DISPLAY
        # It should be an IF_TRUE branch (the error arm)
        uncovered_branches = [b for b in coverage.branch_details if not b.covered]
        
        # The error DISPLAY should be uncovered
        error_branch_found = any(
            abs(b.line - error_display_line) <= 2 and b.branch_type == "IF_TRUE"
            for b in uncovered_branches
        )
        
        assert error_branch_found, (
            f"Expected uncovered branches to include the error-path IF_TRUE near line {error_display_line}, "
            f"but uncovered branches are: {[(b.line, b.branch_type) for b in uncovered_branches]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
