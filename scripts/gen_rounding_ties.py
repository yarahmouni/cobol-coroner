#!/usr/bin/env python3
"""
Generate exact rounding tie cases for CREDIT-FEES.cob test fixture.

A tie occurs when PRINCIPAL * FEE-RATE produces an exact product with digits 3 to 7
after the decimal point equal to 50000 (i.e., the product ends in exactly .XX50000
where XX are the first two decimal digits).

Requirements from design:
- At least 16 even-preceding-digit ties (where digit 2 after decimal is even)
- At least 4 odd-digit control cases (where digit 2 after decimal is odd)
- At least 6 negative even-digit ties
- All rows: segment B or X, INCOME >= 25000.00, DURATION >= 12
- Absolute base fee >= 10.00

The even-digit ties will diverge between COBOL ROUNDED (HALF_UP) and Java HALF_EVEN.
"""

from decimal import Decimal, getcontext
import csv
import sys

# Set high precision for exact arithmetic
getcontext().prec = 50

def is_exact_tie(principal, fee_rate):
    """Check if principal * fee_rate is an exact tie (ends in .XX50000)."""
    product = Decimal(str(principal)) * Decimal(str(fee_rate))
    # Check if the fractional part from position 3 onward equals 0.00050000...
    # This means: product % 0.01 == 0.005 exactly
    remainder = abs(product % Decimal('0.01'))
    return remainder == Decimal('0.005')

def get_preceding_digit(principal, fee_rate):
    """Get the digit at position 2 after decimal point (the tie-breaker digit)."""
    product = Decimal(str(principal)) * Decimal(str(fee_rate))
    abs_product = abs(product)
    # Extract the second decimal digit
    scaled = int(abs_product * 100) % 10
    return scaled

def generate_ties():
    """Generate rounding tie test cases with fixed deterministic values."""
    ties = []
    
    # Strategy: construct cases with known exact ties
    # Using products like 12.345, 23.455, 34.565, etc.
    
    # Pattern 1: Products ending in .X45 where X is even (2, 4, 6, 8)
    # These will have preceding even digit and be exact ties
    
    # 12.345 = 1234.50 * 0.01000
    ties.append(('TIE-001', '1234.50', '0.01000', 'B', False))
    # 12.345 negative
    ties.append(('TIE-002', '-1234.50', '0.01000', 'B', True))
    
    # 12.345 = 2469.00 * 0.00500
    ties.append(('TIE-003', '2469.00', '0.00500', 'B', False))
    # negative
    ties.append(('TIE-004', '-4115.00', '0.00300', 'B', True))
    
    # More even-digit ties
    # 23.445 = 2344.50 * 0.01000
    ties.append(('TIE-005', '2344.50', '0.01000', 'X', False))
    ties.append(('TIE-006', '-2344.50', '0.01000', 'B', True))
    
    # 34.545 = 3454.50 * 0.01000
    ties.append(('TIE-007', '3454.50', '0.01000', 'B', False))
    ties.append(('TIE-008', '-3454.50', '0.01000', 'X', True))
    
    # 45.645 = 4564.50 * 0.01000
    ties.append(('TIE-009', '4564.50', '0.01000', 'B', False))
    ties.append(('TIE-010', '-4564.50', '0.01000', 'B', True))
    
    # 56.745 = 5674.50 * 0.01000
    ties.append(('TIE-011', '5674.50', '0.01000', 'X', False))
    ties.append(('TIE-012', '-5674.50', '0.01000', 'B', True))
    
    # 67.845 = 6784.50 * 0.01000
    ties.append(('TIE-013', '6784.50', '0.01000', 'B', False))
    
    # 78.945 = 7894.50 * 0.01000
    ties.append(('TIE-014', '7894.50', '0.01000', 'X', False))
    
    # 10.245 = 1024.50 * 0.01000
    ties.append(('TIE-015', '1024.50', '0.01000', 'B', False))
    
    # 20.445 = 4089.00 * 0.00500
    ties.append(('TIE-016', '4089.00', '0.00500', 'B', False))
    
    # 30.645 = 6129.00 * 0.00500
    ties.append(('TIE-017', '6129.00', '0.00500', 'X', False))
    
    # 40.845 = 8169.00 * 0.00500
    ties.append(('TIE-018', '8169.00', '0.00500', 'B', False))
    
    # Pattern 2: Odd-digit control cases (won't diverge)
    # 10.235 = 1023.50 * 0.01000 (digit 3 is odd)
    ties.append(('TIE-019', '1023.50', '0.01000', 'B', False))
    
    # 10.255 = 500.00 * 0.02051 (digit 5 is odd)
    ties.append(('TIE-020', '500.00', '0.02051', 'B', False))
    
    # 10.235 negative
    ties.append(('TIE-021', '-2047.00', '0.00500', 'B', True))
    
    # 20.355 = 2035.50 * 0.01000 (digit 5 is odd)
    ties.append(('TIE-022', '2035.50', '0.01000', 'X', False))
    
    # Additional even ties to exceed minimum counts
    # 89.045 = 8904.50 * 0.01000
    ties.append(('TIE-023', '8904.50', '0.01000', 'B', False))
    
    # 11.245 = 1124.50 * 0.01000
    ties.append(('TIE-024', '1124.50', '0.01000', 'B', False))
    
    # 21.445 = 4289.00 * 0.00500
    ties.append(('TIE-025', '4289.00', '0.00500', 'X', False))
    
    # 31.645 = 6329.00 * 0.00500
    ties.append(('TIE-026', '6329.00', '0.00500', 'B', False))
    
    # More negative even ties
    ties.append(('TIE-027', '-1124.50', '0.01000', 'B', True))
    ties.append(('TIE-028', '-2469.00', '0.00500', 'X', True))
    
    # Additional cases to get variety
    # 50.245 = 5024.50 * 0.01000
    ties.append(('TIE-029', '5024.50', '0.01000', 'B', False))
    
    # 60.445 = 12089.00 * 0.00500
    ties.append(('TIE-030', '12089.00', '0.00500', 'B', False))
    
    return ties

def main():
    ties = generate_ties()
    
    # Verify all ties meet requirements and classify them
    even_ties = []
    odd_ties = []
    negative_even_ties = []
    
    for case_id, principal, fee_rate, segment, is_negative in ties:
        principal_dec = Decimal(principal)
        fee_rate_dec = Decimal(fee_rate)
        
        # Verify it's an exact tie
        if not is_exact_tie(principal_dec, fee_rate_dec):
            print(f"ERROR: {case_id} is not an exact tie", file=sys.stderr)
            sys.exit(1)
        
        # Verify absolute base fee >= 10.00
        abs_fee = abs(principal_dec * fee_rate_dec)
        if abs_fee < Decimal('10.00'):
            print(f"ERROR: {case_id} has fee {abs_fee} < 10.00", file=sys.stderr)
            sys.exit(1)
        
        # Classify by preceding digit (even/odd)
        digit = get_preceding_digit(principal_dec, fee_rate_dec)
        if digit % 2 == 0:
            even_ties.append(case_id)
            if is_negative:
                negative_even_ties.append(case_id)
        else:
            odd_ties.append(case_id)
    
    # Verify counts
    if len(even_ties) < 16:
        print(f"ERROR: Only {len(even_ties)} even ties, need at least 16", file=sys.stderr)
        sys.exit(1)
    
    if len(odd_ties) < 4:
        print(f"ERROR: Only {len(odd_ties)} odd ties, need at least 4", file=sys.stderr)
        sys.exit(1)
    
    if len(negative_even_ties) < 6:
        print(f"ERROR: Only {len(negative_even_ties)} negative even ties, need at least 6", file=sys.stderr)
        sys.exit(1)
    
    # Write CSV
    output_path = 'samples/credit-fees/fixtures/rounding-ties.csv'
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['CASE-ID', 'PRINCIPAL', 'FEE-RATE', 'DURATION-MONTHS', 'CUSTOMER-SEGMENT', 'INCOME'])
        
        for case_id, principal, fee_rate, segment, _ in ties:
            # Use fixed values for eligibility: INCOME=50000.00, DURATION=24
            writer.writerow([case_id, principal, fee_rate, '24', segment, '50000.00'])
    
    print(f"Generated {len(ties)} tie cases:")
    print(f"  Even-digit ties: {len(even_ties)}")
    print(f"  Odd-digit control ties: {len(odd_ties)}")
    print(f"  Negative even-digit ties: {len(negative_even_ties)}")
    print(f"Written to {output_path}")

if __name__ == '__main__':
    main()
