"""Output comparison with exact field-by-field matching."""
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from typing import Any

from coroner.parse.schema import Schema


@dataclass
class CaseResult:
    """Result of comparing one case."""
    case_id: str
    divergent: bool
    divergent_fields: list[tuple[str, str, str]]  # (field_name, cobol_value, java_value)


@dataclass
class ComparisonResult:
    """Result of comparing all cases."""
    cases: list[CaseResult]
    run_return_codes: tuple[int, int]  # (cobol, java)
    row_count_match: bool
    total_divergent: int


def normalize_decimal(value: str, scale: int) -> tuple[str, bool]:
    """
    Normalize a decimal value to the given scale.
    
    Returns (normalized_value, is_divergent).
    If the value has non-zero digits beyond scale, it is divergent.
    Normalization never rounds.
    """
    try:
        dec = Decimal(value.strip())
    except (InvalidOperation, ValueError):
        return (value, True)
    
    # Create a scale quantizer
    scale_quantizer = Decimal(10) ** -scale
    
    # Check if there are non-zero digits beyond the schema scale
    # Compare the value with itself quantized to the scale
    try:
        quantized = dec.quantize(scale_quantizer, rounding=ROUND_DOWN)
    except InvalidOperation:
        # Number is too large or has issues - treat as invalid
        return (value, True)
    
    # If truncating to scale changes the value, there are extra non-zero digits
    if quantized != dec:
        return (value, True)
    
    # Normalize to the scale (pad with zeros if needed)
    # The value equals its quantized version, so no extra digits
    normalized = str(quantized)
    return (normalized, False)


def normalize_string(value: str) -> str:
    """Normalize a string by trimming trailing spaces only."""
    return value.rstrip()


def compare_outputs(
    cobol_csv: str,
    java_csv: str,
    schema: Schema,
    cobol_return_code: int,
    java_return_code: int
) -> ComparisonResult:
    """
    Compare COBOL and Java outputs field by field.
    
    Returns ComparisonResult with per-case divergences.
    """
    # Parse CSVs
    cobol_rows = {}
    java_rows = {}
    
    with open(cobol_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            case_id = row[schema.output_columns[0].name]
            cobol_rows[case_id] = row
    
    with open(java_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            case_id = row[schema.output_columns[0].name]
            java_rows[case_id] = row
    
    # Check row counts
    row_count_match = len(cobol_rows) == len(java_rows)
    
    # Get all case IDs from both outputs
    all_case_ids = sorted(set(cobol_rows.keys()) | set(java_rows.keys()))
    
    cases = []
    total_divergent = 0
    
    for case_id in all_case_ids:
        divergent_fields = []
        
        # Check if case is missing in either output
        if case_id not in cobol_rows:
            divergent_fields.append(("<row>", "missing", "present"))
        elif case_id not in java_rows:
            divergent_fields.append(("<row>", "present", "missing"))
        else:
            cobol_row = cobol_rows[case_id]
            java_row = java_rows[case_id]
            
            # Compare each output column
            for col in schema.output_columns:
                col_name = col.name
                
                # Get values
                cobol_val = cobol_row.get(col_name)
                java_val = java_row.get(col_name)
                
                # Check if column is missing
                if cobol_val is None:
                    divergent_fields.append((col_name, "missing", java_val or ""))
                    continue
                if java_val is None:
                    divergent_fields.append((col_name, cobol_val, "missing"))
                    continue
                
                # Normalize and compare based on type
                if col.type == "decimal":
                    cobol_norm, cobol_div = normalize_decimal(cobol_val, col.scale)
                    java_norm, java_div = normalize_decimal(java_val, col.scale)
                    
                    # If either is divergent due to extra decimals, report divergence
                    if cobol_div or java_div:
                        divergent_fields.append((col_name, cobol_val, java_val))
                    elif cobol_norm != java_norm:
                        divergent_fields.append((col_name, cobol_val, java_val))
                else:
                    # String or integer
                    cobol_norm = normalize_string(cobol_val)
                    java_norm = normalize_string(java_val)
                    
                    if cobol_norm != java_norm:
                        divergent_fields.append((col_name, cobol_val, java_val))
        
        is_divergent = len(divergent_fields) > 0
        if is_divergent:
            total_divergent += 1
        
        cases.append(CaseResult(
            case_id=case_id,
            divergent=is_divergent,
            divergent_fields=divergent_fields
        ))
    
    return ComparisonResult(
        cases=cases,
        run_return_codes=(cobol_return_code, java_return_code),
        row_count_match=row_count_match,
        total_divergent=total_divergent
    )
