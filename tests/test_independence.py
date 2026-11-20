"""Tests for the independence track table generation."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def repo_root():
    """Repository root directory."""
    return Path(__file__).parent.parent


def test_parse_certificate(tmp_path, repo_root):
    """Test that run_table.py can parse a real certificate."""
    # Copy an existing run to tmp_path
    src_run = repo_root / "runs" / "0d1e698359fb"
    if not src_run.exists():
        pytest.skip("Run 0d1e698359fb not found")
    
    tmp_runs = tmp_path / "runs"
    tmp_runs.mkdir()
    dest_run = tmp_runs / "0d1e698359fb"
    shutil.copytree(src_run, dest_run)
    
    # Read certificate
    cert_file = dest_run / "certificate.json"
    assert cert_file.exists()
    
    with open(cert_file, "r", encoding="utf-8") as f:
        cert = json.load(f)
    
    # Check required fields
    assert cert["status"] in ("ALIVE", "ZOMBIE")
    assert "cases_divergent" in cert
    assert "cases_total" in cert
    assert cert["cases_total"] == 2000
    assert cert["random_seed"] == 42
    
    # Read branch reconciliation
    recon_file = dest_run / "branch_reconciliation.json"
    assert recon_file.exists()
    
    with open(recon_file, "r", encoding="utf-8") as f:
        recon = json.load(f)
    
    # Check structure
    assert "branches" in recon
    assert "grand_total" in recon
    assert isinstance(recon["branches"], list)


def test_source_label_parsing(repo_root):
    """Test that SOURCE.md files can be parsed for source labels."""
    # Claude format: "- Source: ..."
    claude_source = repo_root / "samples/independence/ports/claude/SOURCE.md"
    if claude_source.exists():
        with open(claude_source, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Should have "- Source:" line
        assert "- Source:" in content
        
        for line in content.splitlines():
            if line.strip().startswith("- Source:"):
                source = line.split(":", 1)[1].strip()
                assert len(source) > 0
                assert "Claude" in source or "Anthropic" in source
                break
    
    # Kiro format: "- **Producer**: ..."
    kiro_source = repo_root / "samples/independence/ports/kiro/SOURCE.md"
    if kiro_source.exists():
        with open(kiro_source, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Should have "- **Producer**:" line
        assert "- **Producer**:" in content
        
        for line in content.splitlines():
            if "**Producer**:" in line:
                source = line.split(":", 1)[1].strip()
                assert len(source) > 0
                assert "Kiro" in source or "kiro" in source
                break


@pytest.mark.slow
def test_run_table_end_to_end(tmp_path, repo_root):
    """
    End-to-end test: run run_table.py in a temporary copy and check TABLE.md.
    
    This test verifies that the table values match the certificates.
    """
    # Create a temporary workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Copy the necessary directories
    samples_dir = workspace / "samples"
    samples_dir.mkdir()
    independence_dir = samples_dir / "independence"
    shutil.copytree(
        repo_root / "samples" / "independence",
        independence_dir,
    )
    
    # Copy T1 trap
    traps_dir = samples_dir / "traps"
    traps_dir.mkdir()
    t1_dir = traps_dir / "T1-ebcdic-match-merge"
    shutil.copytree(
        repo_root / "samples" / "traps" / "T1-ebcdic-match-merge",
        t1_dir,
    )
    
    # Copy runs directory (for any existing runs)
    runs_dir = workspace / "runs"
    runs_dir.mkdir()
    
    # Copy pyproject.toml (needed for repo root detection)
    shutil.copy(repo_root / "pyproject.toml", workspace / "pyproject.toml")
    
    # Run the script with --cases 200 for faster testing
    script = independence_dir / "run_table.py"
    result = subprocess.run(
        [sys.executable, str(script), "--cases", "200"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    
    # Check that TABLE.md was created
    table_file = independence_dir / "TABLE.md"
    assert table_file.exists()
    
    with open(table_file, "r", encoding="utf-8") as f:
        table_content = f.read()
    
    # Parse the table and verify against certificates
    lines = table_content.strip().split("\n")
    
    # Find the data rows (skip header and separator)
    data_rows = []
    for line in lines:
        if line.startswith("| claude") or line.startswith("| kiro") or line.startswith("| hand-written"):
            data_rows.append(line)
    
    assert len(data_rows) >= 2, "Should have at least claude and kiro rows"
    
    # Check each port against its certificate
    for row in data_rows:
        parts = [p.strip() for p in row.split("|")]
        # Format: | port | source | verdict | divergent cases | run_id | java_sha256 | exposure |
        port = parts[1]
        verdict = parts[3]
        cases = parts[4]
        run_id = parts[5]
        
        if port == "hand-written":
            # Hand-written port should be pending
            assert verdict == "pending"
            assert cases == "pending"
            assert run_id == "pending"
            continue
        
        # For real ports, verify against certificate
        if run_id != "pending":
            cert_file = runs_dir / run_id / "certificate.json"
            assert cert_file.exists(), f"Certificate not found for {port}: {run_id}"
            
            with open(cert_file, "r", encoding="utf-8") as f:
                cert = json.load(f)
            
            # Verify verdict
            assert cert["status"] == verdict
            
            # Verify case counts
            if "of" in cases:
                divergent_str, total_str = cases.split(" of ")
                divergent = int(divergent_str)
                total = int(total_str)
                assert cert["cases_divergent"] == divergent
                assert cert["cases_total"] == total
                # Should be 200 cases since we passed --cases 200
                assert total == 200
