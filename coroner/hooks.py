"""Kiro hooks for Coroner: delivery gate and stop hook."""
import json
import os
import sys
import subprocess
import hashlib
from pathlib import Path
from typing import Optional


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


def load_scope(scope_path: str = ".kiro/coroner-scope.json") -> dict:
    """Load the scope file."""
    with open(scope_path) as f:
        return json.load(f)


def find_certificate(scope: dict) -> Optional[str]:
    """
    Find the newest certificate whose recorded hashes match current files.
    Returns the certificate path or None.
    """
    runs_dir = Path("runs")
    if not runs_dir.exists():
        return None
    
    # Compute current hashes
    current_cobol_hash = compute_file_hash(scope["cobol"])
    current_java_hash = compute_file_hash(scope["java"])
    current_schema_hash = compute_file_hash(scope["schema"])
    current_copybook_hashes = compute_directory_hash(scope["copybooks"])
    
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
                cert_data.get("schema_file_sha256") == current_schema_hash):
                
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


def replay_certificate(cert_path: str) -> tuple[int, str, dict]:
    """
    Replay a certificate using 'python -m coroner verify cert_path'.
    Returns (exit_code, verdict_line, cert_data).
    """
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "verify", cert_path],
        capture_output=True,
        text=True
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


def get_staged_files() -> list[str]:
    """Get list of staged files using git diff --cached --name-only."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True
        )
        return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def is_audited_file_staged(scope: dict, staged: list[str]) -> bool:
    """Check if COBOL or Java from scope is staged."""
    cobol_path = scope["cobol"]
    java_path = scope["java"]
    
    # Normalize paths for comparison (handle both absolute and relative)
    cobol_abs = str(Path(cobol_path).resolve())
    java_abs = str(Path(java_path).resolve())
    
    for staged_file in staged:
        staged_abs = str(Path(staged_file).resolve())
        if staged_abs == cobol_abs or staged_abs == java_abs:
            return True
        # Also check if the relative path matches
        if staged_file == cobol_path or staged_file == java_path:
            return True
    
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
    
    # Load scope and find certificate
    try:
        scope = load_scope()
        cert_path = find_certificate(scope)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # If scope or certificate lookup fails, allow (fail open)
        sys.exit(0)
    
    if cert_path:
        # Certificate found: replay it
        exit_code, verdict_line, cert_data = replay_certificate(cert_path)
        
        if exit_code == 0:
            # ALIVE and valid: allow
            sys.exit(0)
        else:
            # ZOMBIE (exit 1) or invalid (exit 3): block
            message = build_block_message(cert_data)
            print(json.dumps({"decision": "block", "reason": message}))
            print(message, file=sys.stderr)
            sys.exit(2)
    else:
        # Certificate missing: check if audited files are staged
        staged = get_staged_files()
        if is_audited_file_staged(scope, staged):
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
    
    # Load scope and find certificate
    try:
        scope = load_scope()
        cert_path = find_certificate(scope)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # If scope or certificate lookup fails, allow
        sys.exit(0)
    
    # Check certificate status
    should_block = False
    block_message = ""
    
    if cert_path:
        exit_code, verdict_line, cert_data = replay_certificate(cert_path)
        if exit_code != 0:
            # ZOMBIE or invalid: should block
            should_block = True
            block_message = build_block_message(cert_data)
    else:
        # Certificate missing: check if audited files are staged
        staged = get_staged_files()
        if is_audited_file_staged(scope, staged):
            should_block = True
            block_message = "Certificate missing. Run run_differential_check first."
    
    if not should_block:
        # ALIVE and valid: allow
        sys.exit(0)
    
    # Should block: check count
    hooks_dir = Path("build/hooks")
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


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m coroner.hooks {gate|stop}", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
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
