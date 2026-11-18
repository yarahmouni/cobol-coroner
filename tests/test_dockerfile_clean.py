#!/usr/bin/env python3
"""Test that Dockerfile does not COPY any gitignored paths."""
import re
import subprocess
from pathlib import Path


def test_dockerfile_clean():
    """Verify all COPY/ADD source paths in Dockerfile are not gitignored and exist in git ls-files."""
    repo_root = Path(__file__).resolve().parents[1]
    dockerfile_path = repo_root / "Dockerfile"
    assert dockerfile_path.exists()
    
    content = dockerfile_path.read_text()
    
    # Parse COPY and ADD instructions, excluding --from= copies
    copy_add_pattern = re.compile(
        r'^(?:COPY|ADD)\s+(?!--from=)(?:--\w+(?:=\S+)?\s+)*(\S+)',
        re.MULTILINE
    )
    
    source_paths = []
    for match in copy_add_pattern.finditer(content):
        path = match.group(1)
        # Skip if it's a flag (starts with --)
        if not path.startswith('--'):
            source_paths.append(path)
    
    # For each source path, verify it's not gitignored and exists in git ls-files
    for path in source_paths:
        # Check if gitignored
        check_ignore = subprocess.run(
            ['git', 'check-ignore', '-q', path],
            capture_output=True,
            cwd=repo_root
        )
        
        # check-ignore returns 0 if the path is ignored, 1 if not ignored
        assert check_ignore.returncode != 0, (
            f"Dockerfile COPY/ADD source path '{path}' is gitignored. "
            f"All COPY/ADD sources must be tracked or explicitly not ignored."
        )
        
        # Verify the path or at least one file under it exists in git ls-files
        # Strip trailing slash for git ls-files lookup
        lookup_path = path.rstrip('/')
        result = subprocess.run(
            ['git', 'ls-files', '--', lookup_path],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root
        )
        git_files = [f for f in result.stdout.strip().split('\n') if f]
        
        assert git_files, (
            f"Dockerfile COPY/ADD source directory '{path}' has no tracked files"
        )
