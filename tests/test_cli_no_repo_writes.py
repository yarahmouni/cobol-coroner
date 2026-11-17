"""Test that CLI subprocess tests do not write to the repository's runs/."""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_cli_subprocess_does_not_write_to_repo_runs(tmp_path):
    """Assert that a CLI test run with CORONER_BASE_DIR does not modify the repository's runs/."""
    repo_runs = Path.cwd() / "runs"
    
    # Count entries and get mtime before the run
    entries_before = list(repo_runs.iterdir()) if repo_runs.exists() else []
    count_before = len(entries_before)
    mtime_before = {p.name: p.stat().st_mtime for p in entries_before}
    
    # Run CLI in tmp_path
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", "samples/credit-fees/CREDIT-FEES.cob",
            "--copybooks", "samples/credit-fees/copybooks",
            "--java", "samples/credit-fees/java/CreditFees.java",
            "--schema", "samples/credit-fees/schema.json",
            "--cases", "30",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=env
    )
    
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    
    # Check runs/ after
    entries_after = list(repo_runs.iterdir()) if repo_runs.exists() else []
    count_after = len(entries_after)
    mtime_after = {p.name: p.stat().st_mtime for p in entries_after}
    
    # Assert count unchanged
    assert count_after == count_before, f"runs/ entry count changed: {count_before} -> {count_after}"
    
    # Assert no entry was modified
    for name in mtime_before:
        if name in mtime_after:
            assert mtime_after[name] == mtime_before[name], f"runs/{name} was modified"
    
    # Verify run was written to tmp_path instead
    tmp_runs = tmp_path / "runs"
    assert tmp_runs.exists(), "tmp_path/runs/ does not exist"
    # Filter for actual run directories (have inputs.json)
    tmp_entries = [d for d in tmp_runs.iterdir() if d.is_dir() and (d / "inputs.json").exists()]
    assert len(tmp_entries) == 1, f"Expected 1 run in tmp_path, got {len(tmp_entries)}"
