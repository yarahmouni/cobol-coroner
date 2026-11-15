"""Trace parsing module for Coroner."""

import re
from pathlib import Path


def parse_trace(path: str) -> set[int]:
    """
    Parse GnuCOBOL trace file and return executed line numbers.
    
    Args:
        path: Path to the trace file
        
    Returns:
        Set of executed line numbers
        
    Raises:
        FileNotFoundError: If trace file does not exist
        ValueError: If trace file is empty
    """
    trace_path = Path(path)
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")
    
    content = trace_path.read_text()
    if not content.strip():
        raise ValueError("Trace file is empty")
    
    line_pattern = re.compile(r'Line:\s+(\d+)')
    lines = set()
    
    for match in line_pattern.finditer(content):
        line_num = int(match.group(1))
        lines.add(line_num)
    
    return lines
