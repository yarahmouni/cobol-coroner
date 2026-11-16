"""Given/When/Then card generation module for Coroner."""

from pathlib import Path
from typing import Optional
from coroner.diag.report import FailureReport
from coroner.parse.schema import Schema


def _find_subtotal_paragraphs(cobol_source_path: str) -> set[str]:
    """
    Find paragraphs that contain ADD statements to subtotal or suspense accumulators.
    
    Returns a set of paragraph names (uppercase).
    """
    subtotal_paragraphs = set()
    
    try:
        with open(cobol_source_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return subtotal_paragraphs
    
    current_paragraph = None
    in_procedure_division = False
    
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        
        # Track when we enter PROCEDURE DIVISION
        if 'PROCEDURE DIVISION' in upper:
            in_procedure_division = True
            continue
        
        if not in_procedure_division:
            continue
        
        # Detect paragraph names: a line ending with a period that's not a statement
        # Must be at the start of a line (or after leading spaces) and contain only word characters
        # Skip lines that start with known verbs or keywords
        if stripped and not stripped.startswith('*') and stripped.endswith('.'):
            # Check if it looks like a paragraph header (single word or hyphenated name ending with period)
            words = stripped.split()
            if len(words) == 1 or (len(words) == 2 and words[1] == 'SECTION.'):
                first_word = words[0].rstrip('.')
                # Check it's not a verb or statement
                if not any(first_word.startswith(verb) for verb in [
                    'MOVE', 'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'COMPUTE',
                    'IF', 'ELSE', 'END-IF', 'PERFORM', 'ACCEPT', 'DISPLAY',
                    'OPEN', 'CLOSE', 'READ', 'WRITE', 'STOP', 'CONTINUE',
                    'RETURN', 'RELEASE', 'SORT', 'UNSTRING', 'STRING',
                    'EVALUATE', 'WHEN', 'END-EVALUATE', 'SET', 'INITIALIZE',
                    'GO', 'EXIT', 'GOBACK'
                ]):
                    # This looks like a paragraph name
                    current_paragraph = first_word
        
        # Check for ADD statements that target subtotal or suspense accumulators
        if current_paragraph and 'ADD' in upper and ' TO ' in upper:
            # Extract the target field (after TO)
            if ' TO ' in upper:
                target_part = upper.split(' TO ', 1)[1]
                # Remove END-ADD and other trailing keywords
                target_part = target_part.split('END-ADD')[0]
                target_part = target_part.split('END-IF')[0]
                target_part = target_part.split('ELSE')[0]
                # Check if the target contains subtotal or accumulator patterns
                if any(pattern in target_part for pattern in [
                    'SUBTOTAL', 'SUSP-', 'TOTAL', 'ACCUMULATOR', 'TABLE-', 'SUM', '-BALANCE'
                ]):
                    subtotal_paragraphs.add(current_paragraph)
    
    return subtotal_paragraphs


def _get_paragraph_bounds_from_source(cobol_source_path: str) -> dict[str, tuple[int, int]]:
    """
    Extract paragraph bounds from COBOL source file.
    
    Returns a dict mapping paragraph name (uppercase) to (start_line, end_line).
    A paragraph ends when the next paragraph begins or at end of file.
    """
    bounds = {}
    
    try:
        with open(cobol_source_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return bounds
    
    in_procedure_division = False
    paragraphs = []  # List of (name, line_number)
    
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        upper = stripped.upper()
        
        # Track when we enter PROCEDURE DIVISION
        if 'PROCEDURE DIVISION' in upper:
            in_procedure_division = True
            continue
        
        if not in_procedure_division:
            continue
        
        # Detect paragraph names: a line ending with a period that's not a statement
        # Must be at the start of a line (or after leading spaces) and contain only word characters
        if stripped and not stripped.startswith('*') and stripped.endswith('.'):
            # Check if it looks like a paragraph header (single word or hyphenated name ending with period)
            words = stripped.split()
            if len(words) == 1 or (len(words) == 2 and words[1] == 'SECTION.'):
                first_word = words[0].rstrip('.')
                # For hyphenated names, check the full name, not just the first part
                # A paragraph name like READ-INPUT-SKIP-HEADER is not the verb READ
                # Only exclude lines that are exactly a verb (no hyphens) or END-* markers
                if first_word.startswith('END-'):
                    # END-IF, END-PERFORM, etc. are not paragraphs
                    continue
                elif '-' in first_word:
                    # Hyphenated name: this is a paragraph
                    paragraphs.append((first_word, i))
                elif not any(first_word == verb for verb in [
                    'MOVE', 'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'COMPUTE',
                    'IF', 'ELSE', 'PERFORM', 'ACCEPT', 'DISPLAY',
                    'OPEN', 'CLOSE', 'READ', 'WRITE', 'STOP', 'CONTINUE',
                    'RETURN', 'RELEASE', 'SORT', 'UNSTRING', 'STRING',
                    'EVALUATE', 'WHEN', 'SET', 'INITIALIZE',
                    'GO', 'EXIT', 'GOBACK'
                ]):
                    paragraphs.append((first_word, i))
    
    # Calculate bounds: each paragraph extends until the next paragraph
    for i, (name, start_line) in enumerate(paragraphs):
        if i + 1 < len(paragraphs):
            end_line = paragraphs[i + 1][1] - 1
        else:
            end_line = len(lines)
        bounds[name] = (start_line, end_line)
    
    return bounds


def _filter_relevant_lines(
    executed_lines: list[tuple[str, int]],
    divergent_field_names: list[str],
    cobol_source_path: str,
    copybook_dir: str,
    has_group_key: bool = False,
    trace_path: Optional[str] = None
) -> list[tuple[str, int, str]]:
    """
    Filter executed lines to keep only statements that can change divergent output fields.
    
    For schemas without group_key:
    - Arithmetic statements: COMPUTE, ADD, SUBTRACT, MULTIPLY, DIVIDE
    - MOVE statements whose target is an output field or a field moved into it
    
    For schemas with group_key and subtotal:
    - Keep only executed lines that belong to paragraphs containing ADD statements
      to subtotal or suspense accumulators (table subtotals, SUSP-SUBTOTAL, etc.)
    
    Returns list of (source_file, line_number, statement_text) tuples in source order.
    
    Args:
        executed_lines: List of (source_file, line_number) tuples from trace
        divergent_field_names: List of divergent output field names
        cobol_source_path: Path to COBOL source file
        copybook_dir: Directory containing copybooks
        has_group_key: Whether schema has group_key (enables subtotal paragraph filtering)
        trace_path: Optional path to trace file for extracting paragraph bounds
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
    
    # For group_key schemas: filter by subtotal-accumulating paragraphs
    if has_group_key:
        # Find paragraphs that accumulate subtotals
        subtotal_paragraphs = _find_subtotal_paragraphs(cobol_source_path)
        
        if not subtotal_paragraphs:
            # No subtotal paragraphs found, return empty list
            return []
        
        # Get paragraph bounds from source structure
        para_bounds = _get_paragraph_bounds_from_source(cobol_source_path)
        
        # Filter executed lines to those within subtotal paragraphs
        relevant = []
        for source_file, line_num in executed_lines:
            if (source_file, line_num) not in line_map:
                continue
            
            resolved_path, line_text = line_map[(source_file, line_num)]
            
            # Only keep lines from the main source file
            if Path(resolved_path).resolve() != Path(cobol_source_path).resolve():
                continue
            
            # Check if this line is within any subtotal paragraph
            for para_name in subtotal_paragraphs:
                if para_name in para_bounds:
                    start_line, end_line = para_bounds[para_name]
                    if start_line <= line_num <= end_line:
                        relevant.append((source_file, line_num, line_text))
                        break
        
        return relevant
    
    # For non-group_key schemas: original logic
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
    # For multi-row cases, list all minimal rows
    if failure_report.minimal_case_rows:
        # Multi-row case: list each row
        lines.append("Given the following input rows:")
        for row in failure_report.minimal_case_rows:
            row_parts = []
            for col in schema.input_columns:
                value = row.get(col.name, "")
                row_parts.append(f"{col.name}={value}")
            lines.append("  " + ", ".join(row_parts))
    else:
        # Single-row case
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
    divergent_field_names = []
    
    for div_info in failure_report.divergent_fields:
        # Handle both new dict format and legacy tuple format
        if isinstance(div_info, dict):
            kind = div_info.get("kind", "value_mismatch")
            
            if kind == "missing_in_java":
                # Row present in COBOL, missing in Java
                output_key = div_info.get("output_key", {})
                cobol_values = div_info.get("cobol_values", {})
                # Format key columns (excluding case id)
                key_parts = [f"{k}={v}" for k, v in output_key.items() if k != "CASE-ID" and k in output_key]
                key_desc = ", ".join(key_parts) if key_parts else "row"
                # Format relevant values
                value_parts = [f"{k}={v}" for k, v in cobol_values.items() if k not in output_key]
                if value_parts:
                    then_parts.append(
                        f"COBOL writes row {key_desc} with {', '.join(value_parts)}, Java does not"
                    )
                else:
                    then_parts.append(
                        f"COBOL writes row {key_desc}, Java does not"
                    )
            elif kind == "missing_in_cobol":
                # Row present in Java, missing in COBOL
                output_key = div_info.get("output_key", {})
                java_values = div_info.get("java_values", {})
                # Format key columns (excluding case id)
                key_parts = [f"{k}={v}" for k, v in output_key.items() if k != "CASE-ID" and k in output_key]
                key_desc = ", ".join(key_parts) if key_parts else "row"
                # Format relevant values
                value_parts = [f"{k}={v}" for k, v in java_values.items() if k not in output_key]
                if value_parts:
                    then_parts.append(
                        f"Java writes row {key_desc} with {', '.join(value_parts)}, COBOL does not"
                    )
                else:
                    then_parts.append(
                        f"Java writes row {key_desc}, COBOL does not"
                    )
            else:
                # value_mismatch
                field_name = div_info.get("field_name", "")
                cobol_value = div_info.get("cobol_value", "")
                java_value = div_info.get("java_value", "")
                then_parts.append(
                    f"COBOL returns {field_name}={cobol_value} and Java returns {field_name}={java_value}"
                )
                divergent_field_names.append(field_name)
        else:
            # Legacy tuple format: (field_name, cobol_value, java_value)
            field_name, cobol_value, java_value = div_info
            then_parts.append(
                f"COBOL returns {field_name}={cobol_value} and Java returns {field_name}={java_value}"
            )
            divergent_field_names.append(field_name)
    
    # Add exit status comparison if they differ
    if failure_report.cobol_return_code != failure_report.java_return_code:
        then_parts.append(
            f"COBOL exits {failure_report.cobol_return_code} and Java exits {failure_report.java_return_code}"
        )
    
    for part in then_parts:
        lines.append(f"Then {part}")
    
    # COBOL lines involved: filter to relevant statements only
    if failure_report.executed_lines:
        has_group_key = hasattr(schema, 'group_key') and schema.group_key is not None
        
        # For group_key schemas, pass the trace path to extract paragraph bounds
        trace_path = None
        if has_group_key and hasattr(failure_report, 'minimal_case_trace') and failure_report.minimal_case_trace:
            trace_path = failure_report.minimal_case_trace
        
        relevant_lines = _filter_relevant_lines(
            failure_report.executed_lines,
            divergent_field_names,
            cobol_source_path,
            copybook_dir,
            has_group_key,
            trace_path
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
