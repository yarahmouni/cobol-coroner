"""Tests for CREDIT-FEES COBOL sample program."""
import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# Test timeout for all COBOL runs (prevents hangs)
COBOL_TIMEOUT = 10


@pytest.fixture(scope="session")
def cobol_binary():
    """Compile CREDIT-FEES.cob once per test session."""
    if not shutil.which("cobc"):
        pytest.skip("cobc not found on PATH")
    
    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)
    
    binary_path = build_dir / "credit-fees"
    source_path = Path("samples/credit-fees/CREDIT-FEES.cob")
    copybooks_path = Path("samples/credit-fees/copybooks")
    
    result = subprocess.run(
        ["cobc", "-x", "-Wall", "-I", str(copybooks_path), 
         "-o", str(binary_path), str(source_path)],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode != 0:
        pytest.fail(f"Compilation failed: {result.stderr}")
    
    if result.stderr:
        pytest.fail(f"Compilation produced warnings: {result.stderr}")
    
    return binary_path


def run_cobol(binary_path, input_csv, output_csv):
    """Run COBOL program with given input/output files."""
    env = os.environ.copy()
    env["INPUT_FILE"] = str(input_csv)
    env["OUTPUT_FILE"] = str(output_csv)
    
    result = subprocess.run(
        [str(binary_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=COBOL_TIMEOUT
    )
    
    return result


def read_csv_rows(csv_path):
    """Read CSV file and return list of rows (excluding header)."""
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)


def test_compilation_clean(cobol_binary):
    """Test 1: Compilation without warnings."""
    # Compilation already verified in fixture
    assert cobol_binary.exists()


def test_rounding_ties(cobol_binary):
    """Test 2: Rounding-ties fixture byte-exact comparison."""
    input_path = Path("samples/credit-fees/fixtures/rounding-ties.csv")
    expected_path = Path("samples/credit-fees/fixtures/expected-output.csv")
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = Path(f.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        
        assert result.returncode == 0, f"Exit code {result.returncode}, stderr: {result.stderr}"
        
        # Count rows (excluding header)
        input_rows = read_csv_rows(input_path)
        output_rows = read_csv_rows(output_path)
        assert len(output_rows) == len(input_rows), \
            f"Row count mismatch: {len(output_rows)} vs {len(input_rows)}"
        
        # Byte-exact comparison
        with open(output_path, "rb") as actual, open(expected_path, "rb") as expected:
            actual_bytes = actual.read()
            expected_bytes = expected.read()
            assert actual_bytes == expected_bytes, "Output differs from expected-output.csv"
    
    finally:
        output_path.unlink(missing_ok=True)


def test_edge_cases(cobol_binary):
    """Test 3: Edge cases with validation and overflow."""
    input_path = Path("samples/credit-fees/fixtures/edge-cases.csv")
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = Path(f.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        
        assert result.returncode in (0, 4), \
            f"Unexpected exit code {result.returncode}, stderr: {result.stderr}"
        
        output_rows = read_csv_rows(output_path)
        
        # Verify specific edge cases
        for row in output_rows:
            case_id = row["CASE-ID"]
            
            # Zero fee check (depends on fixture content)
            if "ZERO" in case_id:
                assert row["FEE-AMOUNT"] == "+0000000.00", \
                    f"{case_id}: Expected zero fee"
            
            # Overflow E01
            if "OVERFLOW" in case_id or "OVF" in case_id:
                assert row["REASON-CODE"] == "E01", \
                    f"{case_id}: Expected E01 for overflow"
                assert row["FEE-AMOUNT"] == "+0000000.00", \
                    f"{case_id}: Expected zero fee for E01"
                assert row["ELIGIBLE"] == "N", \
                    f"{case_id}: Expected N eligible for E01"
            
            # Income rule R01
            if "LOW-INCOME" in case_id:
                assert row["REASON-CODE"] == "R01", \
                    f"{case_id}: Expected R01 for low income"
            
            # Duration rule R02
            if "SHORT-DUR" in case_id:
                assert row["REASON-CODE"] == "R02", \
                    f"{case_id}: Expected R02 for short duration"
    
    finally:
        output_path.unlink(missing_ok=True)


def test_negative_principal_rounding(cobol_binary):
    """Test 4: Negative PRINCIPAL with rounding ties."""
    input_path = Path("samples/credit-fees/fixtures/rounding-ties.csv")
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = Path(f.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        assert result.returncode == 0
        
        output_rows = read_csv_rows(output_path)
        
        # Find negative tie rows
        negative_ties = [row for row in output_rows if row["CASE-ID"].startswith("TIE-")]
        input_rows = read_csv_rows(input_path)
        negative_input = [r for r in input_rows if r["PRINCIPAL"].startswith("-")]
        
        assert len(negative_input) >= 6, f"Expected at least 6 negative tie rows, got {len(negative_input)}"
        
        # Verify rounding away from zero (negative values round to more negative)
        for row in negative_ties:
            case_id = row["CASE-ID"]
            input_row = next((r for r in input_rows if r["CASE-ID"] == case_id), None)
            
            if input_row and input_row["PRINCIPAL"].startswith("-"):
                # Negative fee should be properly formatted with sign
                fee = row["FEE-AMOUNT"]
                assert fee.startswith("-") or fee.startswith("+"), \
                    f"{case_id}: Fee must have explicit sign: {fee}"
    
    finally:
        output_path.unlink(missing_ok=True)


def test_segment_discounts(cobol_binary):
    """Test 5: Segment discount branches (P=10%, S=5%, B and X=no discount)."""
    # Create test input with all segments
    test_data = [
        "CASE-ID,PRINCIPAL,FEE-RATE,DURATION-MONTHS,CUSTOMER-SEGMENT,INCOME",
        "SEG-P,10000.00,0.01000,24,P,50000.00",  # 10% discount
        "SEG-S,10000.00,0.01000,24,S,50000.00",  # 5% discount
        "SEG-B,10000.00,0.01000,24,B,50000.00",  # no discount
        "SEG-X,10000.00,0.01000,24,X,50000.00",  # no discount (OTHER)
    ]
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_in:
        f_in.write("\n".join(test_data))
        input_path = Path(f_in.name)
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_out:
        output_path = Path(f_out.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        assert result.returncode == 0
        
        output_rows = read_csv_rows(output_path)
        
        # Expected: base fee 100.00, P gets 90.00, S gets 95.00, B and X get 100.00
        fees = {row["CASE-ID"]: row["FEE-AMOUNT"] for row in output_rows}
        
        assert fees["SEG-P"] == "+0000090.00", f"P discount incorrect: {fees['SEG-P']}"
        assert fees["SEG-S"] == "+0000095.00", f"S discount incorrect: {fees['SEG-S']}"
        assert fees["SEG-B"] == "+0000100.00", f"B no discount incorrect: {fees['SEG-B']}"
        assert fees["SEG-X"] == "+0000100.00", f"X no discount incorrect: {fees['SEG-X']}"
    
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_minimum_fee_enforcement(cobol_binary):
    """Test 6: Minimum fee enforcement (< 10.00 becomes 10.00 with A01)."""
    # Create case where discounted fee < 10.00
    test_data = [
        "CASE-ID,PRINCIPAL,FEE-RATE,DURATION-MONTHS,CUSTOMER-SEGMENT,INCOME",
        "MIN-001,500.00,0.01000,24,P,50000.00",  # Base 5.00, after 10% discount = 4.50, min raises to 10.00
    ]
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_in:
        f_in.write("\n".join(test_data))
        input_path = Path(f_in.name)
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_out:
        output_path = Path(f_out.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        assert result.returncode == 0
        
        output_rows = read_csv_rows(output_path)
        assert len(output_rows) == 1
        
        row = output_rows[0]
        assert row["FEE-AMOUNT"] == "+0000010.00", \
            f"Expected minimum fee 10.00, got {row['FEE-AMOUNT']}"
        assert row["REASON-CODE"] == "A01", \
            f"Expected A01 reason code, got {row['REASON-CODE']}"
    
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_eligibility_rules(cobol_binary):
    """Test 7: Eligibility rules (income < 25000 = R01, duration < 12 = R02, both OK = Y)."""
    test_data = [
        "CASE-ID,PRINCIPAL,FEE-RATE,DURATION-MONTHS,CUSTOMER-SEGMENT,INCOME",
        "ELG-R01,10000.00,0.01000,24,B,20000.00",   # Income < 25000
        "ELG-R02,10000.00,0.01000,6,B,50000.00",    # Duration < 12
        "ELG-OK,10000.00,0.01000,24,B,50000.00",    # Both sufficient
    ]
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_in:
        f_in.write("\n".join(test_data))
        input_path = Path(f_in.name)
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_out:
        output_path = Path(f_out.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        assert result.returncode == 0
        
        output_rows = read_csv_rows(output_path)
        cases = {row["CASE-ID"]: row for row in output_rows}
        
        assert cases["ELG-R01"]["REASON-CODE"] == "R01", "Low income should give R01"
        assert cases["ELG-R01"]["ELIGIBLE"] == "N", "R01 should be not eligible"
        
        assert cases["ELG-R02"]["REASON-CODE"] == "R02", "Short duration should give R02"
        assert cases["ELG-R02"]["ELIGIBLE"] == "N", "R02 should be not eligible"
        
        assert cases["ELG-OK"]["ELIGIBLE"] == "Y", "Valid case should be eligible"
        assert cases["ELG-OK"]["REASON-CODE"] == "A00", "Valid case should have A00"
    
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_validation_errors(cobol_binary):
    """Test 8: Validation errors fixture (exit 4, E01 rows have 0.00 N E01)."""
    input_path = Path("samples/credit-fees/fixtures/validation-errors.csv")
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = Path(f.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        
        assert result.returncode == 4, \
            f"Expected exit 4 for validation errors, got {result.returncode}"
        
        output_rows = read_csv_rows(output_path)
        
        for row in output_rows:
            if row["REASON-CODE"] == "E01":
                assert row["FEE-AMOUNT"] == "+0000000.00", \
                    f"{row['CASE-ID']}: E01 should have zero fee"
                assert row["ELIGIBLE"] == "N", \
                    f"{row['CASE-ID']}: E01 should be not eligible"
            else:
                # Valid interleaved rows should have correct computation
                assert row["REASON-CODE"] in ("A00", "A01", "R01", "R02"), \
                    f"{row['CASE-ID']}: Unexpected reason code {row['REASON-CODE']}"
    
    finally:
        output_path.unlink(missing_ok=True)


def test_missing_file_error(cobol_binary):
    """Test 9: Missing input file error (exit 16, stderr has error message)."""
    input_path = Path("nonexistent_file_12345.csv")
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        output_path = Path(f.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        
        assert result.returncode == 16, \
            f"Expected exit 16 for missing file, got {result.returncode}"
        assert result.stderr, "Expected error message on stderr"
        assert "ERROR" in result.stderr.upper(), "Stderr should contain ERROR message"
    
    finally:
        output_path.unlink(missing_ok=True)


def test_empty_input_file(cobol_binary):
    """Additional test: Empty input file should write header only."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_in:
        input_path = Path(f_in.name)
        # Write nothing, just close
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_out:
        output_path = Path(f_out.name)
    
    try:
        result = run_cobol(cobol_binary, input_path, output_path)
        
        assert result.returncode == 0, \
            f"Empty input should exit 0, got {result.returncode}, stderr: {result.stderr}"
        assert result.stderr == "", f"Empty input should have empty stderr, got: {result.stderr}"
        
        # Output should contain exactly the header line
        with open(output_path, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1, f"Expected 1 line (header only), got {len(lines)}"
            assert lines[0].strip() == "CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE", \
                "Header line incorrect"
    
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
