"""Tests for Trap 1: EBCDIC vs ASCII collating order."""

import os
import subprocess
from pathlib import Path

import pytest


TRAP_DIR = Path("samples/traps/T1-ebcdic-match-merge")
FIXTURES = TRAP_DIR / "fixtures"
BUILD_DIR = Path("build/traps/T1")


@pytest.fixture(scope="module", autouse=True)
def build_programs():
    """Build COBOL and Java programs."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Compile COBOL
    cobol_bin = BUILD_DIR / "MATCH-MERGE"
    result = subprocess.run(
        ["cobc", "-x", "-Wall", str(TRAP_DIR / "MATCH-MERGE.cob"), "-o", str(cobol_bin)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"COBOL compilation failed: {result.stderr}")
    
    # Compile correct Java
    result = subprocess.run(
        ["javac", "-Xlint:all", "-d", str(BUILD_DIR / "correct"), 
         str(TRAP_DIR / "java/correct/MatchMerge.java")],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Correct Java compilation failed: {result.stderr}")
    
    # Compile faulty Java
    result = subprocess.run(
        ["javac", "-Xlint:all", "-d", str(BUILD_DIR / "faulty"), 
         str(TRAP_DIR / "java/faulty/MatchMerge.java")],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Faulty Java compilation failed: {result.stderr}")


def run_cobol(input_file: Path, output_file: Path) -> int:
    """Run COBOL program and return exit code."""
    env = os.environ.copy()
    env["INPUT_FILE"] = str(input_file)
    env["OUTPUT_FILE"] = str(output_file)
    
    result = subprocess.run(
        [str(BUILD_DIR / "MATCH-MERGE")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.returncode


def run_java(variant: str, input_file: Path, output_file: Path) -> int:
    """Run Java program and return exit code."""
    env = os.environ.copy()
    env["INPUT_FILE"] = str(input_file)
    env["OUTPUT_FILE"] = str(output_file)
    
    result = subprocess.run(
        ["java", "-cp", str(BUILD_DIR / variant), "MatchMerge"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.returncode


def test_cobol_compiles_and_runs():
    """COBOL program compiles and runs successfully on fixture."""
    input_file = FIXTURES / "branch-ordering.csv"
    output_file = BUILD_DIR / "cobol-output.csv"
    
    rc = run_cobol(input_file, output_file)
    assert rc == 0, f"COBOL exited with {rc}"
    
    # Check output exists and has data rows
    assert output_file.exists()
    content = output_file.read_text()
    lines = content.strip().split('\n')
    assert len(lines) > 1, "Output has no data rows"
    assert lines[0] == "CASE-ID,BRANCH,SUBTOTAL"


def test_expected_file_equals_cobol_output():
    """Committed expected file equals COBOL output."""
    input_file = FIXTURES / "branch-ordering.csv"
    output_file = BUILD_DIR / "cobol-fresh.csv"
    expected_file = FIXTURES / "branch-ordering-expected.csv"
    
    rc = run_cobol(input_file, output_file)
    assert rc == 0
    
    cobol_output = output_file.read_text()
    expected_output = expected_file.read_text()
    
    assert cobol_output == expected_output, "Expected file diverges from COBOL output"


def test_correct_java_equals_cobol():
    """Correct Java output equals COBOL output byte-for-byte."""
    input_file = FIXTURES / "branch-ordering.csv"
    cobol_output = BUILD_DIR / "cobol-output.csv"
    java_output = BUILD_DIR / "java-correct-output.csv"
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java("correct", input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0
    
    cobol_content = cobol_output.read_text()
    java_content = java_output.read_text()
    
    assert cobol_content == java_content, "Correct Java diverges from COBOL"


def test_faulty_java_diverges_from_cobol():
    """Faulty Java subtotals differ but TOTAL rows match."""
    input_file = FIXTURES / "branch-ordering.csv"
    cobol_output = BUILD_DIR / "cobol-faulty.csv"
    java_output = BUILD_DIR / "java-faulty-output.csv"
    
    rc_cobol = run_cobol(input_file, cobol_output)
    rc_java = run_java("faulty", input_file, java_output)
    
    assert rc_cobol == 0
    assert rc_java == 0
    
    cobol_lines = cobol_output.read_text().strip().split('\n')
    java_lines = java_output.read_text().strip().split('\n')
    
    # Headers must match
    assert cobol_lines[0] == java_lines[0]
    
    # TOTAL rows must match
    cobol_totals = [line for line in cobol_lines if ',TOTAL,' in line]
    java_totals = [line for line in java_lines if ',TOTAL,' in line]
    assert cobol_totals == java_totals, "TOTAL rows diverged"
    
    # At least one subtotal must differ
    cobol_subtotals = [line for line in cobol_lines if ',TOTAL,' not in line and line != cobol_lines[0]]
    java_subtotals = [line for line in java_lines if ',TOTAL,' not in line and line != java_lines[0]]
    
    assert cobol_subtotals != java_subtotals, "No subtotal divergence found"


def test_coroner_correct_java_alive():
    """Coroner verify with correct Java returns ALIVE."""
    result = subprocess.run(
        [".venv/bin/python", "-m", "coroner", "verify",
         "--cobol", str(TRAP_DIR / "MATCH-MERGE.cob"),
         "--copybooks", str(TRAP_DIR / "copybooks"),
         "--java", str(TRAP_DIR / "java/correct/MatchMerge.java"),
         "--schema", str(TRAP_DIR / "schema.json"),
         "--cases", "200",
         "--seed", "42"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Coroner exited {result.returncode}: {result.stderr}"
    assert "ALIVE" in result.stdout
    assert "return code differs" not in result.stdout


def test_coroner_faulty_java_zombie():
    """Coroner verify with faulty Java returns ZOMBIE with matching grand totals."""
    result = subprocess.run(
        [".venv/bin/python", "-m", "coroner", "verify",
         "--cobol", str(TRAP_DIR / "MATCH-MERGE.cob"),
         "--copybooks", str(TRAP_DIR / "copybooks"),
         "--java", str(TRAP_DIR / "java/faulty/MatchMerge.java"),
         "--schema", str(TRAP_DIR / "schema.json"),
         "--cases", "200",
         "--seed", "42"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 1, f"Expected ZOMBIE (exit 1), got {result.returncode}"
    assert "ZOMBIE" in result.stdout
    assert "grand total matches: yes" in result.stdout.lower() or "FAIL: business behavior diverged" in result.stdout
    assert "return code differs" not in result.stdout
