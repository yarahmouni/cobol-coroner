"""COBOL and Java compilation and execution module."""

import os
import subprocess
import time
import hashlib
import shutil
import tempfile
import functools
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    """Result of a program execution."""
    output_path: str
    return_code: int
    stderr: str
    wall_time: float


@functools.lru_cache(maxsize=1)
def get_cobc_version() -> str:
    """Get cobc version string, cached per process."""
    result = subprocess.run(
        ['cobc', '--version'],
        capture_output=True,
        text=True,
        timeout=10.0
    )
    return result.stdout.strip()


@functools.lru_cache(maxsize=1)
def get_javac_version() -> str:
    """Get javac version string, cached per process."""
    result = subprocess.run(
        ['javac', '-version'],
        capture_output=True,
        text=True,
        timeout=10.0
    )
    return result.stderr.strip()


@functools.lru_cache(maxsize=1)
def get_java_version() -> str:
    """Get java version string, cached per process."""
    result = subprocess.run(
        ['java', '-version'],
        capture_output=True,
        text=True,
        timeout=10.0
    )
    return result.stderr.strip()


def _compute_cache_key(source_path: str, copybook_paths: list[str], flags: list[str], version: str) -> str:
    """
    Compute cache key from source, copybooks, flags and tool version.
    
    Args:
        source_path: Path to source file
        copybook_paths: List of copybook paths (sorted)
        flags: Compiler flags (sorted)
        version: Tool version string
        
    Returns:
        SHA-256 hex string
    """
    h = hashlib.sha256()
    
    # Hash source bytes
    with open(source_path, 'rb') as f:
        h.update(f.read())
    
    # Hash copybook bytes in sorted order
    for cp_path in sorted(copybook_paths):
        with open(cp_path, 'rb') as f:
            h.update(f.read())
    
    # Hash flags
    h.update('|'.join(sorted(flags)).encode('utf-8'))
    
    # Hash version
    h.update(version.encode('utf-8'))
    
    return h.hexdigest()


def _get_cache_dir(base_dir: str, cache_key: str) -> Path:
    """Get cache directory for a given key."""
    return Path(base_dir) / "build" / "cache" / cache_key


def _atomic_cache_create(cache_dir: Path, build_fn) -> None:
    """
    Atomically create cache entry.
    
    Args:
        cache_dir: Target cache directory
        build_fn: Function that builds outputs in given temp directory
    """
    if cache_dir.exists():
        return  # Another process created it
    
    # Build in temp directory
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix='cache_', dir=cache_dir.parent))
    
    try:
        build_fn(temp_dir)
        
        # Atomic rename
        try:
            temp_dir.rename(cache_dir)
        except FileExistsError:
            # Another process won the race, clean up
            shutil.rmtree(temp_dir)
    except Exception:
        # Clean up on failure
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise


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


def compile_cobol(source: str, copybooks: str, output: str, flags: list[str], base_dir: str = ".") -> None:
    """
    Compile COBOL source with cobc, using build cache.
    
    Args:
        source: Path to COBOL source file
        copybooks: Path to copybook directory
        output: Path to output binary
        flags: Additional compiler flags (e.g., ['-ftraceall'])
        base_dir: Base directory for cache (default ".")
        
    Raises:
        RuntimeError: If compilation fails or times out
    """
    # Collect copybook paths
    copybook_paths = []
    for entry in sorted(os.listdir(copybooks)):
        path = os.path.join(copybooks, entry)
        if os.path.isfile(path):
            copybook_paths.append(path)
    
    # Compute cache key
    version = get_cobc_version()
    cache_key = _compute_cache_key(source, copybook_paths, flags, version)
    cache_dir = _get_cache_dir(base_dir, cache_key)
    
    # Binary name from output path
    binary_name = Path(output).name
    
    # Check cache (find any binary in cache dir)
    if cache_dir.exists():
        cached_binaries = list(cache_dir.iterdir())
        if cached_binaries:
            # Cache hit: copy to output
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cached_binaries[0], output)
            return
    
    # Cache miss: compile
    def build_fn(temp_dir: Path):
        temp_output = temp_dir / binary_name
        cmd = ['cobc', '-x', '-Wall', '-I', copybooks, '-o', str(temp_output), source] + flags
        
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
    
    _atomic_cache_create(cache_dir, build_fn)
    
    # Copy from cache to output
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    cached_binaries = list(cache_dir.iterdir())
    shutil.copy2(cached_binaries[0], output)


def compile_java(source: str, output_dir: str, base_dir: str = ".") -> None:
    """
    Compile Java source with javac, using build cache.
    
    Args:
        source: Path to Java source file
        output_dir: Directory for compiled .class files
        base_dir: Base directory for cache (default ".")
        
    Raises:
        RuntimeError: If compilation fails or times out
    """
    # Compute cache key (no copybooks, no flags for Java)
    version = get_javac_version()
    cache_key = _compute_cache_key(source, [], [], version)
    cache_dir = _get_cache_dir(base_dir, cache_key)
    
    # Check cache (look for .class files)
    if cache_dir.exists() and any(cache_dir.glob('*.class')):
        # Cache hit: copy to output
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        for class_file in cache_dir.glob('*.class'):
            shutil.copy2(class_file, output_dir)
        return
    
    # Cache miss: compile
    def build_fn(temp_dir: Path):
        cmd = ['javac', '-Xlint:all', '-d', str(temp_dir), source]
        
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
    
    _atomic_cache_create(cache_dir, build_fn)
    
    # Copy from cache to output
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for class_file in cache_dir.glob('*.class'):
        shutil.copy2(class_file, output_dir)


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
