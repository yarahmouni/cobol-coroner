"""Case generation module for Coroner."""

import csv
import hashlib
import random
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from coroner.parse.schema import GeneratorScriptError, Schema, SchemaColumn

# Generator version for regression testing
# Increment when generation logic changes in a way that affects output bytes
GENERATOR_VERSION = 1


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
    # Check if schema opts into product-pairs tie strategy (T2 trap)
    tie_strategy = getattr(schema, 'tie_strategy', None)
    if tie_strategy == 'product_pairs':
        return generate_ties_product_pairs(schema, num_ties, rng)
    
    # Default credit-fees logic
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


def generate_ties_product_pairs(schema: Schema, num_ties: int, rng: random.Random) -> list[dict]:
    """
    Generate rounding tie cases from products of input pairs (T2 trap logic).
    
    Finds the first two decimal input columns in the schema and generates ties
    from their product. For PRINCIPAL (scale 2) x RATE (scale 5), product scale
    is 7, so ties occur when the product has exactly 0.005 at the third decimal.
    
    Construction: RATE = 0.01000, PRINCIPAL chosen so the product ends in
    ...X.5000000 where X is the even/odd preceding digit.
    
    About 2/3 should have even preceding digits (will diverge under HALF_EVEN).
    Mix positive and negative.
    """
    ties = []
    
    # Find the first two decimal input columns from the schema
    decimal_cols = [col for col in schema.input_columns if col.type == 'decimal']
    
    if len(decimal_cols) < 2:
        return ties
    
    # Use the first two decimal columns
    principal_col = decimal_cols[0]
    rate_col = decimal_cols[1]
    
    # Target: about 2/3 even-digit ties, 1/3 odd-digit controls
    num_even = int(num_ties * 2 / 3)
    num_odd = num_ties - num_even
    
    # Use RATE = 0.01000 for most ties
    rate = Decimal("0.01000")
    
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
        
        # Make half negative if column is signed
        if principal_col.signed and i < num_even // 2 and principal >= Decimal("10.00"):
            principal = -principal
        
        # Verify it's a tie
        product = principal * rate
        product_str = str(abs(product))
        
        ties.append({
            principal_col.name: principal,
            rate_col.name: rate,
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
        
        # Make half negative if column is signed
        if principal_col.signed and i < num_odd // 2 and principal >= Decimal("10.00"):
            principal = -principal
        
        ties.append({
            principal_col.name: principal,
            rate_col.name: rate,
            'tie_type': 'odd',
            'product': principal * rate
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


def generate_packed_hex(rng: random.Random, digits: int, sign_nibbles: list[str], sign_weights: list[int] | None = None) -> str:
    """
    Generate a packed hex string for COMP-3 testing.
    
    Args:
        rng: Random number generator
        digits: Number of digit nibbles (9 for S9(7)V99)
        sign_nibbles: Allowed sign nibbles (e.g., ['C', 'D', 'F'])
        sign_weights: Optional weights for sign nibbles
        
    Returns:
        Hex string with digits+1 hex characters (digit nibbles + sign nibble)
    """
    # Generate digit nibbles
    digit_str = ''
    for _ in range(digits):
        digit = draw_int(rng, 0, 9)
        digit_str += str(digit)
    
    # Choose sign nibble
    if sign_weights:
        if len(sign_weights) != len(sign_nibbles):
            raise ValueError(f"sign_weights length {len(sign_weights)} != sign_nibbles length {len(sign_nibbles)}")
        
        # Build cumulative weights
        cumulative = []
        total = 0
        for w in sign_weights:
            if w <= 0:
                raise ValueError("sign_weights must be positive integers")
            total += w
            cumulative.append(total)
        
        # Draw a random number in [0, total)
        r = rng.random() * total
        
        # Find which bucket r falls into
        idx = 0
        for i, cumul in enumerate(cumulative):
            if r < cumul:
                idx = i
                break
        
        sign_nibble = sign_nibbles[idx]
    else:
        # Uniform sampling
        idx = draw_int(rng, 0, len(sign_nibbles) - 1)
        sign_nibble = sign_nibbles[idx]
    
    return digit_str + sign_nibble


def generate_zoned_overpunch(rng: random.Random, digits: int, convention: str, sign_share: float) -> str:
    """
    Generate a zoned decimal string with EBCDIC overpunch convention.
    
    Args:
        rng: Random number generator
        digits: Total number of digit positions (e.g., 9 for S9(7)V99)
        convention: Must be "EBCDIC"
        sign_share: Probability of negative sign (0.5 = half negative)
        
    Returns:
        String with digits characters, last character carrying the sign per EBCDIC overpunch table
        
    EBCDIC overpunch table (docs/evidence/gnucobol-encodings.md):
        '{' and 'A' to 'I' = +0 to +9
        '}' and 'J' to 'R' = -0 to -9
        Plain digit '0' to '9' = positive
    """
    if convention != "EBCDIC":
        raise ValueError(f"Only EBCDIC convention is supported, got {convention}")
    
    # Generate all but last digit
    digit_str = ''
    for _ in range(digits - 1):
        digit = draw_int(rng, 0, 9)
        digit_str += str(digit)
    
    # Last digit carries the sign
    last_digit = draw_int(rng, 0, 9)
    
    # Determine sign
    is_negative = rng.random() < sign_share
    
    if is_negative:
        # Use EBCDIC negative overpunch: } = -0, J to R = -1 to -9
        if last_digit == 0:
            last_char = '}'
        else:
            # J=1, K=2, ..., R=9
            last_char = chr(ord('J') + last_digit - 1)
    else:
        # Use EBCDIC positive overpunch: { = +0, A to I = +1 to +9
        if last_digit == 0:
            last_char = '{'
        else:
            # A=1, B=2, ..., I=9
            last_char = chr(ord('A') + last_digit - 1)
    
    return digit_str + last_char


def generate_dirty_numeric(
    rng: random.Random, 
    digits: int, 
    dirty_chars: list[str], 
    clean_weight: float = 0.7,
    dirty_weight: float = 0.3
) -> str:
    """
    Generate a numeric string that may contain one invalid character.
    
    Used for testing REDEFINES of invalid numeric data (trap T5).
    
    Args:
        rng: Random number generator
        digits: Total number of digit positions
        dirty_chars: List of non-digit characters to inject (e.g., ['A', 'B', 'J', 'Z', ' '])
        clean_weight: Probability of generating clean digits only
        dirty_weight: Probability of generating one invalid character
        
    Returns:
        String with digits characters, either all digits or one replaced with a dirty char
    """
    # Decide if this value should be clean or dirty
    is_clean = rng.random() < (clean_weight / (clean_weight + dirty_weight))
    
    # Generate base digits
    digit_str = ''
    for _ in range(digits):
        digit = draw_int(rng, 0, 9)
        digit_str += str(digit)
    
    if is_clean or not dirty_chars:
        # Return clean numeric string
        return digit_str
    else:
        # Inject one invalid character at a random position
        # (not the first position to keep it readable)
        pos = draw_int(rng, 1, digits - 1) if digits > 1 else 0
        dirty_char = dirty_chars[draw_int(rng, 0, len(dirty_chars) - 1)]
        
        # Replace the digit at pos with the dirty character
        char_list = list(digit_str)
        char_list[pos] = dirty_char
        return ''.join(char_list)


@dataclass(frozen=True)
class GeneratorScript:
    """
    The bytes of a generator script and their SHA-256, taken from one read.

    The bytes that are executed and the hash that is recorded in inputs.json and
    the certificate both come from this object, so they cannot differ.
    """
    source: bytes
    sha256: str

    @classmethod
    def read(cls, schema: Schema) -> "GeneratorScript":
        """Read the schema's resolved generator script once."""
        source = Path(schema.generator_script_path).read_bytes()
        return cls(source=source, sha256=hashlib.sha256(source).hexdigest())


def generate_cases_from_script(
    schema: Schema, rng: random.Random, num_cases: int, base_dir: str,
    script: GeneratorScript | None = None
) -> str:
    """
    Generate cases with the schema's generator_script and write generated_cases.csv.

    The script path was checked when the schema was loaded (inside the schema
    folder, symlinks resolved). The bytes are compiled and executed in a fresh
    namespace: no import machinery, no __pycache__ written next to the script.
    Pass the GeneratorScript that was read for hashing so that exactly those bytes
    run; when omitted, the file is read here (once). It must define
    generate_cases(schema, rng, num_cases) and return one dict per case with
    exactly the schema's input column names. str, int and Decimal values are
    accepted (Decimal is written at the column's scale); anything else is an error.

    Returns:
        Path to generated_cases.csv (LF line endings, UTF-8)
    """
    script_path = Path(schema.generator_script_path)
    if script is None:
        script = GeneratorScript.read(schema)
    namespace = {"__name__": "coroner_generator_script", "__file__": str(script_path)}
    exec(compile(script.source, str(script_path), "exec"), namespace)
    script_fn = namespace.get("generate_cases")
    if not callable(script_fn):
        raise GeneratorScriptError(f"generator script has no generate_cases function: {schema.generator_script}")
    
    cases = script_fn(schema, rng, num_cases)
    if not isinstance(cases, list) or len(cases) != num_cases:
        raise GeneratorScriptError(f"generator script must return a list of {num_cases} cases")
    
    columns = {col.name: col for col in schema.input_columns}
    rows = []
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or set(case) != set(columns):
            raise GeneratorScriptError(f"generator script case {index} does not have exactly the schema input columns")
        row = {}
        for name, value in case.items():
            if isinstance(value, Decimal) and columns[name].scale is not None:
                text = format_decimal(value, columns[name].scale, columns[name].signed)
            elif type(value) in (str, int):
                text = str(value)
            else:
                raise GeneratorScriptError(f"generator script case {index} column {name}: unsupported value type {type(value).__name__}")
            if '\n' in text or '\r' in text:
                raise GeneratorScriptError(f"generator script case {index} column {name}: line break in value")
            row[name] = text
        rows.append(row)
    
    output_dir = Path(base_dir) / 'runs' / 'temp'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'generated_cases.csv'
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[col.name for col in schema.input_columns], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    return str(output_path)


def generate_cases(
    schema: Schema,
    cobol_structure: dict,
    seed: int,
    num_cases: int,
    tie_share: float = 0.06,
    base_dir: str = ".",
    script: GeneratorScript | None = None
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
        script: GeneratorScript read for hashing; the bytes it holds are the ones executed
        
    Returns:
        Path to generated_cases.csv
    """
    rng = random.Random(seed)
    
    # A schema with generator_script uses that script instead of the built-in generator
    if schema.generator_script_path:
        return generate_cases_from_script(schema, rng, num_cases, base_dir, script)
    
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
    
    # Check if this is a credit-fees schema
    credit_fees_columns = {'PRINCIPAL', 'FEE-RATE', 'DURATION-MONTHS', 'CUSTOMER-SEGMENT', 'INCOME'}
    schema_column_names = {col.name for col in schema.input_columns}
    is_credit_fees = credit_fees_columns.issubset(schema_column_names)
    
    # Add tie cases first
    if is_credit_fees:
        # Credit-fees specific tie filling (preserves gen_b5f10da hash)
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
    else:
        # Generic tie filling for other schemas (T2, T3, etc.)
        for tie_spec in tie_cases:
            row = {}
            
            # Set columns from tie_spec (column names are determined by the schema)
            for col in schema.input_columns:
                if col.name == 'CASE-ID':
                    continue  # Added later
                
                if col.name in tie_spec and col.name not in ['tie_type', 'product']:
                    # This column is set by the tie spec
                    if col.type == 'decimal':
                        row[col.name] = format_decimal(tie_spec[col.name], col.scale, col.signed)
                    else:
                        row[col.name] = str(tie_spec[col.name])
                else:
                    # Fill other fields randomly based on column type
                    if col.type == 'decimal':
                        value = draw_decimal_by_magnitude(rng, col.pic.count('9'), col.scale, col.signed)
                        row[col.name] = format_decimal(value, col.scale, col.signed)
                    elif col.type == 'integer':
                        max_val = 10 ** col.pic.count('9') - 1 if col.pic else 999
                        row[col.name] = str(draw_int(rng, 0, max_val))
                    elif col.type == 'string':
                        # Check for packed_hex spec
                        if hasattr(col, 'packed_hex') and col.packed_hex:
                            digits = col.packed_hex['digits']
                            sign_nibbles = col.packed_hex['sign_nibbles']
                            sign_weights = col.packed_hex.get('sign_weights')
                            row[col.name] = generate_packed_hex(rng, digits, sign_nibbles, sign_weights)
                        elif hasattr(col, 'zoned_overpunch') and col.zoned_overpunch:
                            digits = col.zoned_overpunch['digits']
                            convention = col.zoned_overpunch['convention']
                            sign_share = col.zoned_overpunch.get('sign_share', 0.5)
                            row[col.name] = generate_zoned_overpunch(rng, digits, convention, sign_share)
                        elif hasattr(col, 'domain') and col.domain == 'dirty_numeric':
                            # Generate numeric text with possible invalid characters
                            # For string PIC X(n), extract the length
                            import re
                            pic_match = re.search(r'X\((\d+)\)', col.pic) if col.pic else None
                            if pic_match:
                                digits = int(pic_match.group(1))
                            elif col.pic == 'X':
                                digits = 1
                            else:
                                digits = 7  # Default
                            dirty_chars = getattr(col, 'dirty_chars', ['A', 'B', 'J', 'Z', ' '])
                            domain_weights = getattr(col, 'domain_weights', {})
                            clean_weight = domain_weights.get('clean', 0.7)
                            dirty_weight = domain_weights.get('dirty', 0.3)
                            row[col.name] = generate_dirty_numeric(rng, digits, dirty_chars, clean_weight, dirty_weight)
                        else:
                            row[col.name] = ''
            
            rows.append(row)
    
    # Generate random cases for the rest
    num_random = num_cases - len(rows)
    
    if is_credit_fees:
        # Original credit-fees generation logic (exact reproduction of gen_b5f10da)
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
    else:
        # Generic generation for other schemas (T2, T3, etc.)
        for i in range(num_random):
            row = {}
            
            for col in schema.input_columns:
                if col.name == 'CASE-ID':
                    continue  # Added later
                
                if col.type == 'decimal':
                    signed = col.pic and 'S' in col.pic
                    # Count integer digits from PIC
                    if col.pic:
                        # V9(5) means no integer part, V is the decimal point
                        if col.pic.startswith('V'):
                            max_int_digits = 0
                        else:
                            # Extract digit count from PIC (e.g., "S9(9)V99" -> 9)
                            import re
                            match = re.search(r'9\((\d+)\)', col.pic)
                            if match:
                                # This is the integer part if before V
                                pic_part = col.pic.split('V')[0] if 'V' in col.pic else col.pic
                                match = re.search(r'9\((\d+)\)', pic_part)
                                max_int_digits = int(match.group(1)) if match else 0
                            else:
                                # Count 9s before V
                                pic_part = col.pic.split('V')[0] if 'V' in col.pic else col.pic
                                max_int_digits = pic_part.count('9')
                    else:
                        max_int_digits = 9
                    
                    value = draw_decimal_by_magnitude(rng, max_int_digits, col.scale, signed)
                    row[col.name] = format_decimal(value, col.scale, signed)
                    
                elif col.type == 'integer':
                    max_val = 10 ** col.pic.count('9') - 1 if col.pic else 999
                    row[col.name] = str(draw_int(rng, 0, max_val))
                    
                elif col.type == 'string':
                    # Check for packed_hex spec
                    if hasattr(col, 'packed_hex') and col.packed_hex:
                        digits = col.packed_hex['digits']
                        sign_nibbles = col.packed_hex['sign_nibbles']
                        sign_weights = col.packed_hex.get('sign_weights')
                        row[col.name] = generate_packed_hex(rng, digits, sign_nibbles, sign_weights)
                    elif hasattr(col, 'zoned_overpunch') and col.zoned_overpunch:
                        digits = col.zoned_overpunch['digits']
                        convention = col.zoned_overpunch['convention']
                        sign_share = col.zoned_overpunch.get('sign_share', 0.5)
                        row[col.name] = generate_zoned_overpunch(rng, digits, convention, sign_share)
                    elif hasattr(col, 'domain') and col.domain == 'dirty_numeric':
                        # Generate numeric text with possible invalid characters
                        # For string PIC X(n), extract the length
                        import re
                        pic_match = re.search(r'X\((\d+)\)', col.pic) if col.pic else None
                        if pic_match:
                            digits = int(pic_match.group(1))
                        elif col.pic == 'X':
                            digits = 1
                        else:
                            digits = 7  # Default
                        dirty_chars = getattr(col, 'dirty_chars', ['A', 'B', 'J', 'Z', ' '])
                        domain_weights = getattr(col, 'domain_weights', {})
                        clean_weight = domain_weights.get('clean', 0.7)
                        dirty_weight = domain_weights.get('dirty', 0.3)
                        row[col.name] = generate_dirty_numeric(rng, digits, dirty_chars, clean_weight, dirty_weight)
                    else:
                        # Use empty string
                        row[col.name] = ''
            
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
                    # Check for amount_range option
                    amount_range = getattr(col, 'amount_range', None)
                    negative_share = getattr(col, 'negative_share', None)
                    
                    if amount_range:
                        # Draw from specified range
                        min_val = Decimal(str(amount_range['min']))
                        max_val = Decimal(str(amount_range['max']))
                        value = draw_decimal(rng, min_val, max_val, col.scale or 0)
                        
                        # Apply negative_share if specified
                        if negative_share is not None and rng.random() < negative_share:
                            value = -value
                        
                        row[col.name] = format_decimal(value, col.scale or 0, col.signed)
                    else:
                        # Original magnitude-based drawing
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
                    # Check for packed_hex spec first
                    packed_hex = getattr(col, 'packed_hex', None)
                    if packed_hex:
                        # Generate packed hex string for COMP-3 testing
                        digits = packed_hex['digits']
                        sign_nibbles = packed_hex['sign_nibbles']
                        sign_weights = packed_hex.get('sign_weights')
                        row[col.name] = generate_packed_hex(rng, digits, sign_nibbles, sign_weights)
                    else:
                        # Check if domain is provided
                        domain = getattr(col, 'domain', None)
                        if domain:
                            # Check for domain_weights
                            domain_weights = getattr(col, 'domain_weights', None)
                            if domain_weights:
                                # Weighted sampling using cumulative weights
                                if len(domain_weights) != len(domain):
                                    raise ValueError(f"domain_weights length {len(domain_weights)} != domain length {len(domain)} for column {col.name}")
                                
                                # Build cumulative weights
                                cumulative = []
                                total = 0
                                for w in domain_weights:
                                    if w <= 0:
                                        raise ValueError(f"domain_weights must be positive integers for column {col.name}")
                                    total += w
                                    cumulative.append(total)
                                
                                # Draw a random number in [0, total)
                                r = rng.random() * total
                                
                                # Find which bucket r falls into
                                idx = 0
                                for i, cumul in enumerate(cumulative):
                                    if r < cumul:
                                        idx = i
                                        break
                                
                                row[col.name] = domain[idx]
                            else:
                                # Uniform sampling
                                idx = draw_int(rng, 0, len(domain) - 1)
                                row[col.name] = domain[idx]
                        else:
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
