"""Multi-row minimal case reduction for Coroner."""

import csv
import tempfile
from pathlib import Path

from coroner.compare import compare_outputs
from coroner.parse.schema import Schema
from coroner.run import run_cobol, run_java


def reduce_multirow_case(
    cobol_path: str,
    copybooks_path: str,
    java_path: str,
    schema: Schema,
    case_rows: list[dict],
    base_dir: str,
    cobol_binary: str | None = None,
    java_classpath: str | None = None,
    timeout: float = 60.0
) -> list[dict]:
    """
    Apply delta reduction to find the minimal subset of rows that still diverges.
    
    Uses greedy removal: try removing each row in turn. If the subset still
    diverges, keep the removal. Otherwise revert. After the greedy pass, try
    removing each remaining row once more until no single removal keeps the
    divergence (1-minimality).
    
    Args:
        cobol_path: Path to COBOL source file
        copybooks_path: Path to copybooks directory
        java_path: Path to Java source file
        schema: Schema with input/output definitions
        case_rows: All rows of the divergent case (sorted by case id)
        base_dir: Directory for temporary files
        cobol_binary: Path to pre-compiled COBOL binary (reuses if provided)
        java_classpath: Path to pre-compiled Java classes (reuses if provided)
        timeout: Execution timeout in seconds
        
    Returns:
        Minimal subset of rows that still diverges
        
    Raises:
        ValueError: If the final subset does not diverge
    """
    if not case_rows:
        raise ValueError("Cannot reduce empty case")
    
    # Compile binaries once if not provided
    if cobol_binary is None or java_classpath is None:
        from coroner.run import compile_cobol, compile_java
        
        if cobol_binary is None:
            cobol_binary = str(Path(base_dir) / "minimal_cobol")
            cobol_flags = schema.cobc_flags or []
            compile_cobol(cobol_path, copybooks_path, cobol_binary, cobol_flags, base_dir)
        
        if java_classpath is None:
            java_classpath = str(Path(base_dir) / "minimal_java")
            Path(java_classpath).mkdir(parents=True, exist_ok=True)
            compile_java(java_path, java_classpath, base_dir)
    
    # Start with all rows
    current_rows = list(case_rows)
    
    # Greedy pass: try removing each row
    i = 0
    while i < len(current_rows):
        # Create candidate subset without row i
        candidate = current_rows[:i] + current_rows[i+1:]
        
        if not candidate:
            # Cannot remove the last row
            i += 1
            continue
        
        # Test if candidate still diverges
        if _test_divergence(java_path, schema, candidate, base_dir, cobol_binary, java_classpath, timeout):
            # Keep the removal
            current_rows = candidate
            # Don't increment i, test the next row at the same index
        else:
            # Revert, move to next row
            i += 1
    
    # 1-minimality pass: try removing each remaining row once more
    changed = True
    while changed:
        changed = False
        for i in range(len(current_rows)):
            candidate = current_rows[:i] + current_rows[i+1:]
            
            if not candidate:
                continue
            
            if _test_divergence(java_path, schema, candidate, base_dir, cobol_binary, java_classpath, timeout):
                current_rows = candidate
                changed = True
                break
    
    # Final check: the minimal subset must diverge
    if not _test_divergence(java_path, schema, current_rows, base_dir, cobol_binary, java_classpath, timeout):
        raise ValueError("Minimal case reduction failed: final subset does not diverge")
    
    return current_rows


def _test_divergence(
    java_path: str,
    schema: Schema,
    rows: list[dict],
    base_dir: str,
    cobol_binary: str,
    java_classpath: str,
    timeout: float
) -> bool:
    """
    Test if a subset of rows produces divergent outputs.
    
    Returns True if divergent, False if outputs match.
    """
    # Write temporary input CSV
    temp_input = Path(base_dir) / f"test_input_{id(rows)}.csv"
    with open(temp_input, 'w', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[col.name for col in schema.input_columns])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    
    temp_cobol_output = Path(base_dir) / f"test_cobol_{id(rows)}.csv"
    temp_java_output = Path(base_dir) / f"test_java_{id(rows)}.csv"
    
    try:
        # Run COBOL
        cobol_result = run_cobol(
            binary=cobol_binary,
            input_csv=str(temp_input),
            output_csv=str(temp_cobol_output),
            timeout=timeout
        )
        
        # Run Java
        java_class_name = Path(java_path).stem
        java_result = run_java(
            class_name=java_class_name,
            classpath=java_classpath,
            input_csv=str(temp_input),
            output_csv=str(temp_java_output),
            timeout=timeout
        )
        
        # Compare outputs
        if not temp_cobol_output.exists() or not temp_java_output.exists():
            # Missing output is considered divergent
            return True
        
        comparison = compare_outputs(
            cobol_csv=str(temp_cobol_output),
            java_csv=str(temp_java_output),
            schema=schema,
            cobol_return_code=cobol_result.return_code,
            java_return_code=java_result.return_code
        )
        
        # Check if any case diverged or return codes differ
        divergent = (
            comparison.total_divergent > 0 or
            cobol_result.return_code != java_result.return_code
        )
        
        return divergent
        
    finally:
        # Clean up temporary files
        temp_input.unlink(missing_ok=True)
        temp_cobol_output.unlink(missing_ok=True)
        temp_java_output.unlink(missing_ok=True)
