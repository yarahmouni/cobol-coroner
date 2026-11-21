"""Regression tests for case generator."""

import hashlib
from pathlib import Path

from coroner.gen import GENERATOR_VERSION, generate_cases
from coroner.parse.copybook import parse_cobol_structure
from coroner.parse.schema import load_schema

# Golden hashes keyed by generator version and seed
# A new version entry may only be added in a reviewed commit that documents the reason
# Existing entries are never edited
GOLDEN = {
    1: {
        42: "8ecf05228da2a6df4da73fbf9cd904d41ebf9d686434f87e9d9be9fd2c116e88",
        123: "5a860b7f29edbf2d0a0649cf031b66e8eb3b706d74d12292eca5e9d8ebb51a7b",
    }
}


def test_generator_version_has_golden_hashes():
    """
    Generator version guard: GENERATOR_VERSION must have golden hashes recorded.
    
    A version bump without recorded golden hashes fails immediately.
    """
    assert GENERATOR_VERSION in GOLDEN, (
        f"GENERATOR_VERSION {GENERATOR_VERSION} has no golden hashes recorded in GOLDEN.\n"
        f"A version bump requires recording the new golden hashes in a reviewed commit."
    )


def test_credit_fees_seed_42_hash(tmp_path):
    """
    Regression test: credit-fees with seed 42 must produce the same output
    as the golden hash for the current generator version.
    
    An output change without a version bump fails.
    """
    schema_path = Path("samples/credit-fees/schema.json")
    schema = load_schema(schema_path)
    
    cobol_structure = parse_cobol_structure(
        'samples/credit-fees/CREDIT-FEES.cob',
        'samples/credit-fees/copybooks'
    )
    
    output_path = generate_cases(schema, cobol_structure, seed=42, num_cases=2000, base_dir=str(tmp_path))
    
    # Compute SHA-256 of the generated file
    with open(output_path, 'rb') as f:
        content = f.read()
        actual_hash = hashlib.sha256(content).hexdigest()
    
    expected_hash = GOLDEN[GENERATOR_VERSION][42]
    assert actual_hash == expected_hash, (
        f"Generator output changed for credit-fees seed 42 (version {GENERATOR_VERSION}).\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {actual_hash}\n"
        f"This breaks reproducibility per D-30. Increment GENERATOR_VERSION and record new hashes."
    )


def test_credit_fees_seed_123_hash(tmp_path):
    """
    Regression test: credit-fees with seed 123 must produce the same output
    as the golden hash for the current generator version.
    
    An output change without a version bump fails.
    """
    schema_path = Path("samples/credit-fees/schema.json")
    schema = load_schema(schema_path)
    
    cobol_structure = parse_cobol_structure(
        'samples/credit-fees/CREDIT-FEES.cob',
        'samples/credit-fees/copybooks'
    )
    
    output_path = generate_cases(schema, cobol_structure, seed=123, num_cases=2000, base_dir=str(tmp_path))
    
    # Compute SHA-256 of the generated file
    with open(output_path, 'rb') as f:
        content = f.read()
        actual_hash = hashlib.sha256(content).hexdigest()
    
    expected_hash = GOLDEN[GENERATOR_VERSION][123]
    assert actual_hash == expected_hash, (
        f"Generator output changed for credit-fees seed 123 (version {GENERATOR_VERSION}).\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {actual_hash}\n"
        f"This breaks reproducibility per D-30. Increment GENERATOR_VERSION and record new hashes."
    )
