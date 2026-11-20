"""Tests for the independence track table generation."""

import json
import os
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
    # Run the engine once in tmp_path to generate a certificate
    env = {**os.environ, "CORONER_BASE_DIR": str(tmp_path)}
    
    cobol = repo_root / "samples" / "traps" / "T1-ebcdic-match-merge" / "MATCH-MERGE.cob"
    copybooks = repo_root / "samples" / "traps" / "T1-ebcdic-match-merge" / "copybooks"
    java = repo_root / "samples" / "independence" / "ports" / "claude" / "MatchMerge.java"
    schema = repo_root / "samples" / "traps" / "T1-ebcdic-match-merge" / "schema.json"
    
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", str(cobol),
            "--copybooks", str(copybooks),
            "--java", str(java),
            "--schema", str(schema),
            "--cases", "50",
            "--seed", "42",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    
    assert result.returncode in (0, 1), f"Verify failed: {result.stderr}"
    
    # Extract run id from output
    run_id = None
    for line in result.stdout.splitlines():
        if line.startswith("Run: runs/"):
            run_id = line.split("/")[1]
            break
    
    assert run_id is not None, "Run id not found in output"
    
    # Read certificate
    cert_file = tmp_path / "runs" / run_id / "certificate.json"
    assert cert_file.exists()
    
    with open(cert_file, "r", encoding="utf-8") as f:
        cert = json.load(f)
    
    # Check required fields against what we passed
    assert cert["status"] in ("ALIVE", "ZOMBIE")
    assert "cases_divergent" in cert
    assert "cases_total" in cert
    assert cert["cases_total"] == 50
    assert cert["random_seed"] == 42
    
    # Read branch reconciliation
    recon_file = tmp_path / "runs" / run_id / "branch_reconciliation.json"
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
    
    # Check that environment line is present
    assert "Environment:" in table_content
    
    # Parse the table and verify against certificates
    lines = table_content.strip().split("\n")
    
    # Find the data rows (skip header and separator)
    data_rows = []
    for line in lines:
        if (line.startswith("| Kiro") or line.startswith("| Claude") or 
            line.startswith("| hand-written")):
            data_rows.append(line)
    
    assert len(data_rows) >= 2, "Should have at least claude and kiro rows"
    
    # Check each port against its certificate
    for row in data_rows:
        parts = [p.strip() for p in row.split("|")]
        # Format: | label | source | verdict | divergent cases | run_id | java_sha256 | exposure | same_file |
        label = parts[1]
        verdict = parts[3]
        cases = parts[4]
        run_id = parts[5]
        same_file = parts[8]
        
        if "hand-written" in label:
            # Hand-written port should be pending
            assert verdict == "pending"
            assert cases == "pending"
            assert run_id == "pending"
            assert same_file == "pending"
            continue
        
        # For real ports, verify against certificate
        if run_id != "pending":
            cert_file = runs_dir / run_id / "certificate.json"
            assert cert_file.exists(), f"Certificate not found for {label}: {run_id}"
            
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
            
            # Verify same_file column
            assert same_file in ("no", "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java",
                                "samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java")


def test_same_file_detection(tmp_path, repo_root):
    """Test that same_file detection works correctly and excludes samples/independence/."""
    # Import the function
    sys.path.insert(0, str(repo_root / "samples" / "independence"))
    try:
        from run_table import find_matching_repository_file, compute_full_sha256
        
        # Test 1: A port equal to T1 faulty should match that path
        faulty_port = repo_root / "samples" / "traps" / "T1-ebcdic-match-merge" / "java" / "faulty" / "MatchMerge.java"
        assert faulty_port.exists(), "Faulty port not found"
        
        temp_java = tmp_path / "MatchMerge.java"
        shutil.copy(faulty_port, temp_java)
        
        result = find_matching_repository_file(temp_java, repo_root)
        assert result == "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java"
        
        # Test 2: A port equal only to a file under samples/independence/ gives "no"
        independence_port = repo_root / "samples" / "independence" / "ports" / "kiro" / "MatchMerge.java"
        assert independence_port.exists(), "Kiro port not found"
        
        temp_java2 = tmp_path / "MatchMerge2.java"
        shutil.copy(independence_port, temp_java2)
        
        result = find_matching_repository_file(temp_java2, repo_root)
        assert result == "no", "Port equal to independence/kiro should give 'no'"
        
        # Test 3: Modified file should not match
        with open(temp_java, "a", encoding="utf-8") as f:
            f.write("\n// Modified\n")
        
        result = find_matching_repository_file(temp_java, repo_root)
        assert result == "no"
    finally:
        sys.path.pop(0)
