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
    divergent_fields: list[dict[str, Any]]  # Structured divergence information


@dataclass
class ComparisonResult:
    """Result of comparing all cases."""
    cases: list[CaseResult]
    run_return_codes: tuple[int, int]  # (cobol, java)
    row_count_match: bool
    total_divergent: int
    exposure_sum: Decimal | None = None
    exposure_max: Decimal | None = None
    affected_branches: int | None = None
    suspense_difference: Decimal | None = None
    grand_total_matches: bool | None = None


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
    
    Returns ComparisonResult with per-case divergences and optional exposure.
    """
    # Check if we need to use output_key for indexing
    if schema.output_key:
        return compare_outputs_with_key(cobol_csv, java_csv, schema, cobol_return_code, java_return_code)
    
    # Original line-order comparison
    # Parse CSVs
    cobol_rows = {}
    java_rows = {}
    
    # Read COBOL output
    with open(cobol_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Strip column names from header
        if reader.fieldnames:
            reader.fieldnames = [name.rstrip() for name in reader.fieldnames]
        
        # Verify all required columns are present
        for col in schema.output_columns:
            if col.name not in reader.fieldnames:
                raise ValueError(
                    f"column {col.name} not found in COBOL output header: {reader.fieldnames}"
                )
        
        for row in reader:
            case_id = row[schema.output_columns[0].name]
            cobol_rows[case_id] = row
    
    # Read Java output
    with open(java_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Strip column names from header
        if reader.fieldnames:
            reader.fieldnames = [name.rstrip() for name in reader.fieldnames]
        
        # Verify all required columns are present
        for col in schema.output_columns:
            if col.name not in reader.fieldnames:
                raise ValueError(
                    f"column {col.name} not found in Java output header: {reader.fieldnames}"
                )
        
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
            divergent_fields.append({
                "field_name": "<row>",
                "kind": "missing_in_cobol",
                "cobol_value": "missing",
                "java_value": "present"
            })
        elif case_id not in java_rows:
            divergent_fields.append({
                "field_name": "<row>",
                "kind": "missing_in_java",
                "cobol_value": "present",
                "java_value": "missing"
            })
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
                    divergent_fields.append({
                        "field_name": col_name,
                        "kind": "value_mismatch",
                        "cobol_value": "missing",
                        "java_value": java_val or ""
                    })
                    continue
                if java_val is None:
                    divergent_fields.append({
                        "field_name": col_name,
                        "kind": "value_mismatch",
                        "cobol_value": cobol_val,
                        "java_value": "missing"
                    })
                    continue
                
                # Normalize and compare based on type
                if col.type == "decimal":
                    cobol_norm, cobol_div = normalize_decimal(cobol_val, col.scale)
                    java_norm, java_div = normalize_decimal(java_val, col.scale)
                    
                    # If either is divergent due to extra decimals, report divergence
                    if cobol_div or java_div:
                        divergent_fields.append({
                            "field_name": col_name,
                            "kind": "value_mismatch",
                            "cobol_value": cobol_val,
                            "java_value": java_val
                        })
                    elif cobol_norm != java_norm:
                        divergent_fields.append({
                            "field_name": col_name,
                            "kind": "value_mismatch",
                            "cobol_value": cobol_val,
                            "java_value": java_val
                        })
                else:
                    # String or integer
                    cobol_norm = normalize_string(cobol_val)
                    java_norm = normalize_string(java_val)
                    
                    if cobol_norm != java_norm:
                        divergent_fields.append({
                            "field_name": col_name,
                            "kind": "value_mismatch",
                            "cobol_value": cobol_val,
                            "java_value": java_val
                        })
        
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


def compare_outputs_with_key(
    cobol_csv: str,
    java_csv: str,
    schema: Schema,
    cobol_return_code: int,
    java_return_code: int
) -> ComparisonResult:
    """
    Compare outputs using output_key for row indexing and compute exposure.
    
    When output_key is declared, rows are indexed by the key fields (tuple of values).
    A case is divergent when any of its rows diverges or is missing on one side.
    """
    # Parse CSVs into dictionaries keyed by output_key
    cobol_rows = {}
    java_rows = {}
    
    # Read COBOL output
    with open(cobol_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Strip column names from header
        if reader.fieldnames:
            reader.fieldnames = [name.rstrip() for name in reader.fieldnames]
        
        # Verify all required columns are present
        for col in schema.output_columns:
            if col.name not in reader.fieldnames:
                raise ValueError(
                    f"column {col.name} not found in COBOL output header: {reader.fieldnames}"
                )
        
        for row in reader:
            key = tuple(row[field] for field in schema.output_key)
            cobol_rows[key] = row
    
    # Read Java output
    with open(java_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Strip column names from header
        if reader.fieldnames:
            reader.fieldnames = [name.rstrip() for name in reader.fieldnames]
        
        # Verify all required columns are present
        for col in schema.output_columns:
            if col.name not in reader.fieldnames:
                raise ValueError(
                    f"column {col.name} not found in Java output header: {reader.fieldnames}"
                )
        
        for row in reader:
            key = tuple(row[field] for field in schema.output_key)
            java_rows[key] = row
    
    # Get all keys from both outputs
    all_keys = sorted(set(cobol_rows.keys()) | set(java_rows.keys()))
    
    # Check row counts
    row_count_match = len(cobol_rows) == len(java_rows)
    
    # Group keys by case ID (first element of output_key is assumed to be CASE-ID)
    case_divergences = {}
    
    for key in all_keys:
        case_id = key[0]
        divergent_fields = []
        
        # Build output_key dict (trimmed values)
        output_key_dict = {}
        for i, field_name in enumerate(schema.output_key):
            output_key_dict[field_name] = key[i].rstrip() if isinstance(key[i], str) else key[i]
        
        # Check if row is missing in either output
        if key not in cobol_rows:
            # Row present in Java, missing in COBOL
            java_row = java_rows[key]
            divergent_fields.append({
                "kind": "missing_in_cobol",
                "output_key": output_key_dict,
                "cobol_values": {},
                "java_values": {col.name: java_row.get(col.name, "") for col in schema.output_columns}
            })
        elif key not in java_rows:
            # Row present in COBOL, missing in Java
            cobol_row = cobol_rows[key]
            divergent_fields.append({
                "kind": "missing_in_java",
                "output_key": output_key_dict,
                "cobol_values": {col.name: cobol_row.get(col.name, "") for col in schema.output_columns},
                "java_values": {}
            })
        else:
            cobol_row = cobol_rows[key]
            java_row = java_rows[key]
            
            # Compare each output column
            for col in schema.output_columns:
                col_name = col.name
                
                # Get values
                cobol_val = cobol_row.get(col_name)
                java_val = java_row.get(col_name)
                
                # Check if column is missing
                if cobol_val is None:
                    divergent_fields.append({
                        "field_name": col_name,
                        "kind": "value_mismatch",
                        "output_key": output_key_dict,
                        "cobol_value": "missing",
                        "java_value": java_val or ""
                    })
                    continue
                if java_val is None:
                    divergent_fields.append({
                        "field_name": col_name,
                        "kind": "value_mismatch",
                        "output_key": output_key_dict,
                        "cobol_value": cobol_val,
                        "java_value": "missing"
                    })
                    continue
                
                # Normalize and compare based on type
                if col.type == "decimal":
                    cobol_norm, cobol_div = normalize_decimal(cobol_val, col.scale)
                    java_norm, java_div = normalize_decimal(java_val, col.scale)
                    
                    if cobol_div or java_div:
                        divergent_fields.append({
                            "field_name": col_name,
                            "kind": "value_mismatch",
                            "output_key": output_key_dict,
                            "cobol_value": cobol_val,
                            "java_value": java_val
                        })
                    elif cobol_norm != java_norm:
                        divergent_fields.append({
                            "field_name": col_name,
                            "kind": "value_mismatch",
                            "output_key": output_key_dict,
                            "cobol_value": cobol_val,
                            "java_value": java_val
                        })
                else:
                    # String or integer
                    cobol_norm = normalize_string(cobol_val)
                    java_norm = normalize_string(java_val)
                    
                    if cobol_norm != java_norm:
                        divergent_fields.append({
                            "field_name": col_name,
                            "kind": "value_mismatch",
                            "output_key": output_key_dict,
                            "cobol_value": cobol_val,
                            "java_value": java_val
                        })
        
        # Track divergences per case
        if case_id not in case_divergences:
            case_divergences[case_id] = []
        if divergent_fields:
            case_divergences[case_id].extend(divergent_fields)
    
    # Build CaseResult objects
    cases = []
    total_divergent = 0
    all_case_ids = sorted(set(key[0] for key in all_keys))
    
    for case_id in all_case_ids:
        divergent_fields = case_divergences.get(case_id, [])
        is_divergent = len(divergent_fields) > 0
        if is_divergent:
            total_divergent += 1
        
        cases.append(CaseResult(
            case_id=case_id,
            divergent=is_divergent,
            divergent_fields=divergent_fields
        ))
    
    # Compute exposure if group_key, subtotal and grand_total_key are declared
    exposure_sum = None
    exposure_max = None
    affected_branches = None
    suspense_difference = None
    grand_total_matches = None
    
    if schema.group_key and schema.subtotal and schema.grand_total_key:
        exposure_sum, exposure_max, affected_branches, suspense_difference, grand_total_matches = compute_exposure(
            cobol_rows, java_rows, schema
        )
    
    return ComparisonResult(
        cases=cases,
        run_return_codes=(cobol_return_code, java_return_code),
        row_count_match=row_count_match,
        total_divergent=total_divergent,
        exposure_sum=exposure_sum,
        exposure_max=exposure_max,
        affected_branches=affected_branches,
        suspense_difference=suspense_difference,
        grand_total_matches=grand_total_matches
    )


def compute_exposure(
    cobol_rows: dict,
    java_rows: dict,
    schema: Schema
) -> tuple[Decimal, Decimal, int, Decimal | None, bool]:
    """
    Compute unreconciled branch exposure.
    
    Returns (sum, max, affected_branches, suspense_difference, grand_total_matches).
    """
    group_key_idx = schema.output_key.index(schema.group_key)
    subtotal_col = None
    for col in schema.output_columns:
        if col.name == schema.subtotal:
            subtotal_col = col
            break
    
    # Sum subtotals per group_key value across all cases
    from collections import defaultdict
    cobol_subtotals = defaultdict(lambda: Decimal(0))
    java_subtotals = defaultdict(lambda: Decimal(0))
    
    for key, row in cobol_rows.items():
        group_val = key[group_key_idx].rstrip()
        if group_val == schema.grand_total_key:
            continue
        subtotal_str = row[schema.subtotal]
        try:
            subtotal = Decimal(subtotal_str.strip())
        except Exception as e:
            raise RuntimeError(f"Failed to parse subtotal '{subtotal_str}' as Decimal: {e}")
        cobol_subtotals[group_val] += subtotal
    
    for key, row in java_rows.items():
        group_val = key[group_key_idx].rstrip()
        if group_val == schema.grand_total_key:
            continue
        subtotal_str = row[schema.subtotal]
        try:
            subtotal = Decimal(subtotal_str.strip())
        except Exception as e:
            raise RuntimeError(f"Failed to parse subtotal '{subtotal_str}' as Decimal: {e}")
        java_subtotals[group_val] += subtotal
    
    # Trim suspense_key and grand_total_key for comparison
    suspense_key_trimmed = schema.suspense_key.rstrip() if schema.suspense_key else None
    
    # Compute differences for branches only (excluding suspense and grand total)
    all_groups = set(cobol_subtotals.keys()) | set(java_subtotals.keys())
    differences = []
    suspense_difference = None
    
    for group in all_groups:
        cobol_val = cobol_subtotals.get(group, Decimal(0))
        java_val = java_subtotals.get(group, Decimal(0))
        diff = abs(cobol_val - java_val)
        
        # Track suspense separately if schema defines it
        if suspense_key_trimmed and group == suspense_key_trimmed:
            suspense_difference = diff
            continue
        
        if diff > 0:
            differences.append(diff)
    
    if differences:
        exposure_sum = sum(differences)
        exposure_max = max(differences)
        affected_branches = len(differences)
    else:
        exposure_sum = Decimal(0)
        exposure_max = Decimal(0)
        affected_branches = 0
    
    # Check grand total match - sum all grand_total_key rows across all cases
    cobol_grand = Decimal(0)
    java_grand = Decimal(0)
    
    for key, row in cobol_rows.items():
        if key[group_key_idx].rstrip() == schema.grand_total_key:
            try:
                cobol_grand += Decimal(row[schema.subtotal].strip())
            except Exception as e:
                raise RuntimeError(f"Failed to parse grand total '{row[schema.subtotal]}' as Decimal: {e}")
    
    for key, row in java_rows.items():
        if key[group_key_idx].rstrip() == schema.grand_total_key:
            try:
                java_grand += Decimal(row[schema.subtotal].strip())
            except Exception as e:
                raise RuntimeError(f"Failed to parse grand total '{row[schema.subtotal]}' as Decimal: {e}")
    
    grand_total_matches = (cobol_grand == java_grand)
    
    return (exposure_sum, exposure_max, affected_branches, suspense_difference, grand_total_matches)
