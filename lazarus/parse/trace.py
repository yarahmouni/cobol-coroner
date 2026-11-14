"""Parse GnuCOBOL trace files to extract executed line numbers."""

import re
from pathlib import Path


def parse_trace(trace_file_path: str) -> set[int]:
    """
    Parse a GnuCOBOL trace file and return executed line numbers.
    
    Args:
        trace_file_path: Path to the trace output file
        
    Returns:
        Set of line numbers that were executed
        
    Raises:
        FileNotFoundError: trace file does not exist
        ValueError: trace file is empty or unparseable
    """
    path = Path(trace_file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_file_path}")
    
    content = path.read_text()
    
    if not content.strip():
        raise ValueError("Trace file is empty")
    
    # Extract line numbers from executed statement records.
    # Format: "Program-Id: TOY ... Line: 9"
    # Only lines with "Line:" field carry line numbers (executed statements).
    # Header lines like "Source:" and bare "Program-Id:" lines have no line number.
    line_numbers = set()
    pattern = re.compile(r'\bLine:\s+(\d+)')
    
    for match in pattern.finditer(content):
        line_number = int(match.group(1))
        line_numbers.add(line_number)
    
    return line_numbers
