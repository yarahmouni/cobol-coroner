"""Tests for Kiro hooks."""
import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
import pytest

from coroner.hooks import (
    parse_hook_input,
    is_git_commit_push_merge,
    build_block_message,
)


def test_parse_hook_input_v2_stop():
    """Test parsing v2 stop hook input."""
    stdin_text = '{"hook_event_name":"stop","cwd":"/tmp","session_id":"abc123"}'
    result = parse_hook_input(stdin_text)
    assert result["hook_event_name"] == "stop"
    assert result["session_id"] == "abc123"


def test_parse_hook_input_v3_stop():
    """Test parsing v3 stop hook input."""
    stdin_text = '{"session_id":"xyz789","hook_event_name":"Stop","cwd":"/tmp"}'
    result = parse_hook_input(stdin_text)
    assert result["hook_event_name"] == "Stop"
    assert result["session_id"] == "xyz789"


def test_parse_hook_input_v2_pretooluse():
    """Test parsing v2 preToolUse hook input."""
    stdin_text = '{"hook_event_name":"preToolUse","tool_name":"shell","tool_input":{"command":"git commit -m test"}}'
    result = parse_hook_input(stdin_text)
    assert result["hook_event_name"] == "preToolUse"
    assert result["tool_name"] == "shell"
    assert result["tool_input"]["command"] == "git commit -m test"


def test_parse_hook_input_v3_pretooluse():
    """Test parsing v3 preToolUse hook input."""
    stdin_text = '{"hook_event_name":"PreToolUse","tool_name":"execute_bash","tool_input":{"command":"git push origin main"}}'
    result = parse_hook_input(stdin_text)
    assert result["hook_event_name"] == "PreToolUse"
    assert result["tool_name"] == "execute_bash"
    assert result["tool_input"]["command"] == "git push origin main"


def test_is_git_commit_push_merge():
    """Test git command detection."""
    assert is_git_commit_push_merge("git commit -m test")
    assert is_git_commit_push_merge("git push origin main")
    assert is_git_commit_push_merge("git merge feature-branch")
    
    assert not is_git_commit_push_merge("ls")
    assert not is_git_commit_push_merge("git status")
    assert not is_git_commit_push_merge("git log")
    assert not is_git_commit_push_merge("echo git commit")
    assert not is_git_commit_push_merge("git diff")


def test_build_block_message_no_group_key():
    """Test block message without group key."""
    cert_data = {
        "status": "ZOMBIE",
        "verdict": "FAIL: business behavior diverged on 75 cases",
        "divergences": 75
    }
    
    message = build_block_message(cert_data)
    assert "ZOMBIE: FAIL: business behavior diverged on 75 cases" in message
    assert "Unreconciled branch exposure: not applicable (no group key in the schema)" in message
    assert "Run get_failure_report and export_junit_test" in message


def test_gate_ignores_non_git_commands(tmp_path):
    """Test that gate ignores non-git commands."""
    # Create a minimal scope file
    scope_file = tmp_path / "coroner-scope.json"
    scope_file.write_text(json.dumps({
        "cobol": "test.cob",
        "copybooks": "copybooks",
        "java": "Test.java",
        "schema": "schema.json"
    }))
    
    # Get absolute path to python
    python_path = Path(sys.executable).absolute()
    
    # Test various non-git commands
    commands = ["ls -la", "git status", "echo git commit", "python test.py"]
    
    for cmd in commands:
        hook_input = {
            "hook_event_name": "preToolUse",
            "tool_name": "shell",
            "tool_input": {"command": cmd}
        }
        
        result = subprocess.run(
            [str(python_path), "-m", "coroner.hooks", "gate"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            cwd=tmp_path
        )
        
        # Should exit 0 silently
        assert result.returncode == 0
        assert result.stdout == ""


_REPO_ROOT = Path(__file__).resolve().parent.parent
_T1_SAMPLE = "samples/traps/T1-ebcdic-match-merge"


def _gate_workspace(tmp_path, copy_runs, run, port):
    """A small repository of its own for the gate: the T1 sample, a scope file and one real run.

    The gate looks for the certificate in <repository root>/runs, where the root is the git top
    level of its working directory, and matches it by the SHA-256 of the files named in
    .kiro/coroner-scope.json. So the workspace holds a copy of the T1 sample (the certificate of
    the shared session run records these relative paths), the scope of `port` ("faulty" or
    "correct"), and a copy of the shared run under runs/. The repository runs/ folder is never read.
    """
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(_REPO_ROOT / _T1_SAMPLE, root / _T1_SAMPLE)
    scope = root / ".kiro" / "coroner-scope.json"
    scope.parent.mkdir()
    scope.write_text(json.dumps({
        "cobol": f"{_T1_SAMPLE}/MATCH-MERGE.cob",
        "copybooks": f"{_T1_SAMPLE}/copybooks",
        "java": f"{_T1_SAMPLE}/java/{port}/MatchMerge.java",
        "schema": f"{_T1_SAMPLE}/schema.json",
    }))
    copy_runs(run.base, root, run.run_id)
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    return root


def _run_gate(root, command):
    """Run `python -m coroner.hooks gate` in `root` with a preToolUse input for `command`."""
    env = {k: v for k, v in os.environ.items() if k not in ("CORONER_BASE_DIR", "CORONER_REPLAY_TIMEOUT")}
    hook_input = {
        "hook_event_name": "preToolUse",
        "tool_name": "shell",
        "tool_input": {"command": command},
    }
    return subprocess.run(
        [str(Path(sys.executable).absolute()), "-m", "coroner.hooks", "gate"],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=300,
    )


def test_gate_blocks_zombie_certificate(tmp_path, copy_runs, t1_faulty_30):
    """The gate blocks git commit when the certificate of the files in scope is ZOMBIE.

    The certificate is a real one (T1 faulty port, 30 cases, seed 42, made by the engine). The
    gate finds it by file hashes, replays it with `python -m coroner verify` (exit 1) and blocks.
    """
    root = _gate_workspace(tmp_path, copy_runs, t1_faulty_30, "faulty")
    cert = json.loads((root / "runs" / t1_faulty_30.run_id / "certificate.json").read_text())
    assert cert["status"] == "ZOMBIE"
    assert cert["cases_divergent"] > 0

    result = _run_gate(root, "git commit -m test")

    # Block: exit status 2, the decision as JSON on stdout, the same message on stderr
    assert result.returncode == 2, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    reason = output["reason"]
    assert reason.startswith("ZOMBIE:")
    assert "Unreconciled branch exposure:" in reason
    assert "Run get_failure_report and export_junit_test, fix the Java port, then run run_differential_check again." in reason
    assert reason in result.stderr

    # The same ZOMBIE certificate also blocks git push and git merge
    for command in ("git push origin main", "git merge feature"):
        other = _run_gate(root, command)
        assert other.returncode == 2, f"{command}: {other.stdout}\n{other.stderr}"
        assert json.loads(other.stdout)["decision"] == "block"


def test_gate_allows_alive_certificate(tmp_path, copy_runs, t1_correct_200):
    """The gate allows git commit when the certificate of the files in scope is ALIVE.

    The certificate is a real one (T1 correct port, 200 cases, seed 42, made by the engine). The
    gate finds it by file hashes, replays it (exit 0) and allows silently.
    """
    root = _gate_workspace(tmp_path, copy_runs, t1_correct_200, "correct")
    cert = json.loads((root / "runs" / t1_correct_200.run_id / "certificate.json").read_text())
    assert cert["status"] == "ALIVE"
    assert cert["cases_divergent"] == 0

    result = _run_gate(root, "git commit -m test")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert result.stdout == ""


def test_gate_does_not_match_a_certificate_of_other_files(tmp_path, copy_runs, t1_faulty_30):
    """A ZOMBIE certificate of the faulty port does not block a commit whose scope is the correct port.

    The gate matches certificates by the hashes of the files in scope. With the correct Java in
    scope and only the faulty port's certificate in runs/, no certificate matches: nothing audited
    is staged, so the commit is allowed. This shows the two tests above block and allow because of
    the certificate they found, not for another reason.
    """
    root = _gate_workspace(tmp_path, copy_runs, t1_faulty_30, "correct")

    result = _run_gate(root, "git commit -m test")

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert result.stdout == ""


def test_gate_blocks_missing_certificate_when_staged(tmp_path):
    """Test that gate blocks when certificate is missing but audited files are staged."""
    # Create a temporary git repository
    git_dir = tmp_path / "repo"
    git_dir.mkdir()
    
    # Initialize git
    subprocess.run(["git", "init"], cwd=git_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=git_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=git_dir, check=True, capture_output=True)
    
    # Create minimal files
    cobol_file = git_dir / "test.cob"
    cobol_file.write_text("IDENTIFICATION DIVISION.\nPROGRAM-ID. TEST.\n")
    
    java_file = git_dir / "Test.java"
    java_file.write_text("public class Test {}\n")
    
    # Create scope file
    scope_file = git_dir / ".kiro" / "coroner-scope.json"
    scope_file.parent.mkdir(parents=True, exist_ok=True)
    scope_file.write_text(json.dumps({
        "cobol": str(cobol_file),
        "copybooks": "copybooks",
        "java": str(java_file),
        "schema": "schema.json"
    }))
    
    # Stage the Java file
    subprocess.run(["git", "add", str(java_file)], cwd=git_dir, check=True, capture_output=True)
    
    # Get absolute path to python
    python_path = Path(sys.executable).absolute()
    
    # Test the gate (no certificate exists)
    hook_input = {
        "hook_event_name": "preToolUse",
        "tool_name": "shell",
        "tool_input": {"command": "git commit -m test"}
    }
    
    result = subprocess.run(
        [str(python_path), "-m", "coroner.hooks", "gate"],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        cwd=git_dir
    )
    
    # Should block with exit 2
    assert result.returncode == 2
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert "Certificate missing" in output["reason"]
    
    # Block message should also be on stderr (for v2 engine visibility)
    assert "Certificate missing" in result.stderr
    assert "Run run_differential_check first" in result.stderr


def test_stop_blocks_three_times(tmp_path):
    """Test that stop hook blocks 3 times then allows."""
    # Create a minimal scope file (certificate lookup will fail, but we can test the count logic)
    scope_file = tmp_path / ".kiro" / "coroner-scope.json"
    scope_file.parent.mkdir(parents=True, exist_ok=True)
    scope_file.write_text(json.dumps({
        "cobol": "test.cob",
        "copybooks": "copybooks",
        "java": "Test.java",
        "schema": "schema.json"
    }))
    
    # Create COBOL and Java files to trigger staging check
    (tmp_path / "test.cob").write_text("IDENTIFICATION DIVISION.\n")
    (tmp_path / "Test.java").write_text("public class Test {}\n")
    
    # Initialize git and stage the files
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "Test.java"], cwd=tmp_path, check=True, capture_output=True)
    
    # Get absolute path to python
    python_path = Path(sys.executable).absolute()
    
    session_id = "test-session-123"
    
    # Call stop 4 times
    for i in range(4):
        hook_input = {
            "hook_event_name": "stop",
            "session_id": session_id,
            "cwd": str(tmp_path)
        }
        
        result = subprocess.run(
            [str(python_path), "-m", "coroner.hooks", "stop"],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            cwd=tmp_path
        )
        
        # All should exit 0 (stop hook format)
        assert result.returncode == 0
        
        if i < 3:
            # First 3 times: should block
            output = json.loads(result.stdout)
            assert output["decision"] == "block"
        else:
            # 4th time: should allow silently
            assert result.stdout == ""
    
    # Check that failure file exists
    failure_file = tmp_path / "build" / "hooks" / f"{session_id}-failure.json"
    assert failure_file.exists()
    
    with open(failure_file) as f:
        failure_data = json.load(f)
    
    assert failure_data["session_id"] == session_id
    assert failure_data["attempts"] == 4
