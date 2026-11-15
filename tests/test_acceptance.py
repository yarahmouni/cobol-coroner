"""
Acceptance tests for the Coroner engine (S1).

These tests verify the S1 acceptance criteria from sprints.md:
- 2,000 cases give ALIVE with the correct Java and ZOMBIE with the HALF_EVEN variant
- Coverage decision (D-07) met
- Wall-clock time under 60 seconds per verify (compilation included)
- 0 false ZOMBIE on 10 runs of the correct Java
- 0 false ALIVE on 10 runs of the HALF_EVEN variant
- HALF_EVEN divergence count between 80 and 120 for seed 42

These tests are marked as slow and run via 'make acceptance'.
They use 2,000 cases and take significant time.

Fixed seeds used for reproducibility:
- s1=42 (default seed, used for calibration)
- s2=123
- s3=456
- s4=789
- s5=1011
- s6=1213
- s7=1415
- s8=1617
- s9=1819
- s10=2021
"""
import pytest
import subprocess
import shutil
import time
from pathlib import Path


# Skip all tests if cobc or javac is missing
def check_tools():
    """Check if cobc and javac are available."""
    cobc = shutil.which("cobc")
    javac = shutil.which("javac")
    if not cobc:
        pytest.skip("cobc not available")
    if not javac:
        pytest.skip("javac not available")


# Fixed seeds for reproducible tests
SEEDS = [42, 123, 456, 789, 1011, 1213, 1415, 1617, 1819, 2021]

# Paths
COBOL_PATH = "samples/credit-fees/CREDIT-FEES.cob"
COPYBOOKS_PATH = "samples/credit-fees/copybooks"
JAVA_CORRECT_PATH = "samples/credit-fees/java/CreditFees.java"
JAVA_VARIANT_PATH = "build/variants/CreditFees.java"
SCHEMA_PATH = "samples/credit-fees/schema.json"


def run_verify(java_path: str, seed: int, cases: int = 2000) -> tuple[int, str, float]:
    """
    Run coroner verify and return exit code, stdout, and wall-clock time.
    
    Args:
        java_path: Path to Java source
        seed: Random seed
        cases: Number of cases (default 2000)
        
    Returns:
        Tuple of (exit_code, stdout, wall_time_seconds)
    """
    start = time.time()
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", COBOL_PATH,
            "--copybooks", COPYBOOKS_PATH,
            "--java", java_path,
            "--schema", SCHEMA_PATH,
            "--cases", str(cases),
            "--seed", str(seed),
        ],
        capture_output=True,
        text=True,
        timeout=120  # 2 minute timeout for safety
    )
    elapsed = time.time() - start
    return result.returncode, result.stdout, elapsed


def extract_divergent_count(stdout: str) -> int:
    """Extract divergent case count from ZOMBIE verdict output."""
    # Look for "FAIL: business behavior diverged on N cases"
    for line in stdout.split('\n'):
        if "FAIL: business behavior diverged on" in line:
            # Extract number before "cases"
            parts = line.split("on")
            if len(parts) >= 2:
                count_str = parts[1].split("cases")[0].strip()
                return int(count_str)
    return 0


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_acceptance_no_false_zombie(seed):
    """
    Test that correct Java produces ALIVE verdict for all seeds.
    
    This verifies there are 0 false ZOMBIE verdicts on 10 runs
    of the correct Java with different seeds.
    """
    check_tools()
    
    exit_code, stdout, elapsed = run_verify(JAVA_CORRECT_PATH, seed)
    
    # Print result for the table
    verdict = "ALIVE" if exit_code == 0 else "ZOMBIE"
    divergences = extract_divergent_count(stdout) if exit_code != 0 else 0
    print(f"\nSeed {seed:4d}: {verdict:6s} | {divergences:3d} divergences | {elapsed:5.1f} s")
    
    # Assert ALIVE (exit code 0)
    assert exit_code == 0, f"Expected ALIVE for seed {seed}, got exit code {exit_code}:\n{stdout}"
    assert "ALIVE: PASS: business behavior preserved on 2000 cases" in stdout


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_acceptance_no_false_alive(seed):
    """
    Test that HALF_EVEN variant produces ZOMBIE verdict for all seeds.
    
    This verifies there are 0 false ALIVE verdicts on 10 runs
    of the HALF_EVEN variant with different seeds.
    """
    check_tools()
    
    # Ensure variant exists
    variant_path = Path(JAVA_VARIANT_PATH)
    if not variant_path.exists():
        # Generate it
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                ".venv/bin/python", "-m", "coroner.catalog.legacy_variant",
                JAVA_CORRECT_PATH,
                str(variant_path)
            ],
            check=True,
            capture_output=True
        )
    
    exit_code, stdout, elapsed = run_verify(JAVA_VARIANT_PATH, seed)
    
    # Print result for the table
    verdict = "ZOMBIE" if exit_code == 1 else "ALIVE"
    divergences = extract_divergent_count(stdout)
    print(f"\nSeed {seed:4d}: {verdict:6s} | {divergences:3d} divergences | {elapsed:5.1f} s")
    
    # Assert ZOMBIE (exit code 1) and at least one divergent case
    assert exit_code == 1, f"Expected ZOMBIE for seed {seed}, got exit code {exit_code}:\n{stdout}"
    assert "FAIL: business behavior diverged on" in stdout
    assert divergences > 0, f"Expected at least one divergent case for seed {seed}"


@pytest.mark.slow
def test_acceptance_half_even_calibration():
    """
    Test that seed 42 with HALF_EVEN variant has 80-120 divergences.
    
    This is the calibration target, not a strict requirement.
    The calibrated tie_share=0.06 should give divergences in this range.
    """
    check_tools()
    
    # Ensure variant exists
    variant_path = Path(JAVA_VARIANT_PATH)
    if not variant_path.exists():
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                ".venv/bin/python", "-m", "coroner.catalog.legacy_variant",
                JAVA_CORRECT_PATH,
                str(variant_path)
            ],
            check=True,
            capture_output=True
        )
    
    exit_code, stdout, elapsed = run_verify(JAVA_VARIANT_PATH, 42)
    
    divergences = extract_divergent_count(stdout)
    print(f"\nSeed 42 calibration: {divergences} divergences (target: 80-120)")
    
    # Assert ZOMBIE
    assert exit_code == 1, f"Expected ZOMBIE for seed 42, got exit code {exit_code}:\n{stdout}"
    
    # Assert divergence count in calibration range
    assert 80 <= divergences <= 120, (
        f"Calibration target not met: {divergences} divergences, expected 80-120.\n"
        f"The tie_share may need adjustment."
    )


@pytest.mark.slow
def test_acceptance_wall_clock_under_60s():
    """
    Test that one verify with 2,000 cases completes in under 60 seconds.
    
    This measures wall-clock time including compilation.
    """
    check_tools()
    
    exit_code, stdout, elapsed = run_verify(JAVA_CORRECT_PATH, 42)
    
    # Print timing breakdown from stdout
    print(f"\nWall-clock time: {elapsed:.1f} s")
    print("Stdout timing info:")
    for line in stdout.split('\n'):
        if 'Duration:' in line or 's' in line:
            print(f"  {line}")
    
    # Assert under 60 seconds
    assert elapsed < 60.0, (
        f"Verify took {elapsed:.1f} s, exceeds 60 second target.\n"
        f"Performance optimization may be needed."
    )
    
    # Assert ALIVE
    assert exit_code == 0, f"Expected ALIVE, got exit code {exit_code}:\n{stdout}"


if __name__ == "__main__":
    # Run with: .venv/bin/pytest tests/test_acceptance.py -m slow -s
    pytest.main([__file__, "-m", "slow", "-s"])
