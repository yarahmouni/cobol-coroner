"""Regression tests for case generator."""

import hashlib
from pathlib import Path

from coroner.gen import generate_cases
from coroner.parse.copybook import parse_cobol_structure
from coroner.parse.schema import load_schema


def test_credit_fees_seed_42_hash():
    """
    Regression test: credit-fees with seed 42 must produce the same output
    as the last good generator (gen_b5f10da).
    
    Expected SHA-256: 8ecf05228da2a6df4da73fbf9cd904d41ebf9d686434f87e9d9be9fd2c116e88
    """
    schema_path = Path("samples/credit-fees/schema.json")
    schema = load_schema(schema_path)
    
    cobol_structure = parse_cobol_structure(
        'samples/credit-fees/CREDIT-FEES.cob',
        'samples/credit-fees/copybooks'
    )
    
    output_path = generate_cases(schema, cobol_structure, seed=42, num_cases=2000, base_dir=".")
    
    # Compute SHA-256 of the generated file
    with open(output_path, 'rb') as f:
        content = f.read()
        actual_hash = hashlib.sha256(content).hexdigest()
    
    expected_hash = "8ecf05228da2a6df4da73fbf9cd904d41ebf9d686434f87e9d9be9fd2c116e88"
    assert actual_hash == expected_hash, (
        f"Generator output changed for credit-fees seed 42.\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {actual_hash}\n"
        f"This breaks reproducibility per D-30."
    )


def test_credit_fees_seed_123_hash():
    """
    Regression test: credit-fees with seed 123 must produce the same output
    as the last good generator (gen_b5f10da).
    
    Expected SHA-256: 5a860b7f29edbf2d0a0649cf031b66e8eb3b706d74d12292eca5e9d8ebb51a7b
    """
    schema_path = Path("samples/credit-fees/schema.json")
    schema = load_schema(schema_path)
    
    cobol_structure = parse_cobol_structure(
        'samples/credit-fees/CREDIT-FEES.cob',
        'samples/credit-fees/copybooks'
    )
    
    output_path = generate_cases(schema, cobol_structure, seed=123, num_cases=2000, base_dir=".")
    
    # Compute SHA-256 of the generated file
    with open(output_path, 'rb') as f:
        content = f.read()
        actual_hash = hashlib.sha256(content).hexdigest()
    
    expected_hash = "5a860b7f29edbf2d0a0649cf031b66e8eb3b706d74d12292eca5e9d8ebb51a7b"
    assert actual_hash == expected_hash, (
        f"Generator output changed for credit-fees seed 123.\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {actual_hash}\n"
        f"This breaks reproducibility per D-30."
    )
