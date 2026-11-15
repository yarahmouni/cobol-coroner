"""Tests for engine extensions: case_rows, output_key, group_key, cobc_flags."""
import pytest
import json
import tempfile
import os
from pathlib import Path
from decimal import Decimal

from coroner.parse.schema import load_schema, Schema
from coroner.gen import generate_cases
from coroner.compare import compare_outputs
from coroner.verdict import compute_verdict


def test_schema_parse_case_rows():
    """Schema parser reads case_rows correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        schema_data = {
            "program": "TEST",
            "description": "Test batch input",
            "input": {
                "file": "INPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"},
                    {"name": "AMOUNT", "type": "decimal", "pic": "S9(7)V99", "scale": 2, "description": "Amount"}
                ]
            },
            "output": {
                "file": "OUTPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"},
                    {"name": "TOTAL", "type": "decimal", "pic": "+9(7).99", "scale": 2, "description": "Total"}
                ]
            },
            "case_rows": {"min": 2, "max": 5}
        }
        json.dump(schema_data, f)
        f.flush()
        
        schema = load_schema(f.name)
        assert schema.case_rows == {"min": 2, "max": 5}
        
        os.unlink(f.name)


def test_schema_parse_output_key():
    """Schema parser reads output_key correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        schema_data = {
            "program": "TEST",
            "description": "Test output key",
            "input": {
                "file": "INPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"}
                ]
            },
            "output": {
                "file": "OUTPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"},
                    {"name": "BRANCH", "type": "string", "pic": "X(3)", "description": "Branch"}
                ]
            },
            "output_key": ["CASE-ID", "BRANCH"]
        }
        json.dump(schema_data, f)
        f.flush()
        
        schema = load_schema(f.name)
        assert schema.output_key == ["CASE-ID", "BRANCH"]
        
        os.unlink(f.name)


def test_schema_parse_group_keys():
    """Schema parser reads group_key, subtotal, grand_total_key correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        schema_data = {
            "program": "TEST",
            "description": "Test group keys",
            "input": {
                "file": "INPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"}
                ]
            },
            "output": {
                "file": "OUTPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"},
                    {"name": "BRANCH", "type": "string", "pic": "X(5)", "description": "Branch"},
                    {"name": "SUBTOTAL", "type": "decimal", "pic": "+9(7).99", "scale": 2, "description": "Subtotal"}
                ]
            },
            "output_key": ["CASE-ID", "BRANCH"],
            "group_key": "BRANCH",
            "subtotal": "SUBTOTAL",
            "grand_total_key": "TOTAL"
        }
        json.dump(schema_data, f)
        f.flush()
        
        schema = load_schema(f.name)
        assert schema.group_key == "BRANCH"
        assert schema.subtotal == "SUBTOTAL"
        assert schema.grand_total_key == "TOTAL"
        
        os.unlink(f.name)


def test_schema_parse_cobc_flags():
    """Schema parser reads cobc_flags correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        schema_data = {
            "program": "TEST",
            "description": "Test cobc flags",
            "input": {
                "file": "INPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"}
                ]
            },
            "output": {
                "file": "OUTPUT_FILE",
                "columns": [
                    {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "Case ID"}
                ]
            },
            "cobc_flags": ["-fsign=EBCDIC"]
        }
        json.dump(schema_data, f)
        f.flush()
        
        schema = load_schema(f.name)
        assert schema.cobc_flags == ["-fsign=EBCDIC"]
        
        os.unlink(f.name)


def test_compare_with_output_key_and_exposure():
    """Comparison with output_key computes exposure correctly."""
    # Create schema with output_key and group keys
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="INPUT_FILE",
        input_columns=[],
        output_file="OUTPUT_FILE",
        output_columns=[
            type('Column', (), {
                'name': 'CASE-ID', 'type': 'string', 'scale': None
            })(),
            type('Column', (), {
                'name': 'BRANCH', 'type': 'string', 'scale': None
            })(),
            type('Column', (), {
                'name': 'SUBTOTAL', 'type': 'decimal', 'scale': 2
            })()
        ],
        output_key=["CASE-ID", "BRANCH"],
        group_key="BRANCH",
        subtotal="SUBTOTAL",
        grand_total_key="TOTAL"
    )
    
    # Create temporary CSV files
    with tempfile.NamedTemporaryFile(mode='w', suffix='_cobol.csv', delete=False) as cobol_f:
        cobol_f.write("CASE-ID,BRANCH,SUBTOTAL\n")
        cobol_f.write("GEN-001,A01,100.00\n")
        cobol_f.write("GEN-001,A02,200.00\n")
        cobol_f.write("GEN-001,TOTAL,300.00\n")
        cobol_path = cobol_f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='_java.csv', delete=False) as java_f:
        java_f.write("CASE-ID,BRANCH,SUBTOTAL\n")
        java_f.write("GEN-001,A01,150.00\n")  # Divergent subtotal
        java_f.write("GEN-001,A02,150.00\n")  # Divergent subtotal
        java_f.write("GEN-001,TOTAL,300.00\n")  # Grand total matches
        java_path = java_f.name
    
    try:
        comparison = compare_outputs(cobol_path, java_path, schema, 0, 0)
        
        # Check exposure was computed
        assert comparison.exposure_sum is not None
        assert comparison.exposure_max is not None
        assert comparison.affected_branches is not None
        assert comparison.grand_total_matches is not None
        
        # Check values
        # A01: |100 - 150| = 50, A02: |200 - 150| = 50
        assert comparison.exposure_sum == Decimal('100.00')
        assert comparison.exposure_max == Decimal('50.00')
        assert comparison.affected_branches == 2
        assert comparison.grand_total_matches is True
        
        # Verdict should be ZOMBIE (divergent subtotals)
        verdict = compute_verdict(comparison)
        assert verdict.status == "ZOMBIE"
        assert verdict.exposure_sum == Decimal('100.00')
        
    finally:
        os.unlink(cobol_path)
        os.unlink(java_path)


def test_compare_without_output_key_no_exposure():
    """Comparison without output_key does not compute exposure."""
    schema = Schema(
        program_name="TEST",
        description="Test",
        input_file="INPUT_FILE",
        input_columns=[],
        output_file="OUTPUT_FILE",
        output_columns=[
            type('Column', (), {
                'name': 'CASE-ID', 'type': 'string', 'scale': None
            })(),
            type('Column', (), {
                'name': 'FEE', 'type': 'decimal', 'scale': 2
            })()
        ]
    )
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='_cobol.csv', delete=False) as cobol_f:
        cobol_f.write("CASE-ID,FEE\n")
        cobol_f.write("GEN-001,10.00\n")
        cobol_path = cobol_f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='_java.csv', delete=False) as java_f:
        java_f.write("CASE-ID,FEE\n")
        java_f.write("GEN-001,10.00\n")
        java_path = java_f.name
    
    try:
        comparison = compare_outputs(cobol_path, java_path, schema, 0, 0)
        
        # No exposure computed
        assert comparison.exposure_sum is None
        assert comparison.exposure_max is None
        assert comparison.affected_branches is None
        assert comparison.grand_total_matches is None
        
        verdict = compute_verdict(comparison)
        assert verdict.status == "ALIVE"
        assert verdict.exposure_sum is None
        
    finally:
        os.unlink(cobol_path)
        os.unlink(java_path)
