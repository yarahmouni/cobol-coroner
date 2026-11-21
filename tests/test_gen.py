"""Tests for case generation module."""

import csv
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from coroner.gen import generate_cases, draw_int, draw_decimal, generate_case_id
from coroner.parse.schema import GeneratorScriptError, load_schema


def test_draw_int_in_range():
    """Test that draw_int produces values in the specified range."""
    import random
    rng = random.Random(42)
    
    for _ in range(100):
        val = draw_int(rng, 10, 20)
        assert 10 <= val <= 20


def test_draw_int_deterministic():
    """Test that draw_int is deterministic with the same seed."""
    import random
    
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    
    values1 = [draw_int(rng1, 0, 100) for _ in range(10)]
    values2 = [draw_int(rng2, 0, 100) for _ in range(10)]
    
    assert values1 == values2


def test_draw_decimal_in_range():
    """Test that draw_decimal produces values in the specified range."""
    import random
    rng = random.Random(42)
    
    for _ in range(100):
        val = draw_decimal(rng, Decimal("0.00"), Decimal("10.00"), 2)
        assert Decimal("0.00") <= val <= Decimal("10.00")
        # Check scale
        assert val.as_tuple().exponent >= -2


def test_draw_decimal_deterministic():
    """Test that draw_decimal is deterministic with the same seed."""
    import random
    
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    
    values1 = [draw_decimal(rng1, Decimal("0.00"), Decimal("100.00"), 2) for _ in range(10)]
    values2 = [draw_decimal(rng2, Decimal("0.00"), Decimal("100.00"), 2) for _ in range(10)]
    
    assert values1 == values2


def test_generate_case_id_format():
    """Test that case IDs are formatted correctly."""
    case_id = generate_case_id(1, 10)
    assert case_id == "GEN-000001"
    
    case_id = generate_case_id(42, 10)
    assert case_id == "GEN-000042"
    
    case_id = generate_case_id(999999, 10)
    assert case_id == "GEN-999999"


def test_generate_cases_deterministic():
    """Test that generate_cases produces byte-identical output with the same seed."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [Decimal('10.00'), Decimal('25000.00'), Decimal('12')],
        'paragraphs': {},
        'branches': []
    }
    
    # Generate with seed 42 twice
    path1 = generate_cases(schema, cobol_structure, seed=42, num_cases=100, tie_share=0.05)
    content1 = Path(path1).read_bytes()
    
    path2 = generate_cases(schema, cobol_structure, seed=42, num_cases=100, tie_share=0.05)
    content2 = Path(path2).read_bytes()
    
    # Should be byte-identical
    assert content1 == content2


def test_generate_cases_different_seeds():
    """Test that different seeds produce different output."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [Decimal('10.00'), Decimal('25000.00'), Decimal('12')],
        'paragraphs': {},
        'branches': []
    }
    
    # Generate with different seeds
    path1 = generate_cases(schema, cobol_structure, seed=42, num_cases=100, tie_share=0.05)
    content1 = Path(path1).read_bytes()
    
    path2 = generate_cases(schema, cobol_structure, seed=123, num_cases=100, tie_share=0.05)
    content2 = Path(path2).read_bytes()
    
    # Should be different
    assert content1 != content2


def test_generate_cases_row_count():
    """Test that generate_cases produces the correct number of rows."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [Decimal('10.00'), Decimal('25000.00'), Decimal('12')],
        'paragraphs': {},
        'branches': []
    }
    
    path = generate_cases(schema, cobol_structure, seed=42, num_cases=200, tie_share=0.05)
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 200


def test_generate_cases_case_id_format():
    """Test that CASE-ID values are correctly formatted and zero-padded."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [],
        'paragraphs': {},
        'branches': []
    }
    
    path = generate_cases(schema, cobol_structure, seed=42, num_cases=50, tie_share=0.05)
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Check first and last case IDs
    assert rows[0]['CASE-ID'] == 'GEN-000001'
    assert rows[49]['CASE-ID'] == 'GEN-000050'
    
    # All IDs should be 10 characters
    for row in rows:
        assert len(row['CASE-ID']) == 10


def test_generate_cases_canonical_format():
    """Test that numeric values use canonical format (no '+', no exponent, no spaces)."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [],
        'paragraphs': {},
        'branches': []
    }
    
    path = generate_cases(schema, cobol_structure, seed=42, num_cases=100, tie_share=0.05)
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    for row in rows:
        # PRINCIPAL can have leading '-', but no '+'
        assert '+' not in row['PRINCIPAL']
        assert 'e' not in row['PRINCIPAL'].lower()
        assert row['PRINCIPAL'].strip() == row['PRINCIPAL']
        
        # FEE-RATE should not have '+', exponent, or spaces
        assert '+' not in row['FEE-RATE']
        assert 'e' not in row['FEE-RATE'].lower()
        assert row['FEE-RATE'].strip() == row['FEE-RATE']
        
        # INCOME should not have sign (unsigned)
        assert not row['INCOME'].startswith('-')
        assert not row['INCOME'].startswith('+')


def test_generate_cases_rounding_ties():
    """Test that rounding ties are generated correctly."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [Decimal('10.00'), Decimal('25000.00'), Decimal('12')],
        'paragraphs': {},
        'branches': []
    }
    
    # Generate with 5% tie share from 2000 cases = 100 intentional ties
    path = generate_cases(schema, cobol_structure, seed=42, num_cases=2000, tie_share=0.05)
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Count intentional ties (those with FEE-RATE=0.01000)
    # Random cases may also create ties, but we only verify the intentional ones
    intentional_tie_count = 0
    even_digit_count = 0
    
    for row in rows:
        fee_rate = Decimal(row['FEE-RATE'])
        
        # Only check intentional ties (FEE-RATE=0.01000)
        if fee_rate == Decimal('0.01000'):
            principal = Decimal(row['PRINCIPAL'])
            product = principal * fee_rate
            
            # Verify it's actually a tie
            abs_product = abs(product)
            product_3dec = abs_product.quantize(Decimal('0.001'))
            remainder = product_3dec % Decimal('0.01')
            
            if remainder == Decimal('0.005'):
                intentional_tie_count += 1
                
                # Check preceding digit (units digit of the product)
                product_str = str(abs_product)
                if '.' in product_str:
                    integer_part = product_str.split('.')[0]
                    if integer_part:
                        preceding_digit = int(integer_part[-1])
                        if preceding_digit % 2 == 0:
                            even_digit_count += 1
    
    # Should have exactly 100 intentional ties (5% of 2000)
    assert 80 <= intentional_tie_count <= 120, \
        f"Expected 80-120 intentional ties, got {intentional_tie_count}"
    
    # About 2/3 should have even preceding digits
    if intentional_tie_count > 0:
        expected_even = int(intentional_tie_count * 2 / 3)
        # Allow some tolerance (within 25%)
        assert abs(even_digit_count - expected_even) <= intentional_tie_count * 0.25, \
            f"Expected ~{expected_even} even-digit ties, got {even_digit_count}"


def test_generate_cases_utf8_lf():
    """Test that generated CSV uses UTF-8 encoding and LF line endings."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [],
        'paragraphs': {},
        'branches': []
    }
    
    path = generate_cases(schema, cobol_structure, seed=42, num_cases=50, tie_share=0.05)
    
    # Read as bytes and check line endings
    content = Path(path).read_bytes()
    
    # Should not contain CRLF
    assert b'\r\n' not in content
    
    # Should contain LF
    assert b'\n' in content
    
    # Should decode as UTF-8
    text = content.decode('utf-8')
    assert text


def test_generate_cases_header_matches_schema():
    """Test that CSV header matches schema input column names."""
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [],
        'paragraphs': {},
        'branches': []
    }
    
    path = generate_cases(schema, cobol_structure, seed=42, num_cases=10, tie_share=0.05)
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
    
    expected_header = [col.name for col in schema.input_columns]
    assert header == expected_header


def test_no_forbidden_random_functions():
    """Test that coroner/gen does not use forbidden random functions."""
    # Read the gen module source
    gen_file = Path('coroner/gen/__init__.py')
    content = gen_file.read_text()
    
    # Check for forbidden functions
    forbidden = ['randrange', 'choice', 'shuffle', 'sample', 'uniform', 'randint']
    
    for func in forbidden:
        # Check that the function is not called (not just mentioned in comments)
        # Look for patterns like "rng.randrange(" or "random.choice("
        import re
        pattern = rf'\b{func}\s*\('
        matches = re.findall(pattern, content)
        
        assert len(matches) == 0, \
            f"Found forbidden function '{func}' in coroner/gen/__init__.py: {matches}"


def cobc_available():
    """Check if cobc is available."""
    try:
        result = subprocess.run(['cobc', '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not cobc_available(), reason="cobc not available")
def test_generate_cases_viable_on_real_cobol():
    """
    Test that generated cases produce viable output on the real COBOL program.
    
    Verifies:
    - E01 (arithmetic overflow) rows are at most 10% of cases
    - Every reason code (A00, A01, R01, R02, E01) appears at least once
    - Every segment value appears at least once
    """
    schema = load_schema('samples/credit-fees/schema.json')
    cobol_structure = {
        'constants': [Decimal('10.00'), Decimal('25000.00'), Decimal('12')],
        'paragraphs': {},
        'branches': []
    }
    
    # Generate 2,000 cases with seed 42
    cases_path = generate_cases(schema, cobol_structure, seed=42, num_cases=2000, tie_share=0.05)
    
    # Compile COBOL program
    build_dir = Path('build')
    build_dir.mkdir(exist_ok=True)
    
    cobol_src = 'samples/credit-fees/CREDIT-FEES.cob'
    copybook_dir = 'samples/credit-fees/copybooks'
    binary = build_dir / 'CREDIT-FEES'
    
    # Compile with -x (executable), -Wall, -I (copybook path)
    compile_cmd = [
        'cobc', '-x', '-Wall',
        '-I', copybook_dir,
        '-o', str(binary),
        cobol_src
    ]
    
    result = subprocess.run(compile_cmd, capture_output=True, timeout=30)
    assert result.returncode == 0, f"Compilation failed: {result.stderr.decode()}"
    
    # Run the COBOL program
    output_path = build_dir / 'cobol_output.csv'
    
    # Set environment variables for COBOL program
    import os
    env = os.environ.copy()
    env['INPUT_FILE'] = str(cases_path)
    env['OUTPUT_FILE'] = str(output_path)
    
    run_result = subprocess.run(
        [str(binary)],
        env=env,
        capture_output=True,
        timeout=30
    )
    
    # Check that the program ran successfully
    assert run_result.returncode in [0, 4], \
        f"COBOL program failed: {run_result.stderr.decode()}"
    
    # Read output
    with open(output_path, 'r') as f:
        reader = csv.DictReader(f)
        output_rows = list(reader)
    
    # Count reason codes
    reason_codes = {}
    segments_seen = set()
    
    for row in output_rows:
        reason = row.get('REASON-CODE', '')
        reason_codes[reason] = reason_codes.get(reason, 0) + 1
        
        # Track segments from input (need to read cases file again)
    
    # Read input to track segments
    with open(cases_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            segment = row.get('CUSTOMER-SEGMENT', '')
            if segment:
                segments_seen.add(segment)
    
    # Verify E01 is at most 10% of cases
    e01_count = reason_codes.get('E01', 0)
    e01_percent = e01_count / len(output_rows) * 100
    
    assert e01_percent <= 10.0, \
        f"E01 overflow cases are {e01_percent:.1f}% of total, expected at most 10%"
    
    # Verify every reason code appears at least once
    required_codes = ['A00', 'A01', 'R01', 'R02', 'E01']
    for code in required_codes:
        assert code in reason_codes, \
            f"Reason code {code} not found in output. Found: {list(reason_codes.keys())}"
    
    # Verify every segment value appears in input
    # Segments from COBOL: P, S, B, plus non-matching
    expected_segments = {'P', 'S', 'B'}
    for segment in expected_segments:
        assert segment in segments_seen, \
            f"Segment {segment} not found in generated input"
    
    # Print counts for review
    print(f"\nReason code counts (total {len(output_rows)} rows):")
    for code in sorted(reason_codes.keys()):
        count = reason_codes[code]
        percent = count / len(output_rows) * 100
        print(f"  {code}: {count:4d} ({percent:5.1f}%)")


def test_draw_decimal_by_magnitude_range():
    """Test that draw_decimal_by_magnitude produces values in valid range."""
    import random
    from coroner.gen import draw_decimal_by_magnitude
    
    rng = random.Random(42)
    
    # Test S9(9)V99: max value 999999999.99
    for _ in range(100):
        val = draw_decimal_by_magnitude(rng, max_int_digits=9, scale=2, signed=True)
        assert abs(val) <= Decimal("999999999.99")
        
        # Check scale
        exponent = val.as_tuple().exponent
        assert exponent >= -2


def test_draw_decimal_by_magnitude_distribution():
    """Test that draw_decimal_by_magnitude produces varied magnitudes."""
    import random
    from coroner.gen import draw_decimal_by_magnitude
    
    rng = random.Random(42)
    
    # Generate 1000 values and check distribution across magnitudes
    values = []
    for _ in range(1000):
        val = draw_decimal_by_magnitude(rng, max_int_digits=9, scale=2, signed=True)
        values.append(abs(val))
    
    # Count values in different magnitude ranges
    small = sum(1 for v in values if v < Decimal("10"))
    medium = sum(1 for v in values if Decimal("10") <= v < Decimal("1000"))
    large = sum(1 for v in values if Decimal("1000") <= v < Decimal("1000000"))
    huge = sum(1 for v in values if v >= Decimal("1000000"))
    
    # Should have values across all ranges
    assert small > 50, "Not enough small values"
    assert medium > 50, "Not enough medium values"
    assert large > 50, "Not enough large values"
    # Huge values should be present but less common
    assert huge > 0, "No huge values generated"


# generator_script (schema key): the engine validates what the script returns

SCRIPT_SCHEMA = {
    "program": "TEST-PROGRAM",
    "description": "Test program",
    "input": {"file": "in.csv", "columns": [
        {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "id"},
        {"name": "AMOUNT", "type": "decimal", "pic": "S9(5)V99", "description": "amount"},
        {"name": "COUNT", "type": "integer", "pic": "9(3)", "description": "count"}]},
    "output": {"file": "out.csv", "columns": [
        {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "id"}]},
}


def load_with_script(tmp_path, script_source):
    import json
    (tmp_path / "gen.py").write_text(script_source)
    (tmp_path / "schema.json").write_text(json.dumps(dict(SCRIPT_SCHEMA, generator_script="gen.py")))
    return load_schema(str(tmp_path / "schema.json"))


def test_generator_script_receives_the_seeded_rng_and_writes_the_csv(tmp_path):
    schema = load_with_script(tmp_path, (
        "from decimal import Decimal\n"
        "def generate_cases(schema, rng, num_cases):\n"
        "    return [{'CASE-ID': f'C{i}', 'AMOUNT': Decimal(int(rng.random() * 100000)) / 100, 'COUNT': i}\n"
        "            for i in range(num_cases)]\n"
    ))
    path = generate_cases(schema, {}, 7, 3, 0.06, str(tmp_path / "base"))
    again = generate_cases(schema, {}, 7, 3, 0.06, str(tmp_path / "base2"))
    other = generate_cases(schema, {}, 8, 3, 0.06, str(tmp_path / "base3"))
    data = Path(path).read_bytes()
    assert data == Path(again).read_bytes()
    assert data != Path(other).read_bytes()
    rows = list(csv.DictReader(data.decode().splitlines()))
    assert [r["CASE-ID"] for r in rows] == ["C0", "C1", "C2"]
    assert all(len(r["AMOUNT"].split(".")[1]) == 2 for r in rows)  # Decimal written at the column scale
    assert [r["COUNT"] for r in rows] == ["0", "1", "2"]
    assert b"\r" not in data
    assert not (tmp_path / "__pycache__").exists()


@pytest.mark.parametrize("body, message", [
    ("return []", "list of 2 cases"),
    ("return [{'CASE-ID': 'A', 'AMOUNT': '1.00'}] * 2", "exactly the schema input columns"),
    ("return [{'CASE-ID': 'A', 'AMOUNT': '1.00', 'COUNT': 1, 'EXTRA': 1}] * 2", "exactly the schema input columns"),
    ("return [{'CASE-ID': 'A', 'AMOUNT': 1.5, 'COUNT': 1}] * 2", "unsupported value type float"),
    ("return [{'CASE-ID': 'A\\nB', 'AMOUNT': '1.00', 'COUNT': 1}] * 2", "line break"),
])
def test_generator_script_bad_output_is_an_error(tmp_path, body, message):
    schema = load_with_script(tmp_path, f"def generate_cases(schema, rng, num_cases):\n    {body}\n")
    with pytest.raises(GeneratorScriptError, match=message):
        generate_cases(schema, {}, 1, 2, 0.06, str(tmp_path / "base"))


def test_generator_script_without_generate_cases_is_an_error(tmp_path):
    schema = load_with_script(tmp_path, "x = 1\n")
    with pytest.raises(GeneratorScriptError, match="no generate_cases function"):
        generate_cases(schema, {}, 1, 2, 0.06, str(tmp_path / "base"))


# Contract: the bytes that are executed are the bytes that are hashed and recorded

SCRIPT_A = (
    "def generate_cases(schema, rng, num_cases):\n"
    "    return [{'CASE-ID': f'A{i}', 'AMOUNT': '1.00', 'COUNT': i} for i in range(num_cases)]\n"
)
SCRIPT_B = SCRIPT_A.replace("f'A{i}'", "f'B{i}'")


def test_generator_script_read_holds_the_bytes_and_their_hash(tmp_path):
    import hashlib
    from coroner.gen import GeneratorScript

    schema = load_with_script(tmp_path, SCRIPT_A)
    script = GeneratorScript.read(schema)
    assert script.source == SCRIPT_A.encode()
    assert script.sha256 == hashlib.sha256(SCRIPT_A.encode()).hexdigest()


def test_generator_script_executes_the_bytes_that_were_hashed(tmp_path):
    """The file changes after the read: the cases still come from the bytes that were read."""
    from coroner.gen import GeneratorScript

    schema = load_with_script(tmp_path, SCRIPT_A)
    script = GeneratorScript.read(schema)
    (tmp_path / "gen.py").write_text(SCRIPT_B)

    path = generate_cases(schema, {}, 1, 2, 0.06, str(tmp_path / "base"), script)
    ids = [row["CASE-ID"] for row in csv.DictReader(Path(path).read_text().splitlines())]
    assert ids == ["A0", "A1"]

    # Without a script argument the file is read once at generation time
    path = generate_cases(schema, {}, 1, 2, 0.06, str(tmp_path / "base2"))
    ids = [row["CASE-ID"] for row in csv.DictReader(Path(path).read_text().splitlines())]
    assert ids == ["B0", "B1"]


def collect_inputs_for(tmp_path, schema_path, script_sha256):
    from coroner.store import collect_inputs

    (tmp_path / "p.cob").write_text("       IDENTIFICATION DIVISION.\n")
    (tmp_path / "P.java").write_text("class P {}\n")
    (tmp_path / "cpy").mkdir(exist_ok=True)
    (tmp_path / "cases.csv").write_text("CASE-ID,AMOUNT,COUNT\nA0,1.00,0\n")
    return collect_inputs(
        str(tmp_path / "p.cob"), str(tmp_path / "cpy"), str(tmp_path / "P.java"),
        str(schema_path), str(tmp_path / "cases.csv"), 1, 1, None, script_sha256,
    )


def test_collect_inputs_records_the_executed_hash_and_keeps_the_run_id(tmp_path):
    from coroner.gen import GeneratorScript
    from coroner.store import compute_run_id

    schema = load_with_script(tmp_path, SCRIPT_A)
    script = GeneratorScript.read(schema)
    from_executed = collect_inputs_for(tmp_path, tmp_path / "schema.json", script.sha256)
    from_disk = collect_inputs_for(tmp_path, tmp_path / "schema.json", None)

    assert from_executed["generator_script_sha256"] == script.sha256
    assert from_executed["generator_script"] == "gen.py"
    # The run id of an unchanged script is what it was before this contract existed
    assert compute_run_id(from_executed) == compute_run_id(from_disk)


def test_collect_inputs_refuses_a_hash_the_disk_no_longer_has(tmp_path):
    from coroner.gen import GeneratorScript

    schema = load_with_script(tmp_path, SCRIPT_A)
    script = GeneratorScript.read(schema)
    (tmp_path / "gen.py").write_text(SCRIPT_B)

    with pytest.raises(GeneratorScriptError, match="generator script changed during the run: gen.py"):
        collect_inputs_for(tmp_path, tmp_path / "schema.json", script.sha256)
