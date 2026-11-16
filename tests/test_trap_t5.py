"""Tests for Trap 5 (T5-redefines-invalid): REDEFINES of invalid numeric data."""
import subprocess
import os
from pathlib import Path
import pytest


TRAP_DIR = Path("samples/traps/T5-redefines-invalid")
BUILD_DIR = Path("build/traps/T5")


@pytest.fixture(scope="module", autouse=True)
def build_programs():
    """Build COBOL and Java programs."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Compile COBOL
    cobol_bin = BUILD_DIR / "ref" / "REDEFINES-INVALID"
    cobol_bin.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ['cobc', '-x', '-Wall', str(TRAP_DIR / 'REDEFINES-INVALID.cob'),
         '-o', str(cobol_bin)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"COBOL compilation failed: {result.stderr}")
    
    # Compile correct Java
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(BUILD_DIR / 'correct'),
         str(TRAP_DIR / 'java/correct/RedefinesInvalid.java')],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Correct Java compilation failed: {result.stderr}")
    
    # Compile faulty Java
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', str(BUILD_DIR / 'faulty'),
         str(TRAP_DIR / 'java/faulty/RedefinesInvalid.java')],
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
        [str(BUILD_DIR / 'ref' / 'REDEFINES-INVALID')],
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
        ['java', '-cp', str(BUILD_DIR / variant), 'RedefinesInvalid'],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.returncode


def test_t5_cobol_runs_fixture():
    """T5 COBOL program runs on fixture, returns 0, produces non-empty output with data rows."""
    input_file = TRAP_DIR / 'fixtures/invalid-numerics.csv'
    output_file = BUILD_DIR / 't5-cobol-fixture-out.csv'
    
    rc = run_cobol(input_file, output_file)
    
    assert rc == 0, f"COBOL program failed with rc {rc}"
    
    # Check output exists and has data rows
    assert output_file.exists(), "Output file not created"
    
    lines = output_file.read_text().strip().split('\n')
    assert len(lines) > 1, "No data rows in output"
    assert lines[0] == "CASE-ID,AMOUNT,NUMERIC-OK", f"Wrong header: {lines[0]}"


def test_t5_fixture_expected_equals_cobol():
    """T5 fixture expected output equals fresh COBOL run."""
    input_file = TRAP_DIR / 'fixtures/invalid-numerics.csv'
    output_file = BUILD_DIR / 't5-cobol-fresh.csv'
    
    run_cobol(input_file, output_file)
    
    fresh = output_file.read_text()
    expected = (TRAP_DIR / 'fixtures/expected-output.csv').read_text()
    
    assert fresh == expected, "Expected output does not match fresh COBOL run"


def test_t5_correct_java_equals_cobol_fixture():
    """T5 correct Java output equals COBOL output on fixture."""
    input_file = TRAP_DIR / 'fixtures/invalid-numerics.csv'
    cobol_output = BUILD_DIR / 't5-cobol-out.csv'
    java_output = BUILD_DIR / 't5-java-correct-out.csv'
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java('correct', input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0, f"Java failed with rc {rc_java}"
    
    cobol_content = cobol_output.read_text()
    java_content = java_output.read_text()
    
    assert java_content == cobol_content, "Correct Java output differs from COBOL"


def test_t5_faulty_java_differs_from_cobol_fixture():
    """T5 faulty Java output differs from COBOL on fixture."""
    input_file = TRAP_DIR / 'fixtures/invalid-numerics.csv'
    cobol_output = BUILD_DIR / 't5-cobol-out2.csv'
    java_output = BUILD_DIR / 't5-java-faulty-out.csv'
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java('faulty', input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0
    
    cobol_content = cobol_output.read_text()
    java_content = java_output.read_text()
    
    assert java_content != cobol_content, "Faulty Java output should differ from COBOL"


@pytest.mark.slow
def test_t5_correct_java_alive_200_cases():
    """T5 correct Java gives ALIVE on 200 generated cases."""
    result = subprocess.run(
        ['.venv/bin/python', '-m', 'coroner', 'verify',
         '--cobol', str(TRAP_DIR / 'REDEFINES-INVALID.cob'),
         '--copybooks', str(TRAP_DIR),
         '--java', str(TRAP_DIR / 'java/correct/RedefinesInvalid.java'),
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
def test_t5_faulty_java_zombie_200_cases():
    """T5 faulty Java gives ZOMBIE on 200 generated cases."""
    result = subprocess.run(
        ['.venv/bin/python', '-m', 'coroner', 'verify',
         '--cobol', str(TRAP_DIR / 'REDEFINES-INVALID.cob'),
         '--copybooks', str(TRAP_DIR),
         '--java', str(TRAP_DIR / 'java/faulty/RedefinesInvalid.java'),
         '--schema', str(TRAP_DIR / 'schema.json'),
         '--cases', '200',
         '--seed', '42'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 1, f"Should be ZOMBIE: {result.stdout}\n{result.stderr}"
    assert "ZOMBIE" in result.stdout, f"Expected ZOMBIE: {result.stdout}"
