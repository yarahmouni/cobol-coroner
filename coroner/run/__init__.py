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
    
    # Build command: cobc -x -Wall -I <copybooks> -o <output> <source> [flags]
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
