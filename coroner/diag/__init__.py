"""Diagnostic module for Coroner."""

from coroner.diag.coverage import (
    BranchDetail,
    CoverageReport,
    ParagraphDetail,
    compute_coverage,
)
from coroner.diag.minimal_case import select_minimal_case
from coroner.diag.report import FailureReport, generate_failure_report

__all__ = [
    "BranchDetail",
    "CoverageReport",
    "ParagraphDetail",
    "compute_coverage",
    "select_minimal_case",
    "FailureReport",
    "generate_failure_report",
]

