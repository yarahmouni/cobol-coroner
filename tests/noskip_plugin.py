"""Pytest plugin to turn skips into failures when CORONER_NO_SKIP=1."""
import os

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Turn skipped tests into failures when CORONER_NO_SKIP=1 is set."""
    outcome = yield
    report = outcome.get_result()
    
    if os.environ.get("CORONER_NO_SKIP") == "1":
        if report.outcome == "skipped" and report.when in ("setup", "call"):
            report.outcome = "failed"
            original_reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
            report.longrepr = f"skipped in CI (CORONER_NO_SKIP=1): {original_reason}"
