"""Test that CORONER_NO_SKIP=1 turns skips into failures in CI."""
import textwrap
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]


def test_skip_without_env_var(pytester, monkeypatch):
    """Without CORONER_NO_SKIP, pytest.skip reports as skipped."""
    # Ensure CORONER_NO_SKIP is not set
    monkeypatch.delenv("CORONER_NO_SKIP", raising=False)
    
    # Add tests/ directory to PYTHONPATH so noskip_plugin can be imported in subprocess
    tests_dir = Path(__file__).parent.resolve()
    monkeypatch.setenv("PYTHONPATH", str(tests_dir))
    
    # Create a conftest that imports the hook
    pytester.makeconftest("from noskip_plugin import pytest_runtest_makereport")
    
    # Create a test that skips
    pytester.makepyfile(test_inner=textwrap.dedent("""
        import pytest
        
        def test_skip_example():
            pytest.skip("tool not available")
    """))
    
    # Run without CORONER_NO_SKIP
    result = pytester.runpytest_subprocess("-v")
    result.assert_outcomes(skipped=1)


def test_skip_with_env_var(pytester, monkeypatch):
    """With CORONER_NO_SKIP=1, pytest.skip reports as failed."""
    # Set CORONER_NO_SKIP=1
    monkeypatch.setenv("CORONER_NO_SKIP", "1")
    
    # Add tests/ directory to PYTHONPATH so noskip_plugin can be imported in subprocess
    tests_dir = Path(__file__).parent.resolve()
    monkeypatch.setenv("PYTHONPATH", str(tests_dir))
    
    # Create a conftest that imports the hook
    pytester.makeconftest("from noskip_plugin import pytest_runtest_makereport")
    
    # Create a test that skips
    pytester.makepyfile(test_inner=textwrap.dedent("""
        import pytest
        
        def test_skip_example():
            pytest.skip("tool not available")
    """))
    
    # Run with CORONER_NO_SKIP=1
    result = pytester.runpytest_subprocess("-v")
    result.assert_outcomes(failed=1)
    
    # Check the failure message
    result.stdout.fnmatch_lines([
        "*skipped in CI (CORONER_NO_SKIP=1): Skipped: tool not available*"
    ])
