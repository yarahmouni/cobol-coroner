"""Tests for scripts/precommit_guard.py"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from precommit_guard import check, parse_allowed_paths


def test_added_root_file_not_listed_is_refused():
    """Added root file not in allowed list is refused."""
    staged = [("A", "newfile.txt")]
    allowed = {"README.md", "LICENSE"}
    
    def read_text(path):
        return "content"
    
    errors = check(staged, read_text, allowed)
    assert len(errors) == 1
    assert "newfile.txt" in errors[0]
    assert "not listed" in errors[0]


def test_listed_root_file_passes():
    """Listed root file passes."""
    staged = [("A", "README.md")]
    allowed = {"README.md", "LICENSE"}
    
    def read_text(path):
        return "content"
    
    errors = check(staged, read_text, allowed)
    assert len(errors) == 0


def test_added_scripts_file_not_listed_is_refused():
    """Added scripts/x.py not in allowed list is refused."""
    staged = [("A", "scripts/helper.py")]
    allowed = {"scripts/precommit_guard.py"}
    
    def read_text(path):
        return "content"
    
    errors = check(staged, read_text, allowed)
    assert len(errors) == 1
    assert "scripts/helper.py" in errors[0]
    assert "not listed" in errors[0]


def test_modified_file_with_home_prefix_is_refused():
    """Modified file containing home prefix is refused."""
    home_prefix = "/" + "Users" + "/"
    staged = [("M", "tests/test_foo.py")]
    allowed = set()
    
    def read_text(path):
        return f"path = '{home_prefix}yassinr/file.txt'"
    
    errors = check(staged, read_text, allowed)
    assert len(errors) == 1
    assert "test_foo.py" in errors[0]
    assert "home path" in errors[0]


def test_file_in_tests_not_subject_to_rule_2():
    """File in tests/ is not subject to rule 2."""
    staged = [("A", "tests/test_new.py")]
    allowed = set()  # Empty allowed set
    
    def read_text(path):
        return "content"
    
    errors = check(staged, read_text, allowed)
    assert len(errors) == 0


def test_file_in_samples_not_subject_to_rule_2():
    """File in samples/ is not subject to rule 2."""
    staged = [("A", "samples/new-sample/input.csv")]
    allowed = set()  # Empty allowed set
    
    def read_text(path):
        return "content"
    
    errors = check(staged, read_text, allowed)
    assert len(errors) == 0


def test_parse_allowed_paths_from_architecture():
    """Parse of architecture.md layout returns the 12 paths."""
    arch_content = """
# Architecture

## Repository layout

### Root files
- `.dockerignore`
- `.gitattributes`
- `.gitignore`
- `Dockerfile`
- `LICENSE`
- `Makefile`
- `README.md`
- `pyproject.toml`

### Scripts
- `scripts/check_cobol_rules.py`
- `scripts/gen_parity_cases.py`
- `scripts/gen_rounding_ties.py`
- `scripts/precommit_guard.py`

## Security
"""
    
    allowed = parse_allowed_paths(arch_content)
    
    # 8 root files + 4 scripts = 12 paths
    expected = {
        ".dockerignore",
        ".gitattributes",
        ".gitignore",
        "Dockerfile",
        "LICENSE",
        "Makefile",
        "README.md",
        "pyproject.toml",
        "scripts/check_cobol_rules.py",
        "scripts/gen_parity_cases.py",
        "scripts/gen_rounding_ties.py",
        "scripts/precommit_guard.py",
    }
    
    assert allowed == expected
    assert len(allowed) == 12
