"""Case generation module for Coroner."""

import csv
import random
from decimal import Decimal
from pathlib import Path

from coroner.parse.schema import Schema, SchemaColumn


def draw_int(rng: random.Random, lo: int, hi: int) -> int:
    """
    Draw an integer in [lo, hi] from rng.random() only.
    
    Uses only rng.random() for reproducibility per D-30.
    """
    if lo > hi:
        raise ValueError(f"Invalid range: lo={lo}, hi={hi}")
    return lo + int(rng.random() * (hi - lo + 1))


def draw_decimal(rng: random.Random, lo: Decimal, hi: Decimal, scale: int) -> Decimal:
    """
    Draw a decimal in [lo, hi] at the given scale from rng.random() only.
    
    Uses only rng.random() for reproducibility per D-30.
    """
    if lo > hi:
        raise ValueError(f"Invalid range: lo={lo}, hi={hi}")
    step = Decimal(10) ** -scale
    n = int((hi - lo) / step)
    offset = draw_int(rng, 0, n)
    return lo + step * offset


def format_decimal(value: Decimal, scale: int, signed: bool) -> str:
    """
    Format a decimal value to canonical text format.
    
    Canonical format: optional leading '-', digits, optional '.', more digits.
    No leading '+', no exponent, no spaces.
    """
    # Quantize to the exact scale
    quantized = value.quantize(Decimal(10) ** -scale)
    s = str(quantized)
    
    # Remove leading '+'
    if s.startswith('+'):
        s = s[1:]
    
    return s


def generate_case_id(index: int, max_length: int = 10) -> str:
    """Generate a case ID in format GEN-00001, zero-padded to fit max_length."""
    # Format: GEN-NNNNN
    # Reserve 4 characters for "GEN-", rest for the number
    num_digits = max_length - 4
    return f"GEN-{index:0{num_digits}d}"


def generate_limits(schema: Schema, rng: random.Random) -> list[dict]:
    """Generate limit cases (min/max for each PIC)."""
    cases = []
    
    # For each numeric input column, generate min and max values
    for col in schema.input_columns:
        if col.type == 'decimal':
            signed, total_digits, scale = col.signed, 0, col.scale
            # Compute max based on PIC
            # S9(9)V99 -> -999999999.99 to 999999999.99
            # Extract digits from PIC
            import re
            digit_match = re.search(r'9\((\d+)\)', col.pic)
            if digit_match:
                integer_digits = int(digit_match.group(1))
            else:
                # Count individual 9s
                integer_digits = col.pic.count('9') - scale
            
            max_val = Decimal(10 ** integer_digits) - Decimal(10) ** -scale
            if signed:
                cases.append({'column': col.name, 'value': -max_val})
            cases.append({'column': col.name, 'value': max_val})
            
        elif col.type == 'integer':
            # 9(3) -> 0 to 999
            import re
            digit_match = re.search(r'9\((\d+)\)', col.pic)
            if digit_match:
                num_digits = int(digit_match.group(1))
                max_val = 10 ** num_digits - 1
                cases.append({'column': col.name, 'value': 0})
                cases.append({'column': col.name, 'value': max_val})
    
    return cases


def generate_boundaries(schema: Schema, constants: list[Decimal], rng: random.Random) -> list[dict]:
    """Generate boundary cases around constants."""
    cases = []
    
    for constant in constants:
        # For each numeric input with compatible scale
        for col in schema.input_columns:
            if col.type == 'decimal' and col.scale is not None:
                # Generate C - delta, C, C + delta
                delta = Decimal(10) ** -col.scale
                for offset in [-delta, Decimal(0), delta]:
                    val = constant + offset
                    # Check if in valid range
                    import re
                    digit_match = re.search(r'9\((\d+)\)', col.pic)
                    if digit_match:
                        integer_digits = int(digit_match.group(1))
                        max_val = Decimal(10 ** integer_digits) - delta
                        if col.signed:
                            min_val = -max_val
                        else:
                            min_val = Decimal(0)
                        
                        if min_val <= val <= max_val:
                            cases.append({'column': col.name, 'value': val, 'constant': constant})
            elif col.type == 'integer':
                # Integer boundaries
                for offset in [-1, 0, 1]:
                    val = int(constant) + offset
                    if val >= 0:
                        cases.append({'column': col.name, 'value': val, 'constant': constant})
    
    return cases


def generate_ties(schema: Schema, num_ties: int, rng: random.Random) -> list[dict]:
    """
    Generate rounding tie cases from products of input pairs.
    
    For PRINCIPAL (scale 2) x FEE-RATE (scale 5), product scale is 7.
    Output scale is 2, so ties occur when the product has exactly 0.005 at the third decimal.
    
    Construction: FEE-RATE = 0.01000 (or 0.00100, 0.10000), PRINCIPAL chosen so
    the product ends in ...X.5000000 where X is the even/odd preceding digit.
    
    For FEE-RATE = 0.01000:
        PRINCIPAL ending in .50 gives product with tenths digit 5
        E.g., 1234.50 x 0.01000 = 12.34500 (preceding digit 4, even)
        E.g., 1235.50 x 0.01000 = 12.35500 (preceding digit 5, odd)
    
    About 2/3 should have even preceding digits (will diverge under HALF_EVEN).
    Mix positive and negative, segment B or non-matching letter (no discount).
    """
    ties = []
    
    # Find PRINCIPAL and FEE-RATE columns
    principal_col = None
    fee_rate_col = None
    for col in schema.input_columns:
        if col.name == 'PRINCIPAL':
            principal_col = col
        elif col.name == 'FEE-RATE':
            fee_rate_col = col
    
    if not principal_col or not fee_rate_col:
        return ties
    
    # Target: about 2/3 even-digit ties, 1/3 odd-digit controls
    num_even = int(num_ties * 2 / 3)
    num_odd = num_ties - num_even
    
    # Use FEE-RATE = 0.01000 for most ties
    fee_rate = Decimal("0.01000")
    
    # Generate even-digit ties
    for i in range(num_even):
        # Choose PRINCIPAL so product has even preceding digit
        # For 0.01000, PRINCIPAL = XXXX.50 gives product = XX.XX500
        # The preceding digit is the units digit of the product
        # which is the hundreds digit of PRINCIPAL
        
        # Choose random even hundreds digit (0, 2, 4, 6, 8)
        even_hundreds = [0, 2, 4, 6, 8][i % 5]
        
        # Build PRINCIPAL: [thousands][even_hundreds][tens][units].50
        thousands = draw_int(rng, 1, 9)
        tens = draw_int(rng, 0, 9)
        units = draw_int(rng, 0, 9)
        
        principal = Decimal(f"{thousands}{even_hundreds}{tens}{units}.50")
        
        # Make half negative, ensure absolute value >= 10.00 (minimum fee threshold)
        if i < num_even // 2 and principal >= Decimal("10.00"):
            principal = -principal
        
        # Verify it's a tie
        product = principal * fee_rate
        product_str = str(abs(product))
        
        ties.append({
            'PRINCIPAL': principal,
            'FEE-RATE': fee_rate,
            'tie_type': 'even',
            'product': product
        })
    
    # Generate odd-digit control ties
    for i in range(num_odd):
        # Choose PRINCIPAL so product has odd preceding digit
        odd_hundreds = [1, 3, 5, 7, 9][i % 5]
        
        thousands = draw_int(rng, 1, 9)
        tens = draw_int(rng, 0, 9)
        units = draw_int(rng, 0, 9)
        
        principal = Decimal(f"{thousands}{odd_hundreds}{tens}{units}.50")
        
        # Make half negative
        if i < num_odd // 2 and principal >= Decimal("10.00"):
            principal = -principal
        
        ties.append({
            'PRINCIPAL': principal,
            'FEE-RATE': fee_rate,
            'tie_type': 'odd',
            'product': principal * fee_rate
        })
    
    return ties


def generate_string_values(col: SchemaColumn, cobol_literals: set[str], rng: random.Random) -> list[str]:
    """Generate string values including COBOL literals and a non-matching value."""
    values = list(cobol_literals)
    
    # Add empty value
    values.append('')
    
    # Add a non-matching value (for WHEN OTHER testing)
    # Choose a letter not in the literals
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    for letter in alphabet:
        if letter not in cobol_literals:
            values.append(letter)
            break
    
    return values


def draw_decimal_by_magnitude(rng: random.Random, max_int_digits: int, scale: int, signed: bool) -> Decimal:
    """
    Draw a decimal by magnitude to avoid excessive overflow cases.
    
    First draws the number of integer digits uniformly from 0 to max_int_digits,
    then draws the digits, then the decimals at scale.
    
    Args:
        rng: Random number generator
        max_int_digits: Maximum number of integer digits (from PIC)
        scale: Number of decimal places
        signed: Whether the value can be negative
        
    Returns:
        A decimal value drawn by magnitude
    """
    # Draw number of integer digits (0 to max_int_digits)
    num_int_digits = draw_int(rng, 0, max_int_digits)
    
    if num_int_digits == 0:
        # Value is in [0, 1) or (-1, 0] if signed
        integer_part = 0
    else:
        # Draw integer part with exactly num_int_digits digits
        # First digit is 1-9, rest are 0-9
        first_digit = draw_int(rng, 1, 9)
        integer_part = first_digit
        for _ in range(num_int_digits - 1):
            digit = draw_int(rng, 0, 9)
            integer_part = integer_part * 10 + digit
    
    # Draw decimal part
    if scale > 0:
        max_fractional = 10 ** scale - 1
        fractional_part = draw_int(rng, 0, max_fractional)
        value = Decimal(integer_part) + Decimal(fractional_part) / Decimal(10 ** scale)
    else:
        value = Decimal(integer_part)
    
    # Apply sign
    if signed and rng.random() < 0.5:
        value = -value
    
    return value


def generate_cases(
    schema: Schema,
    cobol_structure: dict,
    seed: int,
    num_cases: int,
    tie_share: float = 0.06,
    base_dir: str = "."
) -> str:
    """
    Generate test cases from schema and COBOL structure.
    
    Args:
        schema: Parsed schema with input/output columns
        cobol_structure: Parsed COBOL constants, paragraphs, branches
        seed: Fixed seed for reproducibility
        num_cases: Total number of cases to generate
        tie_share: Fraction of cases that are rounding ties (default 0.06)
        base_dir: Base directory for runs/ (default current directory)
        
    Returns:
        Path to generated_cases.csv
    """
    rng = random.Random(seed)
    
    # Check if we are generating multiple rows per case
    if schema.case_rows:
        return generate_batch_cases(schema, cobol_structure, seed, num_cases, tie_share, base_dir)
    
    # Original single-row-per-case logic
    # Calculate number of targeted cases
    num_ties = int(num_cases * tie_share)
    
    # Generate targeted cases
    tie_cases = generate_ties(schema, num_ties, rng)
    
    # Build complete rows
    rows = []
    
    # Add tie cases first
    for tie_spec in tie_cases:
        row = {}
        
        # Set PRINCIPAL and FEE-RATE from tie
        row['PRINCIPAL'] = format_decimal(tie_spec['PRINCIPAL'], 2, True)
        row['FEE-RATE'] = format_decimal(tie_spec['FEE-RATE'], 5, False)
        
        # Set other fields randomly
        # DURATION-MONTHS: random in [1, 999]
        row['DURATION-MONTHS'] = str(draw_int(rng, 1, 999))
        
        # CUSTOMER-SEGMENT: 'B' or non-matching letter (no discount)
        # Use 'B' for half, 'Z' (non-matching) for the other half
        segment = 'B' if len(rows) % 2 == 0 else 'Z'
        row['CUSTOMER-SEGMENT'] = segment
        
        # INCOME: random eligible value (>= 25000.00) for half, random for others
        if len(rows) % 2 == 0:
            income_int_digits = draw_int(rng, 5, 9)
            income = draw_decimal_by_magnitude(rng, income_int_digits, 2, False)
            if income < Decimal("25000.00"):
                income = Decimal("25000.00") + income
        else:
            income_int_digits = draw_int(rng, 0, 9)
            income = draw_decimal_by_magnitude(rng, income_int_digits, 2, False)
        row['INCOME'] = format_decimal(income, 2, False)
        
        rows.append(row)
    
    # Generate random cases for the rest
    num_random = num_cases - len(rows)
    
    # Customer segment literals from COBOL (EVALUATE on 'P', 'S', 'B')
    segment_values = ['P', 'S', 'B', 'Z', '']
    
    for i in range(num_random):
        row = {}
        
        # PRINCIPAL: S9(9)V99, scale 2, signed
        # Draw by magnitude to avoid excessive overflow cases
        principal_int_digits = draw_int(rng, 0, 9)
        principal = draw_decimal_by_magnitude(rng, principal_int_digits, 2, True)
        row['PRINCIPAL'] = format_decimal(principal, 2, True)
        
        # FEE-RATE: V9(5), scale 5, unsigned
        # This is always < 1, so magnitude doesn't apply
        fee_rate = draw_decimal(rng, Decimal("0.00000"), Decimal("0.99999"), 5)
        row['FEE-RATE'] = format_decimal(fee_rate, 5, False)
        
        # DURATION-MONTHS: 9(3), unsigned integer [0, 999]
        row['DURATION-MONTHS'] = str(draw_int(rng, 0, 999))
        
        # CUSTOMER-SEGMENT: X(1), from literals
        idx = draw_int(rng, 0, len(segment_values) - 1)
        row['CUSTOMER-SEGMENT'] = segment_values[idx]
        
        # INCOME: 9(9)V99, scale 2, unsigned
        # Draw by magnitude
        income_int_digits = draw_int(rng, 0, 9)
        income = draw_decimal_by_magnitude(rng, income_int_digits, 2, False)
        row['INCOME'] = format_decimal(income, 2, False)
        
        rows.append(row)
    
    # Add CASE-ID to all rows
    for idx, row in enumerate(rows, start=1):
        case_id = generate_case_id(idx, 10)
        row['CASE-ID'] = case_id
    
    # Write CSV with LF line endings
    output_dir = Path(base_dir) / 'runs' / 'temp'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'generated_cases.csv'
    
    # Get column names from schema
    column_names = [col.name for col in schema.input_columns]
    
    # Write with explicit LF
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=column_names, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    
    return str(output_path)


def generate_batch_cases(
    schema: Schema,
    cobol_structure: dict,
    seed: int,
    num_cases: int,
    tie_share: float,
    base_dir: str
) -> str:
    """
    Generate batch cases with multiple rows per CASE-ID.
    
    When schema.case_rows is declared, emit between min and max input rows
    per case, all with the same CASE-ID.
    """
    rng = random.Random(seed)
    
    min_rows = schema.case_rows['min']
    max_rows = schema.case_rows['max']
    
    all_rows = []
    
    for case_idx in range(1, num_cases + 1):
        case_id = generate_case_id(case_idx, 10)
        
        # Draw number of rows for this case using random()
        num_rows = min_rows + int(rng.random() * (max_rows - min_rows + 1))
        if num_rows > max_rows:
            num_rows = max_rows
        
        # Generate num_rows input rows for this case
        for _ in range(num_rows):
            row = {'CASE-ID': case_id}
            
            # Generate values for all other input columns
            for col in schema.input_columns:
                if col.name == 'CASE-ID':
                    continue
                
                if col.type == 'decimal':
                    # Draw by magnitude
                    import re
                    digit_match = re.search(r'9\((\d+)\)', col.pic)
                    if digit_match:
                        max_int_digits = int(digit_match.group(1))
                    else:
                        max_int_digits = col.pic.count('9') - (col.scale or 0)
                    
                    value = draw_decimal_by_magnitude(rng, max_int_digits, col.scale or 0, col.signed)
                    row[col.name] = format_decimal(value, col.scale or 0, col.signed)
                
                elif col.type == 'integer':
                    import re
                    digit_match = re.search(r'9\((\d+)\)', col.pic)
                    if digit_match:
                        max_val = 10 ** int(digit_match.group(1)) - 1
                    else:
                        max_val = 10 ** col.pic.count('9') - 1
                    value = draw_int(rng, 0, max_val)
                    row[col.name] = str(value)
                
                elif col.type == 'string':
                    # Draw random string or empty
                    import re
                    len_match = re.search(r'X\((\d+)\)', col.pic)
                    if len_match:
                        max_len = int(len_match.group(1))
                    else:
                        max_len = 1
                    
                    # Simple random letter or empty
                    if rng.random() < 0.5:
                        # Generate a random uppercase letter or digit
                        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -'
                        length = draw_int(rng, 0, min(max_len, 3))
                        value = ''.join(chars[draw_int(rng, 0, len(chars) - 1)] for _ in range(length))
                        row[col.name] = value
                    else:
                        row[col.name] = ''
            
            all_rows.append(row)
    
    # Write CSV with LF line endings
    output_dir = Path(base_dir) / 'runs' / 'temp'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'generated_cases.csv'
    
    # Get column names from schema
    column_names = [col.name for col in schema.input_columns]
    
    # Write with explicit LF
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=column_names, lineterminator='\n')
        writer.writeheader()
        writer.writerows(all_rows)
    
    return str(output_path)
