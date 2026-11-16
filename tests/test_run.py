"""Tests for COBOL and Java compilation and execution."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from coroner.run import (
    RunResult,
    _build_subprocess_env,
    compile_cobol,
    compile_java,
    run_cobol,
    run_cobol_instrumented,
    run_java,
)


def test_build_subprocess_env():
    """Test _build_subprocess_env passes through GnuCOBOL variables and filters secrets."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Set up fake parent environment with passthrough and secret variables
        os.environ['LD_LIBRARY_PATH'] = '/opt/gnucobol/lib'
        os.environ['COB_LIBRARY_PATH'] = '/opt/cobol'
        os.environ['JAVA_HOME'] = '/usr/lib/jvm/java-17'
        os.environ['SECRET_TOKEN'] = 'should-not-pass-through'
        os.environ['API_KEY'] = 'also-secret'
        
        # Build environment with extra variables
        env = _build_subprocess_env(
            INPUT_FILE='/tmp/input.csv',
            OUTPUT_FILE='/tmp/output.csv'
        )
        
        # Check required variables are present
        assert 'PATH' in env
        assert 'HOME' in env
        assert 'LANG' in env
        assert env['LANG'] == 'C.UTF-8'
        
        # Check GnuCOBOL and Java variables passed through
        assert env['LD_LIBRARY_PATH'] == '/opt/gnucobol/lib'
        assert env['COB_LIBRARY_PATH'] == '/opt/cobol'
        assert env['JAVA_HOME'] == '/usr/lib/jvm/java-17'
        
        # Check extra variables included
        assert env['INPUT_FILE'] == '/tmp/input.csv'
        assert env['OUTPUT_FILE'] == '/tmp/output.csv'
        
        # Check secrets NOT passed through
        assert 'SECRET_TOKEN' not in env
        assert 'API_KEY' not in env
        
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_build_subprocess_env_missing_optional():
    """Test _build_subprocess_env when optional GnuCOBOL variables are not set."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear optional variables
        for var in ['LD_LIBRARY_PATH', 'COB_LIBRARY_PATH', 'COB_CONFIG_DIR', 
                    'COB_COPY_DIR', 'JAVA_HOME']:
            os.environ.pop(var, None)
        
        # Build environment
        env = _build_subprocess_env()
        
        # Check required variables present
        assert 'PATH' in env
        assert 'HOME' in env
        assert 'LANG' in env
        
        # Check optional variables not present
        assert 'LD_LIBRARY_PATH' not in env
        assert 'COB_LIBRARY_PATH' not in env
        assert 'COB_CONFIG_DIR' not in env
        assert 'COB_COPY_DIR' not in env
        assert 'JAVA_HOME' not in env
        
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    # Cleanup
    shutil.rmtree(tmpdir)


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_compile_cobol(temp_dir):
    """Test COBOL compilation succeeds."""
    source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    output = temp_dir / "CREDIT-FEES"
    
    # Compile without instrumentation
    compile_cobol(source, copybooks, str(output), [], str(temp_dir))
    
    # Check binary was created
    assert output.exists()


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_compile_cobol_instrumented(temp_dir):
    """Test COBOL compilation with -ftraceall succeeds."""
    source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    output = temp_dir / "CREDIT-FEES-traced"
    
    # Compile with instrumentation
    compile_cobol(source, copybooks, str(output), ['-ftraceall'], str(temp_dir))
    
    # Check binary was created
    assert output.exists()


@pytest.mark.skipif(not shutil.which("javac"), reason="javac not available")
def test_compile_java(temp_dir):
    """Test Java compilation succeeds."""
    source = "samples/credit-fees/java/CreditFees.java"
    output_dir = temp_dir / "java"
    
    # Compile Java
    compile_java(source, str(output_dir), str(temp_dir))
    
    # Check .class file was created
    class_file = output_dir / "CreditFees.class"
    assert class_file.exists()


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_compile_cobol_cache(temp_dir):
    """Test build cache: second identical compile is a cache hit."""
    source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    
    # First compile
    output1 = temp_dir / "CREDIT-FEES-1"
    compile_cobol(source, copybooks, str(output1), [], str(temp_dir))
    assert output1.exists()
    
    # Read binary bytes
    with open(output1, 'rb') as f:
        binary1_bytes = f.read()
    
    # Second compile with same inputs (cache hit)
    output2 = temp_dir / "CREDIT-FEES-2"
    compile_cobol(source, copybooks, str(output2), [], str(temp_dir))
    assert output2.exists()
    
    # Binary bytes must be identical
    with open(output2, 'rb') as f:
        binary2_bytes = f.read()
    assert binary1_bytes == binary2_bytes
    
    # Modify flags (cache miss)
    output3 = temp_dir / "CREDIT-FEES-3"
    compile_cobol(source, copybooks, str(output3), ["-ftraceall"], str(temp_dir))
    assert output3.exists()


@pytest.mark.skipif(not shutil.which("javac"), reason="javac not available")
def test_compile_java_cache(temp_dir):
    """Test Java build cache."""
    source = "samples/credit-fees/java/CreditFees.java"
    
    # First compile
    output1 = temp_dir / "out1"
    compile_java(source, str(output1), str(temp_dir))
    assert (output1 / "CreditFees.class").exists()
    
    # Read class bytes
    with open(output1 / "CreditFees.class", 'rb') as f:
        class1_bytes = f.read()
    
    # Second compile (cache hit)
    output2 = temp_dir / "out2"
    compile_java(source, str(output2), str(temp_dir))
    assert (output2 / "CreditFees.class").exists()
    
    # Bytes must be identical
    with open(output2 / "CreditFees.class", 'rb') as f:
        class2_bytes = f.read()
    assert class1_bytes == class2_bytes


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_run_cobol(temp_dir):
    """Test COBOL execution returns RunResult with return_code 0 and output_path."""
    # Compile first
    source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    binary = temp_dir / "CREDIT-FEES"
    compile_cobol(source, copybooks, str(binary), [], str(temp_dir))
    
    # Run on rounding-ties fixture
    input_csv = "samples/credit-fees/fixtures/rounding-ties.csv"
    output_csv = temp_dir / "output.csv"
    
    result = run_cobol(str(binary), input_csv, str(output_csv), timeout=60.0)
    
    # Check result
    assert isinstance(result, RunResult)
    assert result.return_code == 0
    assert result.output_path == str(output_csv)
    assert output_csv.exists()
    assert result.wall_time > 0


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_run_cobol_validation_errors(temp_dir):
    """Test COBOL execution on validation errors returns exit code 4."""
    # Compile first
    source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    binary = temp_dir / "CREDIT-FEES"
    compile_cobol(source, copybooks, str(binary), [], str(temp_dir))
    
    # Run on validation-errors fixture
    input_csv = "samples/credit-fees/fixtures/validation-errors.csv"
    output_csv = temp_dir / "output.csv"
    
    result = run_cobol(str(binary), input_csv, str(output_csv), timeout=60.0)
    
    # Check result
    assert result.return_code == 4
    assert output_csv.exists()


@pytest.mark.skipif(not shutil.which("javac"), reason="javac not available")
def test_run_java(temp_dir):
    """Test Java execution returns RunResult with return_code 0."""
    # Compile first
    source = "samples/credit-fees/java/CreditFees.java"
    java_dir = temp_dir / "java"
    compile_java(source, str(java_dir), str(temp_dir))
    
    # Run on rounding-ties fixture
    input_csv = "samples/credit-fees/fixtures/rounding-ties.csv"
    output_csv = temp_dir / "output.csv"
    
    result = run_java("CreditFees", str(java_dir), input_csv, str(output_csv), timeout=60.0)
    
    # Check result
    assert isinstance(result, RunResult)
    assert result.return_code == 0
    assert result.output_path == str(output_csv)
    assert output_csv.exists()
    assert result.wall_time > 0


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
@pytest.mark.skipif(not shutil.which("javac"), reason="javac not available")
def test_cobol_and_java_byte_identical_rounding_ties(temp_dir):
    """Test COBOL and Java produce byte-identical outputs on rounding-ties fixture."""
    # Compile COBOL
    cobol_source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    cobol_binary = temp_dir / "CREDIT-FEES"
    compile_cobol(cobol_source, copybooks, str(cobol_binary), [], str(temp_dir))
    
    # Compile Java
    java_source = "samples/credit-fees/java/CreditFees.java"
    java_dir = temp_dir / "java"
    compile_java(java_source, str(java_dir), str(temp_dir))
    
    # Run both on rounding-ties
    input_csv = "samples/credit-fees/fixtures/rounding-ties.csv"
    cobol_output = temp_dir / "cobol_output.csv"
    java_output = temp_dir / "java_output.csv"
    
    cobol_result = run_cobol(str(cobol_binary), input_csv, str(cobol_output), timeout=60.0)
    java_result = run_java("CreditFees", str(java_dir), input_csv, str(java_output), timeout=60.0)
    
    # Compare return codes
    assert cobol_result.return_code == java_result.return_code == 0
    
    # Compare outputs byte for byte
    cobol_bytes = cobol_output.read_bytes()
    java_bytes = java_output.read_bytes()
    assert cobol_bytes == java_bytes


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
@pytest.mark.skipif(not shutil.which("javac"), reason="javac not available")
def test_cobol_and_java_byte_identical_validation_errors(temp_dir):
    """Test COBOL and Java produce byte-identical outputs on validation-errors fixture."""
    # Compile COBOL
    cobol_source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    cobol_binary = temp_dir / "CREDIT-FEES"
    compile_cobol(cobol_source, copybooks, str(cobol_binary), [], str(temp_dir))
    
    # Compile Java
    java_source = "samples/credit-fees/java/CreditFees.java"
    java_dir = temp_dir / "java"
    compile_java(java_source, str(java_dir), str(temp_dir))
    
    # Run both on validation-errors
    input_csv = "samples/credit-fees/fixtures/validation-errors.csv"
    cobol_output = temp_dir / "cobol_output.csv"
    java_output = temp_dir / "java_output.csv"
    
    cobol_result = run_cobol(str(cobol_binary), input_csv, str(cobol_output), timeout=60.0)
    java_result = run_java("CreditFees", str(java_dir), input_csv, str(java_output), timeout=60.0)
    
    # Compare return codes
    assert cobol_result.return_code == java_result.return_code == 4
    
    # Compare outputs byte for byte
    cobol_bytes = cobol_output.read_bytes()
    java_bytes = java_output.read_bytes()
    assert cobol_bytes == java_bytes


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_run_cobol_instrumented_produces_trace(temp_dir):
    """Test instrumented COBOL run produces a trace file."""
    # Compile instrumented binary
    source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    binary = temp_dir / "CREDIT-FEES-traced"
    compile_cobol(source, copybooks, str(binary), ['-ftraceall'], str(temp_dir))
    
    # Run instrumented
    input_csv = "samples/credit-fees/fixtures/rounding-ties.csv"
    output_csv = temp_dir / "output.csv"
    trace_file = temp_dir / "trace.txt"
    
    result = run_cobol_instrumented(
        str(binary), 
        input_csv, 
        str(output_csv), 
        str(trace_file), 
        timeout=60.0
    )
    
    # Check result
    assert result.return_code == 0
    assert output_csv.exists()
    assert trace_file.exists()
    
    # Check trace has content
    trace_content = trace_file.read_text()
    assert "Line:" in trace_content
    assert "Source:" in trace_content


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_run_cobol_instrumented_single_case(temp_dir):
    """Test re-running instrumented COBOL on a single case."""
    # Compile instrumented binary
    source = "samples/credit-fees/CREDIT-FEES.cob"
    copybooks = "samples/credit-fees/copybooks"
    binary = temp_dir / "CREDIT-FEES-traced"
    compile_cobol(source, copybooks, str(binary), ['-ftraceall'], str(temp_dir))
    
    # Create single-case input (header + one row)
    single_case_input = temp_dir / "single_case.csv"
    single_case_input.write_text(
        "CASE-ID,PRINCIPAL,FEE-RATE,DURATION-MONTHS,CUSTOMER-SEGMENT,INCOME\n"
        "TEST-01,1000.00,0.01500,12,B,50000.00\n"
    )
    
    # Run instrumented
    output_csv = temp_dir / "output.csv"
    trace_file = temp_dir / "trace.txt"
    
    result = run_cobol_instrumented(
        str(binary), 
        str(single_case_input), 
        str(output_csv), 
        str(trace_file), 
        timeout=60.0
    )
    
    # Check result
    assert result.return_code == 0
    assert output_csv.exists()
    assert trace_file.exists()


@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not available")
def test_timeout_cobol(temp_dir):
    """Test timeout for COBOL execution with a sleeping program."""
    # Create a tiny COBOL program that sleeps
    sleep_cobol = temp_dir / "sleep.cob"
    sleep_cobol.write_text("""
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SLEEPER.
       
       PROCEDURE DIVISION.
           CALL "C$SLEEP" USING "3".
           STOP RUN.
    """)
    
    # Compile
    binary = temp_dir / "sleeper"
    try:
        compile_cobol(str(sleep_cobol), str(temp_dir), str(binary), [], str(temp_dir))
    except RuntimeError:
        # C$SLEEP might not be available, skip test
        pytest.skip("C$SLEEP not available in this GnuCOBOL build")
    
    # Run with 1 second timeout (should timeout)
    input_csv = temp_dir / "dummy.csv"
    input_csv.write_text("header\n")
    output_csv = temp_dir / "output.csv"
    
    with pytest.raises(RuntimeError, match="timed out"):
        run_cobol(str(binary), str(input_csv), str(output_csv), timeout=1.0)


@pytest.mark.skipif(not shutil.which("javac"), reason="javac not available")
def test_timeout_java(temp_dir):
    """Test timeout for Java execution with a sleeping program."""
    # Create a tiny Java program that sleeps
    sleep_java = temp_dir / "Sleeper.java"
    sleep_java.write_text("""
public class Sleeper {
    public static void main(String[] args) throws Exception {
        Thread.sleep(3000);
    }
}
    """)
    
    # Compile
    java_dir = temp_dir / "java"
    compile_java(str(sleep_java), str(java_dir), str(temp_dir))
    
    # Run with 1 second timeout (should timeout)
    input_csv = temp_dir / "dummy.csv"
    input_csv.write_text("header\n")
    output_csv = temp_dir / "output.csv"
    
    with pytest.raises(RuntimeError, match="timed out"):
        run_java("Sleeper", str(java_dir), str(input_csv), str(output_csv), timeout=1.0)
