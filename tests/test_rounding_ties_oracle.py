"""
Oracle test for rounding ties fixture.

Verifies the rounding-ties.csv fixture independently of COBOL:
- Each row is an exact tie (product % 0.01 == 0.005)
- Even-digit ties diverge between HALF_UP and HALF_EVEN
- Odd-digit ties produce the same result for both rounding modes
- Counts meet minimum requirements (16 even, 4 odd, 6 negative even)
"""

import csv
import os
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, getcontext

getcontext().prec = 50

FIXTURE_PATH = 'samples/credit-fees/fixtures/rounding-ties.csv'


def is_exact_tie(principal, fee_rate):
    """Check if principal * fee_rate is an exact tie."""
    product = Decimal(str(principal)) * Decimal(str(fee_rate))
    remainder = abs(product % Decimal('0.01'))
    return remainder == Decimal('0.005')


def get_preceding_digit(principal, fee_rate):
    """Get the digit at position 2 after decimal (tie-breaker digit)."""
    product = Decimal(str(principal)) * Decimal(str(fee_rate))
    abs_product = abs(product)
    scaled = int(abs_product * 100) % 10
    return scaled


def compute_rounded_fee(principal, fee_rate, rounding_mode):
    """Compute fee with specified rounding mode."""
    product = Decimal(str(principal)) * Decimal(str(fee_rate))
    return product.quantize(Decimal('0.01'), rounding=rounding_mode)


def test_fixture_exists():
    """Verify the fixture file exists."""
    assert os.path.exists(FIXTURE_PATH), f"Fixture not found: {FIXTURE_PATH}"


def test_all_rows_are_exact_ties():
    """Verify every row in the fixture is an exact tie."""
    with open(FIXTURE_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) >= 20, f"Expected at least 20 rows, got {len(rows)}"
    
    for row in rows:
        principal = Decimal(row['PRINCIPAL'])
        fee_rate = Decimal(row['FEE-RATE'])
        assert is_exact_tie(principal, fee_rate), \
            f"{row['CASE-ID']}: {principal} * {fee_rate} is not an exact tie"


def test_even_digit_ties_diverge():
    """Verify even-digit ties produce different results for HALF_UP vs HALF_EVEN."""
    with open(FIXTURE_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    divergence_count = 0
    
    for row in rows:
        principal = Decimal(row['PRINCIPAL'])
        fee_rate = Decimal(row['FEE-RATE'])
        digit = get_preceding_digit(principal, fee_rate)
        
        if digit % 2 == 0:  # Even-digit tie
            half_up = compute_rounded_fee(principal, fee_rate, ROUND_HALF_UP)
            half_even = compute_rounded_fee(principal, fee_rate, ROUND_HALF_EVEN)
            
            # These should diverge
            assert half_up != half_even, \
                f"{row['CASE-ID']}: even-digit tie should diverge, got {half_up} == {half_even}"
            
            # Verify the divergence is exactly 0.01 in absolute value
            diff = abs(half_up - half_even)
            assert diff == Decimal('0.01'), \
                f"{row['CASE-ID']}: divergence should be 0.01, got {diff}"
            
            divergence_count += 1
    
    assert divergence_count >= 16, \
        f"Expected at least 16 even-digit ties, got {divergence_count}"


def test_odd_digit_ties_agree():
    """Verify odd-digit ties produce the same result for HALF_UP and HALF_EVEN."""
    with open(FIXTURE_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    odd_count = 0
    
    for row in rows:
        principal = Decimal(row['PRINCIPAL'])
        fee_rate = Decimal(row['FEE-RATE'])
        digit = get_preceding_digit(principal, fee_rate)
        
        if digit % 2 == 1:  # Odd-digit tie
            half_up = compute_rounded_fee(principal, fee_rate, ROUND_HALF_UP)
            half_even = compute_rounded_fee(principal, fee_rate, ROUND_HALF_EVEN)
            
            # These should agree
            assert half_up == half_even, \
                f"{row['CASE-ID']}: odd-digit tie should agree, got {half_up} != {half_even}"
            
            odd_count += 1
    
    assert odd_count >= 4, \
        f"Expected at least 4 odd-digit control ties, got {odd_count}"


def test_negative_even_ties_count():
    """Verify at least 6 negative even-digit ties."""
    with open(FIXTURE_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    negative_even_count = 0
    
    for row in rows:
        principal = Decimal(row['PRINCIPAL'])
        fee_rate = Decimal(row['FEE-RATE'])
        
        if principal < 0:
            digit = get_preceding_digit(principal, fee_rate)
            if digit % 2 == 0:
                negative_even_count += 1
    
    assert negative_even_count >= 6, \
        f"Expected at least 6 negative even-digit ties, got {negative_even_count}"


def test_all_rows_meet_business_rules():
    """Verify all rows meet business rules for valid processing."""
    with open(FIXTURE_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    for row in rows:
        principal = Decimal(row['PRINCIPAL'])
        fee_rate = Decimal(row['FEE-RATE'])
        income = Decimal(row['INCOME'])
        duration = int(row['DURATION-MONTHS'])
        segment = row['CUSTOMER-SEGMENT']
        
        # All should be segment B or X (no discount)
        assert segment in ['B', 'X'], \
            f"{row['CASE-ID']}: segment should be B or X, got {segment}"
        
        # Income should be >= 25000.00
        assert income >= Decimal('25000.00'), \
            f"{row['CASE-ID']}: income should be >= 25000.00, got {income}"
        
        # Duration should be >= 12
        assert duration >= 12, \
            f"{row['CASE-ID']}: duration should be >= 12, got {duration}"
        
        # Absolute base fee should be >= 10.00
        abs_fee = abs(principal * fee_rate)
        assert abs_fee >= Decimal('10.00'), \
            f"{row['CASE-ID']}: absolute fee should be >= 10.00, got {abs_fee}"


def test_fixture_counts():
    """Print and verify the counts for documentation."""
    with open(FIXTURE_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    even_count = 0
    odd_count = 0
    negative_even_count = 0
    
    for row in rows:
        principal = Decimal(row['PRINCIPAL'])
        fee_rate = Decimal(row['FEE-RATE'])
        digit = get_preceding_digit(principal, fee_rate)
        
        if digit % 2 == 0:
            even_count += 1
            if principal < 0:
                negative_even_count += 1
        else:
            odd_count += 1
    
    print(f"\nFixture counts:")
    print(f"  Total rows: {len(rows)}")
    print(f"  Even-digit ties: {even_count}")
    print(f"  Odd-digit control ties: {odd_count}")
    print(f"  Negative even-digit ties: {negative_even_count}")
    
    assert even_count >= 16
    assert odd_count >= 4
    assert negative_even_count >= 6


def test_expected_output_matches_oracle():
    """Verify EVERY row in expected-output.csv matches oracle HALF_UP."""
    expected_path = 'samples/credit-fees/fixtures/expected-output.csv'
    
    if not os.path.exists(expected_path):
        import pytest
        pytest.skip(f"Expected output not found: {expected_path}")
    
    with open(FIXTURE_PATH, 'r') as f_in:
        input_reader = csv.DictReader(f_in)
        input_rows = list(input_reader)
    
    with open(expected_path, 'r') as f_out:
        output_reader = csv.DictReader(f_out)
        output_rows = list(output_reader)
    
    assert len(output_rows) == len(input_rows), \
        f"Row count mismatch: {len(output_rows)} output vs {len(input_rows)} input"
    
    for input_row, output_row in zip(input_rows, output_rows):
        case_id = input_row['CASE-ID']
        assert output_row['CASE-ID'] == case_id, \
            f"Case ID mismatch at position"
        
        principal = Decimal(input_row['PRINCIPAL'])
        fee_rate = Decimal(input_row['FEE-RATE'])
        
        # Oracle computation: ROUND_HALF_UP (COBOL ROUNDED default)
        oracle_fee = compute_rounded_fee(principal, fee_rate, ROUND_HALF_UP)
        
        # Format as +9(7).99
        if oracle_fee >= 0:
            oracle_formatted = f"+{abs(oracle_fee):010.2f}"
        else:
            oracle_formatted = f"-{abs(oracle_fee):010.2f}"
        
        actual_fee = output_row['FEE-AMOUNT']
        
        assert actual_fee == oracle_formatted, \
            f"{case_id}: expected {oracle_formatted}, got {actual_fee} (oracle: {oracle_fee})"
