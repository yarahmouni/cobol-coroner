"""Test multi-row JUnit test generation and verification."""

import tempfile
from pathlib import Path
from coroner.diag.junit import verify_junit_test


def test_t1_junit_fails_on_faulty_passes_on_correct():
    """Test that T1 JUnit test fails on faulty port and passes on correct port."""
    junit_jar = "build/junit/junit-platform-console-standalone-6.1.3.jar"
    
    if not Path(junit_jar).exists():
        # Skip if JUnit jar not downloaded yet
        return
    
    # Use the generated test from run 92a9f12d2aaa
    test_path = "runs/92a9f12d2aaa/ZombieRegressionTest.java"
    
    if not Path(test_path).exists():
        # Skip if the test doesn't exist
        return
    
    faulty_java = "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java"
    correct_java = "samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java"
    
    # Test against faulty port with relative work_dir - should fail
    with tempfile.TemporaryDirectory() as work_dir:
        result, summary = verify_junit_test(test_path, faulty_java, junit_jar, work_dir)
        print(f"\nFaulty port result: {result}")
        print(f"Summary (first 500 chars): {summary[:500]}")
        assert result == "failed", f"Test should fail against faulty port, got: {result}"
        assert "AssertionFailedError" in summary
    
    # Test against correct port with relative work_dir - should pass
    with tempfile.TemporaryDirectory() as work_dir:
        result, summary = verify_junit_test(test_path, correct_java, junit_jar, work_dir)
        print(f"\nCorrect port result: {result}")
        print(f"Summary (first 500 chars): {summary[:500]}")
        assert result == "passed", f"Test should pass against correct port, got: {result}. Summary: {summary[:500]}"
    
    # Test against faulty port with absolute work_dir - should fail
    with tempfile.TemporaryDirectory() as work_dir:
        abs_work_dir = str(Path(work_dir).resolve())
        result, summary = verify_junit_test(test_path, faulty_java, junit_jar, abs_work_dir)
        print(f"\nFaulty port (absolute path) result: {result}")
        assert result == "failed", f"Test should fail against faulty port with absolute path, got: {result}"
    
    # Test against correct port with absolute work_dir - should pass
    with tempfile.TemporaryDirectory() as work_dir:
        abs_work_dir = str(Path(work_dir).resolve())
        result, summary = verify_junit_test(test_path, correct_java, junit_jar, abs_work_dir)
        print(f"\nCorrect port (absolute path) result: {result}")
        assert result == "passed", f"Test should pass against correct port with absolute path, got: {result}"


def test_junit_error_on_empty_test():
    """Test that a test file with no @Test methods gives error result."""
    junit_jar = "build/junit/junit-platform-console-standalone-6.1.3.jar"
    
    if not Path(junit_jar).exists():
        # Skip if JUnit jar not downloaded yet
        return
    
    correct_java = "samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java"
    
    # Create a test file with no @Test method
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
        print(f"\nEmpty test result: {result}")
        print(f"Summary (first 500 chars): {summary[:500]}")
        assert result == "error", f"Empty test should give error result, got: {result}"
        assert "0 tests found" in summary
