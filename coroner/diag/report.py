"""Failure report generation module for Coroner."""

import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from coroner.compare import CaseResult
from coroner.parse.schema import Schema
from coroner.parse.trace import parse_trace_counts
from coroner.run import run_cobol_instrumented, run_java


@dataclass
class FailureReport:
    """Detailed failure report for a minimal case."""
    case_id: str
    input_row: dict[str, str]
    cobol_output: dict[str, str]
    java_output: dict[str, str]
    divergent_fields: list[tuple[str, str, str]]  # (field_name, cobol_value, java_value)
    cobol_return_code: int
    java_return_code: int
    executed_lines: list[tuple[str, int]]  # (source_file, line_number)


def generate_failure_report(
    minimal_case: CaseResult,
    input_rows: dict[str, dict],
    schema: Schema,
    cobol_instrumented_binary: str,
    java_class_name: str,
    java_classpath: str,
    run_dir: str,
    timeout: float = 60.0
) -> FailureReport:
    """
    Generate a detailed failure report for the minimal case.
    
    Re-runs the minimal case alone on instrumented COBOL and Java to capture
    full details: both outputs, return codes, and executed COBOL lines.
    
    Args:
        minimal_case: The minimal CaseResult to analyze
        input_rows: Dict mapping case_id to input row dict
        schema: Schema with input/output column definitions
        cobol_instrumented_binary: Path to instrumented COBOL binary
        java_class_name: Java main class name
        java_classpath: Java classpath
        run_dir: Directory for temporary files
        timeout: Execution timeout in seconds
        
    Returns:
        FailureReport with all details
    """
    case_id = minimal_case.case_id
    input_row = input_rows[case_id]
    
    # Create temporary files for single-case re-run
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, dir=run_dir) as input_file:
        input_csv_path = input_file.name
        writer = csv.DictWriter(input_file, fieldnames=[col.name for col in schema.input_columns])
        writer.writeheader()
        writer.writerow(input_row)
    
    cobol_output_path = Path(run_dir) / f"minimal_case_cobol_output.csv"
    java_output_path = Path(run_dir) / f"minimal_case_java_output.csv"
    trace_path = Path(run_dir) / f"minimal_case_trace.txt"
    
    # Re-run instrumented COBOL on this single case
    cobol_result = run_cobol_instrumented(
        binary=cobol_instrumented_binary,
        input_csv=input_csv_path,
        output_csv=str(cobol_output_path),
        trace_file=str(trace_path),
        timeout=timeout
    )
    
    # Re-run Java on this single case
    java_result = run_java(
        class_name=java_class_name,
        classpath=java_classpath,
        input_csv=input_csv_path,
        output_csv=str(java_output_path),
        timeout=timeout
    )
    
    # Read outputs
    cobol_output = {}
    java_output = {}
    
    if cobol_output_path.exists():
        with open(cobol_output_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                cobol_output = rows[0]
    
    if java_output_path.exists():
        with open(java_output_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                java_output = rows[0]
    
    # Parse trace to get executed lines
    executed_lines = []
    if trace_path.exists():
        trace_counts = parse_trace_counts(str(trace_path))
        # Convert to sorted list of (source, line) tuples
        executed_lines = sorted(trace_counts.keys(), key=lambda x: (x[0], x[1]))
    
    # Clean up temporary input file
    Path(input_csv_path).unlink(missing_ok=True)
    
    return FailureReport(
        case_id=case_id,
        input_row=input_row,
        cobol_output=cobol_output,
        java_output=java_output,
        divergent_fields=minimal_case.divergent_fields,
        cobol_return_code=cobol_result.return_code,
        java_return_code=java_result.return_code,
        executed_lines=executed_lines
    )

