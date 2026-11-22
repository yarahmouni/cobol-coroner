"""Verdict computation for COBOL Coroner."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


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


def decimal_output_columns(schema) -> set[str]:
    """Names of the decimal output columns of a loaded schema."""
    return {column.name for column in schema.output_columns if column.type == "decimal"}


def amount_difference_from_fields(divergent_fields, decimal_columns) -> tuple[Decimal, Decimal, int] | None:
    """
    The money figure of a ZOMBIE run without a branch exposure: (sum, largest, count) of
    |COBOL - Java| over the divergent values of the decimal output columns, in exact Decimal
    arithmetic, nothing rounded. `divergent_fields` is every divergent field entry of every case, as
    the comparison records them (in memory or in comparison_results.json).

    Returns None when no honest figure exists: a divergence is not a plain value mismatch (a row
    missing on one side), a divergent decimal value cannot be read as a finite number, or every
    difference is zero (for example -0.00 against +0.00). A divergence on a string column is not an
    amount and is skipped.
    """
    total = Decimal(0)
    largest = Decimal(0)
    count = 0
    for field in divergent_fields:
        if field.get("kind") != "value_mismatch":
            return None
        if field.get("field_name") not in decimal_columns:
            continue
        try:
            cobol_value = Decimal(field["cobol_value"].strip())
            java_value = Decimal(field["java_value"].strip())
        except (InvalidOperation, KeyError, AttributeError):
            return None
        if not (cobol_value.is_finite() and java_value.is_finite()):
            return None
        difference = abs(cobol_value - java_value)
        if difference > 0:
            total += difference
            largest = max(largest, difference)
            count += 1
    if count == 0:
        return None
    return total, largest, count


def amount_difference(comparison, schema) -> tuple[Decimal, Decimal, int] | None:
    """
    The money figure of the comparison of a run (see amount_difference_from_fields), or None when
    the run has a branch exposure: that figure already reports the money, so the two never appear
    together.
    """
    if getattr(comparison, "exposure_sum", None) is not None:
        return None
    return amount_difference_from_fields(
        (field for case in comparison.cases for field in case.divergent_fields),
        decimal_output_columns(schema),
    )


def verdict_from_dict(data: dict) -> Verdict:
    """The Verdict recorded in a run's verdict.json (exposure fields are strings there)."""
    def decimal(key: str) -> Decimal | None:
        value = data.get(key)
        return Decimal(value) if value is not None else None

    return Verdict(
        status=data["status"],
        sub_label=data["sub_label"],
        cases_total=data["cases_total"],
        cases_divergent=data["cases_divergent"],
        run_return_codes=tuple(data["run_return_codes"]),
        validation_notice=data.get("validation_notice", "Validated under GnuCOBOL 3.x"),
        exposure_sum=decimal("exposure_sum"),
        exposure_max=decimal("exposure_max"),
        affected_branches=data.get("affected_branches"),
        suspense_difference=decimal("suspense_difference"),
        grand_total_matches=data.get("grand_total_matches"),
    )


def exposure_text(verdict: Verdict) -> str | None:
    """The "Unreconciled branch exposure" line of the CLI, or None when the run has no exposure."""
    if verdict.exposure_sum is None:
        return None
    matches_text = "yes" if verdict.grand_total_matches else "no"
    line = (f"Unreconciled branch exposure: sum {verdict.exposure_sum:.2f}, max {verdict.exposure_max:.2f}, "
            f"{verdict.affected_branches} branches affected")
    if verdict.suspense_difference is not None:
        line += f", suspense difference {verdict.suspense_difference:.2f}"
    return f"{line}, grand total matches: {matches_text}"


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
