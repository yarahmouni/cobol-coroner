"""Minimal case selection module for Coroner."""

from decimal import Decimal, InvalidOperation

from coroner.compare import CaseResult
from coroner.parse.schema import Schema


def select_minimal_case(
    divergent_cases: list[CaseResult],
    schema: Schema,
    input_rows: dict[str, dict | list[dict]]
) -> CaseResult:
    """
    Select the minimal failing case from divergent cases.
    
    Deterministic rule: among divergent cases, order by the numeric input columns
    in schema order by absolute Decimal value (smallest first), then by case_id.
    Non-numeric values sort last.
    
    For multi-row cases, uses the first row's numeric values.
    
    Args:
        divergent_cases: List of divergent CaseResult objects
        schema: Schema with input column definitions
        input_rows: Dict mapping case_id to input row dict (or list of dicts for multi-row)
        
    Returns:
        The minimal CaseResult
    """
    if not divergent_cases:
        raise ValueError("No divergent cases to select from")
    
    def case_sort_key(case: CaseResult):
        """
        Compute sort key for a case.
        
        Returns tuple: (numeric_values, case_id)
        where numeric_values is list of (is_numeric, abs_value)
        """
        case_data = input_rows.get(case.case_id, {})
        
        # Handle multi-row cases: use first row
        if isinstance(case_data, list):
            input_row = case_data[0] if case_data else {}
        else:
            input_row = case_data
        
        numeric_values = []
        
        for col in schema.input_columns:
            col_name = col.name
            value = input_row.get(col_name, "")
            
            # Try to parse as Decimal
            try:
                if col.type in ("decimal", "integer"):
                    dec_value = Decimal(str(value).strip())
                    abs_value = abs(dec_value)
                    # Sort numeric values first, by absolute value
                    numeric_values.append((False, abs_value))
                else:
                    # String values sort last
                    numeric_values.append((True, 0))
            except (InvalidOperation, ValueError):
                # Non-numeric or invalid values sort last
                numeric_values.append((True, 0))
        
        return (numeric_values, case.case_id)
    
    # Sort and return the first (minimal) case
    sorted_cases = sorted(divergent_cases, key=case_sort_key)
    return sorted_cases[0]

