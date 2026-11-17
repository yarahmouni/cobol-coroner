"""Tests for Trap 2 (T2-rounding): Rounding mode divergence."""
import subprocess
import sys
import os
from pathlib import Path
import pytest


TRAP_DIR = Path("samples/traps/T2-rounding")
BUILD_DIR = Path("build/traps/T2")


@pytest.fixture(scope="module", autouse=True)
def build_programs():
    """Build COBOL and Java programs."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Compile COBOL
    cobol_bin = BUILD_DIR / "ref" / "ROUNDING-CALC"
    cobol_bin.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ['cobc', '-x', '-Wall', str(TRAP_DIR / 'ROUNDING-CALC.cob'),
         '-o', str(cobol_bin)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"COBOL compilation failed: {result.stderr}")
    
    # Compile correct Java
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(BUILD_DIR / 'correct'),
         str(TRAP_DIR / 'java/correct/RoundingCalc.java')],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Correct Java compilation failed: {result.stderr}")
    
    # Compile faulty Java
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(BUILD_DIR / 'faulty'),
         str(TRAP_DIR / 'java/faulty/RoundingCalc.java')],
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
        [str(BUILD_DIR / 'ref' / 'ROUNDING-CALC')],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.returncode


def run_java(variant: str, input_file: Path, output_file: Path) -> int:
    """Run Java program and return exit code."""
    env = os.environ.copy()
    env['INPUT_FILE'] = str(input_file)
    env['OUTPUT_FILE'] = str(output_file)
    
    result = subprocess.run(
        ['java', '-cp', str(BUILD_DIR / variant), 'RoundingCalc'],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.returncode


def test_t2_cobol_runs_fixture():
    """T2 COBOL program runs on fixture, returns 0, produces non-empty output with data rows."""
    input_file = TRAP_DIR / 'fixtures/ties.csv'
    output_file = BUILD_DIR / 't2-cobol-fixture-out.csv'
    
    rc = run_cobol(input_file, output_file)
    
    assert rc == 0, f"COBOL program failed with rc {rc}"
    
    # Check output exists and has data rows
    assert output_file.exists(), "Output file not created"
    
    lines = output_file.read_text().strip().split('\n')
    assert len(lines) > 1, "No data rows in output"
    assert lines[0] == "CASE-ID,FEE1,FEE2", f"Wrong header: {lines[0]}"


def test_t2_fixture_expected_equals_cobol():
    """T2 fixture expected output equals fresh COBOL run."""
    input_file = TRAP_DIR / 'fixtures/ties.csv'
    output_file = BUILD_DIR / 't2-cobol-fresh.csv'
    
    run_cobol(input_file, output_file)
    
    fresh = output_file.read_text()
    expected = (TRAP_DIR / 'fixtures/ties-expected.csv').read_text()
    
    assert fresh == expected, "Expected output does not match fresh COBOL run"


def test_t2_correct_java_equals_cobol_fixture():
    """T2 correct Java output equals COBOL output on fixture."""
    input_file = TRAP_DIR / 'fixtures/ties.csv'
    cobol_output = BUILD_DIR / 't2-cobol-out.csv'
    java_output = BUILD_DIR / 't2-java-correct-out.csv'
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java('correct', input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0, f"Java failed with rc {rc_java}"
    
    cobol_content = cobol_output.read_text()
    java_content = java_output.read_text()
    
    assert java_content == cobol_content, "Correct Java output differs from COBOL"


def test_t2_faulty_java_differs_from_cobol_fixture():
    """T2 faulty Java output differs from COBOL on fixture."""
    input_file = TRAP_DIR / 'fixtures/ties.csv'
    cobol_output = BUILD_DIR / 't2-cobol-out2.csv'
    java_output = BUILD_DIR / 't2-java-faulty-out.csv'
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java('faulty', input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0
    
    cobol_content = cobol_output.read_text()
    java_content = java_output.read_text()
    
    assert java_content != cobol_content, "Faulty Java output should differ from COBOL"


@pytest.mark.slow
def test_t2_correct_java_alive_200_cases():
    """T2 correct Java gives ALIVE on 200 generated cases."""
    result = subprocess.run(
        [sys.executable, '-m', 'coroner', 'verify',
         '--cobol', str(TRAP_DIR / 'ROUNDING-CALC.cob'),
         '--copybooks', str(TRAP_DIR),
         '--java', str(TRAP_DIR / 'java/correct/RoundingCalc.java'),
         '--schema', str(TRAP_DIR / 'schema.json'),
         '--cases', '200',
         '--seed', '42'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Should be ALIVE: {result.stdout}\n{result.stderr}"
    assert "ALIVE" in result.stdout, f"Expected ALIVE: {result.stdout}"


@pytest.mark.slow
def test_t2_faulty_java_zombie_200_cases():
    """T2 faulty Java gives ZOMBIE on 200 generated cases."""
    result = subprocess.run(
        [sys.executable, '-m', 'coroner', 'verify',
         '--cobol', str(TRAP_DIR / 'ROUNDING-CALC.cob'),
         '--copybooks', str(TRAP_DIR),
         '--java', str(TRAP_DIR / 'java/faulty/RoundingCalc.java'),
         '--schema', str(TRAP_DIR / 'schema.json'),
         '--cases', '200',
         '--seed', '42'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 1, f"Should be ZOMBIE: {result.stdout}\n{result.stderr}"
    assert "ZOMBIE" in result.stdout, f"Expected ZOMBIE: {result.stdout}"
