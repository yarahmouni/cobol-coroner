"""Generate trap-specific ZOMBIE sentences."""

import json
from decimal import Decimal
from pathlib import Path


def generate_zombie_sentence(trap_id: str, run_dir: Path) -> str:
    """
    Generate a trap-specific ZOMBIE sentence from run files.
    
    Args:
        trap_id: T1, T2, T3, T4, T5, T6
        run_dir: Path to run directory
        
    Returns:
        Generated sentence string
    """
    if trap_id == "T1":
        return _generate_t1_sentence(run_dir)
    elif trap_id == "T2":
        return _generate_t2_sentence(run_dir)
    elif trap_id == "T3":
        return _generate_t3_sentence(run_dir)
    elif trap_id == "T4":
        return _generate_t4_sentence(run_dir)
    elif trap_id == "T5":
        return _generate_t5_sentence(run_dir)
    elif trap_id == "T6":
        return _generate_t6_sentence(run_dir)
    else:
        # Fallback to sub_label
        verdict_file = run_dir / "verdict.json"
        verdict = json.loads(verdict_file.read_text())
        return verdict.get("sub_label", "")


def _generate_t1_sentence(run_dir: Path) -> str:
    """Generate T1 sentence (branch subtotals)."""
    verdict_file = run_dir / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    
    affected_branches = verdict.get("affected_branches", 0)
    grand_total_matches = verdict.get("grand_total_matches", False)
    
    sentence = f"This Java migration is not safe to promote: {affected_branches} branch subtotals do not reconcile with COBOL."
    
    if grand_total_matches:
        sentence += " The grand total still balances, so the error is hidden in branch-level reporting."
    
    return sentence


def _generate_t2_sentence(run_dir: Path) -> str:
    """Generate T2 sentence (rounding)."""
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    divergent_count = 0
    max_diff = Decimal(0)
    
    # Count divergent fees and find maximum difference
    for case in comparison["cases"]:
        if case.get("divergent", False):
            for field in case.get("divergent_fields", []):
                if "FEE" in field["field_name"].upper():
                    divergent_count += 1
                    
                    cobol_val_str = field["cobol_value"].strip().replace("+", "").replace("-", "")
                    java_val_str = field["java_value"].strip().replace("+", "").replace("-", "")
                    
                    try:
                        cobol_val = Decimal(cobol_val_str)
                        java_val = Decimal(java_val_str)
                        diff = abs(cobol_val - java_val)
                        if diff > max_diff:
                            max_diff = diff
                    except:
                        pass
    
    # Count total fee fields
    total_cases = len(comparison["cases"])
    
    # Estimate fee fields per case
    fee_fields_per_case = 0
    if comparison["cases"]:
        for case in comparison["cases"]:
            if case.get("divergent", False):
                for field in case.get("divergent_fields", []):
                    if "FEE" in field["field_name"].upper():
                        fee_fields_per_case += 1
                break
    
    total_fees = total_cases * fee_fields_per_case if fee_fields_per_case > 0 else divergent_count
    
    if max_diff == Decimal("0.01"):
        return f"This Java migration is not safe to promote: {divergent_count} of {total_fees} fee amounts differ from COBOL by rounding, each by exactly 0.01."
    else:
        return f"This Java migration is not safe to promote: {divergent_count} of {total_fees} fee amounts differ from COBOL by rounding (maximum difference {max_diff})."


def _generate_t3_sentence(run_dir: Path) -> str:
    """Generate T3 sentence (COMP-3 sign nibble)."""
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    count = 0
    
    # Count positive COBOL values read as negative in Java
    for case in comparison["cases"]:
        if case.get("divergent", False):
            for field in case.get("divergent_fields", []):
                cobol_str = field["cobol_value"].strip()
                java_str = field["java_value"].strip()
                
                try:
                    cobol_val = Decimal(cobol_str.replace("+", ""))
                    java_val = Decimal(java_str.replace("+", ""))
                    
                    if cobol_val > 0 and java_val < 0:
                        count += 1
                except:
                    pass
    
    return f"This Java migration is not safe to promote: {count} positive amounts are read as negative."


def _generate_t4_sentence(run_dir: Path) -> str:
    """Generate T4 sentence (zoned overpunch)."""
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    divergent_count = 0
    total_cases = len(comparison["cases"])
    wrong_sign_count = 0
    
    for case in comparison["cases"]:
        if case.get("divergent", False):
            for field in case.get("divergent_fields", []):
                if field["field_name"] == "DECODED-VALUE":
                    divergent_count += 1
                    
                    cobol_str = field["cobol_value"].strip()
                    java_str = field["java_value"].strip()
                    
                    try:
                        cobol_val = Decimal(cobol_str.replace("+", ""))
                        java_val = Decimal(java_str.replace("+", ""))
                        
                        if (cobol_val >= 0) != (java_val >= 0):
                            wrong_sign_count += 1
                    except:
                        pass
    
    return f"This Java migration is not safe to promote: {divergent_count} of {total_cases} balances are decoded wrongly, {wrong_sign_count} of them with the wrong sign."


def _generate_t5_sentence(run_dir: Path) -> str:
    """Generate T5 sentence (REDEFINES and invalid numeric data)."""
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    count = 0
    
    for case in comparison["cases"]:
        if case.get("divergent", False):
            count += 1
    
    return f"This Java migration is not safe to promote: {count} invalid amounts are silently treated as zero instead of being processed like COBOL."


def _generate_t6_sentence(run_dir: Path) -> str:
    """Generate T6 sentence (modulo of a negative day offset)."""
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())

    count = 0
    negative_java = 0

    for case in comparison["cases"]:
        if case.get("divergent", False):
            for field in case.get("divergent_fields", []):
                if field["field_name"] == "SLOT":
                    count += 1
                    try:
                        if Decimal(field["java_value"].strip()) < 0:
                            negative_java += 1
                    except Exception:
                        pass

    sentence = f"This Java migration is not safe to promote: {count} rotation slots differ from COBOL for days before the reference date."
    if count > 0 and negative_java == count:
        sentence += " Java gives a negative slot where COBOL gives 0 to 6."
    return sentence
