"""Verdict computation for COBOL Coroner."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Verdict:
    """Verdict result from comparing COBOL and Java outputs."""
    status: str  # "ALIVE" or "ZOMBIE"
    sub_label: str
    cases_total: int
    cases_divergent: int
    run_return_codes: tuple[int, int]  # (cobol, java)
    validation_notice: str = "Validated under GnuCOBOL 3.x"
    exposure_sum: Decimal | None = None
    exposure_max: Decimal | None = None
    affected_branches: int | None = None
    suspense_difference: Decimal | None = None
    grand_total_matches: bool | None = None


def compute_verdict(comparison) -> Verdict:
    """
    Compute verdict from comparison results.
    
    Args:
        comparison: ComparisonResult with cases, run_return_codes, total_divergent, optional exposure
        
    Returns:
        Verdict with status ALIVE or ZOMBIE and appropriate sub_label
    """
    cobol_rc, java_rc = comparison.run_return_codes
    cases_total = len(comparison.cases)
    cases_divergent = comparison.total_divergent
    
    return_codes_differ = cobol_rc != java_rc
    
    # Extract exposure fields if present (use getattr for backward compatibility with mocks)
    exposure_sum = getattr(comparison, 'exposure_sum', None)
    exposure_max = getattr(comparison, 'exposure_max', None)
    affected_branches = getattr(comparison, 'affected_branches', None)
    suspense_difference = getattr(comparison, 'suspense_difference', None)
    grand_total_matches = getattr(comparison, 'grand_total_matches', None)
    
    if cases_divergent == 0 and not return_codes_differ:
        # ALIVE: no divergences and return codes match
        case_word = "case" if cases_total == 1 else "cases"
        return Verdict(
            status="ALIVE",
            sub_label=f"PASS: business behavior preserved on {cases_total} {case_word}",
            cases_total=cases_total,
            cases_divergent=0,
            run_return_codes=(cobol_rc, java_rc),
            exposure_sum=exposure_sum,
            exposure_max=exposure_max,
            affected_branches=affected_branches,
            suspense_difference=suspense_difference,
            grand_total_matches=grand_total_matches
        )
    
    # ZOMBIE: at least one issue
    parts = []
    if cases_divergent > 0:
        case_word = "case" if cases_divergent == 1 else "cases"
        parts.append(f"business behavior diverged on {cases_divergent} {case_word}")
    
    if return_codes_differ:
        parts.append(f"return code differs (COBOL {cobol_rc}, Java {java_rc})")
    
    sub_label = "FAIL: " + "; ".join(parts)
    
    return Verdict(
        status="ZOMBIE",
        sub_label=sub_label,
        cases_total=cases_total,
        cases_divergent=cases_divergent,
        run_return_codes=(cobol_rc, java_rc),
        exposure_sum=exposure_sum,
        exposure_max=exposure_max,
        affected_branches=affected_branches,
        suspense_difference=suspense_difference,
        grand_total_matches=grand_total_matches
    )
