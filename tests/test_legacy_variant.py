"""Tests for legacy variant generation."""

import csv
import os
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from coroner.catalog.legacy_variant import generate_half_even_variant


def test_generate_half_even_variant_replaces_string():
    """Test that generate_half_even_variant replaces RoundingMode.HALF_UP."""
    source_content = """
import java.math.RoundingMode;

public class Test {
    void compute() {
        x = y.setScale(2, RoundingMode.HALF_UP);
        z = a.setScale(2, RoundingMode.HALF_UP);
    }
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
        f.write(source_content)
        source_path = f.name
    
    output_path = source_path.replace('.java', '_variant.java')
    
    try:
        count = generate_half_even_variant(source_path, output_path)
        
        assert count == 2, f"Expected 2 replacements, got {count}"
        
        with open(output_path, 'r') as f:
            output_content = f.read()
        
        assert 'RoundingMode.HALF_EVEN' in output_content
        assert 'RoundingMode.HALF_UP' not in output_content
        assert output_content.count('RoundingMode.HALF_EVEN') == 2
    finally:
        os.unlink(source_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_generate_half_even_variant_raises_on_no_occurrence():
    """Test that ValueError is raised when no HALF_UP is found."""
    source_content = """
public class Test {
    void compute() {
        x = y.setScale(2, RoundingMode.DOWN);
    }
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
        f.write(source_content)
        source_path = f.name
    
    output_path = source_path.replace('.java', '_variant.java')
    
    try:
        with pytest.raises(ValueError, match="No 'RoundingMode.HALF_UP' found"):
            generate_half_even_variant(source_path, output_path)
    finally:
        os.unlink(source_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_credit_fees_variant_properties(tmp_path):
    """Test CreditFees variant has same line count and differs only on replaced lines."""
    source_path = 'samples/credit-fees/java/CreditFees.java'
    if not os.path.exists(source_path):
        pytest.skip(f"Source file {source_path} not found")
    
    # Use a subdirectory for the variant
    os.makedirs(tmp_path / 'variant', exist_ok=True)
    output_path = str(tmp_path / 'variant' / 'CreditFees.java')
    
    count = generate_half_even_variant(source_path, output_path)
    
    assert count > 0, "Expected at least one replacement"
    
    # Read both files
    with open(source_path, 'r') as f:
        original_lines = f.readlines()
    
    with open(output_path, 'r') as f:
        variant_lines = f.readlines()
    
    # Check same number of lines
    assert len(variant_lines) == len(original_lines), \
        f"Line count differs: original {len(original_lines)}, variant {len(variant_lines)}"
    
    # Check that variant contains no HALF_UP
    variant_content = ''.join(variant_lines)
    assert 'RoundingMode.HALF_UP' not in variant_content, \
        "Variant still contains RoundingMode.HALF_UP"
    
    # Check that only replaced lines differ
    diff_count = 0
    for i, (orig, var) in enumerate(zip(original_lines, variant_lines)):
        if orig != var:
            diff_count += 1
            # Each differing line should be a replacement
            assert 'RoundingMode.HALF_EVEN' in var, \
                f"Line {i+1} differs but doesn't contain HALF_EVEN: {var.strip()}"
            assert 'RoundingMode.HALF_UP' in orig, \
                f"Line {i+1} differs but original doesn't contain HALF_UP: {orig.strip()}"
    
    assert diff_count == count, \
        f"Expected {count} differing lines, got {diff_count}"


def test_credit_fees_variant_compiles(tmp_path):
    """Test that the variant compiles with javac -Xlint:all."""
    source_path = 'samples/credit-fees/java/CreditFees.java'
    if not os.path.exists(source_path):
        pytest.skip(f"Source file {source_path} not found")
    
    # Check if javac is available
    try:
        subprocess.run(['javac', '-version'], capture_output=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("javac not available")
    
    # Use a subdirectory for the variant
    os.makedirs(tmp_path / 'variant', exist_ok=True)
    output_path = str(tmp_path / 'variant' / 'CreditFees.java')
    
    generate_half_even_variant(source_path, output_path)
    
    # Compile the variant to its own directory
    os.makedirs(tmp_path / 'variant_classes', exist_ok=True)
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(tmp_path / 'variant_classes'), output_path],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, \
        f"Compilation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"


def is_even_digit_tie(principal: Decimal, fee_rate: Decimal) -> bool:
    """
    Check if the product creates a tie with an even preceding digit.
    
    A tie occurs when the product has exactly 5 in the third decimal place.
    The preceding digit (second decimal) must be even for HALF_EVEN to diverge.
    """
    product = principal * fee_rate
    # Round to 3 decimals to see the tie
    product_str = str(product.quantize(Decimal('0.001')))
    
    # Check if it's a tie (ends in .XX5)
    if not product_str.endswith('5'):
        return False
    
    # Extract the second decimal digit (preceding digit)
    parts = product_str.split('.')
    if len(parts) != 2 or len(parts[1]) < 2:
        return False
    
    second_decimal = int(parts[1][-2])
    return second_decimal % 2 == 0


def test_credit_fees_variant_diverges_on_even_ties(tmp_path):
    """Test that HALF_EVEN variant diverges on exactly the even-digit tie rows."""
    source_path = 'samples/credit-fees/java/CreditFees.java'
    fixtures_dir = 'samples/credit-fees/fixtures'
    ties_csv = f'{fixtures_dir}/rounding-ties.csv'
    expected_csv = f'{fixtures_dir}/expected-output.csv'
    
    if not os.path.exists(source_path):
        pytest.skip(f"Source file {source_path} not found")
    if not os.path.exists(ties_csv):
        pytest.skip(f"Test data {ties_csv} not found")
    if not os.path.exists(expected_csv):
        pytest.skip(f"Expected output {expected_csv} not found")
    
    # Check if cobc is available (needed to verify COBOL reference)
    try:
        subprocess.run(['cobc', '--version'], capture_output=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("cobc not available")
    
    # Check if javac and java are available
    try:
        subprocess.run(['javac', '-version'], capture_output=True, timeout=5)
        subprocess.run(['java', '-version'], capture_output=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("javac or java not available")
    
    # Generate and compile the variant
    os.makedirs(tmp_path / 'variant', exist_ok=True)
    os.makedirs(tmp_path / 'variant_classes', exist_ok=True)
    variant_path = str(tmp_path / 'variant' / 'CreditFees.java')
    generate_half_even_variant(source_path, variant_path)
    
    # Compile the variant
    compile_result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(tmp_path / 'variant_classes'), variant_path],
        capture_output=True,
        text=True,
        timeout=60
    )
    assert compile_result.returncode == 0, \
        f"Variant compilation failed: {compile_result.stderr}"
    
    # Run the variant
    variant_output = str(tmp_path / 'rounding-ties-variant.csv')
    env = os.environ.copy()
    env['INPUT_FILE'] = ties_csv
    env['OUTPUT_FILE'] = variant_output
    
    run_result = subprocess.run(
        ['java', '-cp', str(tmp_path / 'variant_classes'), 'CreditFees'],
        env=env,
        capture_output=True,
        text=True,
        timeout=60
    )
    assert run_result.returncode == 0, \
        f"Variant execution failed: {run_result.stderr}"
    
    # Read input to compute which rows should diverge
    with open(ties_csv, 'r') as f:
        reader = csv.DictReader(f)
        input_rows = list(reader)
    
    # Read expected (COBOL) output
    with open(expected_csv, 'r') as f:
        reader = csv.DictReader(f)
        expected_rows = list(reader)
    
    # Read variant output
    with open(variant_output, 'r') as f:
        reader = csv.DictReader(f)
        variant_rows = list(reader)
    
    # Skip header comparison
    assert len(input_rows) == len(expected_rows) == len(variant_rows), \
        "Row counts don't match"
    
    # Compute which rows should diverge based on even-digit ties
    expected_divergent = []
    for i, row in enumerate(input_rows):
        principal = Decimal(row['PRINCIPAL'])
        fee_rate = Decimal(row['FEE-RATE'])
        
        if is_even_digit_tie(principal, fee_rate):
            expected_divergent.append(i)
    
    # Count actual divergences
    actual_divergent = []
    for i, (exp_row, var_row) in enumerate(zip(expected_rows, variant_rows)):
        # Compare the FEE-AMOUNT field (the rounded result)
        if exp_row['FEE-AMOUNT'] != var_row['FEE-AMOUNT']:
            actual_divergent.append(i)
    
    # Verify the counts match
    assert len(actual_divergent) == len(expected_divergent), \
        f"Expected {len(expected_divergent)} divergences, got {len(actual_divergent)}"
    
    # Verify it's exactly the even-tie rows
    assert set(actual_divergent) == set(expected_divergent), \
        f"Divergent rows don't match: expected {expected_divergent}, got {actual_divergent}"
    
    # According to R-26, there should be 26 even-digit ties out of 30
    assert len(expected_divergent) == 26, \
        f"Expected 26 even-digit ties per R-26, computed {len(expected_divergent)}"
