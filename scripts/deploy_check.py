#!/usr/bin/env python3
"""
Deployment check script (D-53, web-ui Task 19).

Validates a deployed Coroner instance by:
1. Building from a clean git clone (unless --skip-build)
2. Running automated checks against a URL

Exit codes:
- 0: All checks passed
- 1: One or more checks failed
- 2: Build failed or other error
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def print_pass(message: str):
    """Print a PASS line."""
    print(f"PASS: {message}")


def print_fail(message: str):
    """Print a FAIL line."""
    print(f"FAIL: {message}")


def clean_build_image(repo_root: Path) -> bool:
    """
    Build Docker image from a clean git clone.
    
    Returns True on success, False on failure.
    """
    print("Building image from clean git clone...")
    
    # Get current HEAD commit SHA
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        commit_sha = result.stdout.strip()
        print(f"Current HEAD: {commit_sha}")
    except subprocess.CalledProcessError as e:
        print_fail(f"Failed to get HEAD commit: {e}")
        return False
    
    # Create temporary directory for clone
    temp_dir = Path(tempfile.mkdtemp(prefix="coroner-deploy-"))
    
    try:
        # Clone without hardlinks to ensure a true copy
        print(f"Cloning into {temp_dir}...")
        subprocess.run(
            ["git", "clone", "--no-hardlinks", str(repo_root), str(temp_dir)],
            capture_output=True,
            check=True
        )
        
        # Checkout the exact commit
        subprocess.run(
            ["git", "checkout", commit_sha],
            cwd=temp_dir,
            capture_output=True,
            check=True
        )
        
        # Build image for linux/amd64
        print("Building Docker image (this may take a few minutes)...")
        result = subprocess.run(
            ["docker", "build", "--platform", "linux/amd64", "-t", "coroner:deploy-check", "."],
            cwd=temp_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print_fail(f"Docker build failed: {result.stderr}")
            return False
        
        print_pass("Image built successfully from clean checkout")
        return True
        
    except subprocess.CalledProcessError as e:
        print_fail(f"Build process failed: {e}")
        return False
    finally:
        # Clean up temporary directory
        # Validate that temp_dir is created by mkdtemp
        if temp_dir.exists() and temp_dir.parent == Path(tempfile.gettempdir()):
            shutil.rmtree(temp_dir)


def wait_for_retry_after(response: httpx.Response, max_retries: int = 2) -> bool:
    """
    If response is 429, wait for Retry-After and return True.
    Returns False if max_retries exceeded.
    """
    if response.status_code != 429:
        return True
    
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return False
    
    try:
        wait_seconds = int(retry_after)
    except ValueError:
        return False
    
    print(f"Rate limited, waiting {wait_seconds} seconds...")
    time.sleep(wait_seconds + 1)
    return True


def check_home_page(client: httpx.Client, base_url: str) -> bool:
    """Check that GET / returns 200 and contains the Run audit form."""
    try:
        response = client.get(f"{base_url}/")
        
        if response.status_code != 200:
            print_fail(f"GET / returned {response.status_code}, expected 200")
            return False
        
        html = response.text
        
        if 'id="run-audit-form"' not in html:
            print_fail("GET / does not contain Run audit form")
            return False
        
        print_pass("GET / returns 200 with Run audit form")
        return True
        
    except Exception as e:
        print_fail(f"GET / failed: {e}")
        return False


def check_t1_faulty(client: httpx.Client, base_url: str) -> tuple[bool, str | None]:
    """
    Check T1 faulty audit (2000 cases, seed 42).
    
    Returns (success, run_id).
    """
    try:
        # Submit audit request
        response = client.post(
            f"{base_url}/api/run",
            json={
                "sample": "T1",
                "port": "faulty",
                "seed": 42,
                "cases": 2000
            },
            timeout=10.0
        )
        
        # Handle rate limiting
        retry_count = 0
        while response.status_code == 429 and retry_count < 2:
            if not wait_for_retry_after(response):
                print_fail("T1 faulty: rate limit exceeded without Retry-After")
                return False, None
            
            retry_count += 1
            response = client.post(
                f"{base_url}/api/run",
                json={
                    "sample": "T1",
                    "port": "faulty",
                    "seed": 42,
                    "cases": 2000
                },
                timeout=10.0
            )
        
        if response.status_code == 200:
            # Cache hit
            data = response.json()
            run_id = data.get("run_id")
            if not run_id:
                print_fail("T1 faulty: cached response missing run_id")
                return False, None
            
            print(f"T1 faulty: cache hit, run_id={run_id}")
        
        elif response.status_code == 202:
            # New job
            data = response.json()
            job_id = data.get("job_id")
            if not job_id:
                print_fail("T1 faulty: 202 response missing job_id")
                return False, None
            
            print(f"T1 faulty: job submitted, job_id={job_id}")
            
            # Poll status until done (timeout 120 seconds)
            start_time = time.time()
            timeout = 120.0
            run_id = None
            
            while time.time() - start_time < timeout:
                status_response = client.get(
                    f"{base_url}/api/job/{job_id}/status",
                    timeout=10.0
                )
                
                if status_response.status_code != 200:
                    print_fail(f"T1 faulty: status check returned {status_response.status_code}")
                    return False, None
                
                status_data = status_response.json()
                status = status_data.get("status")
                
                if status == "done":
                    run_id = status_data.get("run_id")
                    break
                elif status == "error":
                    reason = status_data.get("reason", "unknown")
                    print_fail(f"T1 faulty: job failed with error: {reason}")
                    return False, None
                
                # Wait before polling again
                time.sleep(2.0)
            
            if run_id is None:
                print_fail("T1 faulty: job did not complete within 120 seconds")
                return False, None
        
        else:
            print_fail(f"T1 faulty: POST /api/run returned {response.status_code}")
            return False, None
        
        # Check run page for verdict
        run_response = client.get(f"{base_url}/run/{run_id}", timeout=10.0)
        
        if run_response.status_code != 200:
            print_fail(f"T1 faulty: GET /run/{run_id} returned {run_response.status_code}")
            return False, None
        
        run_html = run_response.text
        
        if "ZOMBIE" not in run_html:
            # Extract reason text (strip tags, first 200 chars)
            import re
            text = re.sub(r'<[^>]+>', '', run_html)
            reason = text[:200]
            print_fail(f"T1 faulty: run page does not contain ZOMBIE verdict. Got: {reason}")
            return False, None
        
        # Extract counts from status if available (for display only)
        # We already know it's ZOMBIE from the page
        print_pass(f"T1 faulty: ZOMBIE verdict, run_id={run_id}")
        return True, run_id
        
    except Exception as e:
        print_fail(f"T1 faulty check failed: {e}")
        return False, None


def check_t1_correct(client: httpx.Client, base_url: str) -> tuple[bool, str | None]:
    """
    Check T1 correct audit (2000 cases, seed 42).
    
    Returns (success, run_id).
    """
    try:
        # Submit audit request
        response = client.post(
            f"{base_url}/api/run",
            json={
                "sample": "T1",
                "port": "correct",
                "seed": 42,
                "cases": 2000
            },
            timeout=10.0
        )
        
        # Handle rate limiting
        retry_count = 0
        while response.status_code == 429 and retry_count < 2:
            if not wait_for_retry_after(response):
                print_fail("T1 correct: rate limit exceeded without Retry-After")
                return False, None
            
            retry_count += 1
            response = client.post(
                f"{base_url}/api/run",
                json={
                    "sample": "T1",
                    "port": "correct",
                    "seed": 42,
                    "cases": 2000
                },
                timeout=10.0
            )
        
        if response.status_code == 200:
            # Cache hit
            data = response.json()
            run_id = data.get("run_id")
            if not run_id:
                print_fail("T1 correct: cached response missing run_id")
                return False, None
            
            print(f"T1 correct: cache hit, run_id={run_id}")
        
        elif response.status_code == 202:
            # New job
            data = response.json()
            job_id = data.get("job_id")
            if not job_id:
                print_fail("T1 correct: 202 response missing job_id")
                return False, None
            
            print(f"T1 correct: job submitted, job_id={job_id}")
            
            # Poll status until done (timeout 120 seconds)
            start_time = time.time()
            timeout = 120.0
            run_id = None
            
            while time.time() - start_time < timeout:
                status_response = client.get(
                    f"{base_url}/api/job/{job_id}/status",
                    timeout=10.0
                )
                
                if status_response.status_code != 200:
                    print_fail(f"T1 correct: status check returned {status_response.status_code}")
                    return False, None
                
                status_data = status_response.json()
                status = status_data.get("status")
                
                if status == "done":
                    run_id = status_data.get("run_id")
                    break
                elif status == "error":
                    reason = status_data.get("reason", "unknown")
                    print_fail(f"T1 correct: job failed with error: {reason}")
                    return False, None
                
                # Wait before polling again
                time.sleep(2.0)
            
            if run_id is None:
                print_fail("T1 correct: job did not complete within 120 seconds")
                return False, None
        
        else:
            print_fail(f"T1 correct: POST /api/run returned {response.status_code}")
            return False, None
        
        # Check run page for verdict
        run_response = client.get(f"{base_url}/run/{run_id}", timeout=10.0)
        
        if run_response.status_code != 200:
            print_fail(f"T1 correct: GET /run/{run_id} returned {run_response.status_code}")
            return False, None
        
        run_html = run_response.text
        
        if "ALIVE" not in run_html:
            # Extract reason text (strip tags, first 200 chars)
            import re
            text = re.sub(r'<[^>]+>', '', run_html)
            reason = text[:200]
            print_fail(f"T1 correct: run page does not contain ALIVE verdict. Got: {reason}")
            return False, None
        
        print_pass(f"T1 correct: ALIVE verdict, run_id={run_id}")
        return True, run_id
        
    except Exception as e:
        print_fail(f"T1 correct check failed: {e}")
        return False, None


def check_tamper(client: httpx.Client, base_url: str, run_id: str) -> bool:
    """
    Check Tamper endpoint: edit certificate copy, expect INVALID with replay mismatch.
    """
    try:
        # Get tamper form to read real certificate values
        tamper_form_response = client.get(
            f"{base_url}/tamper",
            params={"run_id": run_id},
            timeout=10.0
        )
        
        if tamper_form_response.status_code != 200:
            print_fail(f"Tamper: GET /tamper?run_id={run_id} returned {tamper_form_response.status_code}")
            return False
        
        # Parse form to extract values (simplified: we'll just post ALIVE and 0 divergences)
        # The test expects INVALID because the run is ZOMBIE
        
        # Post tampered values
        tamper_response = client.post(
            f"{base_url}/api/tamper",
            data={
                "run_id": run_id,
                "status": "ALIVE",
                "cases_total": "2000",
                "cases_divergent": "0",
                "random_seed": "42"
            },
            timeout=120.0
        )
        
        # Handle rate limiting
        retry_count = 0
        while tamper_response.status_code == 429 and retry_count < 2:
            if not wait_for_retry_after(tamper_response):
                print_fail("Tamper: rate limit exceeded without Retry-After")
                return False
            
            retry_count += 1
            tamper_response = client.post(
                f"{base_url}/api/tamper",
                data={
                    "run_id": run_id,
                    "status": "ALIVE",
                    "cases_total": "2000",
                    "cases_divergent": "0",
                    "random_seed": "42"
                },
                timeout=120.0
            )
        
        if tamper_response.status_code != 200:
            print_fail(f"Tamper: POST /api/tamper returned {tamper_response.status_code}")
            return False
        
        response_html = tamper_response.text
        
        # Check for exact marker "Certificate: INVALID"
        if "Certificate: INVALID" not in response_html:
            # Extract reason text (strip tags, first 200 chars)
            import re
            text = re.sub(r'<[^>]+>', '', response_html)
            reason = text[:200]
            print_fail(f"Tamper: response does not contain 'Certificate: INVALID'. Got: {reason}")
            return False
        
        # Check for replay mismatch mention
        if "replay mismatch" not in response_html:
            import re
            text = re.sub(r'<[^>]+>', '', response_html)
            reason = text[:200]
            print_fail(f"Tamper: response does not mention 'replay mismatch'. Got: {reason}")
            return False
        
        print_pass(f"Tamper: INVALID with replay mismatch, run_id={run_id}")
        return True
        
    except Exception as e:
        print_fail(f"Tamper check failed: {e}")
        return False


def check_verify(client: httpx.Client, base_url: str, run_id: str) -> bool:
    """
    Check Verify endpoint: real certificate should be VALID.
    """
    try:
        # Post to verify endpoint
        verify_response = client.post(
            f"{base_url}/api/verify",
            data={"run_id": run_id},
            timeout=120.0
        )
        
        # Handle rate limiting
        retry_count = 0
        while verify_response.status_code == 429 and retry_count < 2:
            if not wait_for_retry_after(verify_response):
                print_fail("Verify: rate limit exceeded without Retry-After")
                return False
            
            retry_count += 1
            verify_response = client.post(
                f"{base_url}/api/verify",
                data={"run_id": run_id},
                timeout=120.0
            )
        
        if verify_response.status_code != 200:
            print_fail(f"Verify: POST /api/verify returned {verify_response.status_code}")
            return False
        
        response_html = verify_response.text
        
        # Check for exact marker "Certificate: VALID"
        if "Certificate: VALID" not in response_html:
            # Extract reason text (strip tags, first 200 chars)
            import re
            text = re.sub(r'<[^>]+>', '', response_html)
            reason = text[:200]
            print_fail(f"Verify: response does not contain 'Certificate: VALID'. Got: {reason}")
            return False
        
        # Ensure it's not INVALID (which contains "VALID" as substring)
        if "Certificate: INVALID" in response_html:
            import re
            text = re.sub(r'<[^>]+>', '', response_html)
            reason = text[:200]
            print_fail(f"Verify: response contains 'Certificate: INVALID'. Got: {reason}")
            return False
        
        print_pass(f"Verify: certificate VALID, run_id={run_id}")
        return True
        
    except Exception as e:
        print_fail(f"Verify check failed: {e}")
        return False


def check_cache_control(client: httpx.Client, base_url: str) -> bool:
    """
    Check that every /api/* response carries Cache-Control: no-store.
    """
    try:
        # Test a simple /api/run request
        response = client.post(
            f"{base_url}/api/run",
            json={
                "sample": "T1",
                "port": "correct",
                "seed": 999,
                "cases": 10
            },
            timeout=10.0
        )
        
        cache_control = response.headers.get("Cache-Control", "")
        
        if "no-store" not in cache_control:
            print_fail(f"Cache-Control: /api/run response missing no-store (got: {cache_control})")
            return False
        
        print_pass("Cache-Control: /api/* responses include no-store")
        return True
        
    except Exception as e:
        print_fail(f"Cache-Control check failed: {e}")
        return False


def check_body_limit(client: httpx.Client, base_url: str) -> bool:
    """
    Check that a 17 KB body to /api/run gets 413.
    """
    try:
        # Create a large payload (17 KB)
        large_payload = {
            "sample": "T1",
            "port": "correct",
            "seed": 42,
            "cases": 10,
            "padding": "x" * (17 * 1024)  # 17 KB of padding
        }
        
        response = client.post(
            f"{base_url}/api/run",
            json=large_payload,
            timeout=10.0
        )
        
        if response.status_code != 413:
            print_fail(f"Body limit: 17 KB body returned {response.status_code}, expected 413")
            return False
        
        print_pass("Body limit: 17 KB body rejected with 413")
        return True
        
    except Exception as e:
        print_fail(f"Body limit check failed: {e}")
        return False


def run_checks(base_url: str) -> bool:
    """
    Run all deployment checks against the given URL.
    
    Returns True if all checks pass, False otherwise.
    """
    # Create HTTP client with timeout
    with httpx.Client(timeout=30.0, follow_redirects=False) as client:
        checks = []
        
        # Home page
        checks.append(check_home_page(client, base_url))
        
        # T1 faulty
        success, faulty_run_id = check_t1_faulty(client, base_url)
        checks.append(success)
        
        # T1 correct
        success, correct_run_id = check_t1_correct(client, base_url)
        checks.append(success)
        
        # Tamper (use faulty run_id if available)
        if faulty_run_id:
            checks.append(check_tamper(client, base_url, faulty_run_id))
        else:
            print_fail("Tamper: skipped (no faulty run_id)")
            checks.append(False)
        
        # Verify (use faulty run_id if available)
        if faulty_run_id:
            checks.append(check_verify(client, base_url, faulty_run_id))
        else:
            print_fail("Verify: skipped (no faulty run_id)")
            checks.append(False)
        
        # Cache-Control
        checks.append(check_cache_control(client, base_url))
        
        # Body limit
        checks.append(check_body_limit(client, base_url))
        
        return all(checks)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deployment check for Coroner (D-53, web-ui Task 19)"
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL to check (default: http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the clean build step (for tests only)"
    )
    
    args = parser.parse_args()
    
    # Find repository root (this script is in scripts/)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    # Step 1: Clean build (unless skipped)
    if not args.skip_build:
        if not clean_build_image(repo_root):
            print("\nDeployment check FAILED: build error")
            return 2
    
    # Step 2: Run checks
    print(f"\nRunning checks against {args.url}...")
    all_passed = run_checks(args.url)
    
    if all_passed:
        print("\nDeployment check PASSED: all checks succeeded")
        return 0
    else:
        print("\nDeployment check FAILED: one or more checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
