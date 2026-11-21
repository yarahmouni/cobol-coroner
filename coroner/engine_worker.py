"""
Engine worker that polls exchange directory and executes jobs.

The worker runs in an isolated container with no network access.
It polls /exchange/jobs/ for queued jobs, executes them with coroner verify,
and writes results back to the exchange directory.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple


def get_repo_root() -> Path:
    """
    Get repository root from the installed package.
    
    Returns the directory containing coroner/ (the repository root).
    """
    # coroner/engine_worker.py -> coroner/ -> repository root
    return Path(__file__).resolve().parents[1]


def get_variants_dir() -> Path:
    """
    Folder holding the HALF_EVEN variant of the credit-fees port.

    Default: build/variants in the repository (the folder scripts/init_demo_runs.sh and
    make zombie use). CORONER_VARIANTS_DIR replaces it, so that tests never write into
    the shared folder.
    """
    override = os.environ.get("CORONER_VARIANTS_DIR")
    if override:
        return Path(override)
    return get_repo_root() / "build" / "variants"


def discover_trap_folders() -> Dict[str, Path]:
    """
    Discover trap folders by reading trap.json in samples/traps/*.
    
    Returns a mapping from trap id (T1, T2, ...) to folder path.
    """
    repo_root = get_repo_root()
    traps_dir = repo_root / "samples" / "traps"
    
    if not traps_dir.exists():
        return {}
    
    trap_map = {}
    
    for folder in traps_dir.iterdir():
        if not folder.is_dir():
            continue
        
        trap_json = folder / "trap.json"
        if not trap_json.exists():
            continue
        
        try:
            trap_data = json.loads(trap_json.read_text())
            trap_id = trap_data.get("id")
            if trap_id:
                trap_map[trap_id] = folder
        except (json.JSONDecodeError, OSError):
            continue
    
    return trap_map


def resolve_sample_paths(sample: str, port: str, job_dir: Path) -> Tuple[str, str, str, str]:
    """
    Resolve COBOL, Java, schema and copybooks paths for a sample and port.
    
    Args:
        sample: Sample id (credit-fees, T1, T2, T3, T4, T5)
        port: Port type (correct or faulty)
        job_dir: Job directory for generated variants
    
    Returns:
        Tuple of (cobol_path, java_path, schema_path, copybooks_path)
    
    Raises:
        ValueError: If sample is unknown or files are missing or not unique
    """
    repo_root = get_repo_root()
    
    if sample == "credit-fees":
        sample_dir = repo_root / "samples" / "credit-fees"
        
        if not sample_dir.exists():
            raise ValueError(f"sample directory not found: {sample_dir}")
        
        cobol_path = sample_dir / "CREDIT-FEES.cob"
        schema_path = sample_dir / "schema.json"
        copybooks_path = sample_dir / "copybooks"
        
        if not cobol_path.exists():
            raise ValueError(f"COBOL file not found: {cobol_path}")
        if not schema_path.exists():
            raise ValueError(f"schema file not found: {schema_path}")
        if not copybooks_path.exists():
            raise ValueError(f"copybooks directory not found: {copybooks_path}")
        
        if port == "correct":
            java_path = sample_dir / "java" / "CreditFees.java"
            if not java_path.exists():
                raise ValueError(f"Java file not found: {java_path}")
        elif port == "faulty":
            # Use pre-generated HALF_EVEN variant from build/variants/
            # If missing on host (developer machine without make zombie), generate it there
            # In the image it is prebuilt by init_demo_runs.sh
            variant_path = get_variants_dir() / "CreditFees.java"
            
            if not variant_path.exists():
                # Generate the variant
                from coroner.catalog.legacy_variant import generate_half_even_variant
                
                source_path = sample_dir / "java" / "CreditFees.java"
                if not source_path.exists():
                    raise ValueError(f"Source Java file not found: {source_path}")
                
                variant_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write to a temporary name, then rename: a reader never sees a partial file
                temp_path = variant_path.with_name(f".CreditFees.{os.getpid()}.tmp")
                try:
                    generate_half_even_variant(str(source_path), str(temp_path))
                    os.replace(temp_path, variant_path)
                finally:
                    temp_path.unlink(missing_ok=True)
            
            java_path = variant_path
        else:
            raise ValueError(f"unknown port: {port}")
        
        return str(cobol_path), str(java_path), str(schema_path), str(copybooks_path)
    
    # Check if sample is a trap
    trap_map = discover_trap_folders()
    
    if sample not in trap_map:
        raise ValueError(f"unknown sample: {sample}")
    
    trap_dir = trap_map[sample]
    
    # Find the single .cob file
    cob_files = list(trap_dir.glob("*.cob"))
    if len(cob_files) == 0:
        raise ValueError(f"no COBOL file found in {trap_dir}")
    if len(cob_files) > 1:
        raise ValueError(f"multiple COBOL files found in {trap_dir}: {cob_files}")
    
    cobol_path = cob_files[0]
    schema_path = trap_dir / "schema.json"
    
    if not schema_path.exists():
        raise ValueError(f"schema file not found: {schema_path}")
    
    # Copybooks: <folder>/copybooks if it exists, else the folder itself
    copybooks_dir = trap_dir / "copybooks"
    if copybooks_dir.exists():
        copybooks_path = copybooks_dir
    else:
        copybooks_path = trap_dir
    
    # Java: find the single .java in <folder>/java/<port>/
    java_dir = trap_dir / "java" / port
    if not java_dir.exists():
        raise ValueError(f"Java directory not found: {java_dir}")
    
    java_files = list(java_dir.glob("*.java"))
    if len(java_files) == 0:
        raise ValueError(f"no Java file found in {java_dir}")
    if len(java_files) > 1:
        raise ValueError(f"multiple Java files found in {java_dir}: {java_files}")
    
    java_path = java_files[0]
    
    return str(cobol_path), str(java_path), str(schema_path), str(copybooks_path)


def get_exchange_dir() -> Path:
    """Get exchange directory from environment, default /exchange."""
    return Path(os.environ.get("CORONER_EXCHANGE_DIR", "/exchange"))


def get_timeout() -> int:
    """Get job timeout in seconds from environment, default 60."""
    return int(os.environ.get("CORONER_JOB_TIMEOUT", "60"))


def find_oldest_queued_job() -> Path | None:
    """
    Find the oldest queued job in /exchange/jobs/.
    
    Returns the job directory path, or None if no queued job found.
    """
    exchange_dir = get_exchange_dir()
    jobs_dir = exchange_dir / "jobs"
    
    if not jobs_dir.exists():
        return None
    
    queued_jobs = []
    
    for job_dir in jobs_dir.iterdir():
        if not job_dir.is_dir():
            continue
        
        status_file = job_dir / "status.json"
        if not status_file.exists():
            continue
        
        try:
            status_data = json.loads(status_file.read_text())
            if status_data.get("status") == "queued":
                # Get timestamp from status file
                timestamp = status_data.get("queued_at", 0)
                queued_jobs.append((timestamp, job_dir))
        except (json.JSONDecodeError, OSError):
            continue
    
    if not queued_jobs:
        return None
    
    # Sort by timestamp, oldest first
    queued_jobs.sort(key=lambda x: x[0])
    
    return queued_jobs[0][1]


def validate_job_id(job_id: str) -> bool:
    """Validate job_id format: 12 lowercase hexadecimal characters."""
    if len(job_id) != 12:
        return False
    for c in job_id:
        if c not in "0123456789abcdef":
            return False
    return True


def update_status(job_dir: Path, status: str, **kwargs):
    """Update status.json with given status and additional fields."""
    status_file = job_dir / "status.json"
    
    # Read existing status
    status_data = {}
    if status_file.exists():
        try:
            status_data = json.loads(status_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    
    # Update fields
    status_data["status"] = status
    for key, value in kwargs.items():
        status_data[key] = value
    
    # Write atomically
    temp_file = status_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(status_data, indent=2))
    temp_file.replace(status_file)


def execute_job(job_dir: Path):
    """
    Execute a single job.
    
    Reads request.json, runs coroner verify as a subprocess with timeout,
    writes result files. The subprocess timeout kills the process group.
    """
    job_id = job_dir.name
    
    # Validate job_id before any path operations
    if not validate_job_id(job_id):
        update_status(job_dir, "error", reason="invalid job_id format", completed_at=time.time())
        return
    
    # Read request
    request_file = job_dir / "request.json"
    if not request_file.exists():
        update_status(job_dir, "error", reason="request.json not found", completed_at=time.time())
        return
    
    try:
        request_data = json.loads(request_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        update_status(job_dir, "error", reason=f"failed to read request.json: {e}", completed_at=time.time())
        return
    
    # Extract parameters
    sample = request_data.get("sample")
    port = request_data.get("port")
    seed = request_data.get("seed")
    cases = request_data.get("cases")
    
    if not all([sample, port, seed is not None, cases]):
        update_status(job_dir, "error", reason="missing required parameters", completed_at=time.time())
        return
    
    # Validate seed: 0 to 1000000
    if not isinstance(seed, int) or seed < 0 or seed > 1000000:
        update_status(job_dir, "error", reason="seed must be an integer between 0 and 1000000", completed_at=time.time())
        return
    
    # Validate cases: 10 to 2000
    if not isinstance(cases, int) or cases < 10 or cases > 2000:
        update_status(job_dir, "error", reason="cases must be an integer between 10 and 2000", completed_at=time.time())
        return
    
    # Validate port
    if port not in ["correct", "faulty"]:
        update_status(job_dir, "error", reason="port must be 'correct' or 'faulty'", completed_at=time.time())
        return
    
    # Resolve sample paths
    try:
        cobol_path, java_path, schema_path, copybooks_path = resolve_sample_paths(sample, port, job_dir)
    except ValueError as e:
        update_status(job_dir, "error", reason=str(e), completed_at=time.time())
        return
    
    # Update status to running
    update_status(job_dir, "running", started_at=time.time())
    
    # Get timeout
    timeout_seconds = get_timeout()
    
    # Build command
    cmd = [
        sys.executable,
        "-m",
        "coroner",
        "verify",
        "--cobol", cobol_path,
        "--java", java_path,
        "--schema", schema_path,
        "--copybooks", copybooks_path,
        "--cases", str(cases),
        "--seed", str(seed),
    ]
    
    # Set environment
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(job_dir)
    
    try:
        # Start subprocess with process group
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=env,
        )
        
        # Update status with pgid (pgid == pid with start_new_session)
        update_status(job_dir, "running", started_at=time.time(), pgid=proc.pid)
        
        try:
            # Wait for completion with timeout
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Kill the process group
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            
            # Collect output
            proc.communicate()
            
            # Update status and return
            update_status(job_dir, "error", reason="timeout", completed_at=time.time())
            return
        
        # Parse run_id from stdout
        run_id = None
        for line in stdout.splitlines():
            if line.startswith("Run: runs/"):
                # Extract run id from "Run: runs/<id>"
                match = re.match(r"^Run: runs/([0-9a-f]{12})$", line)
                if match:
                    run_id = match.group(1)
                    break
        
        if run_id is None:
            # No run_id found in output
            update_status(job_dir, "error", reason="failed to parse run_id from output", completed_at=time.time())
            return
        
        # Read verdict from run directory
        verdict_file = job_dir / "runs" / run_id / "verdict.json"
        if not verdict_file.exists():
            update_status(job_dir, "error", reason="verdict.json not found", completed_at=time.time())
            return
        
        verdict_data = json.loads(verdict_file.read_text())
        verdict_status = verdict_data.get("status")
        
        # Write result
        result_data = {
            "exit_code": proc.returncode,
            "run_id": run_id,
            "verdict": verdict_status,
        }
        
        result_file = job_dir / "result.json"
        result_file.write_text(json.dumps(result_data, indent=2))
        
        # Update status to done
        update_status(job_dir, "done", completed_at=time.time(), run_id=run_id)
    
    except Exception as e:
        # Other error
        update_status(job_dir, "error", reason=str(e), completed_at=time.time())


def worker_loop():
    """Main worker loop: poll for jobs and execute them."""
    print("Engine worker started", file=sys.stderr)
    
    while True:
        try:
            # Find oldest queued job
            job_dir = find_oldest_queued_job()
            
            if job_dir is None:
                # No jobs, sleep and poll again
                time.sleep(1)
                continue
            
            print(f"Processing job: {job_dir.name}", file=sys.stderr)
            
            # Execute the job
            execute_job(job_dir)
            
            print(f"Completed job: {job_dir.name}", file=sys.stderr)
            
        except KeyboardInterrupt:
            print("Worker interrupted", file=sys.stderr)
            break
        except Exception as e:
            print(f"Worker error: {e}", file=sys.stderr)
            # Continue polling
            time.sleep(1)


def main():
    """Entry point for engine worker."""
    worker_loop()


if __name__ == "__main__":
    main()
