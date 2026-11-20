"""Tests for deployment check script (web-ui Task 19)."""
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest


def find_free_port():
    """Find a free port on localhost."""
    import socket
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    
    return port


def test_deploy_check_against_dead_port():
    """Test that deploy_check exits 1 with FAIL when nothing listens on the port."""
    # Find a port where nothing is listening
    port = find_free_port()
    
    # Run deploy_check with --skip-build against this dead port
    result = subprocess.run(
        [
            sys.executable,
            "scripts/deploy_check.py",
            "--skip-build",
            "--url",
            f"http://127.0.0.1:{port}"
        ],
        capture_output=True,
        text=True
    )
    
    # Should exit 1 (checks failed)
    assert result.returncode == 1
    
    # Should print at least one FAIL line
    assert "FAIL:" in result.stdout


@pytest.mark.slow
def test_deploy_check_end_to_end(tmp_path):
    """
    End-to-end test: start real API and worker, run deploy_check, expect exit 0.
    
    This test runs:
    - Real uvicorn server on a free local port
    - Real engine worker in a separate process
    - scripts/deploy_check.py --skip-build against the server
    """
    # Set up temporary base and exchange directories
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    exchange_dir = tmp_path / "exchange"
    exchange_dir.mkdir()
    
    # Find free port
    port = find_free_port()
    
    # Environment for both processes
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base_dir)
    env["CORONER_EXCHANGE_DIR"] = str(exchange_dir)
    env["CORONER_MAX_QUEUE_LENGTH"] = "3"
    env["CORONER_JOB_TIMEOUT"] = "120"
    
    # Start API server
    api_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "coroner.ui.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port)
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Start engine worker
    env_worker = env.copy()
    env_worker["CORONER_ENGINE_MODE"] = "worker"
    
    worker_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "coroner.ui.app"
        ],
        env=env_worker,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Wait for API to be ready (max 10 seconds)
        import httpx
        
        ready = False
        for _ in range(20):
            try:
                response = httpx.get(f"http://127.0.0.1:{port}/", timeout=1.0)
                if response.status_code == 200:
                    ready = True
                    break
            except Exception:
                pass
            
            time.sleep(0.5)
        
        if not ready:
            # Try to get output
            api_stdout = api_process.stdout.read() if api_process.stdout else ""
            api_stderr = api_process.stderr.read() if api_process.stderr else ""
            pytest.fail(f"API did not become ready. stdout: {api_stdout}, stderr: {api_stderr}")
        
        # Run deploy_check with --skip-build
        result = subprocess.run(
            [
                sys.executable,
                "scripts/deploy_check.py",
                "--skip-build",
                "--url",
                f"http://127.0.0.1:{port}"
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max (2 audits at 2000 cases each)
        )
        
        # Check result
        print("deploy_check stdout:")
        print(result.stdout)
        
        if result.returncode != 0:
            print("deploy_check stderr:")
            print(result.stderr)
        
        # Should exit 0 (all checks passed)
        assert result.returncode == 0
        
        # Should list every check as PASS
        output = result.stdout
        
        assert "PASS: GET / returns 200 with Run audit form" in output
        assert "PASS: T1 faulty: ZOMBIE verdict" in output
        assert "PASS: T1 correct: ALIVE verdict" in output
        assert "PASS: Tamper: INVALID with replay mismatch" in output
        assert "PASS: Verify: certificate VALID" in output
        assert "PASS: Cache-Control: /api/* responses include no-store" in output
        assert "PASS: Body limit: 17 KB body rejected with 413" in output
        
        # Should not contain any FAIL lines
        assert "FAIL:" not in output
        
        # Final message
        assert "Deployment check PASSED: all checks succeeded" in output
        
    finally:
        # Stop both processes
        api_process.terminate()
        worker_process.terminate()
        
        # Wait for clean shutdown (max 5 seconds)
        try:
            api_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()
        
        try:
            worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker_process.kill()
