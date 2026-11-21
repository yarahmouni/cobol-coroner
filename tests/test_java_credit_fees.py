"""Tests for Java 17 version of CREDIT-FEES."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def compile_cobol(tmp_path_factory):
    """Compile COBOL program once per session into a temporary folder; returns the binary path."""
    if not shutil.which("cobc"):
        pytest.skip("cobc not found")
    
    binary = tmp_path_factory.mktemp("credit_fees_cobol") / "credit-fees"
    result = subprocess.run(
        [
            "cobc",
            "-x",
            "-Wall",
            "-I", "samples/credit-fees/copybooks",
            "-o", str(binary),
            "samples/credit-fees/CREDIT-FEES.cob"
        ],
        capture_output=True,
        timeout=30
    )
    
    if result.returncode != 0:
        pytest.fail(f"COBOL compilation failed: {result.stderr.decode('utf-8')}")

    return binary


@pytest.fixture(scope="session")
def compile_java(tmp_path_factory):
    """Compile Java program once per session into a temporary folder; returns the class folder."""
    if not shutil.which("javac"):
        pytest.skip("javac not found")
    
    classes = tmp_path_factory.mktemp("credit_fees_java")
    result = subprocess.run(
        [
            "javac",
            "-Xlint:all",
            "-d", str(classes),
            "samples/credit-fees/java/CreditFees.java"
        ],
        capture_output=True,
        timeout=30
    )
    
    if result.returncode != 0:
        pytest.fail(f"Java compilation failed: {result.stderr.decode('utf-8')}")
    
    if result.stderr:
        pytest.fail(f"Java compilation warnings: {result.stderr.decode('utf-8')}")

    return classes


def run_cobol(input_file, output_file, compile_cobol):
    """Run COBOL program with given input and output files."""
    env = os.environ.copy()
    env["INPUT_FILE"] = input_file
    env["OUTPUT_FILE"] = output_file
    
    result = subprocess.run(
        [str(compile_cobol)],
        env=env,
        capture_output=True,
        timeout=10
    )
    
    return result


def run_java(input_file, output_file, compile_java):
    """Run Java program with given input and output files."""
    if not shutil.which("java"):
        pytest.skip("java not found")
    
    env = os.environ.copy()
    env["INPUT_FILE"] = input_file
    env["OUTPUT_FILE"] = output_file
    
    result = subprocess.run(
        ["java", "-cp", str(compile_java), "CreditFees"],
        env=env,
        capture_output=True,
        timeout=10
    )
    
    return result


@pytest.mark.parametrize("fixture", [
    "samples/credit-fees/fixtures/rounding-ties.csv",
    "samples/credit-fees/fixtures/edge-cases.csv",
    "samples/credit-fees/fixtures/validation-errors.csv",
    "samples/credit-fees/fixtures/parity-cases.csv",
])
def test_java_cobol_equivalence(fixture, compile_cobol, compile_java, tmp_path):
    """Test that Java and COBOL produce byte-identical outputs."""
    # Skip if fixture doesn't exist
    if not Path(fixture).exists():
        pytest.skip(f"Fixture {fixture} not found")
    
    cobol_output = tmp_path / "cobol-output.csv"
    java_output = tmp_path / "java-output.csv"
    
    # Run COBOL
    cobol_result = run_cobol(fixture, str(cobol_output), compile_cobol)
    
    # Run Java
    java_result = run_java(fixture, str(java_output), compile_java)
    
    # Assert exit codes match
    assert java_result.returncode == cobol_result.returncode, \
        f"Exit codes differ: Java {java_result.returncode}, COBOL {cobol_result.returncode}"
    
    # Assert outputs are byte-identical
    cobol_bytes = cobol_output.read_bytes()
    java_bytes = java_output.read_bytes()
    
    if java_bytes != cobol_bytes:
        # Show line-by-line diff for debugging
        cobol_lines = cobol_output.read_text().splitlines()
        java_lines = java_output.read_text().splitlines()
        
        diff_lines = []
        max_lines = max(len(cobol_lines), len(java_lines))
        for i in range(max_lines):
            cobol_line = cobol_lines[i] if i < len(cobol_lines) else "<missing>"
            java_line = java_lines[i] if i < len(java_lines) else "<missing>"
            if cobol_line != java_line:
                diff_lines.append(f"Line {i+1}:")
                diff_lines.append(f"  COBOL: {cobol_line}")
                diff_lines.append(f"  Java:  {java_line}")
        
        pytest.fail(f"Outputs differ:\n" + "\n".join(diff_lines[:10]))  # Show first 10 differences


def test_empty_input(compile_cobol, compile_java, tmp_path):
    """Test that empty input (header only) produces header-only output and exits 0."""
    # Create empty input file (header only)
    empty_input = tmp_path / "empty-input.csv"
    empty_input.write_text("CASE-ID,PRINCIPAL,FEE-RATE,DURATION-MONTHS,CUSTOMER-SEGMENT,INCOME\n")
    
    cobol_output = tmp_path / "cobol-empty-output.csv"
    java_output = tmp_path / "java-empty-output.csv"
    
    # Run COBOL
    cobol_result = run_cobol(str(empty_input), str(cobol_output), compile_cobol)
    
    # Run Java
    java_result = run_java(str(empty_input), str(java_output), compile_java)
    
    # Assert both exit 0
    assert cobol_result.returncode == 0, f"COBOL exit code: {cobol_result.returncode}"
    assert java_result.returncode == 0, f"Java exit code: {java_result.returncode}"
    
    # Assert outputs are byte-identical
    cobol_bytes = cobol_output.read_bytes()
    java_bytes = java_output.read_bytes()
    assert java_bytes == cobol_bytes, "Empty input outputs differ"
    
    # Assert output is header only
    output_lines = java_output.read_text().splitlines()
    assert len(output_lines) == 1, f"Expected 1 line, got {len(output_lines)}"
    assert output_lines[0] == "CASE-ID,FEE-AMOUNT,ELIGIBLE,REASON-CODE"


def test_missing_file(compile_java, tmp_path):
    """Test that missing input file exits 16 with error message."""
    missing_input = tmp_path / "nonexistent.csv"
    java_output = tmp_path / "java-output.csv"
    
    # Run Java
    java_result = run_java(str(missing_input), str(java_output), compile_java)
    
    # Assert exit code 16
    assert java_result.returncode == 16, f"Java exit code: {java_result.returncode}"
    
    # Assert stderr has error message
    stderr_text = java_result.stderr.decode("utf-8")
    assert "ERROR" in stderr_text, f"Expected error message, got: {stderr_text}"
    assert "Cannot open input file" in stderr_text or "INPUT_FILE" in stderr_text


def test_java_rules():
    """Test that CreditFees.java follows coding rules."""
    java_file = Path("samples/credit-fees/java/CreditFees.java")
    
    if not java_file.exists():
        pytest.skip("CreditFees.java not found")
    
    content = java_file.read_text()
    
    # No double or float for amounts
    assert " double " not in content, "Found 'double' in Java code"
    assert " float " not in content, "Found 'float' in Java code"
    
    # No Math.round
    assert "Math.round" not in content, "Found 'Math.round' in Java code"
    
    # Check for suspicious int/long amount variables
    # Allow: int durationMonths, int[] errorCount, int i, int length, int end
    # Disallow: int fee, int principal, long fee, long principal
    suspicious_patterns = [
        "int fee",
        "int principal",
        "long fee",
        "long principal",
        "int income",
        "long income"
    ]
    
    for pattern in suspicious_patterns:
        assert pattern not in content.lower(), f"Found suspicious pattern '{pattern}' in Java code"
