"""Tests for trap T3 (COMP-3 sign nibble)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

TRAP_DIR = Path('samples/traps/T3-comp3-sign')
BUILD_DIR = Path('build/traps/T3')


@pytest.fixture(scope="module", autouse=True)
def build_programs():
    """Build COBOL and Java programs."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Compile COBOL
    cobol_bin = BUILD_DIR / 'ref' / 'COMP3-SIGN'
    cobol_bin.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ['cobc', '-x', '-Wall', str(TRAP_DIR / 'COMP3-SIGN.cob'), '-o', str(cobol_bin)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Compilation failed: {result.stderr}")
    if result.stderr:
        pytest.fail(f"Compilation warnings: {result.stderr}")
    
    # Compile correct Java
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(BUILD_DIR / 'correct'),
         str(TRAP_DIR / 'java/correct/Comp3Sign.java')],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Correct Java compilation failed: {result.stderr}")
    
    # Compile faulty Java
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(BUILD_DIR / 'faulty'),
         str(TRAP_DIR / 'java/faulty/Comp3Sign.java')],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Faulty Java compilation failed: {result.stderr}")


def run_cobol(input_file: Path, output_file: Path) -> int:
    """Run COBOL program and return exit code."""
    env = os.environ.copy()
    env['INPUT_FILE'] = str(input_file)
    env['OUTPUT_FILE'] = str(output_file)
    
    result = subprocess.run(
        [str(BUILD_DIR / 'ref' / 'COMP3-SIGN')],
        env=env,
        capture_output=True,
        text=True,
        timeout=5
    )
    return result.returncode


def run_java(variant: str, input_file: Path, output_file: Path) -> int:
    """Run Java program and return exit code."""
    env = os.environ.copy()
    env['INPUT_FILE'] = str(input_file)
    env['OUTPUT_FILE'] = str(output_file)
    
    result = subprocess.run(
        ['java', '-cp', str(BUILD_DIR / variant), 'Comp3Sign'],
        env=env,
        capture_output=True,
        text=True,
        timeout=5
    )
    return result.returncode


def test_cobol_runs_on_fixture():
    """COBOL program runs successfully on the fixture."""
    input_file = TRAP_DIR / 'fixtures/sign-nibbles.csv'
    output_file = BUILD_DIR / 'cobol-fixture-out.csv'
    
    rc = run_cobol(input_file, output_file)
    
    assert rc == 0, f"COBOL failed with rc {rc}"
    
    # Check output has data rows
    lines = output_file.read_text().strip().split('\n')
    
    assert len(lines) > 1, "Output has no data rows"
    assert len([line for line in lines if line.strip() and not line.startswith('CASE-ID')]) >= 6, \
        "Output has fewer than 6 data rows"


def test_fixture_expected_equals_cobol():
    """Expected output equals a fresh COBOL run."""
    input_file = TRAP_DIR / 'fixtures/sign-nibbles.csv'
    expected_file = TRAP_DIR / 'fixtures/expected-output.csv'
    fresh_output = BUILD_DIR / 'cobol-fresh.csv'
    
    rc = run_cobol(input_file, fresh_output)
    
    assert rc == 0, f"COBOL failed with rc {rc}"
    
    # Compare byte for byte
    expected_bytes = expected_file.read_bytes()
    fresh_bytes = fresh_output.read_bytes()
    
    assert expected_bytes == fresh_bytes, "Expected output does not match fresh COBOL run"


def test_correct_java_equals_cobol():
    """Correct Java output equals COBOL output byte for byte."""
    input_file = TRAP_DIR / 'fixtures/sign-nibbles.csv'
    cobol_output = BUILD_DIR / 'cobol-out.csv'
    java_output = BUILD_DIR / 'java-correct-out.csv'
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java('correct', input_file, java_output)
    
    assert rc_cobol == 0, f"COBOL failed with rc {rc_cobol}"
    assert rc_java == 0, f"Java failed with rc {rc_java}"
    
    # Compare byte for byte
    cobol_bytes = cobol_output.read_bytes()
    java_bytes = java_output.read_bytes()
    
    assert cobol_bytes == java_bytes, "Correct Java output does not match COBOL"


def test_faulty_java_differs():
    """Faulty Java output differs on F sign nibble cases."""
    input_file = TRAP_DIR / 'fixtures/sign-nibbles.csv'
    cobol_output = BUILD_DIR / 'cobol-out2.csv'
    java_output = BUILD_DIR / 'java-faulty-out.csv'
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java('faulty', input_file, java_output)
    
    assert rc_cobol == 0, f"COBOL failed with rc {rc_cobol}"
    assert rc_java == 0, f"Java failed with rc {rc_java}"
    
    # Read outputs
    cobol_lines = cobol_output.read_text().strip().split('\n')
    java_lines = java_output.read_text().strip().split('\n')
    
    # Check that FIX-03 and FIX-06 (F nibble cases) differ
    cobol_dict = {line.split(',')[0].strip(): line for line in cobol_lines if 'FIX-' in line}
    java_dict = {line.split(',')[0].strip(): line for line in java_lines if 'FIX-' in line}
    
    assert cobol_dict['FIX-03'] != java_dict['FIX-03'], "FIX-03 should differ (F nibble positive vs negative)"
    assert cobol_dict['FIX-06'] != java_dict['FIX-06'], "FIX-06 should differ (F nibble positive vs negative)"
    
    # Check that other cases match
    assert cobol_dict['FIX-01'] == java_dict['FIX-01'], "FIX-01 should match (C nibble)"
    assert cobol_dict['FIX-02'] == java_dict['FIX-02'], "FIX-02 should match (D nibble)"


@pytest.mark.slow
def test_verify_correct_alive():
    """Verify with correct Java gives ALIVE on 200 cases."""
    result = subprocess.run(
        [
            sys.executable, '-m', 'coroner', 'verify',
            '--cobol', str(TRAP_DIR / 'COMP3-SIGN.cob'),
            '--copybooks', '.',
            '--java', str(TRAP_DIR / 'java/correct/Comp3Sign.java'),
            '--schema', str(TRAP_DIR / 'schema.json'),
            '--cases', '200',
            '--seed', '42'
        ],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Verify failed: {result.stdout}\n{result.stderr}"
    assert 'ALIVE' in result.stdout, f"Expected ALIVE verdict: {result.stdout}"
    assert 'ZOMBIE' not in result.stdout, f"Unexpected ZOMBIE verdict: {result.stdout}"


@pytest.mark.slow
def test_verify_faulty_zombie():
    """Verify with faulty Java gives ZOMBIE on 200 cases."""
    result = subprocess.run(
        [
            sys.executable, '-m', 'coroner', 'verify',
            '--cobol', str(TRAP_DIR / 'COMP3-SIGN.cob'),
            '--copybooks', '.',
            '--java', str(TRAP_DIR / 'java/faulty/Comp3Sign.java'),
            '--schema', str(TRAP_DIR / 'schema.json'),
            '--cases', '200',
            '--seed', '42'
        ],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 1, f"Expected exit code 1 (ZOMBIE): {result.stdout}\n{result.stderr}"
    assert 'ZOMBIE' in result.stdout, f"Expected ZOMBIE verdict: {result.stdout}"
    assert 'diverged' in result.stdout, f"Expected divergence message: {result.stdout}"


@pytest.mark.slow
def test_verify_2000_cases():
    """Measure divergence count on 2000 cases with seed 42."""
    result = subprocess.run(
        [
            sys.executable, '-m', 'coroner', 'verify',
            '--cobol', str(TRAP_DIR / 'COMP3-SIGN.cob'),
            '--copybooks', '.',
            '--java', str(TRAP_DIR / 'java/faulty/Comp3Sign.java'),
            '--schema', str(TRAP_DIR / 'schema.json'),
            '--cases', '2000',
            '--seed', '42'
        ],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 1, f"Expected exit code 1 (ZOMBIE): {result.stdout}\n{result.stderr}"
    assert 'ZOMBIE' in result.stdout, f"Expected ZOMBIE verdict: {result.stdout}"
    
    # Print divergence count for measurement
    print(f"\n2000-case measurement:\n{result.stdout}")
