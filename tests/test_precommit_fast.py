"""Tests for pre-commit fast mode with staged content."""

import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
import pytest


pytestmark = pytest.mark.slow


def setup_test_repo():
    """
    Create a temporary Git repository with the demo sample.
    Returns (repo_dir, scope_files_dict).
    """
    # Create temporary directory
    repo_dir = Path(tempfile.mkdtemp(prefix="coroner_precommit_test_"))
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    
    # Copy necessary files from current repo
    current_dir = Path.cwd()
    
    # Copy COBOL, copybooks, schema
    cobol_src = current_dir / "samples/credit-fees/CREDIT-FEES.cob"
    copybooks_src = current_dir / "samples/credit-fees/copybooks"
    schema_src = current_dir / "samples/credit-fees/schema.json"
    java_correct_src = current_dir / "samples/credit-fees/java/CreditFees.java"
    
    # Create directories in test repo
    sample_dir = repo_dir / "samples/credit-fees"
    sample_dir.mkdir(parents=True)
    java_dir = sample_dir / "java"
    java_dir.mkdir()
    copybooks_dir = sample_dir / "copybooks"
    copybooks_dir.mkdir()
    
    # Copy files
    cobol_dest = sample_dir / "CREDIT-FEES.cob"
    shutil.copy2(cobol_src, cobol_dest)
    
    schema_dest = sample_dir / "schema.json"
    shutil.copy2(schema_src, schema_dest)
    
    java_dest = java_dir / "CreditFees.java"
    shutil.copy2(java_correct_src, java_dest)
    
    # Copy copybooks
    for entry in copybooks_src.iterdir():
        if entry.is_file():
            shutil.copy2(entry, copybooks_dir / entry.name)
    
    # The HALF_EVEN variant is generated here from the correct port. It is not copied from
    # build/variants/CreditFees.java, a file shared with scripts/init_demo_runs.sh and make zombie.
    variant_dest = repo_dir / "variant_CreditFees.java"
    from coroner.catalog.legacy_variant import generate_half_even_variant
    generate_half_even_variant(str(java_correct_src), str(variant_dest))
    
    # Copy coroner files
    coroner_src = current_dir / "coroner"
    coroner_dest = repo_dir / "coroner"
    shutil.copytree(coroner_src, coroner_dest)
    
    # Copy kiro directory for scope
    kiro_src = current_dir / ".kiro"
    kiro_dest = repo_dir / ".kiro"
    shutil.copytree(kiro_src, kiro_dest)
    
    # Copy scripts
    scripts_src = current_dir / "scripts"
    scripts_dest = repo_dir / "scripts"
    shutil.copytree(scripts_src, scripts_dest)
    
    # Create symlink to venv
    venv_src = current_dir / ".venv"
    venv_dest = repo_dir / ".venv"
    if venv_src.exists():
        venv_dest.symlink_to(venv_src)
    
    # Create .githooks directory
    githooks_dest = repo_dir / ".githooks"
    githooks_dest.mkdir()
    precommit_src = current_dir / ".githooks/pre-commit"
    shutil.copy2(precommit_src, githooks_dest / "pre-commit")
    
    # Commit all files
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    
    scope_files = {
        "cobol": str(cobol_dest.relative_to(repo_dir)),
        "java": str(java_dest.relative_to(repo_dir)),
        "schema": str(schema_dest.relative_to(repo_dir)),
        "variant": str(variant_dest.relative_to(repo_dir))
    }
    
    return repo_dir, scope_files


def test_staged_half_even_blocked():
    """Test that staging HALF_EVEN variant with correct working tree blocks commit."""
    repo_dir, scope = setup_test_repo()
    
    try:
        # Stage the HALF_EVEN variant
        shutil.copy2(repo_dir / scope["variant"], repo_dir / scope["java"])
        subprocess.run(["git", "add", scope["java"]], cwd=repo_dir, check=True, capture_output=True)
        
        # Restore correct working tree (without unstaging) using git show
        java_file = repo_dir / scope["java"]
        result = subprocess.run(
            ["git", "show", f"HEAD:{scope['java']}"],
            cwd=repo_dir,
            capture_output=True,
            check=True
        )
        java_file.write_bytes(result.stdout)
        
        # Set up environment to use main repo's Python
        current_dir = Path.cwd()
        python_exe = sys.executable
        env = os.environ.copy()
        env["CORONER_PYTHON_EXECUTABLE"] = python_exe
        
        # Run pre-commit hook in test repo
        result = subprocess.run(
            [python_exe, "-m", "coroner.hooks", "precommit"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
        output = result.stdout + result.stderr
        assert "Commit blocked by Coroner" in output, f"Expected block message in:\n{output}"
        assert "ZOMBIE" in output, f"Expected ZOMBIE in:\n{output}"
    
    finally:
        shutil.rmtree(repo_dir)


def test_staged_correct_allowed():
    """Test that staging correct Java with HALF_EVEN working tree is allowed."""
    repo_dir, scope = setup_test_repo()
    
    try:
        # First modify the Java file to something (to have something to stage)
        java_file = repo_dir / scope["java"]
        original_content = java_file.read_text()
        java_file.write_text(original_content + "\n// correct version")
        
        # Stage the modified correct Java
        subprocess.run(["git", "add", scope["java"]], cwd=repo_dir, check=True, capture_output=True)
        
        # Modify working tree to HALF_EVEN (not staged)
        shutil.copy2(repo_dir / scope["variant"], repo_dir / scope["java"])
        
        # Set up environment to use main repo's Python
        current_dir = Path.cwd()
        python_exe = sys.executable
        env = os.environ.copy()
        env["CORONER_PYTHON_EXECUTABLE"] = python_exe
        
        # Run pre-commit hook in test repo
        result = subprocess.run(
            [python_exe, "-m", "coroner.hooks", "precommit"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\nOutput: {result.stdout + result.stderr}"
        output = result.stdout + result.stderr
        assert "ALIVE" in output, f"Expected ALIVE in:\n{output}"
    
    finally:
        shutil.rmtree(repo_dir)


def test_no_scope_staged_allowed():
    """Test that no scope file staged allows commit without running check."""
    repo_dir, scope = setup_test_repo()
    
    try:
        # Create and stage an unrelated file
        unrelated = repo_dir / "unrelated.txt"
        unrelated.write_text("test")
        subprocess.run(["git", "add", "unrelated.txt"], cwd=repo_dir, check=True, capture_output=True)
        
        # Set up environment to use main repo's Python
        current_dir = Path.cwd()
        python_exe = sys.executable
        env = os.environ.copy()
        env["CORONER_PYTHON_EXECUTABLE"] = python_exe
        
        # Run pre-commit hook in test repo
        result = subprocess.run(
            [python_exe, "-m", "coroner.hooks", "precommit"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        output = result.stdout + result.stderr
        assert "no audited file staged" in output, f"Expected 'no audited file staged' in:\n{output}"
    
    finally:
        shutil.rmtree(repo_dir)
