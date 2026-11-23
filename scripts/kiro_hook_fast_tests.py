#!/usr/bin/env python3
"""Kiro IDE hook: run a small fast check after a Python file is saved.

Usage: kiro_hook_fast_tests.py <saved file path>

A saved tests/test_*.py file runs itself. A saved module under coroner/ runs the test file
that matches its name: tests/test_<name>.py, then tests/test_<package>_<name>.py; for a
package __init__.py, tests/test_<package>.py. Any other file runs a fixed subset of fast
test files. pytest runs with -x and the marker filter of pyproject.toml (slow tests are
deselected). The run is cut after BUDGET_SECONDS. A cut is reported as such: it is neither
a pass nor a fail.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUDGET_SECONDS = 25
FIXED_SUBSET = (
    "tests/test_verdict.py",
    "tests/test_compare.py",
    "tests/test_copybook.py",
    "tests/test_store.py",
    "tests/test_schema.py",
)


def relative_to_repo(saved):
    """The saved path relative to the repository root, or None when it is outside."""
    path = Path(saved)
    if not path.is_absolute():
        path = REPO_ROOT / path
    try:
        return path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return None


def choose_targets(saved):
    """The test files to run for a saved file, and a short reason."""
    rel = relative_to_repo(saved) if saved else None
    if rel is not None and rel.suffix == ".py" and len(rel.parts) > 1:
        if rel.parts[0] == "tests" and rel.name.startswith("test_"):
            return [rel.as_posix()], "saved test file"
        if rel.parts[0] == "coroner":
            package = rel.parent.name
            if rel.stem == "__init__":
                candidates = [f"tests/test_{package}.py"]
            else:
                candidates = [f"tests/test_{rel.stem}.py"]
                if package != "coroner":
                    candidates.append(f"tests/test_{package}_{rel.stem}.py")
            for candidate in candidates:
                if (REPO_ROOT / candidate).is_file():
                    return [candidate], f"tests that match {rel.as_posix()}"
    return list(FIXED_SUBSET), "fixed subset"


def main(argv):
    saved = argv[1] if len(argv) > 1 else ""
    targets, reason = choose_targets(saved)
    print(f"Fast check ({reason}): {' '.join(targets)}")
    command = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *targets]
    start = time.monotonic()
    process = subprocess.Popen(
        command, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    try:
        output, _ = process.communicate(timeout=BUDGET_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        print(
            f"Fast check stopped after {BUDGET_SECONDS} s. This is neither a pass nor a fail. "
            f"Run by hand: {' '.join(command[2:])}"
        )
        return 0
    print(output.rstrip())
    print(f"Fast check finished in {time.monotonic() - start:.1f} s")
    # pytest exit status 5: no test was collected (for example only slow tests in the file)
    return 0 if process.returncode in (0, 5) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
