"""CI gate that checks verdict and certificate validity."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

from coroner.hooks import (
    load_scope,
    compute_file_hash,
    compute_directory_hash,
    get_repo_root,
)
from coroner.certificate import replay_certificate


def run_audit_and_gate(
    scope: dict, java_path: str, cases: int, seed: int, base_dir: Path
) -> tuple:
    """Run verify, find certificate, replay it."""
    cobol_path = scope["cobol"]
    copybook_dir = scope["copybooks"]
    schema_path = scope["schema"]

    # Run verify as subprocess
    cmd = [
        sys.executable,
        "-m",
        "coroner",
        "verify",
        "--cobol",
        cobol_path,
        "--copybooks",
        copybook_dir,
        "--java",
        java_path,
        "--schema",
        schema_path,
        "--cases",
        str(cases),
        "--seed",
        str(seed),
    ]

    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base_dir)

    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env
    )

    # Parse run_id from output (format: "Run: <run_id>")
    # The value may be "runs/abc123" or just "abc123", extract last component
    run_id = None
    for line in result.stdout.splitlines():
        if line.startswith("Run: "):
            value = line.split("Run: ", 1)[1].strip()
            run_id = Path(value).name
            break

    # Handle ERROR verdict (exit 2)
    if result.returncode == 2:
        return "ERROR", run_id, None

    # Find certificate
    if run_id:
        cert_path = base_dir / "runs" / run_id / "certificate.json"
        if not cert_path.exists():
            return None, run_id, None

        # Replay certificate
        replay_result = replay_certificate(str(cert_path))

        # Load verdict from certificate
        with open(cert_path) as f:
            cert = json.load(f)

        return cert["status"], run_id, "VALID" if replay_result.valid else "INVALID"

    return None, None, None


def gate_certificate(
    cert_path: str, scope: dict, base_dir: Path
) -> tuple:
    """Check an existing certificate."""
    cert_file = Path(cert_path)
    if not cert_file.exists():
        return None, None, False

    # Load certificate
    with open(cert_file) as f:
        cert = json.load(f)

    # Compute current file hashes
    repo_root = get_repo_root()
    cobol_hash = compute_file_hash(repo_root / scope["cobol"])
    java_hash = compute_file_hash(repo_root / scope["java"])
    schema_hash = compute_file_hash(repo_root / scope["schema"])
    copybook_hash = compute_directory_hash(repo_root / scope["copybooks"])

    # Compare with certificate
    hash_match = (
        cert["cobol_file_sha256"] == cobol_hash
        and cert["java_file_sha256"] == java_hash
        and cert["schema_file_sha256"] == schema_hash
        and cert["copybook_hashes"] == copybook_hash
    )

    if not hash_match:
        return cert["status"], None, False

    # Replay certificate
    replay_result = replay_certificate(cert_path)

    return cert["status"], "VALID" if replay_result.valid else "INVALID", True


def write_junit_report(junit_path: str, passed: bool, message: str):
    """Write JUnit XML report."""
    testsuites = ET.Element("testsuites")
    testsuite = ET.SubElement(
        testsuites,
        "testsuite",
        name="coroner",
        tests="1",
        failures="0" if passed else "1",
        errors="0",
    )

    testcase = ET.SubElement(
        testsuite, "testcase", name="coroner_gate", classname="coroner.gate"
    )

    if not passed:
        failure = ET.SubElement(testcase, "failure", message=message)
        failure.text = message

    tree = ET.ElementTree(testsuites)
    tree.write(junit_path, encoding="UTF-8", xml_declaration=True)


def run_gate(
    scope_path: str,
    java_override: Optional[str],
    cases: int,
    seed: int,
    certificate_path: Optional[str],
    junit_path: Optional[str],
) -> int:
    """Main entry point for the gate."""
    repo_root = get_repo_root()
    base_dir = Path(os.environ.get("CORONER_BASE_DIR", str(repo_root)))

    # Load scope
    try:
        scope = load_scope(repo_root, scope_path)
    except Exception as e:
        msg = f"Gate: scope file error: {e}"
        print(msg, file=sys.stderr)
        if junit_path:
            write_junit_report(junit_path, False, msg)
        return 2

    # Certificate mode
    if certificate_path:
        verdict, replay_result, hash_match = gate_certificate(
            certificate_path, scope, base_dir
        )

        if verdict is None:
            msg = "Gate: certificate missing"
            print(msg)
            if junit_path:
                write_junit_report(junit_path, False, msg)
            return 1

        if not hash_match:
            msg = "Gate: certificate does not match the audited files"
            print(msg)
            if junit_path:
                write_junit_report(junit_path, False, msg)
            return 1

        if replay_result != "VALID":
            msg = "Gate: certificate invalid"
            print(msg)
            if junit_path:
                write_junit_report(junit_path, False, msg)
            return 1

        if verdict == "ZOMBIE":
            # Load divergence count from certificate
            with open(certificate_path) as f:
                cert = json.load(f)
            try:
                divergent = cert["cases_divergent"]
                total = cert["cases_total"]
            except KeyError:
                msg = "Gate: certificate invalid"
                print(msg)
                if junit_path:
                    write_junit_report(junit_path, False, msg)
                return 1
            msg = f"Gate: ZOMBIE on {divergent} of {total} cases"
            print(msg)
            if junit_path:
                write_junit_report(junit_path, False, msg)
            return 1

        if verdict == "ALIVE":
            with open(certificate_path) as f:
                cert = json.load(f)
            try:
                total = cert["cases_total"]
            except KeyError:
                msg = "Gate: certificate invalid"
                print(msg)
                if junit_path:
                    write_junit_report(junit_path, False, msg)
                return 1
            msg = f"Gate: ALIVE on {total} cases, certificate VALID"
            print(msg)
            if junit_path:
                write_junit_report(junit_path, True, msg)
            return 0

    # Audit mode
    java_path = java_override if java_override else scope["java"]
    verdict, run_id, replay_result = run_audit_and_gate(
        scope, java_path, cases, seed, base_dir
    )

    if verdict == "ERROR":
        msg = f"Gate: ERROR: reference did not run (run {run_id})"
        print(msg)
        if junit_path:
            write_junit_report(junit_path, False, msg)
        return 2

    if verdict is None:
        msg = "Gate: certificate missing"
        print(msg)
        if junit_path:
            write_junit_report(junit_path, False, msg)
        return 1

    if replay_result != "VALID":
        msg = f"Gate: certificate invalid (run {run_id})"
        print(msg)
        if junit_path:
            write_junit_report(junit_path, False, msg)
        return 1

    if verdict == "ZOMBIE":
        # Load divergence count
        cert_path = base_dir / "runs" / run_id / "certificate.json"
        with open(cert_path) as f:
            cert = json.load(f)
        try:
            divergent = cert["cases_divergent"]
            total = cert["cases_total"]
        except KeyError:
            msg = f"Gate: certificate invalid (run {run_id})"
            print(msg)
            if junit_path:
                write_junit_report(junit_path, False, msg)
            return 1
        msg = f"Gate: ZOMBIE on {divergent} of {total} cases (run {run_id})"
        print(msg)
        if junit_path:
            write_junit_report(junit_path, False, msg)
        return 1

    if verdict == "ALIVE":
        cert_path = base_dir / "runs" / run_id / "certificate.json"
        with open(cert_path) as f:
            cert = json.load(f)
        try:
            total = cert["cases_total"]
        except KeyError:
            msg = f"Gate: certificate invalid (run {run_id})"
            print(msg)
            if junit_path:
                write_junit_report(junit_path, False, msg)
            return 1
        msg = f"Gate: ALIVE on {total} cases, certificate VALID (run {run_id})"
        print(msg)
        if junit_path:
            write_junit_report(junit_path, True, msg)
        return 0

    # Fallback
    msg = "Gate: unexpected error"
    print(msg, file=sys.stderr)
    if junit_path:
        write_junit_report(junit_path, False, msg)
    return 2
