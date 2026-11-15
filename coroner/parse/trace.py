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


def parse_trace_counts(path: str) -> dict[tuple[str, int], int]:
    """
    Parse GnuCOBOL trace file and return execution counts keyed by source file and line.
    
    Streams the trace file and tracks the current source file. Each line execution is
    keyed by (source_file, line_number) and counted.
    
    Args:
        path: Path to the trace file
        
    Returns:
        Dictionary mapping (source_file, line_number) to execution count
        
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
    
    source_pattern = re.compile(r"Source:\s+'([^']+)'")
    line_pattern = re.compile(r'Line:\s+(\d+)')
    
    counts: dict[tuple[str, int], int] = {}
    current_source = None
    
    for line in content.splitlines():
        source_match = source_pattern.search(line)
        if source_match:
            current_source = source_match.group(1)
            continue
        
        line_match = line_pattern.search(line)
        if line_match and current_source:
            line_num = int(line_match.group(1))
            key = (current_source, line_num)
            counts[key] = counts.get(key, 0) + 1
    
    return counts
