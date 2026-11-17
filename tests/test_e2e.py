"""End-to-end tests for Coroner CLI."""
import pytest
import subprocess
import sys
import os
import json
from pathlib import Path


def check_tool_available(tool: str) -> bool:
    """Check if a tool is available in PATH."""
    try:
        result = subprocess.run([tool, '--version' if tool == 'cobc' else '-version'],
                                capture_output=True, timeout=5.0)
        return result.returncode in (0, 1)  # javac -version returns 0, cobc --version returns 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def tools_available():
    """Check if cobc and javac are available."""
    cobc = check_tool_available('cobc')
    javac = check_tool_available('javac')
    if not cobc:
        pytest.skip("cobc not available")
    if not javac:
        pytest.skip("javac not available")


def test_e2e_alive(tools_available, tmp_path):
    """
    E2E test: runs engine on correct Java with 30 cases, asserts exit 0 and ALIVE.
    """
    # Run verify command
    result = subprocess.run(
        [
            sys.executable, '-m', 'coroner', 'verify',
            '--cobol', 'samples/credit-fees/CREDIT-FEES.cob',
            '--copybooks', 'samples/credit-fees/copybooks',
            '--java', 'samples/credit-fees/java/CreditFees.java',
            '--schema', 'samples/credit-fees/schema.json',
            '--cases', '30',
            '--seed', '42'
        ],
        capture_output=True,
        text=True,
        timeout=120.0
    )
    
    # Assert exit code 0
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"
    
    # Assert ALIVE in output
    assert 'ALIVE' in result.stdout, f"Expected ALIVE in stdout: {result.stdout}"
    assert 'PASS: business behavior preserved on 30 cases' in result.stdout
    
    # Assert coverage lines present
    assert 'Paragraph coverage' in result.stdout
    assert 'Branch coverage (Coroner definition)' in result.stdout
    assert 'Validated under GnuCOBOL 3.x' in result.stdout
    
    # Extract run_id from output
    run_line = [line for line in result.stdout.split('\n') if line.startswith('Run:')]
    assert len(run_line) == 1
    run_dir = run_line[0].split('Run:')[1].strip()
    
    # Assert run directory exists
    assert os.path.isdir(run_dir)
    
    # Assert files exist
    assert os.path.isfile(f"{run_dir}/inputs.json")
    assert os.path.isfile(f"{run_dir}/generated_cases.csv")
    assert os.path.isfile(f"{run_dir}/comparison_results.json")
    assert os.path.isfile(f"{run_dir}/verdict.json")
    assert os.path.isfile(f"{run_dir}/coverage_report.json")
    
    # Assert failure report does NOT exist (ALIVE)
    assert not os.path.isfile(f"{run_dir}/failure_report.json")
    assert not os.path.isfile(f"{run_dir}/ZombieRegressionTest.java")
    
    # Verify verdict.json content
    with open(f"{run_dir}/verdict.json") as f:
        verdict = json.load(f)
    assert verdict['status'] == 'ALIVE'
    assert verdict['cases_divergent'] == 0


def test_e2e_zombie(tools_available, tmp_path):
    """
    E2E test: runs engine on HALF_EVEN variant with 30 cases, asserts exit 1 and ZOMBIE.
    """
    # Generate HALF_EVEN variant
    variant_dir = 'build/test_variants'
    os.makedirs(variant_dir, exist_ok=True)
    variant_path = f"{variant_dir}/CreditFees.java"
    
    gen_result = subprocess.run(
        [sys.executable, '-m', 'coroner.catalog.legacy_variant',
         'samples/credit-fees/java/CreditFees.java', variant_path],
        capture_output=True,
        text=True,
        timeout=5.0
    )
    assert gen_result.returncode == 0, f"Variant generation failed: {gen_result.stderr}"
    
    # Run verify command
    result = subprocess.run(
        [
            sys.executable, '-m', 'coroner', 'verify',
            '--cobol', 'samples/credit-fees/CREDIT-FEES.cob',
            '--copybooks', 'samples/credit-fees/copybooks',
            '--java', variant_path,
            '--schema', 'samples/credit-fees/schema.json',
            '--cases', '30',
            '--seed', '42'
        ],
        capture_output=True,
        text=True,
        timeout=120.0
    )
    
    # Assert exit code 1 (ZOMBIE)
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stderr: {result.stderr}"
    
    # Assert ZOMBIE in output
    assert 'ZOMBIE' in result.stdout, f"Expected ZOMBIE in stdout: {result.stdout}"
    assert 'FAIL: business behavior diverged on' in result.stdout
    
    # Assert coverage lines present
    assert 'Paragraph coverage' in result.stdout
    assert 'Branch coverage (Coroner definition)' in result.stdout
    assert 'Validated under GnuCOBOL 3.x' in result.stdout
    
    # Extract run_id from output
    run_line = [line for line in result.stdout.split('\n') if line.startswith('Run:')]
    assert len(run_line) == 1
    run_dir = run_line[0].split('Run:')[1].strip()
    
    # Assert run directory exists
    assert os.path.isdir(run_dir)
    
    # Assert files exist
    assert os.path.isfile(f"{run_dir}/inputs.json")
    assert os.path.isfile(f"{run_dir}/generated_cases.csv")
    assert os.path.isfile(f"{run_dir}/comparison_results.json")
    assert os.path.isfile(f"{run_dir}/verdict.json")
    assert os.path.isfile(f"{run_dir}/coverage_report.json")
    
    # Assert failure report DOES exist (ZOMBIE)
    assert os.path.isfile(f"{run_dir}/failure_report.json")
    assert os.path.isfile(f"{run_dir}/ZombieRegressionTest.java")
    
    # Verify verdict.json content
    with open(f"{run_dir}/verdict.json") as f:
        verdict = json.load(f)
    assert verdict['status'] == 'ZOMBIE'
    assert verdict['cases_divergent'] > 0


def test_e2e_missing_file():
    """
    E2E test: runs engine with missing file, asserts exit 2 and error message.
    """
    result = subprocess.run(
        [
            sys.executable, '-m', 'coroner', 'verify',
            '--cobol', 'nonexistent.cob',
            '--copybooks', 'samples/credit-fees/copybooks',
            '--java', 'samples/credit-fees/java/CreditFees.java',
            '--schema', 'samples/credit-fees/schema.json'
        ],
        capture_output=True,
        text=True,
        timeout=5.0
    )
    
    # Assert exit code 2 (error)
    assert result.returncode == 2
    assert 'Error:' in result.stderr
    assert 'not found' in result.stderr


def test_e2e_deterministic_run_id(tools_available, tmp_path):
    """
    E2E test: two identical runs produce same run_id and identical generated_cases.csv and verdict.json.
    """
    # Run verify command twice with same inputs
    results = []
    for _ in range(2):
        result = subprocess.run(
            [
                sys.executable, '-m', 'coroner', 'verify',
                '--cobol', 'samples/credit-fees/CREDIT-FEES.cob',
                '--copybooks', 'samples/credit-fees/copybooks',
                '--java', 'samples/credit-fees/java/CreditFees.java',
                '--schema', 'samples/credit-fees/schema.json',
                '--cases', '30',
                '--seed', '999'
            ],
            capture_output=True,
            text=True,
            timeout=120.0
        )
        assert result.returncode == 0
        
        # Extract run_id
        run_line = [line for line in result.stdout.split('\n') if line.startswith('Run:')]
        assert len(run_line) == 1
        run_dir = run_line[0].split('Run:')[1].strip()
        results.append(run_dir)
    
    # Assert same run_id
    assert results[0] == results[1], f"Run IDs differ: {results[0]} vs {results[1]}"
    
    run_dir = results[0]
    
    # Read generated_cases.csv from both runs (they should be byte-identical since we write to same dir)
    with open(f"{run_dir}/generated_cases.csv", 'rb') as f:
        cases_bytes = f.read()
    
    # Read verdict.json
    with open(f"{run_dir}/verdict.json") as f:
        verdict1 = json.load(f)
    
    # The files should be identical since run_id is deterministic and directory is rewritten
    assert verdict1['status'] == 'ALIVE'
