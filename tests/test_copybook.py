"""Tests for COBOL source and copybook parsing."""

import pytest
from decimal import Decimal
from coroner.parse.copybook import parse_cobol_structure, BranchInfo


def test_parse_credit_fees_structure():
    """Test parsing of CREDIT-FEES.cob structure."""
    result = parse_cobol_structure(
        "samples/credit-fees/CREDIT-FEES.cob",
        "samples/credit-fees/copybooks"
    )
    
    # Check constants include key thresholds
    constants = result["constants"]
    assert Decimal("10.00") in constants
    assert Decimal("25000.00") in constants
    
    # Check paragraphs
    paragraphs = result["paragraphs"]
    assert "MAIN-PROCESS" in paragraphs
    assert "VALIDATE-INPUT" in paragraphs
    assert "READ-HEADER" in paragraphs
    assert "WRITE-HEADER" in paragraphs
    assert "PROCESS-RECORD" in paragraphs
    assert "PARSE-INPUT" in paragraphs
    assert "VALIDATE-NUMERIC-FIELDS" in paragraphs
    assert "COMPUTE-FEE" in paragraphs
    assert "APPLY-SEGMENT-DISCOUNT" in paragraphs
    assert "CHECK-ELIGIBILITY" in paragraphs
    assert "REJECT-RECORD" in paragraphs
    assert "WRITE-OUTPUT" in paragraphs
    
    # Operator ground truth: 12 paragraphs
    assert len(paragraphs) == 12
    
    # Check branches
    branches = result["branches"]
    
    # Count branch types
    if_true_count = sum(1 for b in branches if b.branch_type == "IF_TRUE")
    if_else_count = sum(1 for b in branches if b.branch_type == "IF_ELSE")
    evaluate_when_count = sum(1 for b in branches if b.branch_type == "EVALUATE_WHEN")
    evaluate_other_count = sum(1 for b in branches if b.branch_type == "EVALUATE_OTHER")
    
    # Operator ground truth: 33 IF, 33 ELSE
    assert if_true_count >= 33, f"Expected at least 33 IF_TRUE branches, got {if_true_count}"
    assert if_else_count >= 33, f"Expected at least 33 IF_ELSE branches, got {if_else_count}"
    
    # Operator ground truth: 1 EVALUATE with 4 WHEN arms (P, S, B, OTHER)
    # This means 3 EVALUATE_WHEN + 1 EVALUATE_OTHER
    assert evaluate_when_count == 3, f"Expected 3 EVALUATE_WHEN branches, got {evaluate_when_count}"
    assert evaluate_other_count == 1, f"Expected 1 EVALUATE_OTHER branch, got {evaluate_other_count}"
    
    # Total branches: at least 33 IF_TRUE + 33 IF_ELSE + 3 EVALUATE_WHEN + 1 EVALUATE_OTHER = 70
    total_branches = len(branches)
    assert total_branches >= 70, f"Expected at least 70 branches (33 IF + 33 ELSE + 4 WHEN), got {total_branches}"


def test_parse_structure_empty_copybook_dir(tmp_path):
    """Test parsing with empty copybook directory."""
    result = parse_cobol_structure(
        "samples/credit-fees/CREDIT-FEES.cob",
        str(tmp_path)  # Empty directory
    )
    
    # Should still parse main source
    assert len(result["paragraphs"]) > 0
    assert len(result["branches"]) > 0


def test_branch_info_dataclass():
    """Test BranchInfo dataclass."""
    branch = BranchInfo(
        paragraph="TEST-PARA",
        line_number=42,
        branch_type="IF_TRUE"
    )
    
    assert branch.paragraph == "TEST-PARA"
    assert branch.line_number == 42
    assert branch.branch_type == "IF_TRUE"


def test_parse_constants_from_copybook():
    """Test that constants from copybooks are extracted."""
    result = parse_cobol_structure(
        "samples/credit-fees/CREDIT-FEES.cob",
        "samples/credit-fees/copybooks"
    )
    
    constants = result["constants"]
    
    # Constants from CONSTANTS.cpy
    assert Decimal("10.00") in constants
    assert Decimal("25000.00") in constants
    assert Decimal("12") in constants
    
    # Literals from APPLY-SEGMENT-DISCOUNT
    assert Decimal("0.10") in constants
    assert Decimal("0.05") in constants


def test_no_shared_branch_markers():
    """Test that no two branches share the same marker line."""
    result = parse_cobol_structure(
        "samples/credit-fees/CREDIT-FEES.cob",
        "samples/credit-fees/copybooks"
    )
    
    branches = result["branches"]
    marker_lines = [b.line_number for b in branches]
    
    # Check for duplicates
    duplicates = [line for line in marker_lines if marker_lines.count(line) > 1]
    
    assert len(duplicates) == 0, f"Found {len(set(duplicates))} shared marker lines: {sorted(set(duplicates))}"


def test_nested_if_markers():
    """Test that nested IF statements have correct distinct markers."""
    result = parse_cobol_structure(
        "samples/credit-fees/CREDIT-FEES.cob",
        "samples/credit-fees/copybooks"
    )
    
    branches = result["branches"]
    
    # Find CHECK-ELIGIBILITY branches
    check_eligibility_branches = [b for b in branches if b.paragraph == "CHECK-ELIGIBILITY"]
    
    # The outer ELSE at line 361 is followed by IF at line 362
    # Outer ELSE marker should be 362 (the IF statement itself)
    # Inner IF true arm marker should be 363 (first statement inside the inner IF)
    outer_else_branch = [b for b in check_eligibility_branches if b.branch_type == "IF_ELSE" and b.line_number == 362]
    inner_if_true_branch = [b for b in check_eligibility_branches if b.branch_type == "IF_TRUE" and b.line_number == 363]
    
    assert len(outer_else_branch) == 1, f"Expected outer ELSE branch at line 362, found {[b.line_number for b in check_eligibility_branches if b.branch_type == 'IF_ELSE']}"
    assert len(inner_if_true_branch) == 1, f"Expected inner IF_TRUE branch at line 363, found {[b.line_number for b in check_eligibility_branches if b.branch_type == 'IF_TRUE']}"


def test_branch_counts():
    """Test that branch and paragraph counts match the ground truth."""
    result = parse_cobol_structure(
        "samples/credit-fees/CREDIT-FEES.cob",
        "samples/credit-fees/copybooks"
    )
    
    branches = result["branches"]
    paragraphs = result["paragraphs"]
    
    # Ground truth: 70 branches total, 12 paragraphs
    assert len(branches) == 70, f"Expected 70 branches, got {len(branches)}"
    assert len(paragraphs) == 12, f"Expected 12 paragraphs, got {len(paragraphs)}"
