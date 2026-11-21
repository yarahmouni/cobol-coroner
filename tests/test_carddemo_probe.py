"""Test CardDemo CBACT04C probe targets."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_probe_upstream(tmp_path):
    """Test probe-upstream reproduces committed files byte for byte."""
    sample_dir = Path("samples/carddemo-cbact04c")
    build_dir = tmp_path / "build"
    probe_dir = tmp_path / "probe"
    
    # Run probe-upstream
    result = subprocess.run(
        ["make", "-C", str(sample_dir), 
         f"BUILD_DIR={build_dir}", 
         f"PROBE_DIR={probe_dir}",
         "probe-upstream"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"probe-upstream failed: {result.stderr}"
    
    # Compare outputs with committed files
    committed_dir = sample_dir / "probe" / "upstream-sample"
    generated_dir = probe_dir / "upstream-sample"
    
    for filename in ["display.txt", "acctdata-before.txt", "acctdata-after.txt", "transact.txt"]:
        committed = (committed_dir / filename).read_bytes()
        generated = (generated_dir / filename).read_bytes()
        assert committed == generated, f"{filename} differs from committed version"


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_probe_nonzero(tmp_path):
    """Test probe-nonzero reproduces committed files byte for byte."""
    sample_dir = Path("samples/carddemo-cbact04c")
    build_dir = tmp_path / "build"
    probe_dir = tmp_path / "probe"
    
    # Run probe-nonzero
    result = subprocess.run(
        ["make", "-C", str(sample_dir), 
         f"BUILD_DIR={build_dir}", 
         f"PROBE_DIR={probe_dir}",
         "probe-nonzero"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"probe-nonzero failed: {result.stderr}"
    
    # Compare outputs with committed files
    committed_dir = sample_dir / "probe" / "probe-nonzero"
    generated_dir = probe_dir / "probe-nonzero"
    
    for filename in ["display.txt", "acctdata-before.txt", "acctdata-after.txt", "transact.txt"]:
        committed = (committed_dir / filename).read_bytes()
        generated = (generated_dir / filename).read_bytes()
        assert committed == generated, f"{filename} differs from committed version"


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_probe_missing_default(tmp_path):
    """Test probe-missing-default reproduces committed files byte for byte."""
    sample_dir = Path("samples/carddemo-cbact04c")
    build_dir = tmp_path / "build"
    probe_dir = tmp_path / "probe"
    
    # Run probe-missing-default
    result = subprocess.run(
        ["make", "-C", str(sample_dir), 
         f"BUILD_DIR={build_dir}", 
         f"PROBE_DIR={probe_dir}",
         "probe-missing-default"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"probe-missing-default failed: {result.stderr}"
    
    # Compare outputs with committed files
    committed_dir = sample_dir / "probe" / "missing-default"
    generated_dir = probe_dir / "missing-default"
    
    for filename in ["display.txt", "acctdata-before.txt", "acctdata-after.txt", "transact.txt", "exit-code.txt"]:
        committed = (committed_dir / filename).read_bytes()
        generated = (generated_dir / filename).read_bytes()
        assert committed == generated, f"{filename} differs from committed version"
    
    # Verify exit code is 231
    exit_code = (generated_dir / "exit-code.txt").read_text().strip()
    assert exit_code == "231", f"Expected exit code 231, got {exit_code}"
