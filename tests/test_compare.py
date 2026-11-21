"""Tests for output comparison."""
import csv
import subprocess
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from coroner.compare import (
    compare_outputs,
    normalize_decimal,
    normalize_string,
    CaseResult,
    ComparisonResult,
)
from coroner.parse.schema import Schema, SchemaColumn


def test_normalize_decimal_exact():
    """Test decimal normalization with exact values."""
    # Exact match at scale
    val, div = normalize_decimal("12.35", 2)
    assert val == "12.35"
    assert div is False
    
    # Padding needed
    val, div = normalize_decimal("12.3", 2)
    assert val == "12.30"
    assert div is False
    
    # Leading zeros
    val, div = normalize_decimal("0012.35", 2)
    assert val == "12.35"
    assert div is False
    
    # Negative
    val, div = normalize_decimal("-12.35", 2)
    assert val == "-12.35"
    assert div is False


def test_normalize_decimal_extra_decimals():
    """Test that extra non-zero decimals are marked divergent."""
    # Extra decimal (non-zero)
    val, div = normalize_decimal("12.355", 2)
    assert div is True
    assert val == "12.355"
    
    # Another extra decimal
    val, div = normalize_decimal("12.361", 2)
    assert div is True
    
    # Trailing zeros are OK
    val, div = normalize_decimal("12.350", 2)
    assert div is False
    assert val == "12.35"


def test_normalize_decimal_invalid():
    """Test that invalid decimals are marked divergent."""
    val, div = normalize_decimal("not-a-number", 2)
    assert div is True
    assert val == "not-a-number"
    
    val, div = normalize_decimal("", 2)
    assert div is True


def test_normalize_string_trailing_spaces():
    """Test that trailing spaces are trimmed."""
    assert normalize_string("ABC   ") == "ABC"
    assert normalize_string("ABC") == "ABC"
    assert normalize_string("  ABC") == "  ABC"  # Leading spaces kept
    assert normalize_string("  ABC  ") == "  ABC"


def test_compare_equal_outputs(tmp_path):
    """Test that equal outputs produce no divergences."""
    # Create schema
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
            SchemaColumn(name="AMOUNT", type="decimal", pic="S9(7)V99", description="Amount", scale=2),
        ]
    )
    
    # Write identical outputs
    cobol_csv = tmp_path / "cobol.csv"
    java_csv = tmp_path / "java.csv"
    
    for path in [cobol_csv, java_csv]:
        with open(path, 'w', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["CASE-ID", "AMOUNT"])
            writer.writeheader()
            writer.writerow({"CASE-ID": "TEST-001", "AMOUNT": "12.35"})
            writer.writerow({"CASE-ID": "TEST-002", "AMOUNT": "-100.00"})
    
    result = compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 0)
    
    assert result.total_divergent == 0
    assert result.row_count_match is True
    assert len(result.cases) == 2
    assert all(not case.divergent for case in result.cases)


def test_compare_divergent_field(tmp_path):
    """Test that divergent fields are reported."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
            SchemaColumn(name="AMOUNT", type="decimal", pic="S9(7)V99", description="Amount", scale=2),
        ]
    )
    
    cobol_csv = tmp_path / "cobol.csv"
    java_csv = tmp_path / "java.csv"
    
    with open(cobol_csv, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID", "AMOUNT"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "TEST-001", "AMOUNT": "12.36"})
    
    with open(java_csv, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID", "AMOUNT"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "TEST-001", "AMOUNT": "12.35"})
    
    result = compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 0)
    
    assert result.total_divergent == 1
    assert len(result.cases) == 1
    assert result.cases[0].divergent is True
    assert len(result.cases[0].divergent_fields) == 1
    div_info = result.cases[0].divergent_fields[0]
    field_name = div_info["field_name"]
    cobol_val = div_info["cobol_value"]
    java_val = div_info["java_value"]
    assert field_name == "AMOUNT"
    assert cobol_val == "12.36"
    assert java_val == "12.35"


def test_compare_row_count_mismatch(tmp_path):
    """Test that missing rows are marked divergent by case ID."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
            SchemaColumn(name="VALUE", type="string", pic="X(5)", description="Value"),
        ]
    )
    
    cobol_csv = tmp_path / "cobol.csv"
    java_csv = tmp_path / "java.csv"
    
    with open(cobol_csv, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID", "VALUE"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "A", "VALUE": "foo"})
        writer.writerow({"CASE-ID": "B", "VALUE": "bar"})
        writer.writerow({"CASE-ID": "C", "VALUE": "baz"})
    
    with open(java_csv, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID", "VALUE"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "A", "VALUE": "foo"})
        writer.writerow({"CASE-ID": "B", "VALUE": "bar"})
    
    result = compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 0)
    
    assert result.row_count_match is False
    assert result.total_divergent == 1
    
    # Find the divergent case (C)
    divergent_cases = [c for c in result.cases if c.divergent]
    assert len(divergent_cases) == 1
    assert divergent_cases[0].case_id == "C"
    assert divergent_cases[0].divergent_fields == [{"field_name": "<row>", "kind": "missing_in_java", "cobol_value": "present", "java_value": "missing"}]
    
    # Cases A and B should not be divergent
    non_divergent = [c for c in result.cases if not c.divergent]
    assert len(non_divergent) == 2
    assert {c.case_id for c in non_divergent} == {"A", "B"}


def test_compare_missing_column(tmp_path):
    """Test that missing columns in Java output raise clear error."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
            SchemaColumn(name="AMOUNT", type="decimal", pic="S9(7)V99", description="Amount", scale=2),
        ]
    )
    
    cobol_csv = tmp_path / "cobol.csv"
    java_csv = tmp_path / "java.csv"
    
    with open(cobol_csv, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID", "AMOUNT"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "TEST-001", "AMOUNT": "12.35"})
    
    with open(java_csv, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "TEST-001"})
    
    # Missing column in Java should raise clear error
    with pytest.raises(ValueError, match="column AMOUNT not found in Java output header"):
        compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 0)


def test_compare_return_codes(tmp_path):
    """Test that return codes are captured."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
        ]
    )
    
    cobol_csv = tmp_path / "cobol.csv"
    java_csv = tmp_path / "java.csv"
    
    for path in [cobol_csv, java_csv]:
        with open(path, 'w', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["CASE-ID"])
            writer.writeheader()
            writer.writerow({"CASE-ID": "TEST-001"})
    
    result = compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 4)
    
    assert result.run_return_codes == (0, 4)


def test_normalize_decimal_padding():
    """Test that padding works correctly."""
    # "12.35", "12.350", "+0000012.35" should all normalize to same value
    val1, div1 = normalize_decimal("12.35", 2)
    val2, div2 = normalize_decimal("12.350", 2)
    val3, div3 = normalize_decimal("+0000012.35", 2)
    
    assert not div1 and not div2 and not div3
    assert val1 == val2 == "12.35"
    # Decimal strips leading + automatically
    assert val3 == "12.35"


# Property-based tests with Hypothesis

@given(st.decimals(allow_nan=False, allow_infinity=False, places=2))
def test_normalize_decimal_idempotent(value):
    """Test that normalizing twice gives the same result."""
    value_str = str(value)
    normalized1, div1 = normalize_decimal(value_str, 2)
    if not div1:
        normalized2, div2 = normalize_decimal(normalized1, 2)
        assert normalized1 == normalized2
        assert div1 == div2


@given(st.text())
def test_normalize_string_idempotent(value):
    """Test that string normalization is idempotent."""
    normalized1 = normalize_string(value)
    normalized2 = normalize_string(normalized1)
    assert normalized1 == normalized2


@given(st.decimals(allow_nan=False, allow_infinity=False, places=5))
def test_extra_decimals_divergent(value):
    """Test that values with extra non-zero decimals are divergent."""
    value_str = str(value)
    normalized, divergent = normalize_decimal(value_str, 2)
    
    # If the value has more than 2 decimal places with non-zero digits beyond scale 2
    dec = Decimal(value_str)
    try:
        rounded = dec.quantize(Decimal("0.01"))
    except InvalidOperation:
        # Number is too large - our function should have caught it
        assert divergent
        return
    
    if dec != rounded:
        # Extra non-zero decimals exist
        assert divergent
    else:
        # No extra non-zero decimals
        assert not divergent


def test_string_all_spaces():
    """Test that all-space strings normalize to empty."""
    assert normalize_string("  ") == ""
    assert normalize_string("   ") == ""
    assert normalize_string(" ") == ""


@given(st.text(min_size=1).filter(lambda s: s.strip() != ""))
def test_string_trim_trailing_only(value):
    """Test that only trailing spaces are trimmed for values with non-space characters."""
    normalized = normalize_string(value)
    
    # Should not have trailing spaces
    assert not normalized.endswith(' ')
    
    # If original had leading spaces, they should be kept
    leading_spaces = len(value) - len(value.lstrip(' '))
    if leading_spaces > 0:
        assert normalized.startswith(' ' * leading_spaces)


# End-to-end test with real COBOL and Java programs

def _check_tool_available(tool: str) -> bool:
    """Check if a tool is available."""
    try:
        result = subprocess.run(
            [tool, "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_program(program_type: str, input_csv: str, output_csv: str, work_dir: Path, timeout: float = 30) -> int:
    """Run COBOL or Java program on the given input; the compiled files go to work_dir (a temporary folder)."""
    import os
    
    if program_type == "cobol":
        # Compile COBOL
        compile_result = subprocess.run(
            [
                "cobc", "-x", "-Wall",
                "-I", "samples/credit-fees/copybooks",
                "-o", str(work_dir / "test_compare_cobol"),
                "samples/credit-fees/CREDIT-FEES.cob"
            ],
            capture_output=True,
            timeout=timeout
        )
        if compile_result.returncode != 0:
            raise RuntimeError(f"COBOL compilation failed: {compile_result.stderr.decode()}")
        
        # Run COBOL
        result = subprocess.run(
            [str(work_dir / "test_compare_cobol")],
            env={**os.environ, "INPUT_FILE": input_csv, "OUTPUT_FILE": output_csv},
            capture_output=True,
            timeout=timeout
        )
        return result.returncode
    
    elif program_type == "java":
        # Compile Java
        (work_dir / "test_compare_java").mkdir(parents=True, exist_ok=True)
        compile_result = subprocess.run(
            [
                "javac", "-Xlint:all",
                "-d", str(work_dir / "test_compare_java"),
                "samples/credit-fees/java/CreditFees.java"
            ],
            capture_output=True,
            timeout=timeout
        )
        if compile_result.returncode != 0:
            raise RuntimeError(f"Java compilation failed: {compile_result.stderr.decode()}")
        
        # Run Java
        result = subprocess.run(
            ["java", "-cp", str(work_dir / "test_compare_java"), "CreditFees"],
            env={**os.environ, "INPUT_FILE": input_csv, "OUTPUT_FILE": output_csv},
            capture_output=True,
            timeout=timeout
        )
        return result.returncode
    
    else:
        raise ValueError(f"Unknown program type: {program_type}")


@pytest.mark.skipif(not _check_tool_available("cobc"), reason="cobc not available")
@pytest.mark.skipif(not _check_tool_available("javac"), reason="javac not available")
def test_e2e_real_programs_no_divergence(tmp_path):
    """Test that COBOL and Java produce identical outputs on validation-errors fixture."""
    # Load schema
    from coroner.parse.schema import load_schema
    schema = load_schema("samples/credit-fees/schema.json")
    
    # Use validation-errors.csv as input
    input_csv = "samples/credit-fees/fixtures/validation-errors.csv"
    cobol_output = tmp_path / "cobol_output.csv"
    java_output = tmp_path / "java_output.csv"
    
    # Run COBOL
    cobol_rc = _run_program("cobol", input_csv, str(cobol_output), tmp_path)
    
    # Run Java
    java_rc = _run_program("java", input_csv, str(java_output), tmp_path)
    
    # Compare
    result = compare_outputs(str(cobol_output), str(java_output), schema, cobol_rc, java_rc)
    
    assert result.total_divergent == 0, f"Expected no divergences, got {result.total_divergent}"
    assert result.row_count_match is True


@pytest.mark.skipif(not _check_tool_available("cobc"), reason="cobc not available")
@pytest.mark.skipif(not _check_tool_available("javac"), reason="javac not available")
def test_e2e_detect_divergence(tmp_path):
    """Test that a modified Java output is detected as divergent."""
    from coroner.parse.schema import load_schema
    schema = load_schema("samples/credit-fees/schema.json")
    
    # Use validation-errors.csv as input
    input_csv = "samples/credit-fees/fixtures/validation-errors.csv"
    cobol_output = tmp_path / "cobol_output.csv"
    java_output_orig = tmp_path / "java_output_orig.csv"
    java_output_modified = tmp_path / "java_output_modified.csv"
    
    # Run COBOL
    cobol_rc = _run_program("cobol", input_csv, str(cobol_output), tmp_path)
    
    # Run Java
    java_rc = _run_program("java", input_csv, str(java_output_orig), tmp_path)
    
    # Modify one FEE-AMOUNT in Java output by 0.01
    with open(java_output_orig, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    
    # Find first row with a non-zero FEE-AMOUNT and modify it
    modified = False
    for row in rows:
        if row.get('FEE-AMOUNT') and row['FEE-AMOUNT'] not in ['', '+0000000.00']:
            try:
                original_fee = Decimal(row['FEE-AMOUNT'])
                modified_fee = original_fee + Decimal('0.01')
                row['FEE-AMOUNT'] = f"{modified_fee:+011.2f}"
                modified = True
                break
            except:
                continue
    
    assert modified, "Could not find a row to modify"
    
    with open(java_output_modified, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    # Compare
    result = compare_outputs(str(cobol_output), str(java_output_modified), schema, cobol_rc, java_rc)
    
    assert result.total_divergent == 1, f"Expected exactly 1 divergent case, got {result.total_divergent}"
    
    # Find the divergent case
    divergent_cases = [c for c in result.cases if c.divergent]
    assert len(divergent_cases) == 1
    
    # Check that FEE-AMOUNT is the divergent field
    divergent_fields = divergent_cases[0].divergent_fields
    assert len(divergent_fields) == 1
    assert divergent_fields[0]["field_name"] == "FEE-AMOUNT"



def test_compare_padded_header_cobol_only(tmp_path):
    """Test that padded headers on COBOL side are handled correctly."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
            SchemaColumn(name="VALUE", type="string", pic="X(5)", description="Value"),
        ]
    )
    
    cobol_csv = tmp_path / "cobol.csv"
    java_csv = tmp_path / "java.csv"
    
    # COBOL header with trailing spaces (realistic legacy output)
    with open(cobol_csv, 'w', encoding='utf-8') as f:
        f.write("CASE-ID   ,VALUE     \n")
        f.write("TEST-001,ABC\n")
    
    # Java header without trailing spaces
    with open(java_csv, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID", "VALUE"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "TEST-001", "VALUE": "ABC"})
    
    result = compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 0)
    
    assert result.total_divergent == 0
    assert result.row_count_match is True


def test_compare_padded_header_both_sides(tmp_path):
    """Test that padded headers on both sides are handled correctly."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
            SchemaColumn(name="AMOUNT", type="decimal", pic="S9(7)V99", description="Amount", scale=2),
        ]
    )
    
    cobol_csv = tmp_path / "cobol.csv"
    java_csv = tmp_path / "java.csv"
    
    # Both headers with trailing spaces
    with open(cobol_csv, 'w', encoding='utf-8') as f:
        f.write("CASE-ID   ,AMOUNT        \n")
        f.write("TEST-001,12.35\n")
    
    with open(java_csv, 'w', encoding='utf-8') as f:
        f.write("CASE-ID   ,AMOUNT        \n")
        f.write("TEST-001,12.35\n")
    
    result = compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 0)
    
    assert result.total_divergent == 0
    assert result.row_count_match is True


def test_compare_missing_column_after_trim(tmp_path):
    """Test that missing column error is clear after trimming."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="input.csv",
        input_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID")
        ],
        output_file="output.csv",
        output_columns=[
            SchemaColumn(name="CASE-ID", type="string", pic="X(10)", description="ID"),
            SchemaColumn(name="MISSING-COL", type="string", pic="X(5)", description="Missing"),
        ]
    )
    
    cobol_csv = tmp_path / "cobol.csv"
    
    # Header with only CASE-ID
    with open(cobol_csv, 'w', encoding='utf-8') as f:
        f.write("CASE-ID\n")
        f.write("TEST-001\n")
    
    java_csv = tmp_path / "java.csv"
    with open(java_csv, 'w', encoding='utf-8') as f:
        f.write("CASE-ID\n")
        f.write("TEST-001\n")
    
    # COBOL should raise clear error
    with pytest.raises(ValueError, match="column MISSING-COL not found in COBOL output header"):
        compare_outputs(str(cobol_csv), str(java_csv), schema, 0, 0)
    
    # Java should also raise clear error
    cobol_csv_ok = tmp_path / "cobol_ok.csv"
    with open(cobol_csv_ok, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["CASE-ID", "MISSING-COL"])
        writer.writeheader()
        writer.writerow({"CASE-ID": "TEST-001", "MISSING-COL": "X"})
    
    with pytest.raises(ValueError, match="column MISSING-COL not found in Java output header"):
        compare_outputs(str(cobol_csv_ok), str(java_csv), schema, 0, 0)
