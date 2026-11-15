"""Tests for pre-commit fast mode."""

import os
import re
import subprocess


def test_precommit_alive():
    """Test make precommit with correct Java returns ALIVE and exits 0."""
    result = subprocess.run(
        ["make", "precommit"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    
    output = result.stdout + result.stderr
    assert "ALIVE" in output, f"Expected ALIVE in output, got:\n{output}"
    
    # Check timing is under 20 seconds
    # The CLI output format includes "on N cases"
    match = re.search(r"on \d+ cases", output)
    assert match is not None, f"Expected 'on N cases' in output, got:\n{output}"


def test_precommit_zombie():
    """Test make precommit with HALF_EVEN variant returns ZOMBIE and exits non-zero."""
    env = os.environ.copy()
    env["CORONER_PRECOMMIT_JAVA"] = "build/variants/CreditFees.java"
    
    # Ensure the variant exists
    subprocess.run(
        ["make", "zombie"],
        capture_output=True,
        timeout=30,
    )
    
    result = subprocess.run(
        ["make", "precommit"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
    
    output = result.stdout + result.stderr
    assert "ZOMBIE" in output, f"Expected ZOMBIE in output, got:\n{output}"


def test_precommit_hook_blocks_zombie():
    """Test pre-commit hook blocks ZOMBIE commits with the legacy variant."""
    env = os.environ.copy()
    env["CORONER_PRECOMMIT_JAVA"] = "build/variants/CreditFees.java"
    
    # Ensure the variant exists
    subprocess.run(
        ["make", "zombie"],
        capture_output=True,
        timeout=30,
    )
    
    result = subprocess.run(
        ["sh", ".githooks/pre-commit"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    
    assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
    
    output = result.stdout + result.stderr
    assert "Commit blocked by Coroner" in output, f"Expected 'Commit blocked by Coroner' in output, got:\n{output}"
    assert "ZOMBIE" in output, f"Expected 'ZOMBIE' in output, got:\n{output}"
