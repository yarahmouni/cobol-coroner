"""Tests for T4 zoned-overpunch trap."""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def t4_dir():
    """T4 trap directory."""
    return Path("samples/traps/T4-zoned-overpunch")


def test_t4_cobol_compiles(t4_dir):
    """T4 COBOL program compiles with -fsign=EBCDIC."""
    cobol_file = t4_dir / "ZONED-OVERPUNCH.cob"
    assert cobol_file.exists()
    
    result = subprocess.run(
        ["cobc", "-x", "-Wall", "-fsign=EBCDIC", "-o", "build/test-t4-cobol", str(cobol_file)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"COBOL compilation failed: {result.stderr}"


def test_t4_cobol_runs(t4_dir):
    """T4 COBOL program runs and produces output."""
    cobol_file = t4_dir / "ZONED-OVERPUNCH.cob"
    fixture_input = t4_dir / "fixtures/zoned-signs.csv"
    test_output = Path("build/test-t4-cobol-output.csv")
    
    # Compile
    subprocess.run(
        ["cobc", "-x", "-Wall", "-fsign=EBCDIC", "-o", "build/test-t4-cobol", str(cobol_file)],
        check=True,
        capture_output=True
    )
    
    # Run
    env = os.environ.copy()
    env["INPUT_FILE"] = str(fixture_input)
    env["OUTPUT_FILE"] = str(test_output)
    
    result = subprocess.run(
        ["./build/test-t4-cobol"],
        env=env,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"COBOL execution failed: {result.stderr}"
    assert test_output.exists(), "COBOL did not create output file"
    
    # Check output has data rows
    with open(test_output) as f:
        lines = f.readlines()
    assert len(lines) > 1, "COBOL output has no data rows"
    
    # Check header
    assert lines[0].strip() == "CASE-ID,DECODED-VALUE"


def test_t4_expected_equals_fresh_cobol_run(t4_dir):
    """Expected output equals a fresh COBOL run."""
    cobol_file = t4_dir / "ZONED-OVERPUNCH.cob"
    fixture_input = t4_dir / "fixtures/zoned-signs.csv"
    expected_output = t4_dir / "fixtures/expected-output.csv"
    test_output = Path("build/test-t4-expected.csv")
    
    # Compile and run COBOL
    subprocess.run(
        ["cobc", "-x", "-Wall", "-fsign=EBCDIC", "-o", "build/test-t4-cobol", str(cobol_file)],
        check=True,
        capture_output=True
    )
    
    env = os.environ.copy()
    env["INPUT_FILE"] = str(fixture_input)
    env["OUTPUT_FILE"] = str(test_output)
    
    subprocess.run(
        ["./build/test-t4-cobol"],
        env=env,
        check=True,
        capture_output=True
    )
    
    # Compare with expected
    with open(expected_output) as f:
        expected = f.read()
    with open(test_output) as f:
        actual = f.read()
    
    assert actual == expected, "Fresh COBOL run differs from expected output"


def test_t4_correct_java_matches_cobol(t4_dir):
    """Correct Java output is byte-identical to COBOL output."""
    fixture_input = t4_dir / "fixtures/zoned-signs.csv"
    cobol_output = Path("build/test-t4-cobol-output.csv")
    java_output = Path("build/test-t4-correct-java-output.csv")
    
    # Run COBOL (already compiled in previous test)
    env = os.environ.copy()
    env["INPUT_FILE"] = str(fixture_input)
    env["OUTPUT_FILE"] = str(cobol_output)
    
    subprocess.run(
        ["./build/test-t4-cobol"],
        env=env,
        check=True,
        capture_output=True
    )
    
    # Compile and run correct Java
    java_file = t4_dir / "java/correct/ZonedOverpunch.java"
    subprocess.run(
        ["javac", "-d", "build", str(java_file)],
        check=True,
        capture_output=True
    )
    
    env["OUTPUT_FILE"] = str(java_output)
    subprocess.run(
        ["java", "-cp", "build", "ZonedOverpunch"],
        env=env,
        check=True,
        capture_output=True
    )
    
    # Compare
    with open(cobol_output) as f:
        cobol_content = f.read()
    with open(java_output) as f:
        java_content = f.read()
    
    assert java_content == cobol_content, "Correct Java differs from COBOL"


def test_t4_faulty_java_differs(t4_dir):
    """Faulty Java output differs from COBOL output."""
    fixture_input = t4_dir / "fixtures/zoned-signs.csv"
    cobol_output = Path("build/test-t4-cobol-output.csv")
    java_output = Path("build/test-t4-faulty-java-output.csv")
    
    # Compile and run faulty Java
    java_file = t4_dir / "java/faulty/ZonedOverpunch.java"
    subprocess.run(
        ["mkdir", "-p", "build/faulty"],
        check=True
    )
    subprocess.run(
        ["javac", "-d", "build/faulty", str(java_file)],
        check=True,
        capture_output=True
    )
    
    env = os.environ.copy()
    env["INPUT_FILE"] = str(fixture_input)
    env["OUTPUT_FILE"] = str(java_output)
    subprocess.run(
        ["java", "-cp", "build/faulty", "ZonedOverpunch"],
        env=env,
        check=True,
        capture_output=True
    )
    
    # Compare
    with open(cobol_output) as f:
        cobol_content = f.read()
    with open(java_output) as f:
        java_content = f.read()
    
    assert java_content != cobol_content, "Faulty Java should differ from COBOL"


@pytest.mark.slow
def test_t4_engine_correct_alive(t4_dir):
    """Engine gives ALIVE on correct Java (200 cases)."""
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", str(t4_dir / "ZONED-OVERPUNCH.cob"),
            "--copybooks", str(t4_dir / "copybooks"),
            "--java", str(t4_dir / "java/correct/ZonedOverpunch.java"),
            "--schema", str(t4_dir / "schema.json"),
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stdout} {result.stderr}"
    assert "ALIVE" in result.stdout


@pytest.mark.slow
def test_t4_engine_faulty_zombie(t4_dir):
    """Engine gives ZOMBIE on faulty Java (200 cases)."""
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", str(t4_dir / "ZONED-OVERPUNCH.cob"),
            "--copybooks", str(t4_dir / "copybooks"),
            "--java", str(t4_dir / "java/faulty/ZonedOverpunch.java"),
            "--schema", str(t4_dir / "schema.json"),
            "--cases", "200",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}: {result.stdout} {result.stderr}"
    assert "ZOMBIE" in result.stdout


@pytest.mark.slow
def test_t4_certificate_records_cobc_flags(t4_dir):
    """Certificate of a T4 run records cobc_flags -fsign=EBCDIC."""
    import json
    
    # Run verification
    result = subprocess.run(
        [
            ".venv/bin/python", "-m", "coroner", "verify",
            "--cobol", str(t4_dir / "ZONED-OVERPUNCH.cob"),
            "--copybooks", str(t4_dir / "copybooks"),
            "--java", str(t4_dir / "java/correct/ZonedOverpunch.java"),
            "--schema", str(t4_dir / "schema.json"),
            "--cases", "100",
            "--seed", "42"
        ],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0
    
    # Find the run directory from the output
    import re
    match = re.search(r'runs/([a-f0-9]{12})', result.stdout)
    assert match, f"Could not find run_id in output: {result.stdout}"
    run_id = match.group(1)
    
    # Check certificate
    cert_path = Path(f"runs/{run_id}/certificate.json")
    assert cert_path.exists(), "Certificate not found"
    
    with open(cert_path) as f:
        cert = json.load(f)
    
    assert "cobc_flags" in cert, "cobc_flags not in certificate"
    assert cert["cobc_flags"] == ["-fsign=EBCDIC"], f"Expected [-fsign=EBCDIC], got {cert['cobc_flags']}"
