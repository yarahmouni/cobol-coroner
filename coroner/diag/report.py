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
    original_case_rows: list[dict] | None = None  # For multi-row cases
    minimal_case_rows: list[dict] | None = None  # For multi-row cases


def generate_failure_report(
    minimal_case: CaseResult,
    input_rows: dict[str, dict],
    schema: Schema,
    cobol_instrumented_binary: str,
    java_class_name: str,
    java_classpath: str,
    run_dir: str,
    cobol_source_path: str | None = None,
    copybooks_path: str | None = None,
    java_source_path: str | None = None,
    timeout: float = 60.0
) -> FailureReport:
    """
    Generate a detailed failure report for the minimal case.
    
    Re-runs the minimal case alone on instrumented COBOL and Java to capture
    full details: both outputs, return codes, and executed COBOL lines.
    
    For multi-row cases (when schema has case_rows), applies delta reduction
    to find the minimal subset of rows that still diverges.
    
    Args:
        minimal_case: The minimal CaseResult to analyze
        input_rows: Dict mapping case_id to input row dict (or list of dicts for multi-row)
        schema: Schema with input/output column definitions
        cobol_instrumented_binary: Path to instrumented COBOL binary
        java_class_name: Java main class name
        java_classpath: Java classpath
        run_dir: Directory for temporary files
        cobol_source_path: Path to COBOL source (required for multi-row reduction)
        copybooks_path: Path to copybooks directory (required for multi-row reduction)
        java_source_path: Path to Java source (required for multi-row reduction)
        timeout: Execution timeout in seconds
        
    Returns:
        FailureReport with all details
    """
    case_id = minimal_case.case_id
    
    # Check if this is a multi-row case
    is_multirow = hasattr(schema, 'case_rows') and schema.case_rows is not None
    
    original_rows = None
    minimal_rows = None
    input_row = None
    
    if is_multirow:
        # Multi-row case: input_rows[case_id] is a list
        case_data = input_rows.get(case_id)
        if isinstance(case_data, list):
            original_rows = case_data
        else:
            # Fallback: single row wrapped in list
            original_rows = [case_data] if case_data else []
        
        # Apply delta reduction
        if cobol_source_path and java_source_path and copybooks_path and original_rows:
            from coroner.diag.minimal import reduce_multirow_case
            minimal_rows = reduce_multirow_case(
                cobol_source_path,
                copybooks_path,
                java_source_path,
                schema,
                original_rows,
                run_dir,
                cobol_binary=cobol_instrumented_binary,
                java_classpath=java_classpath,
                timeout=timeout
            )
        else:
            # Cannot reduce without source paths
            minimal_rows = original_rows
        
        # Use first row as the legacy input_row field
        input_row = original_rows[0] if original_rows else {}
        
        # Write minimal_case_input.csv with the minimal subset
        input_csv_path = Path(run_dir) / "minimal_case_input.csv"
        with open(input_csv_path, 'w', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[col.name for col in schema.input_columns])
            writer.writeheader()
            for row in minimal_rows:
                writer.writerow(row)
        
        input_csv_str = str(input_csv_path)
    else:
        # Single-row case: use existing logic
        input_row = input_rows[case_id]
        
        # Create temporary files for single-case re-run
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, dir=run_dir) as input_file:
            input_csv_str = input_file.name
            writer = csv.DictWriter(input_file, fieldnames=[col.name for col in schema.input_columns])
            writer.writeheader()
            writer.writerow(input_row)
    
    cobol_output_path = Path(run_dir) / "minimal_case_cobol_output.csv"
    java_output_path = Path(run_dir) / "minimal_case_java_output.csv"
    trace_path = Path(run_dir) / "minimal_case_trace.txt"
    
    # Re-run instrumented COBOL on this case
    cobol_result = run_cobol_instrumented(
        binary=cobol_instrumented_binary,
        input_csv=input_csv_str,
        output_csv=str(cobol_output_path),
        trace_file=str(trace_path),
        timeout=timeout
    )
    
    # Re-run Java on this case
    java_result = run_java(
        class_name=java_class_name,
        classpath=java_classpath,
        input_csv=input_csv_str,
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
    
    # Clean up temporary input file for single-row case
    if not is_multirow and input_csv_str:
        Path(input_csv_str).unlink(missing_ok=True)
    
    return FailureReport(
        case_id=case_id,
        input_row=input_row or {},
        cobol_output=cobol_output,
        java_output=java_output,
        divergent_fields=minimal_case.divergent_fields,
        cobol_return_code=cobol_result.return_code,
        java_return_code=java_result.return_code,
        executed_lines=executed_lines,
        original_case_rows=original_rows,
        minimal_case_rows=minimal_rows
    )

