"""COBOL and Java compilation and execution module."""

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    """Result of a program execution."""
    output_path: str
    return_code: int
    stderr: str
    wall_time: float


def _build_subprocess_env(**extra: str) -> dict[str, str]:
    """
    Build subprocess environment with minimal variables.
    
    Always includes PATH, HOME, LANG. Passes through GnuCOBOL and Java
    variables when set in parent: LD_LIBRARY_PATH, COB_LIBRARY_PATH,
    COB_CONFIG_DIR, COB_COPY_DIR, JAVA_HOME. Additional variables from
    extra are added last.
    
    Args:
        **extra: Additional environment variables to include
        
    Returns:
        Environment dictionary for subprocess calls
    """
    env = {
        'PATH': os.environ.get('PATH', ''),
        'HOME': os.environ.get('HOME', ''),
        'LANG': 'C.UTF-8'
    }
    
    # Pass through GnuCOBOL and Java variables when set
    passthrough = [
        'LD_LIBRARY_PATH',
        'COB_LIBRARY_PATH',
        'COB_CONFIG_DIR',
        'COB_COPY_DIR',
        'JAVA_HOME'
    ]
    
    for var in passthrough:
        value = os.environ.get(var)
        if value is not None:
            env[var] = value
    
    # Add call-specific variables
    env.update(extra)
    
    return env


def compile_cobol(source: str, copybooks: str, output: str, flags: list[str]) -> None:
    """
    Compile COBOL source with cobc.
    
    Args:
        source: Path to COBOL source file
        copybooks: Path to copybook directory
        output: Path to output binary
        flags: Additional compiler flags (e.g., ['-ftraceall'])
        
    Raises:
        RuntimeError: If compilation fails or times out
    """
    # Build directory if needed
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    
    # Build command: cobc -x -Wall -I <copybooks> -o <output> <source> [additional flags]
    # Base flags are always -x -Wall
    cmd = ['cobc', '-x', '-Wall', '-I', copybooks, '-o', output, source] + flags
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60.0,
            env=_build_subprocess_env()
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"COBOL compilation failed\n{result.stderr}")
            
    except subprocess.TimeoutExpired:
        raise RuntimeError("COBOL compilation timed out after 60s")


def compile_java(source: str, output_dir: str) -> None:
    """
    Compile Java source with javac.
    
    Args:
        source: Path to Java source file
        output_dir: Directory for compiled .class files
        
    Raises:
        RuntimeError: If compilation fails or times out
    """
    # Build output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Build command: javac -Xlint:all -d <output_dir> <source>
    cmd = ['javac', '-Xlint:all', '-d', output_dir, source]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60.0,
            env=_build_subprocess_env()
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Java compilation failed\n{result.stderr}")
            
    except subprocess.TimeoutExpired:
        raise RuntimeError("Java compilation timed out after 60s")


def validate_reference_output(
    result: RunResult,
    input_csv: str,
    was_killed_by_signal: bool = False
) -> tuple[bool, str]:
    """
    Check if the COBOL reference ran successfully.
    
    A reference "did not run" when:
    - The output file is missing
    - The output has no data rows while the input has data rows
    - stderr contains "libcob: error"
    - The process was killed by a signal or timed out
    
    An exit code alone never triggers this (credit-fees legitimately exits 4).
    
    Args:
        result: The RunResult from run_cobol
        input_csv: Path to input CSV (to count data rows)
        was_killed_by_signal: True if process was killed by signal or timed out
        
    Returns:
        (is_valid, error_reason): (True, "") if valid, (False, reason) if broken
    """
    import csv
    
    # Check 1: Process killed by signal or timed out
    if was_killed_by_signal:
        return (False, "process was killed by a signal or timed out")
    
    # Check 2: stderr contains "libcob: error"
    if "libcob: error" in result.stderr:
        return (False, "libcob error in stderr")
    
    # Check 3: Output file missing
    if not Path(result.output_path).exists():
        return (False, "output file missing")
    
    # Check 4: Count input and output data rows
    # Input data rows = lines - 1 (header)
    input_data_rows = 0
    try:
        with open(input_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for _ in reader:
                input_data_rows += 1
    except Exception as e:
        return (False, f"could not read input file: {e}")
    
    # Output data rows = lines - 1 (header)
    output_data_rows = 0
    try:
        with open(result.output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for _ in reader:
                output_data_rows += 1
    except Exception as e:
        return (False, f"could not read output file: {e}")
    
    # If input has data rows but output has none, reference did not run
    if input_data_rows > 0 and output_data_rows == 0:
        return (False, "no data rows in output while input has data rows")
    
    return (True, "")


def run_cobol(binary: str, input_csv: str, output_csv: str, timeout: float = 60.0) -> RunResult:
    """
    Run COBOL binary with INPUT_FILE and OUTPUT_FILE environment variables.
    
    Args:
        binary: Path to COBOL executable
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file
        timeout: Timeout in seconds
        
    Returns:
        RunResult with output path, return code, stderr, wall time
        
    Raises:
        RuntimeError: If execution times out
    """
    start_time = time.time()
    
    env = _build_subprocess_env(
        INPUT_FILE=str(Path(input_csv).absolute()),
        OUTPUT_FILE=str(Path(output_csv).absolute())
    )
    
    try:
        result = subprocess.run(
            [binary],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        
        wall_time = time.time() - start_time
        
        return RunResult(
            output_path=output_csv,
            return_code=result.returncode,
            stderr=result.stderr,
            wall_time=wall_time
        )
        
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"COBOL execution timed out after {timeout}s")


def run_java(class_name: str, classpath: str, input_csv: str, output_csv: str, timeout: float = 60.0) -> RunResult:
    """
    Run Java main class with INPUT_FILE and OUTPUT_FILE environment variables.
    
    Args:
        class_name: Fully qualified main class name
        classpath: Classpath for java command
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file
        timeout: Timeout in seconds
        
    Returns:
        RunResult with output path, return code, stderr, wall time
        
    Raises:
        RuntimeError: If execution times out
    """
    start_time = time.time()
    
    env = _build_subprocess_env(
        INPUT_FILE=str(Path(input_csv).absolute()),
        OUTPUT_FILE=str(Path(output_csv).absolute())
    )
    
    try:
        result = subprocess.run(
            ['java', '-cp', classpath, class_name],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        
        wall_time = time.time() - start_time
        
        return RunResult(
            output_path=output_csv,
            return_code=result.returncode,
            stderr=result.stderr,
            wall_time=wall_time
        )
        
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Java execution timed out after {timeout}s")


def run_cobol_instrumented(binary: str, input_csv: str, output_csv: str, trace_file: str, timeout: float = 60.0) -> RunResult:
    """
    Run instrumented COBOL binary with trace environment variables.
    
    Args:
        binary: Path to instrumented COBOL executable
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file
        trace_file: Path to trace output file
        timeout: Timeout in seconds
        
    Returns:
        RunResult with output path, return code, stderr, wall time
        
    Raises:
        RuntimeError: If execution times out
    """
    start_time = time.time()
    
    env = _build_subprocess_env(
        INPUT_FILE=str(Path(input_csv).absolute()),
        OUTPUT_FILE=str(Path(output_csv).absolute()),
        COB_SET_TRACE='Y',
        COB_TRACE_FILE=str(Path(trace_file).absolute())
    )
    
    try:
        result = subprocess.run(
            [binary],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        
        wall_time = time.time() - start_time
        
        return RunResult(
            output_path=output_csv,
            return_code=result.returncode,
            stderr=result.stderr,
            wall_time=wall_time
        )
        
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"COBOL execution timed out after {timeout}s")
