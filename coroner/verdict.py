"""Verdict computation for COBOL Coroner."""

from dataclasses import dataclass


@dataclass
class Verdict:
    """Verdict result from comparing COBOL and Java outputs."""
    status: str  # "ALIVE" or "ZOMBIE"
    sub_label: str
    cases_total: int
    cases_divergent: int
    run_return_codes: tuple[int, int]  # (cobol, java)
    validation_notice: str = "Validated under GnuCOBOL 3.x"


def compute_verdict(comparison) -> Verdict:
    """
    Compute verdict from comparison results.
    
    Args:
        comparison: ComparisonResult with cases, run_return_codes, total_divergent
        
    Returns:
        Verdict with status ALIVE or ZOMBIE and appropriate sub_label
    """
    cobol_rc, java_rc = comparison.run_return_codes
    cases_total = len(comparison.cases)
    cases_divergent = comparison.total_divergent
    
    return_codes_differ = cobol_rc != java_rc
    
    if cases_divergent == 0 and not return_codes_differ:
        # ALIVE: no divergences and return codes match
        case_word = "case" if cases_total == 1 else "cases"
        return Verdict(
            status="ALIVE",
            sub_label=f"PASS: business behavior preserved on {cases_total} {case_word}",
            cases_total=cases_total,
            cases_divergent=0,
            run_return_codes=(cobol_rc, java_rc)
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
        run_return_codes=(cobol_rc, java_rc)
    )
