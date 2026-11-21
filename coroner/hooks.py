"""Kiro hooks for Coroner: delivery gate, stop hook, and pre-commit."""
import json
import os
import sys
import subprocess
import hashlib
import tempfile
import shutil
from pathlib import Path
from typing import Optional

from coroner.store import copybook_file_hashes, generator_script_info


def compute_file_hash(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def compute_directory_hash(directory: str) -> dict[str, str]:
    """
    Compute hashes for all files in a directory.
    Returns dict mapping filename to hash.
    
    NOTE: This function is kept for backward compatibility but not used
    by the certificate system. Use copybook_file_hashes from coroner.store
    for copybook directory hashing (*.cpy and *.cbl files only).
    """
    hashes = {}
    if not os.path.isdir(directory):
        return hashes
    
    for entry in sorted(os.listdir(directory)):
        path = os.path.join(directory, entry)
        if os.path.isfile(path):
            hashes[entry] = compute_file_hash(path)
    
    return hashes


def parse_hook_input(stdin_text: str) -> dict:
    """Parse hook input JSON from stdin (v2 or v3 format)."""
    return json.loads(stdin_text)


def get_repo_root() -> Path:
    """Get the git repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to current directory
        return Path.cwd()


def load_scope(repo_root: Path, scope_path: str = ".kiro/coroner-scope.json") -> dict:
    """Load the scope file from the repository root."""
    scope_file = repo_root / scope_path
    with open(scope_file) as f:
        return json.load(f)


def find_certificate(repo_root: Path, scope: dict) -> Optional[str]:
    """
    Find the newest certificate whose recorded hashes match current files.
    Returns the certificate path or None.
    """
    runs_dir = repo_root / "runs"
    if not runs_dir.exists():
        return None
    
    # Compute current hashes (resolve paths relative to repo_root)
    current_cobol_hash = compute_file_hash(str(repo_root / scope["cobol"]))
    current_java_hash = compute_file_hash(str(repo_root / scope["java"]))
    current_schema_hash = compute_file_hash(str(repo_root / scope["schema"]))
    current_copybook_hashes = copybook_file_hashes(str(repo_root / scope["copybooks"]))
    try:
        script_info = generator_script_info(str(repo_root / scope["schema"]))
    except ValueError:  # includes GeneratorScriptError
        return None
    current_script_hash = script_info[1] if script_info else None
    
    matching_certs = []
    
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        
        cert_path = run_dir / "certificate.json"
        if not cert_path.exists():
            continue
        
        try:
            with open(cert_path) as f:
                cert_data = json.load(f)
            
            # Check if hashes match (use actual certificate field names)
            if (cert_data.get("cobol_file_sha256") == current_cobol_hash and
                cert_data.get("java_file_sha256") == current_java_hash and
                cert_data.get("schema_file_sha256") == current_schema_hash and
                cert_data.get("generator_script_sha256") == current_script_hash):
                
                # Check copybook hashes
                cert_copybooks = cert_data.get("copybook_hashes", {})
                if cert_copybooks == current_copybook_hashes:
                    matching_certs.append((cert_path, cert_path.stat().st_mtime))
        
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    
    if not matching_certs:
        return None
    
    # Return the newest
    matching_certs.sort(key=lambda x: x[1], reverse=True)
    return str(matching_certs[0][0])


def replay_certificate(repo_root: Path, cert_path: str, python_executable: Optional[str] = None) -> tuple[int, str, dict]:
    """
    Replay a certificate using 'python -m coroner verify cert_path'.
    Returns (exit_code, verdict_line, cert_data).
    Uses python_executable if provided, otherwise sys.executable.
    """
    if python_executable is None:
        python_executable = sys.executable
    
    result = subprocess.run(
        [python_executable, "-m", "coroner", "verify", cert_path],
        capture_output=True,
        text=True,
        cwd=str(repo_root)
    )
    
    # Extract the verdict line (first line of stdout)
    verdict_line = result.stdout.strip().split('\n')[0] if result.stdout.strip() else ""
    
    # Load certificate data
    with open(cert_path) as f:
        cert_data = json.load(f)
    
    return result.returncode, verdict_line, cert_data


def is_git_commit_push_merge(command: str) -> bool:
    """
    Check if command is a git commit, push or merge.
    Parses command words (not substring search).
    """
    # Simple word splitting (handles most cases)
    words = command.split()
    if len(words) < 2:
        return False
    
    return words[0] == "git" and words[1] in ["commit", "push", "merge"]


def get_staged_files(repo_root: Path) -> list[str]:
    """Get list of staged files using git diff --cached --name-only."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(repo_root)
        )
        return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def is_audited_file_staged(repo_root: Path, scope: dict, staged: list[str]) -> bool:
    """Check if COBOL or Java from scope is staged."""
    cobol_path = scope["cobol"]
    java_path = scope["java"]
    
    for staged_file in staged:
        # Direct relative path comparison
        if staged_file == cobol_path or staged_file == java_path:
            return True
        
        # Also try resolving absolute paths for comparison
        try:
            staged_abs = (repo_root / staged_file).resolve()
            cobol_abs = (repo_root / cobol_path).resolve()
            java_abs = (repo_root / java_path).resolve()
            if staged_abs == cobol_abs or staged_abs == java_abs:
                return True
        except (ValueError, OSError):
            pass
    
    return False


def build_block_message(cert_data: dict) -> str:
    """Build the block message from certificate data."""
    verdict = cert_data.get("verdict", "")
    status = cert_data.get("status", "")
    divergences = cert_data.get("divergences", 0)
    
    # Build verdict line
    if status == "ALIVE":
        verdict_line = f"ALIVE: {verdict}"
    else:
        verdict_line = f"ZOMBIE: {verdict}"
    
    # Check for group key in schema
    exposure_line = "Unreconciled branch exposure: not applicable (no group key in the schema)"
    
    # Try to read schema to check for group key
    try:
        schema_path = cert_data.get("schema_file", "")
        if schema_path and os.path.exists(schema_path):
            with open(schema_path) as f:
                schema = json.load(f)
            
            if "group_key" in schema:
                # Check if exposure metric exists in certificate
                exposure = cert_data.get("unreconciled_branch_exposure", {})
                if exposure:
                    sum_val = exposure.get("sum", 0)
                    max_val = exposure.get("max", 0)
                    count = exposure.get("affected_branches", 0)
                    grand_total_match = exposure.get("grand_total_match", False)
                    exposure_line = f"Unreconciled branch exposure: sum {sum_val}, max {max_val}, {count} branches affected, grand total {'matches' if grand_total_match else 'differs'}"
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    
    fix_instruction = "Run get_failure_report and export_junit_test, fix the Java port, then run run_differential_check again."
    
    return f"{verdict_line}\n{exposure_line}\n{fix_instruction}"


def gate_command(hook_input: dict) -> None:
    """
    Delivery gate hook (preToolUse).
    Blocks git commit/push/merge when certificate is ZOMBIE, missing or invalid.
    """
    # Extract command from tool_input
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")
    
    # If not a git commit/push/merge, allow silently
    if not is_git_commit_push_merge(command):
        sys.exit(0)
    
    # Get repository root
    repo_root = get_repo_root()
    
    # Load scope and find certificate
    try:
        scope = load_scope(repo_root)
        cert_path = find_certificate(repo_root, scope)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # If scope or certificate lookup fails, allow (fail open)
        sys.exit(0)
    
    if cert_path:
        # Certificate found: replay it
        exit_code, verdict_line, cert_data = replay_certificate(repo_root, cert_path)
        
        if exit_code == 0:
            # ALIVE and valid: allow
            sys.exit(0)
        elif exit_code == 2:
            # Reference did not run: block with error message
            message = f"ERROR: reference did not run\nCheck the COBOL program for file errors, libcob errors, or timeouts.\nRun run_differential_check again after fixing the reference."
            print(json.dumps({"decision": "block", "reason": message}))
            print(message, file=sys.stderr)
            sys.exit(2)
        else:
            # ZOMBIE (exit 1) or invalid (exit 3): block
            message = build_block_message(cert_data)
            print(json.dumps({"decision": "block", "reason": message}))
            print(message, file=sys.stderr)
            sys.exit(2)
    else:
        # Certificate missing: check if audited files are staged
        staged = get_staged_files(repo_root)
        if is_audited_file_staged(repo_root, scope, staged):
            # Audited files staged: block
            message = "Certificate missing. Run run_differential_check first."
            print(json.dumps({"decision": "block", "reason": message}))
            print(message, file=sys.stderr)
            sys.exit(2)
        else:
            # Audited files not staged: allow (unrelated commit)
            sys.exit(0)


def stop_command(hook_input: dict) -> None:
    """
    Stop hook.
    Blocks up to 3 times per session_id, then writes failure file and allows.
    """
    session_id = hook_input.get("session_id", "unknown")
    
    # Get repository root
    repo_root = get_repo_root()
    
    # Load scope and find certificate
    try:
        scope = load_scope(repo_root)
        cert_path = find_certificate(repo_root, scope)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # If scope or certificate lookup fails, allow
        sys.exit(0)
    
    # Check certificate status
    should_block = False
    block_message = ""
    is_reference_error = False
    
    if cert_path:
        exit_code, verdict_line, cert_data = replay_certificate(repo_root, cert_path)
        if exit_code == 2:
            # Reference did not run: error, not ZOMBIE
            should_block = True
            is_reference_error = True
            block_message = "ERROR: reference did not run. Check the COBOL program for file errors, libcob errors, or timeouts."
        elif exit_code != 0:
            # ZOMBIE or invalid: should block
            should_block = True
            block_message = build_block_message(cert_data)
    else:
        # Certificate missing: check if audited files are staged
        staged = get_staged_files(repo_root)
        if is_audited_file_staged(repo_root, scope, staged):
            should_block = True
            block_message = "Certificate missing. Run run_differential_check first."
    
    if not should_block:
        # ALIVE and valid: allow
        sys.exit(0)
    
    # Should block: check count
    hooks_dir = repo_root / "build/hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    
    count_file = hooks_dir / f"{session_id}.count"
    
    # Read current count
    if count_file.exists():
        with open(count_file) as f:
            count = int(f.read().strip())
    else:
        count = 0
    
    # Increment count
    count += 1
    
    if count <= 3:
        # Block (count 1, 2, 3)
        with open(count_file, 'w') as f:
            f.write(str(count))
        
        print(json.dumps({"decision": "block", "reason": block_message}))
        sys.exit(0)
    else:
        # Count > 3: write failure file and allow
        failure_file = hooks_dir / f"{session_id}-failure.json"
        failure_data = {
            "session_id": session_id,
            "attempts": count,
            "reasons": [block_message]
        }
        with open(failure_file, 'w') as f:
            json.dump(failure_data, f, indent=2)
        
        sys.exit(0)


def precommit_command() -> None:
    """
    Pre-commit hook: audit staged content with 500 cases.
    Exports staged files, runs verify, blocks ZOMBIE.
    """
    # Get repository root
    repo_root = get_repo_root()
    
    # Allow Python executable override via environment variable (for tests)
    python_executable = os.environ.get("CORONER_PYTHON_EXECUTABLE", sys.executable)
    
    # Load scope
    try:
        scope = load_scope(repo_root)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error loading scope: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Get staged files
    staged = get_staged_files(repo_root)
    
    # Check if any scope files are staged
    scope_files = [
        scope["cobol"],
        scope["java"],
        scope["schema"]
    ]
    
    # Also check copybook directory
    copybooks_dir = scope["copybooks"]
    
    staged_scope_files = []
    for staged_file in staged:
        # Normalize paths for comparison (resolve from repo_root)
        staged_abs = str((repo_root / staged_file).resolve())
        for scope_file in scope_files:
            scope_abs = str((repo_root / scope_file).resolve())
            if staged_abs == scope_abs or staged_file == scope_file:
                staged_scope_files.append(scope_file)
                break
        
        # Check if staged file is in copybooks directory
        try:
            staged_path = repo_root / staged_file
            copybooks_path = repo_root / copybooks_dir
            if copybooks_path in staged_path.parents or staged_path.parent == copybooks_path:
                if copybooks_dir not in staged_scope_files:
                    staged_scope_files.append(copybooks_dir)
        except (ValueError, OSError):
            pass
    
    if not staged_scope_files:
        print("Coroner pre-commit: no audited file staged")
        sys.exit(0)
    
    # Create temporary directory for exported files (in repo_root)
    temp_dir = repo_root / "build/precommit"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    export_base = temp_dir / "staged"
    if export_base.exists():
        shutil.rmtree(export_base)
    export_base.mkdir()
    
    try:
        # Export staged versions of all scope files
        cobol_export = export_base / Path(scope["cobol"]).name
        java_export = export_base / Path(scope["java"]).name
        schema_export = export_base / Path(scope["schema"]).name
        copybooks_export = export_base / "copybooks"
        copybooks_export.mkdir()
        
        # Export COBOL (use staged or index version)
        export_staged_file(repo_root, scope["cobol"], cobol_export)
        
        # Export Java (use staged or index version)
        export_staged_file(repo_root, scope["java"], java_export)
        
        # Export schema (use staged or index version)
        export_staged_file(repo_root, scope["schema"], schema_export)
        
        # Export copybooks directory (file by file)
        copybooks_path = repo_root / scope["copybooks"]
        if copybooks_path.exists() and copybooks_path.is_dir():
            for entry in copybooks_path.iterdir():
                if entry.is_file():
                    relative = entry.relative_to(copybooks_path)
                    dest = copybooks_export / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    copybooks_relative = str(Path(scope["copybooks"]) / relative)
                    export_staged_file(repo_root, copybooks_relative, dest)
        
        # Run verify on exported files
        result = subprocess.run(
            [
                python_executable, "-m", "coroner", "verify",
                "--cobol", str(cobol_export),
                "--copybooks", str(copybooks_export),
                "--java", str(java_export),
                "--schema", str(schema_export),
                "--cases", "500",
                "--seed", "42"
            ],
            capture_output=True,
            text=True,
            cwd=str(repo_root)
        )
        
        # Parse output
        lines = result.stdout.strip().split('\n')
        verdict_line = lines[0] if lines else ""
        duration_line = ""
        
        for line in lines:
            if line.startswith("Duration:"):
                duration_line = line
                break
        
        # Clean up
        shutil.rmtree(export_base)
        
        if result.returncode == 0:
            # ALIVE
            if duration_line:
                print(f"Coroner pre-commit: {verdict_line} ({duration_line})")
            else:
                print(f"Coroner pre-commit: {verdict_line}")
            sys.exit(0)
        elif result.returncode == 1:
            # ZOMBIE
            # Extract run_id from output
            run_id = None
            for line in lines:
                if "runs/" in line:
                    import re
                    match = re.search(r'runs/([a-f0-9]+)', line)
                    if match:
                        run_id = match.group(1)
                        break
            
            if run_id:
                print(f"Commit blocked by Coroner: {verdict_line}. See runs/{run_id}/failure_report.json. Fix the Java port, then run run_differential_check again.", file=sys.stderr)
            else:
                print(f"Commit blocked by Coroner: {verdict_line}. Fix the Java port, then run run_differential_check again.", file=sys.stderr)
            sys.exit(1)
        elif result.returncode == 2:
            # Reference did not run
            print("Commit blocked by Coroner: ERROR: reference did not run.", file=sys.stderr)
            print("Check the COBOL program for file errors, libcob errors, or timeouts.", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(1)
        else:
            # Other error
            print(f"Coroner pre-commit: check error (exit {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(1)
    
    except Exception as e:
        # Clean up on error
        if export_base.exists():
            shutil.rmtree(export_base)
        print(f"Coroner pre-commit: error: {e}", file=sys.stderr)
        sys.exit(1)


def export_staged_file(repo_root: Path, source_path: str, dest_path: Path) -> None:
    """
    Export staged version of a file using git show :<path>.
    If file is not staged, uses index version (also git show :<path>).
    """
    # Try to read from git index
    result = subprocess.run(
        ["git", "show", f":{source_path}"],
        capture_output=True,
        check=False,
        cwd=str(repo_root)
    )
    
    if result.returncode == 0:
        # File is in index (staged or committed)
        dest_path.write_bytes(result.stdout)
    else:
        # File not in index, try working tree
        # This should not happen for scope files, but handle it
        source_abs = repo_root / source_path
        if source_abs.exists():
            dest_path.write_bytes(source_abs.read_bytes())
        else:
            raise FileNotFoundError(f"Cannot export {source_path}: not in index or working tree")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m coroner.hooks {gate|stop|precommit}", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "precommit":
        precommit_command()
    elif command in ["gate", "stop"]:
        # Read hook input from stdin
        stdin_text = sys.stdin.read()
        hook_input = parse_hook_input(stdin_text)
        
        if command == "gate":
            gate_command(hook_input)
        elif command == "stop":
            stop_command(hook_input)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
