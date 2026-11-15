"""Tests for verdict computation."""

from dataclasses import dataclass
from coroner.verdict import Verdict, compute_verdict


@dataclass
class MockCaseResult:
    """Mock case result for testing."""
    case_id: str
    divergent: bool
    divergent_fields: list[tuple[str, str, str]]


@dataclass
class MockComparisonResult:
    """Mock comparison result for testing."""
    cases: list[MockCaseResult]
    run_return_codes: tuple[int, int]
    row_count_match: bool
    total_divergent: int


def test_alive_verdict_multiple_cases():
    """ALIVE verdict has correct sub_label with multiple cases."""
    comparison = MockComparisonResult(
        cases=[
            MockCaseResult("GEN-00001", False, []),
            MockCaseResult("GEN-00002", False, []),
            MockCaseResult("GEN-00003", False, [])
        ],
        run_return_codes=(0, 0),
        row_count_match=True,
        total_divergent=0
    )
    
    verdict = compute_verdict(comparison)
    
    assert verdict.status == "ALIVE"
    assert verdict.sub_label == "PASS: business behavior preserved on 3 cases"
    assert verdict.cases_total == 3
    assert verdict.cases_divergent == 0
    assert verdict.run_return_codes == (0, 0)
    assert verdict.validation_notice == "Validated under GnuCOBOL 3.x"


def test_alive_verdict_single_case():
    """ALIVE verdict uses singular 'case' for one case."""
    comparison = MockComparisonResult(
        cases=[MockCaseResult("GEN-00001", False, [])],
        run_return_codes=(0, 0),
        row_count_match=True,
        total_divergent=0
    )
    
    verdict = compute_verdict(comparison)
    
    assert verdict.status == "ALIVE"
    assert verdict.sub_label == "PASS: business behavior preserved on 1 case"
    assert verdict.cases_total == 1
    assert verdict.cases_divergent == 0


def test_zombie_case_divergence_multiple():
    """ZOMBIE verdict with multiple case divergences has correct sub_label."""
    comparison = MockComparisonResult(
        cases=[
            MockCaseResult("GEN-00001", True, [("FEE", "12.35", "12.34")]),
            MockCaseResult("GEN-00002", False, []),
            MockCaseResult("GEN-00003", True, [("FEE", "10.00", "10.01")])
        ],
        run_return_codes=(0, 0),
        row_count_match=True,
        total_divergent=2
    )
    
    verdict = compute_verdict(comparison)
    
    assert verdict.status == "ZOMBIE"
    assert verdict.sub_label == "FAIL: business behavior diverged on 2 cases"
    assert verdict.cases_total == 3
    assert verdict.cases_divergent == 2
    assert verdict.run_return_codes == (0, 0)


def test_zombie_case_divergence_single():
    """ZOMBIE verdict with one case divergence uses singular 'case'."""
    comparison = MockComparisonResult(
        cases=[
            MockCaseResult("GEN-00001", True, [("FEE", "12.35", "12.34")]),
            MockCaseResult("GEN-00002", False, [])
        ],
        run_return_codes=(0, 0),
        row_count_match=True,
        total_divergent=1
    )
    
    verdict = compute_verdict(comparison)
    
    assert verdict.status == "ZOMBIE"
    assert verdict.sub_label == "FAIL: business behavior diverged on 1 case"
    assert verdict.cases_divergent == 1


def test_zombie_return_code_mismatch_only():
    """ZOMBIE verdict with return code mismatch only has correct sub_label."""
    comparison = MockComparisonResult(
        cases=[
            MockCaseResult("GEN-00001", False, []),
            MockCaseResult("GEN-00002", False, [])
        ],
        run_return_codes=(0, 4),
        row_count_match=True,
        total_divergent=0
    )
    
    verdict = compute_verdict(comparison)
    
    assert verdict.status == "ZOMBIE"
    assert verdict.sub_label == "FAIL: return code differs (COBOL 0, Java 4)"
    assert verdict.cases_total == 2
    assert verdict.cases_divergent == 0
    assert verdict.run_return_codes == (0, 4)


def test_zombie_both_conditions():
    """ZOMBIE verdict with both case divergence and return code mismatch."""
    comparison = MockComparisonResult(
        cases=[
            MockCaseResult("GEN-00001", True, [("FEE", "12.35", "12.34")]),
            MockCaseResult("GEN-00002", False, []),
            MockCaseResult("GEN-00003", True, [("REASON", "R01", "R02")])
        ],
        run_return_codes=(0, 1),
        row_count_match=True,
        total_divergent=2
    )
    
    verdict = compute_verdict(comparison)
    
    assert verdict.status == "ZOMBIE"
    assert verdict.sub_label == "FAIL: business behavior diverged on 2 cases; return code differs (COBOL 0, Java 1)"
    assert verdict.cases_total == 3
    assert verdict.cases_divergent == 2
    assert verdict.run_return_codes == (0, 1)


def test_zombie_exit_status_255():
    """ZOMBIE verdict handles OS exit status range correctly."""
    comparison = MockComparisonResult(
        cases=[MockCaseResult("GEN-00001", False, [])],
        run_return_codes=(0, 255),
        row_count_match=True,
        total_divergent=0
    )
    
    verdict = compute_verdict(comparison)
    
    assert verdict.status == "ZOMBIE"
    assert verdict.sub_label == "FAIL: return code differs (COBOL 0, Java 255)"
    assert verdict.run_return_codes == (0, 255)
