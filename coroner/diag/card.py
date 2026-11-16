"""Given/When/Then card generation module for Coroner."""

from pathlib import Path
from typing import Optional
from coroner.diag.report import FailureReport
from coroner.parse.schema import Schema


def _filter_relevant_lines(
    executed_lines: list[tuple[str, int]],
    divergent_field_names: list[str],
    cobol_source_path: str,
    copybook_dir: str
) -> list[tuple[str, int, str]]:
    """
    Filter executed lines to keep only statements that can change divergent output fields.
    
    Among the executed lines of the minimal case, keep:
    - Arithmetic statements: COMPUTE, ADD, SUBTRACT, MULTIPLY, DIVIDE
    - MOVE statements whose target is an output field or a field moved into it
      (follow MOVE targets back from output record fields by name, one level)
    
    Returns list of (source_file, line_number, statement_text) tuples in source order.
    
    Args:
        executed_lines: List of (source_file, line_number) tuples from trace
        divergent_field_names: List of divergent output field names
        cobol_source_path: Path to COBOL source file
        copybook_dir: Directory containing copybooks
    """
    # Read all source files (main program and copybooks)
    source_cache = {}
    
    def read_source(file_path: str) -> list[str]:
        """Read a source file and cache it."""
        if file_path not in source_cache:
            try:
                with open(file_path, 'r') as f:
                    source_cache[file_path] = f.readlines()
            except FileNotFoundError:
                source_cache[file_path] = []
        return source_cache[file_path]
    
    # Read main source
    main_lines = read_source(cobol_source_path)
    
    # Build map of executed line numbers to their source text
    line_map = {}
    for source_file, line_num in executed_lines:
        # Resolve source file path
        # source_file might be a full path or just a filename
        if Path(source_file).resolve() == Path(cobol_source_path).resolve():
            resolved_path = cobol_source_path
        elif source_file == Path(cobol_source_path).name:
            resolved_path = cobol_source_path
        elif source_file == cobol_source_path:
            resolved_path = cobol_source_path
        else:
            # Try copybook directory
            resolved_path = str(Path(copybook_dir) / Path(source_file).name)
        
        source_lines = read_source(resolved_path)
        if 0 < line_num <= len(source_lines):
            line_text = source_lines[line_num - 1].strip()
            line_map[(source_file, line_num)] = (resolved_path, line_text)
    
    # Filter to relevant statements
    relevant = []
    
    for source_file, line_num in executed_lines:
        if (source_file, line_num) not in line_map:
            continue
        
        resolved_path, line_text = line_map[(source_file, line_num)]
        upper_text = line_text.upper()
        
        # Keep arithmetic statements (match whole words only to avoid matching COMPUTE-FEE paragraph names)
        # Split on common COBOL delimiters
        words = upper_text.replace('=', ' ').replace('(', ' ').replace(')', ' ').replace(',', ' ').split()
        if any(keyword in words for keyword in ['COMPUTE', 'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE']):
            relevant.append((source_file, line_num, line_text))
            continue
        
        # Keep MOVE statements to output fields
        # Simple heuristic: check if any divergent field name appears after MOVE
        if 'MOVE' in upper_text:
            # Check if any divergent field name (or related working storage field) appears in the statement
            # This is a one-level approximation: we look for field names that match output columns
            # or common patterns like WS-<field> or OUT-<field>
            for field_name in divergent_field_names:
                # Build patterns to match
                patterns = [
                    field_name.upper(),
                    f"OUT-{field_name.upper().replace('-', '_')}",
                    f"OUT-{field_name.upper()}",
                    f"WS-{field_name.upper().replace('-', '_')}",
                    f"WS-{field_name.upper()}",
                ]
                
                # Check if any pattern appears after TO in the MOVE statement
                if ' TO ' in upper_text:
                    target_part = upper_text.split(' TO ', 1)[1]
                    if any(pattern in target_part for pattern in patterns):
                        relevant.append((source_file, line_num, line_text))
                        break
    
    return relevant


def generate_card(
    failure_report: FailureReport,
    schema: Schema,
    cobol_source_path: str,
    copybook_dir: str,
    trap_title: Optional[str] = None,
    probable_cause: Optional[str] = None,
    suggested_fix: Optional[str] = None
) -> str:
    """
    Generate a deterministic Given/When/Then card from a failure report.
    
    This is a deterministic template (no LLM, no randomness) that builds
    a card from the minimal case input row, COBOL output row, Java output row,
    divergent fields, exit statuses, and COBOL lines executed.
    
    Args:
        failure_report: The failure report with minimal case details
        schema: Schema with input/output column definitions
        cobol_source_path: Path to COBOL source file
        copybook_dir: Directory containing copybooks
        trap_title: Optional trap title (e.g., "EBCDIC vs ASCII collating order")
        probable_cause: Optional deterministic probable cause from trap catalog
        suggested_fix: Optional one-sentence fix from trap catalog (D-26)
        
    Returns:
        A string with the Given/When/Then card format
    """
    lines = []
    
    # Given: input fields in schema order
    input_field_parts = []
    for col in schema.input_columns:
        value = failure_report.input_row.get(col.name, "")
        input_field_parts.append(f"{col.name}={value}")
    given_line = "Given " + ", ".join(input_field_parts)
    lines.append(given_line)
    
    # When: operation from trap title or program name
    operation = trap_title if trap_title else f"processing {schema.program_name}"
    when_line = f"When the COBOL reference and the Java port process this case"
    lines.append(when_line)
    
    # Then: divergent fields
    then_parts = []
    for field_name, cobol_value, java_value in failure_report.divergent_fields:
        then_parts.append(
            f"COBOL returns {field_name}={cobol_value} and Java returns {field_name}={java_value}"
        )
    
    # Add exit status comparison if they differ
    if failure_report.cobol_return_code != failure_report.java_return_code:
        then_parts.append(
            f"COBOL exits {failure_report.cobol_return_code} and Java exits {failure_report.java_return_code}"
        )
    
    for part in then_parts:
        lines.append(f"Then {part}")
    
    # COBOL lines involved: filter to relevant statements only
    if failure_report.executed_lines:
        divergent_field_names = [field_name for field_name, _, _ in failure_report.divergent_fields]
        relevant_lines = _filter_relevant_lines(
            failure_report.executed_lines,
            divergent_field_names,
            cobol_source_path,
            copybook_dir
        )
        
        if relevant_lines:
            line_parts = []
            for source_file, line_num, line_text in relevant_lines:
                # Format: "file:line STATEMENT"
                line_parts.append(f"{source_file}:{line_num} {line_text}")
            
            cobol_lines = "COBOL lines involved: " + "; ".join(line_parts)
            lines.append(cobol_lines)
    
    # Probable cause (when trap metadata exists)
    if probable_cause:
        lines.append("")
        lines.append(f"Probable cause (deterministic, from the trap catalog): {probable_cause}")
    
    # Suggested fix (D-26: never applied by Coroner)
    if suggested_fix:
        lines.append(f"Suggested fix: {suggested_fix}")
    
    return "\n".join(lines) + "\n"
