"""Test multi-row JUnit test generation and verification."""

import pytest
import tempfile
from pathlib import Path
from coroner.diag.junit import verify_junit_test


@pytest.fixture
def t1_faulty_junit_run(t1_faulty_200):
    """The run folder of the shared T1 faulty run at 200 cases (tests/conftest.py), read only."""
    return t1_faulty_200.run_dir


def test_t1_junit_fails_on_faulty_passes_on_correct(t1_faulty_junit_run):
    """Test that T1 JUnit test fails on faulty port and passes on correct port."""
    junit_jar = "build/junit/junit-platform-console-standalone-6.1.3.jar"
    
    if not Path(junit_jar).exists():
        return
    
    run_dir = t1_faulty_junit_run
    test_path = str(run_dir / "ZombieRegressionTest.java")
    
    assert Path(test_path).exists(), f"JUnit test should exist at {test_path}"
    
    faulty_java = "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java"
    correct_java = "samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java"
    
    with tempfile.TemporaryDirectory() as work_dir:
        result, summary = verify_junit_test(test_path, faulty_java, junit_jar, work_dir)
        assert result == "failed", f"Test should fail against faulty port, got: {result}"
        assert "AssertionFailedError" in summary
    
    with tempfile.TemporaryDirectory() as work_dir:
        result, summary = verify_junit_test(test_path, correct_java, junit_jar, work_dir)
        assert result == "passed", f"Test should pass against correct port, got: {result}. Summary: {summary[:500]}"
    
    with tempfile.TemporaryDirectory() as work_dir:
        abs_work_dir = str(Path(work_dir).resolve())
        result, summary = verify_junit_test(test_path, faulty_java, junit_jar, abs_work_dir)
        assert result == "failed", f"Test should fail against faulty port with absolute path, got: {result}"
    
    with tempfile.TemporaryDirectory() as work_dir:
        abs_work_dir = str(Path(work_dir).resolve())
        result, summary = verify_junit_test(test_path, correct_java, junit_jar, abs_work_dir)
        assert result == "passed", f"Test should pass against correct port with absolute path, got: {result}"


def test_junit_error_on_empty_test():
    """Test that a test file with no @Test methods gives error result."""
    junit_jar = "build/junit/junit-platform-console-standalone-6.1.3.jar"
    
    if not Path(junit_jar).exists():
        return
    
    correct_java = "samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java"
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        empty_test = tmp_path / "EmptyTest.java"
        empty_test.write_text("""
import org.junit.jupiter.api.Test;

public class EmptyTest {
    // No @Test method
    public void notATest() {
    }
}
""")
        
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        
        result, summary = verify_junit_test(str(empty_test), correct_java, junit_jar, str(work_dir))
        assert result == "error", f"Empty test should give error result, got: {result}"
        assert "0 tests found" in summary

