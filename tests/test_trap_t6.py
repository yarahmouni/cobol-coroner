"""Tests for T6 reserved placeholder."""
import os
import pytest


def test_t6_directory_only_has_readme():
    """T6-reserved/ should contain only README.md."""
    t6_dir = "samples/traps/T6-reserved"
    assert os.path.isdir(t6_dir), f"{t6_dir} does not exist"
    
    files = os.listdir(t6_dir)
    assert files == ["README.md"], f"T6-reserved should only contain README.md, found: {files}"


def test_t6_readme_contains_status_line():
    """T6 README.md should contain the status line."""
    readme_path = "samples/traps/T6-reserved/README.md"
    assert os.path.isfile(readme_path), f"{readme_path} does not exist"
    
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "placeholder: owner field trap pending" in content, \
        "README.md must contain 'placeholder: owner field trap pending'"
