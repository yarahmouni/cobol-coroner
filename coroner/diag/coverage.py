"""Coverage report module for Coroner."""

import os
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParagraphDetail:
    """Detail for a single paragraph."""
    name: str
    line: int
    covered: bool


@dataclass
class BranchDetail:
    """Detail for a single branch."""
    paragraph: str
    line: int
    branch_type: str
    covered: bool


@dataclass
class CoverageReport:
    """Coverage report with paragraph and branch counts."""
    paragraphs_covered: int
    paragraphs_total: int
    branches_covered: int
    branches_total: int
    paragraph_details: list[ParagraphDetail]
    branch_details: list[BranchDetail]
    
    @property
    def paragraph_coverage(self) -> str:
        """Return paragraph coverage as a string like '12/12'."""
        return f"{self.paragraphs_covered}/{self.paragraphs_total}"
    
    @property
    def branch_coverage(self) -> str:
        """Return branch coverage as a string like '42/70'."""
        return f"{self.branches_covered}/{self.branches_total}"
    
    @property
    def uncovered_branches(self) -> list[dict]:
        """Return list of uncovered branches with details."""
        return [
            {
                "paragraph": b.paragraph,
                "line": b.line,
                "branch_type": b.branch_type
            }
            for b in self.branch_details if not b.covered
        ]


def _normalize_path(path: str) -> str:
    """
    Normalize a file path for comparison.
    
    Resolves to real path and converts to lowercase on case-insensitive filesystems.
    """
    real_path = os.path.realpath(path)
    # Check if filesystem is case-insensitive (macOS, Windows by default)
    if platform.system() in ('Darwin', 'Windows'):
        return real_path.lower()
    return real_path


def compute_coverage(
    trace: dict[tuple[str, int], int],
    cobol_structure: dict,
    source_path: str,
    copybook_dir: str
) -> CoverageReport:
    """
    Compute coverage from trace and COBOL structure.
    
    Args:
        trace: Dict mapping (source_file, line_number) to execution count
        cobol_structure: Dict with "paragraphs" and "branches" from parse_cobol_structure
        source_path: Path to the COBOL source file
        copybook_dir: Directory containing copybooks
        
    Returns:
        CoverageReport with paragraph and branch coverage
        
    Coverage rules:
    - Paragraph is covered if any line inside it appears in the trace
    - Branch is covered if its first-statement marker line appears in the trace (D-07)
    """
    paragraphs = cobol_structure.get("paragraphs", {})
    branches = cobol_structure.get("branches", [])
    
    # Build map from normalized trace source paths to original paths
    trace_path_map = {}
    for (trace_source, _), _ in trace.items():
        normalized = _normalize_path(trace_source)
        if normalized not in trace_path_map:
            trace_path_map[normalized] = trace_source
    
    # Normalize source and copybook paths for matching
    source_normalized = _normalize_path(source_path)
    copybook_normalized = {}
    copybook_path_obj = Path(copybook_dir)
    if copybook_path_obj.exists():
        for copybook_file in copybook_path_obj.glob('*.cpy'):
            copybook_normalized[_normalize_path(str(copybook_file))] = str(copybook_file)
        for copybook_file in copybook_path_obj.glob('*.CPY'):
            copybook_normalized[_normalize_path(str(copybook_file))] = str(copybook_file)
    
    # Count covered paragraphs and build details
    paragraphs_covered = 0
    paragraph_details = []
    for para_name, para_line in paragraphs.items():
        # Check if this line appears in trace from the source file
        covered = False
        for (trace_source, trace_line), _ in trace.items():
            trace_normalized = _normalize_path(trace_source)
            if trace_normalized == source_normalized and trace_line == para_line:
                covered = True
                paragraphs_covered += 1
                break
        paragraph_details.append(ParagraphDetail(para_name, para_line, covered))
    
    # Count covered branches and build details
    branches_covered = 0
    branch_details = []
    for branch in branches:
        marker_line = branch.line_number
        # Check if this marker line appears in trace from any source
        covered = False
        for (trace_source, trace_line), _ in trace.items():
            trace_normalized = _normalize_path(trace_source)
            # Match against source or any copybook
            if trace_line == marker_line:
                if (trace_normalized == source_normalized or 
                    trace_normalized in copybook_normalized):
                    covered = True
                    branches_covered += 1
                    break
        branch_details.append(BranchDetail(
            branch.paragraph,
            branch.line_number,
            branch.branch_type,
            covered
        ))
    
    return CoverageReport(
        paragraphs_covered=paragraphs_covered,
        paragraphs_total=len(paragraphs),
        branches_covered=branches_covered,
        branches_total=len(branches),
        paragraph_details=paragraph_details,
        branch_details=branch_details
    )
