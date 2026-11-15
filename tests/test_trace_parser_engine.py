"""Tests for engine trace parser with two-source support."""

import pytest
from pathlib import Path
from coroner.parse.trace import parse_trace, parse_trace_counts


def test_parse_trace_counts_two_source():
    """Test parse_trace_counts on a trace with two source files."""
    trace_path = "tests/fixtures/trace2/sample_trace.txt"
    counts = parse_trace_counts(trace_path)
    
    assert isinstance(counts, dict)
    
    main_source = "tests/fixtures/trace2/trace-two-source.cob"
    copybook_source = "tests/fixtures/trace2/HELPER.CPY"
    
    main_lines = [key for key in counts.keys() if key[0] == main_source]
    copybook_lines = [key for key in counts.keys() if key[0] == copybook_source]
    
    assert len(main_lines) >= 5, f"Expected at least 5 main program lines, got {len(main_lines)}"
    assert len(copybook_lines) >= 3, f"Expected at least 3 copybook lines, got {len(copybook_lines)}"


def test_parse_trace_counts_main_program_lines():
    """Test that main program lines are present with correct source key."""
    trace_path = "tests/fixtures/trace2/sample_trace.txt"
    counts = parse_trace_counts(trace_path)
    
    main_source = "tests/fixtures/trace2/trace-two-source.cob"
    
    assert (main_source, 9) in counts
    assert (main_source, 10) in counts
    assert (main_source, 11) in counts
    assert (main_source, 16) in counts
    assert (main_source, 12) in counts
    assert (main_source, 13) in counts
    assert (main_source, 14) in counts


def test_parse_trace_counts_copybook_lines():
    """Test that copybook lines are present and keyed separately."""
    trace_path = "tests/fixtures/trace2/sample_trace.txt"
    counts = parse_trace_counts(trace_path)
    
    copybook_source = "tests/fixtures/trace2/HELPER.CPY"
    
    assert (copybook_source, 1) in counts
    assert (copybook_source, 2) in counts
    assert (copybook_source, 3) in counts


def test_parse_trace_counts_empty_trace():
    """Test that empty trace raises ValueError."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="empty"):
            parse_trace_counts(temp_path)
    finally:
        Path(temp_path).unlink()


def test_parse_trace_counts_missing_file():
    """Test that missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_trace_counts("nonexistent_trace.txt")


def test_parse_trace_wrapper_still_works():
    """Test that the original parse_trace wrapper still works on simple traces."""
    trace_path = "tests/fixtures/sample_trace.txt"
    lines = parse_trace(trace_path)
    
    assert isinstance(lines, set)
    assert 9 in lines
    assert 10 in lines
    assert 11 in lines
    assert 16 in lines
    assert 17 in lines
    assert 13 not in lines


def test_parse_trace_counts_execution_counts():
    """Test that execution counts are tracked correctly."""
    trace_path = "tests/fixtures/trace2/sample_trace.txt"
    counts = parse_trace_counts(trace_path)
    
    for key, count in counts.items():
        assert count >= 1, f"Line {key} should have count >= 1, got {count}"
