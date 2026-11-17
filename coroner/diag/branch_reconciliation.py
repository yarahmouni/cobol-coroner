"""Branch reconciliation for control-break programs."""

import json
from decimal import Decimal
from pathlib import Path


def generate_branch_reconciliation(
    comparison_file: Path,
    schema_data: dict,
    verdict_data: dict,
) -> dict | None:
    """
    Generate branch reconciliation from comparison results.
    
    Returns reconciliation dict or None if schema has no group_key.
    """
    # Check if schema has group_key and subtotal
    if "group_key" not in schema_data or "subtotal" not in schema_data:
        return None
    
    group_key = schema_data["group_key"]
    subtotal_col = schema_data["subtotal"]
    grand_total_key = schema_data.get("grand_total_key")
    
    # Read comparison results
    comparison_data = json.loads(comparison_file.read_text())
    
    # Read output rows and collect by branch
    cobol_totals = {}
    java_totals = {}
    
    cobol_grand = None
    java_grand = None
    
    for case in comparison_data["cases"]:
        cobol_output = case.get("cobol_output", {})
        java_output = case.get("java_output", {})
        
        for row in cobol_output.get("rows", []):
            branch = row.get(group_key)
            subtotal_str = row.get(subtotal_col)
            
            if branch and subtotal_str:
                # Check if this is the grand total
                if grand_total_key and branch == grand_total_key:
                    cobol_grand = Decimal(subtotal_str)
                else:
                    # Branch subtotal
                    if branch not in cobol_totals:
                        cobol_totals[branch] = Decimal(0)
                    cobol_totals[branch] = Decimal(subtotal_str)
        
        for row in java_output.get("rows", []):
            branch = row.get(group_key)
            subtotal_str = row.get(subtotal_col)
            
            if branch and subtotal_str:
                # Check if this is the grand total
                if grand_total_key and branch == grand_total_key:
                    java_grand = Decimal(subtotal_str)
                else:
                    # Branch subtotal
                    if branch not in java_totals:
                        java_totals[branch] = Decimal(0)
                    java_totals[branch] = Decimal(subtotal_str)
    
    # Collect all branch codes
    all_branches = set(cobol_totals.keys()) | set(java_totals.keys())
    
    # Build reconciliation list
    branches = []
    for branch in sorted(all_branches):
        cobol_subtotal = cobol_totals.get(branch, Decimal(0))
        java_subtotal = java_totals.get(branch, Decimal(0))
        
        difference = java_subtotal - cobol_subtotal
        absolute_difference = abs(difference)
        
        status = "MATCH" if absolute_difference == 0 else "MISMATCH"
        
        branches.append({
            "branch": branch,
            "cobol_subtotal": str(cobol_subtotal),
            "java_subtotal": str(java_subtotal),
            "difference": str(difference),
            "absolute_difference": str(absolute_difference),
            "status": status,
        })
    
    # Grand total
    grand_total = {
        "cobol": str(cobol_grand) if cobol_grand is not None else "not recorded",
        "java": str(java_grand) if java_grand is not None else "not recorded",
    }
    
    return {
        "branches": branches,
        "grand_total": grand_total,
    }
