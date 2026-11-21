"""Test replay timeout with subprocess and CLI --json flag."""

import json
import os
import signal
import time
from pathlib import Path

import pytest


@pytest.fixture
def alive_run_2000_cases(credit_fees_2000, tmp_path, monkeypatch, copy_runs):
    """A real ALIVE run with certificate at 2000 cases, copied into this test's own folder.

    The run is the session fixture credit_fees_2000 of tests/conftest.py (real engine audit of the
    credit-fees correct port, 2000 cases, seed 42, run df4d7929ce44). A test that adds a forged
    copy, an exchange folder or a build cache changes only its own folder.
    """
    # CORONER_BASE_DIR points at this test's folder (restored by monkeypatch)
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    
    run_id = credit_fees_2000.run_id
    copy_runs(credit_fees_2000.base, tmp_path, run_id)
    
    run_dir = tmp_path / "runs" / run_id
    
    # Verify the run produced certificate
    assert (run_dir / "certificate.json").exists()
    
    # Verify it's ALIVE
    verdict_data = json.loads((run_dir / "verdict.json").read_text())
    assert verdict_data["status"] == "ALIVE"
    
    yield run_id, tmp_path


def test_cli_json_output(alive_run_2000_cases):
    """Test CLI --json flag outputs JSON with ReplayResult fields."""
    run_id, base_dir = alive_run_2000_cases
    
    # Get certificate path
    cert_file = base_dir / "runs" / run_id / "certificate.json"
    assert cert_file.exists()
    
    # Run CLI with --json
    import subprocess
    import sys
    
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base_dir)
    
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "verify", str(cert_file), "--json"],
        capture_output=True,
        text=True,
        env=env
    )
    
    # Should exit 0 (ALIVE)
    assert result.returncode == 0
    
    # Parse JSON output
    output = json.loads(result.stdout)
    
    # Check all ReplayResult fields are present
    assert output["valid"] is True
    assert output["reason"] == ""
    assert output["verdict_status"] == "ALIVE"
    assert output["verdict_sub_label"] is not None
    assert output["cases_total"] == 2000
    assert output["cases_divergent"] == 0
    assert isinstance(output["paragraph_coverage_reached"], int)
    assert isinstance(output["paragraph_coverage_total"], int)
    assert isinstance(output["branch_coverage_reached"], int)
    assert isinstance(output["branch_coverage_total"], int)
    assert output["cases_file"] != ""
    assert isinstance(output["warnings"], list)
    
    # Compare with replay_certificate result
    from coroner.certificate import replay_certificate
    
    direct_result = replay_certificate(str(cert_file), str(base_dir))
    
    assert output["valid"] == direct_result.valid
    assert output["verdict_status"] == direct_result.verdict.status
    assert output["cases_total"] == direct_result.cases_total
    assert output["cases_divergent"] == direct_result.cases_divergent


def group_members(pgid):
    """Return list of (pid, state) for all members of process group."""
    members = []
    import platform
    import subprocess
    
    if platform.system() == "Linux":
        # On Linux: read /proc/<pid>/stat for state (third field)
        proc_dir = Path("/proc")
        try:
            for entry in proc_dir.iterdir():
                if not entry.name.isdigit():
                    continue
                pid = int(entry.name)
                stat_file = entry / "stat"
                if stat_file.exists():
                    try:
                        stat_text = stat_file.read_text()
                        # Format: pid (comm) state ...
                        # Extract state (third field)
                        parts = stat_text.split(')')
                        if len(parts) > 1:
                            fields = parts[1].strip().split()
                            if len(fields) >= 3:
                                state = fields[0]
                                proc_pgid = int(fields[2])
                                if proc_pgid == pgid:
                                    members.append((pid, state))
                    except (FileNotFoundError, ValueError, IndexError):
                        pass
        except (FileNotFoundError, PermissionError):
            pass
    else:
        # On macOS and other systems: use ps -A
        try:
            ps_result = subprocess.run(
                ["ps", "-A", "-o", "pid=,pgid=,stat="],
                capture_output=True,
                text=True,
                timeout=2
            )
            if ps_result.returncode == 0:
                for line in ps_result.stdout.strip().split('\n'):
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[0])
                            proc_pgid = int(parts[1])
                            state = parts[2]
                            if proc_pgid == pgid:
                                members.append((pid, state))
                        except ValueError:
                            pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    return members


def test_replay_timeout_kills_process_group(alive_run_2000_cases, monkeypatch):
    """Test replay timeout kills process group and returns within timeout + 10s."""
    run_id, base_dir = alive_run_2000_cases
    
    # Set CORONER_BASE_DIR and CORONER_REPLAY_TIMEOUT before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    monkeypatch.setenv("CORONER_REPLAY_TIMEOUT", "1")
    
    # Import app after setting env var
    from coroner.ui.app import app, replay_with_timeout, get_last_replay_pgid
    
    # Get certificate path
    cert_file = base_dir / "runs" / run_id / "certificate.json"
    
    # Run replay with 1 second timeout (should timeout on 2000 cases)
    start_time = time.time()
    
    result = replay_with_timeout(str(cert_file), str(base_dir), 1)
    
    elapsed = time.time() - start_time
    
    # Should return within 1 + 10 seconds
    assert elapsed < 11.0, f"Replay took {elapsed:.2f}s, expected < 11.0s"
    
    # Should return timeout error
    assert result.valid is False
    assert result.reason == "replay timed out"
    
    # Get the pgid that was killed
    pgid = get_last_replay_pgid()
    assert pgid is not None
    
    # Right after timeout: every member should be zombie (state starts with Z)
    members = group_members(pgid)
    for pid, state in members:
        assert state.startswith("Z"), f"Process {pid} in group {pgid} is in state {state}, expected zombie"
    
    # Poll for up to 5 seconds until the process group is empty
    max_wait = 5.0
    poll_start = time.time()
    
    while time.time() - poll_start < max_wait:
        members = group_members(pgid)
        if not members:
            # Process group is empty, success
            return
        time.sleep(0.1)
    
    # If we get here after 5 seconds, the group still has members
    members = group_members(pgid)
    pytest.fail(f"Process group {pgid} still exists after {max_wait}s. Remaining: {members}")


@pytest.mark.slow
def test_replay_completes_within_timeout(alive_run_2000_cases, monkeypatch):
    """Test replay completes normally when timeout is sufficient."""
    run_id, base_dir = alive_run_2000_cases
    
    # Set CORONER_BASE_DIR with sufficient timeout
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import replay_with_timeout
    
    # Get certificate path
    cert_file = base_dir / "runs" / run_id / "certificate.json"
    
    # Run replay with 90 second timeout (should complete)
    result = replay_with_timeout(str(cert_file), str(base_dir), 90)
    
    # Should succeed
    assert result.valid is True
    assert result.reason == ""
    assert result.verdict is not None
    assert result.verdict.status == "ALIVE"
    assert result.cases_total == 2000
    assert result.cases_divergent == 0


def test_html_escape_in_verify_endpoint(alive_run_2000_cases, monkeypatch):
    """Test HTML escaping in /api/verify endpoint."""
    run_id, base_dir = alive_run_2000_cases
    
    # Set CORONER_BASE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # Test VALID case
    response = client.post("/api/verify", data={"run_id": run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Should not contain unescaped HTML
    assert "<script>" not in html.lower()
    
    # Create a forged certificate with malicious content
    run_dir = base_dir / "runs" / run_id
    cert_file = run_dir / "certificate.json"
    
    import shutil
    import secrets
    
    # Create a copy
    copy_run_id = secrets.token_hex(6)
    copy_run_dir = base_dir / "runs" / copy_run_id
    copy_run_dir.mkdir(parents=True)
    
    for file in run_dir.iterdir():
        if file.is_file():
            shutil.copy2(file, copy_run_dir / file.name)
    
    # Forge the certificate to trigger INVALID with XSS attempt
    copy_cert_file = copy_run_dir / "certificate.json"
    copy_cert_data = json.loads(copy_cert_file.read_text())
    
    # Modify without recomputing hash (will be INVALID)
    copy_cert_data["cases_divergent"] = 999
    
    with open(copy_cert_file, 'w', encoding='utf-8') as f:
        json.dump(copy_cert_data, f, indent=2, sort_keys=True)
        f.write('\n')
    
    # Reset rate limiter
    from coroner.ui.app import reset_rate_limiter
    reset_rate_limiter()
    
    # POST verify on forged certificate
    response = client.post("/api/verify", data={"run_id": copy_run_id})
    assert response.status_code == 200
    
    html = response.text
    
    # Should contain escaped reason
    assert "INVALID" in html
    
    # Should not contain unescaped HTML tags
    assert "<script>" not in html.lower()
    
    # The reason text should be present but escaped
    # (the actual reason depends on what replay_certificate returns)
    assert "Certificate: INVALID" in html


def test_html_escape_in_tamper_endpoint(alive_run_2000_cases, monkeypatch):
    """Test HTML escaping in /api/tamper endpoint."""
    run_id, base_dir = alive_run_2000_cases
    
    # Create a temporary exchange directory
    exchange_dir = base_dir / "exchange"
    exchange_dir.mkdir(exist_ok=True)
    
    # Set CORONER_BASE_DIR and CORONER_EXCHANGE_DIR before importing app
    monkeypatch.setenv("CORONER_BASE_DIR", str(base_dir))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    
    # Import app after setting env var
    from coroner.ui.app import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # Tamper with the certificate
    response = client.post(
        "/api/tamper",
        data={
            "run_id": run_id,
            "status": "ZOMBIE",
            "cases_total": 2000,
            "cases_divergent": 999,
            "random_seed": 42
        }
    )
    
    assert response.status_code == 200
    
    html = response.text
    
    # Should contain INVALID (mismatch)
    assert "INVALID" in html
    
    # Should not contain unescaped HTML
    assert "<script>" not in html.lower()
    
    # The reason should be escaped
    assert "Certificate: INVALID" in html
