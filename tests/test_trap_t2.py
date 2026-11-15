"""Tests for Trap 2 (T2-rounding): Rounding mode divergence."""
import subprocess
import os
from pathlib import Path
import pytest


def test_t2_cobol_compiles():
    """T2 COBOL program compiles with cobc -x -Wall."""
    result = subprocess.run(
        ['cobc', '-x', '-Wall', 'samples/traps/T2-rounding/ROUNDING-CALC.cob',
         '-o', 'build/T2-ROUNDING-CALC'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Compilation failed: {result.stderr}"


def test_t2_cobol_runs_fixture():
    """T2 COBOL program runs on fixture, returns 0, produces non-empty output with data rows."""
    # Compile first
    subprocess.run(
        ['cobc', '-x', '-Wall', 'samples/traps/T2-rounding/ROUNDING-CALC.cob',
         '-o', 'build/T2-ROUNDING-CALC'],
        check=True,
        capture_output=True
    )
    
    env = os.environ.copy()
    env['INPUT_FILE'] = 'samples/traps/T2-rounding/fixtures/ties.csv'
    env['OUTPUT_FILE'] = 'build/t2-cobol-fixture-out.csv'
    
    result = subprocess.run(
        ['build/T2-ROUNDING-CALC'],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    
    assert result.returncode == 0, f"COBOL program failed: {result.stderr}"
    
    # Check output exists and has data rows
    output_path = Path('build/t2-cobol-fixture-out.csv')
    assert output_path.exists(), "Output file not created"
    
    lines = output_path.read_text().strip().split('\n')
    assert len(lines) > 1, "No data rows in output"
    assert lines[0] == "CASE-ID,FEE1,FEE2", f"Wrong header: {lines[0]}"


def test_t2_fixture_expected_equals_cobol():
    """T2 fixture expected output equals fresh COBOL run."""
    # Compile
    subprocess.run(
        ['cobc', '-x', '-Wall', 'samples/traps/T2-rounding/ROUNDING-CALC.cob',
         '-o', 'build/T2-ROUNDING-CALC'],
        check=True,
        capture_output=True
    )
    
    env = os.environ.copy()
    env['INPUT_FILE'] = 'samples/traps/T2-rounding/fixtures/ties.csv'
    env['OUTPUT_FILE'] = 'build/t2-cobol-fresh.csv'
    
    subprocess.run(
        ['build/T2-ROUNDING-CALC'],
        env=env,
        check=True,
        capture_output=True,
        timeout=10
    )
    
    fresh = Path('build/t2-cobol-fresh.csv').read_text()
    expected = Path('samples/traps/T2-rounding/fixtures/ties-expected.csv').read_text()
    
    assert fresh == expected, "Expected output does not match fresh COBOL run"


def test_t2_correct_java_compiles():
    """T2 correct Java compiles with javac -Xlint:all."""
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', 'build',
         'samples/traps/T2-rounding/java/correct/RoundingCalc.java'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Java compilation failed: {result.stderr}"


def test_t2_correct_java_equals_cobol_fixture():
    """T2 correct Java output equals COBOL output on fixture."""
    # Compile COBOL
    subprocess.run(
        ['cobc', '-x', '-Wall', 'samples/traps/T2-rounding/ROUNDING-CALC.cob',
         '-o', 'build/T2-ROUNDING-CALC'],
        check=True,
        capture_output=True
    )
    
    # Compile Java
    subprocess.run(
        ['javac', '-Xlint:all', '-d', 'build',
         'samples/traps/T2-rounding/java/correct/RoundingCalc.java'],
        check=True,
        capture_output=True
    )
    
    # Run COBOL
    env = os.environ.copy()
    env['INPUT_FILE'] = 'samples/traps/T2-rounding/fixtures/ties.csv'
    env['OUTPUT_FILE'] = 'build/t2-cobol-out.csv'
    subprocess.run(['build/T2-ROUNDING-CALC'], env=env, check=True, timeout=10)
    
    # Run Java
    env['OUTPUT_FILE'] = 'build/t2-java-correct-out.csv'
    result = subprocess.run(
        ['java', '-cp', 'build', 'RoundingCalc'],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    assert result.returncode == 0, f"Java failed: {result.stderr}"
    
    cobol_output = Path('build/t2-cobol-out.csv').read_text()
    java_output = Path('build/t2-java-correct-out.csv').read_text()
    
    assert java_output == cobol_output, "Correct Java output differs from COBOL"


def test_t2_faulty_java_compiles():
    """T2 faulty Java compiles."""
    result = subprocess.run(
        ['javac', '-Xlint:all', '-d', 'build',
         'samples/traps/T2-rounding/java/faulty/RoundingCalc.java'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Faulty Java compilation failed: {result.stderr}"


def test_t2_faulty_java_differs_from_cobol_fixture():
    """T2 faulty Java output differs from COBOL on fixture."""
    # Compile COBOL
    subprocess.run(
        ['cobc', '-x', '-Wall', 'samples/traps/T2-rounding/ROUNDING-CALC.cob',
         '-o', 'build/T2-ROUNDING-CALC'],
        check=True,
        capture_output=True
    )
    
    # Compile Java
    subprocess.run(
        ['javac', '-Xlint:all', '-d', 'build',
         'samples/traps/T2-rounding/java/faulty/RoundingCalc.java'],
        check=True,
        capture_output=True
    )
    
    # Run COBOL
    env = os.environ.copy()
    env['INPUT_FILE'] = 'samples/traps/T2-rounding/fixtures/ties.csv'
    env['OUTPUT_FILE'] = 'build/t2-cobol-out2.csv'
    subprocess.run(['build/T2-ROUNDING-CALC'], env=env, check=True, timeout=10)
    
    # Run Java
    env['OUTPUT_FILE'] = 'build/t2-java-faulty-out.csv'
    subprocess.run(['java', '-cp', 'build', 'RoundingCalc'], env=env, check=True, timeout=10)
    
    cobol_output = Path('build/t2-cobol-out2.csv').read_text()
    java_output = Path('build/t2-java-faulty-out.csv').read_text()
    
    assert java_output != cobol_output, "Faulty Java output should differ from COBOL"


def test_t2_correct_java_alive_200_cases():
    """T2 correct Java gives ALIVE on 200 generated cases."""
    result = subprocess.run(
        ['.venv/bin/python', '-m', 'coroner', 'verify',
         '--cobol', 'samples/traps/T2-rounding/ROUNDING-CALC.cob',
         '--copybooks', 'samples/traps/T2-rounding',
         '--java', 'samples/traps/T2-rounding/java/correct/RoundingCalc.java',
         '--schema', 'samples/traps/T2-rounding/schema.json',
         '--cases', '200',
         '--seed', '42'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Should be ALIVE: {result.stdout}"
    assert "ALIVE" in result.stdout, f"Expected ALIVE: {result.stdout}"


def test_t2_faulty_java_zombie_200_cases():
    """T2 faulty Java gives ZOMBIE on 200 generated cases."""
    result = subprocess.run(
        ['.venv/bin/python', '-m', 'coroner', 'verify',
         '--cobol', 'samples/traps/T2-rounding/ROUNDING-CALC.cob',
         '--copybooks', 'samples/traps/T2-rounding',
         '--java', 'samples/traps/T2-rounding/java/faulty/RoundingCalc.java',
         '--schema', 'samples/traps/T2-rounding/schema.json',
         '--cases', '200',
         '--seed', '42'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 1, f"Should be ZOMBIE: {result.stdout}"
    assert "ZOMBIE" in result.stdout, f"Expected ZOMBIE: {result.stdout}"
