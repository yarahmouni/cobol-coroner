"""UI page rendering logic."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to human-readable date and time."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return timestamp_str


def get_value_column_from_schema(schema_path: Path) -> Optional[str]:
    """Extract the non-key output column name from schema."""
    try:
        schema = json.loads(schema_path.read_text())
        output_cols = schema["output"]["columns"]
        if len(output_cols) >= 2:
            return output_cols[1]["name"]
    except (KeyError, IndexError, json.JSONDecodeError, OSError):
        pass
    return None


def has_group_key(schema_path: Path) -> bool:
    """Check if schema declares a group key (for branch exposure)."""
    try:
        schema = json.loads(schema_path.read_text())
        return "group_key" in schema
    except (json.JSONDecodeError, OSError):
        return False


def count_divergent_rows(comparison_results: dict) -> int:
    """
    Count the number of divergent output rows.
    
    Divergent rows means divergent output rows: count every output row key
    present in only one side or with a different value, from comparison_results.json.
    """
    count = 0
    for case in comparison_results.get("cases", []):
        divergent_fields = case.get("divergent_fields", [])
        # Each entry in divergent_fields is one divergent row
        count += len(divergent_fields)
    return count


def count_divergent_cases(comparison_results: dict) -> int:
    """Count the number of divergent cases (cases with at least one divergent row)."""
    count = 0
    for case in comparison_results.get("cases", []):
        if case.get("divergent", False):
            count += 1
    return count


def compute_exhibit_data(run_dir: Path, verdict_data: dict, inputs_data: dict) -> Optional[dict]:
    """
    Compute Exhibit 1 (Unreconciled branch exposure) data.
    
    Returns dict with exhibit data if applicable, None otherwise.
    """
    # Extract exposure data from verdict - only if present
    exposure_sum = verdict_data.get("exposure_sum")
    exposure_max = verdict_data.get("exposure_max")
    affected_branches = verdict_data.get("affected_branches")
    grand_total_matches = verdict_data.get("grand_total_matches")
    suspense_difference = verdict_data.get("suspense_difference")
    
    # If these keys exist, the schema has a group key
    if exposure_sum is None or affected_branches is None:
        return None
    
    # exposure_sum and exposure_max might be strings, convert to Decimal
    from decimal import Decimal
    if isinstance(exposure_sum, str):
        exposure_sum = Decimal(exposure_sum)
    if isinstance(exposure_max, str):
        exposure_max = Decimal(exposure_max)
    if isinstance(suspense_difference, str):
        suspense_difference = Decimal(suspense_difference)
    
    # Count divergent cases and rows from comparison_results.json
    comparison_file = run_dir / "comparison_results.json"
    divergent_cases = 0
    divergent_rows = 0
    if comparison_file.exists():
        try:
            comparison_data = json.loads(comparison_file.read_text())
            divergent_cases = count_divergent_cases(comparison_data)
            divergent_rows = count_divergent_rows(comparison_data)
        except (json.JSONDecodeError, OSError):
            pass
    
    return {
        "number": 1,
        "title": "Unreconciled branch exposure",
        "exposure_sum": f"{exposure_sum:.2f}",
        "exposure_max": f"{exposure_max:.2f}" if exposure_max is not None else None,
        "affected_branches": affected_branches,
        "grand_total_matches": grand_total_matches,
        "suspense_difference": f"{abs(suspense_difference):.2f}" if suspense_difference is not None else None,
        "divergent_cases": divergent_cases,
        "divergent_rows": divergent_rows,
        "run_id": run_dir.name
    }
