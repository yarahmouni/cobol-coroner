#!/usr/bin/env python3
"""Pre-commit guard: blocks home paths and unexpected root/scripts files."""

import re
import subprocess
import sys
from pathlib import Path


def check(staged, read_text, allowed):
    """Check staged files against pre-commit rules.
    
    Args:
        staged: List of (status, path) pairs where status is 'A' (added) or 'M' (modified).
        read_text: Function that takes a path and returns its staged content as text.
        allowed: Set of allowed paths for root and scripts/ files.
    
    Returns:
        List of error strings.
    """
    errors = []
    home_prefix = "/" + "Users" + "/"
    
    for status, path in staged:
        if status not in ('A', 'M'):
            continue
        
        # Rule 1: Check content for home path
        content = read_text(path)
        if content is not None and home_prefix in content:
            errors.append(f"{path}: contains forbidden home path prefix")
        
        # Rule 2: Check added root and scripts/ files
        if status == 'A':
            # Root file: no "/" in path
            if "/" not in path:
                if path not in allowed:
                    errors.append(f"{path}: added root file not listed in docs/architecture.md")
            # Direct scripts/ file: path is "scripts/filename.ext"
            elif path.startswith("scripts/") and path.count("/") == 1:
                if path not in allowed:
                    errors.append(f"{path}: added scripts file not listed in docs/architecture.md")
    
    return errors


def parse_allowed_paths(arch_content):
    """Parse allowed paths from docs/architecture.md Repository layout section."""
    allowed = set()
    in_root_files = False
    in_scripts = False
    
    for line in arch_content.splitlines():
        if line.strip() == "### Root files":
            in_root_files = True
            in_scripts = False
        elif line.strip() == "### Scripts":
            in_root_files = False
            in_scripts = True
        elif line.startswith("###") or line.startswith("##"):
            in_root_files = False
            in_scripts = False
        elif in_root_files or in_scripts:
            # Match `path` in backticks
            match = re.search(r'`([^`]+)`', line)
            if match:
                allowed.add(match.group(1))
    
    return allowed


def main():
    """Run pre-commit checks on staged files."""
    # Get staged files
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=AM"],
        capture_output=True,
        text=True,
        check=True
    )
    
    staged = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            status, path = parts
            staged.append((status, path))
    
    # Read text function
    def read_text(path):
        try:
            result = subprocess.run(
                ["git", "show", f":{path}"],
                capture_output=True,
                check=True
            )
            return result.stdout.decode('utf-8')
        except (subprocess.CalledProcessError, UnicodeDecodeError):
            return None
    
    # Parse allowed paths
    arch_path = Path("docs/architecture.md")
    if not arch_path.exists():
        print("Error: docs/architecture.md not found")
        sys.exit(1)
    
    arch_content = arch_path.read_text()
    allowed = parse_allowed_paths(arch_content)
    
    # Check staged files
    errors = check(staged, read_text, allowed)
    
    if errors:
        for error in errors:
            print(f"Pre-commit guard: {error}")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
