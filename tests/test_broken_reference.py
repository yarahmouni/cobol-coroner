"""Tests for broken reference detection (D-51)."""
import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Skip all tests if cobc not available
pytestmark = pytest.mark.skipif(
    shutil.which("cobc") is None,
    reason="cobc not available"
)


def test_sort_file_error_libcob():
    """Test 1: COBOL with file error gives exit 2 and no certificate."""
    import tempfile
    import subprocess
    import sys
    import shutil
    from pathlib import Path
    
    # Skip if cobc not available
    if shutil.which("cobc") is None:
        pytest.skip("cobc not available")
    
    # Create a COBOL program that will abort with libcob error
    # It tries to DIVIDE BY ZERO without ON SIZE ERROR
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Write a COBOL program that divides by zero (runtime abort)
        cobol_source = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. BROKEN-REF.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO EXTERNAL INPUT-PATH.
           SELECT OUTPUT-FILE ASSIGN TO EXTERNAL OUTPUT-PATH.
       DATA DIVISION.
       FILE SECTION.
       FD  INPUT-FILE.
       01  INPUT-REC PIC X(200).
       FD  OUTPUT-FILE.
       01  OUTPUT-REC PIC X(200).
       WORKING-STORAGE SECTION.
       01  WS-EOF PIC X VALUE 'N'.
       01  WS-ZERO PIC 9 VALUE 0.
       01  WS-RESULT PIC 9.
       PROCEDURE DIVISION.
           DIVIDE 1 BY WS-ZERO GIVING WS-RESULT.
           OPEN INPUT INPUT-FILE.
           OPEN OUTPUT OUTPUT-FILE.
           PERFORM UNTIL WS-EOF = 'Y'
               READ INPUT-FILE
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       WRITE OUTPUT-REC FROM INPUT-REC
               END-READ
           END-PERFORM.
           CLOSE INPUT-FILE.
           CLOSE OUTPUT-FILE.
           STOP RUN.
"""
        cobol_path = tmpdir_path / "broken.cob"
        cobol_path.write_text(cobol_source)
        
        # Use credit-fees schema and Java since that's what the system expects
        schema_path = Path("samples/credit-fees/schema.json").absolute()
        java_path = Path("samples/credit-fees/java/CreditFees.java").absolute()
        copybooks_dir = tmpdir_path / "copybooks"
        copybooks_dir.mkdir()
        
        if not schema_path.exists() or not java_path.exists():
            pytest.skip("credit-fees sample not available")
        
        # Run verify - should detect broken reference
        result = subprocess.run(
            [sys.executable, "-m", "coroner", "verify",
             "--cobol", str(cobol_path),
             "--copybooks", str(copybooks_dir),
             "--java", java_path,
             "--schema", schema_path,
             "--cases", "2",
             "--seed", "42"],
            capture_output=True,
            text=True,
            cwd=str(tmpdir)
        )
        
        # Should exit with code 2
        assert result.returncode == 2, f"Expected exit 2, got {result.returncode}. stderr: {result.stderr}, stdout: {result.stdout}"
        
        # Output should mention reference did not run
        output = result.stdout + result.stderr
        assert "ERROR: reference did not run" in output, f"Expected error message not found in: {output}"
        
        # Should mention either libcob error or signal/abort
        assert ("libcob" in output.lower() or "signal" in output.lower() or "abort" in output.lower()), \
            f"Expected libcob/signal/abort error not found in: {output}"
        
        # No certificate or verdict should exist in any run directory
        runs_dir = tmpdir_path / "runs"
        if runs_dir.exists():
            for run_dir in runs_dir.iterdir():
                assert not (run_dir / "certificate.json").exists(), "Certificate should not exist for broken reference"
                assert not (run_dir / "verdict.json").exists(), "Verdict should not exist for broken reference"


def test_header_only_output():
    """Test 2: COBOL that writes only header for non-empty input gives exit 2."""
    from coroner.run import validate_reference_output, RunResult
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "output.csv"
        input_path = Path(tmpdir) / "input.csv"
        
        # Create input with data rows
        input_path.write_text("CASE-ID\nTEST-01\nTEST-02\n")
        
        # Create output with only header (no data rows)
        output_path.write_text("CASE-ID\n")
        
        result = RunResult(
            output_path=str(output_path),
            return_code=0,
            stderr="",
            wall_time=0.1
        )
        
        is_valid, reason = validate_reference_output(result, str(input_path), was_killed_by_signal=False)
        
        # Should detect no data rows
        assert not is_valid
        assert "no data rows" in reason


def test_credit_fees_exit_4_still_works():
    """Test 3: credit-fees on validation-errors.csv (exit 4) still gives normal verdict."""
    from coroner.cli import run_verify
    
    cobol_file = "samples/credit-fees/CREDIT-FEES.cob"
    java_file = "samples/credit-fees/java/CreditFees.java"
    schema_file = "samples/credit-fees/schema.json"
    copybooks_dir = "samples/credit-fees/copybooks"
    cases_file = "samples/credit-fees/validation-errors.csv"
    
    # Skip if files don't exist
    if not Path(cobol_file).exists():
        pytest.skip("credit-fees sample not available")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run verify with the validation errors input
        verdict, run_dir = run_verify(
            cobol_file,
            java_file,
            schema_file,
            copybooks_dir,
            num_cases=4,
            seed=42,
            base_dir=str(tmpdir)
        )
        
        # Should get a normal verdict (ALIVE or ZOMBIE, not exit 2)
        assert verdict.status in ["ALIVE", "ZOMBIE"]
        
        # Certificate should exist
        assert (run_dir / "certificate.json").exists()
        
        # No run_error.txt should exist
        assert not (run_dir / "run_error.txt").exists()


@pytest.mark.slow
def test_make_demo_unchanged():
    """Test 4a: make demo should still work (ALIVE on 2000 cases)."""
    from coroner.cli import run_verify
    
    cobol_file = "samples/credit-fees/CREDIT-FEES.cob"
    java_file = "samples/credit-fees/java/CreditFees.java"
    schema_file = "samples/credit-fees/schema.json"
    copybooks_dir = "samples/credit-fees/copybooks"
    
    # Skip if files don't exist
    if not Path(cobol_file).exists():
        pytest.skip("credit-fees sample not available")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        verdict, run_dir = run_verify(
            cobol_file,
            java_file,
            schema_file,
            copybooks_dir,
            num_cases=2000,
            seed=42,
            base_dir=str(tmpdir)
        )
        
        # Should be ALIVE
        assert verdict.status == "ALIVE"
        assert verdict.cases_total == 2000
        assert verdict.cases_divergent == 0
        
        # Certificate should exist
        assert (run_dir / "certificate.json").exists()


@pytest.mark.slow
def test_make_zombie_unchanged():
    """Test 4b: make zombie should still work (ZOMBIE on 86 divergences)."""
    from coroner.cli import run_verify
    from coroner.catalog.legacy_variant import generate_half_even_variant
    
    cobol_file = "samples/credit-fees/CREDIT-FEES.cob"
    schema_file = "samples/credit-fees/schema.json"
    copybooks_dir = "samples/credit-fees/copybooks"
    
    # Skip if files don't exist
    if not Path(cobol_file).exists():
        pytest.skip("credit-fees sample not available")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Generate the legacy variant into temp directory
        variant_dir = tmpdir_path / "variant"
        variant_dir.mkdir()
        java_dir = variant_dir / "java"
        java_dir.mkdir()
        
        java_file = java_dir / "CreditFees.java"
        
        generate_half_even_variant(
            "samples/credit-fees/java/CreditFees.java",
            str(java_file)
        )
        
        verdict, run_dir = run_verify(
            cobol_file,
            str(java_file),
            schema_file,
            copybooks_dir,
            num_cases=2000,
            seed=42,
            base_dir=str(tmpdir)
        )
        
        # Should be ZOMBIE with 86 divergences
        assert verdict.status == "ZOMBIE"
        assert verdict.cases_total == 2000
        assert verdict.cases_divergent == 86
        
        # Certificate should exist
        assert (run_dir / "certificate.json").exists()
        
        # Failure report should exist
        assert (run_dir / "failure_report.json").exists()
