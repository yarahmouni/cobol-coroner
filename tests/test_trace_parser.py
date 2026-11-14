"""Unit tests for GnuCOBOL trace parser."""

import pytest
from pathlib import Path
from lazarus.parse.trace import parse_trace


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_trace_with_valid_fixture():
    """Test parse_trace with real GnuCOBOL trace fixture."""
    fixture_path = FIXTURES / "sample_trace.txt"
    result = parse_trace(str(fixture_path))
    
    # Line 9: MAIN-LOGIC paragraph (entry + paragraph records)
    # Line 10: IF statement
    # Line 11: DISPLAY in IF branch (THEN)
    # Line 16: MOVE statement after IF
    # Line 17: STOP RUN
    # Line 13 (ELSE branch) is NOT executed, must be absent
    assert result == {9, 10, 11, 16, 17}
    assert 13 not in result, "Line 13 (ELSE branch) should not be in executed lines"


def test_parse_trace_with_empty_file(tmp_path):
    """Test parse_trace with empty trace file raises ValueError."""
    empty_file = tmp_path / "empty_trace.txt"
    empty_file.write_text("")
    
    with pytest.raises(ValueError, match="Trace file is empty"):
        parse_trace(str(empty_file))


def test_parse_trace_with_missing_file(tmp_path):
    """Test parse_trace with non-existent file raises FileNotFoundError."""
    missing_file = tmp_path / "nonexistent_trace.txt"
    
    with pytest.raises(FileNotFoundError, match="Trace file not found"):
        parse_trace(str(missing_file))


def test_parse_trace_with_duplicate_line_numbers(tmp_path):
    """Test parse_trace with duplicate line numbers returns deduplicated set."""
    trace_file = tmp_path / "duplicate_trace.txt"
    trace_content = """Source: 'test.cob'
Program-Id:  TEST
Program-Id:  TEST                  Entry: TEST                            Line:      5
Program-Id:  TEST              Paragraph: LOOP-PARA                       Line:      5
Program-Id:  TEST                         DISPLAY                         Line:     10
Program-Id:  TEST                         ADD                             Line:     11
Program-Id:  TEST                         DISPLAY                         Line:     10
Program-Id:  TEST                         ADD                             Line:     11
Program-Id:  TEST                         DISPLAY                         Line:     10
Program-Id:  TEST                         STOP RUN                        Line:     15
"""
    trace_file.write_text(trace_content)
    result = parse_trace(str(trace_file))
    
    # Set automatically deduplicates
    assert result == {5, 10, 11, 15}
