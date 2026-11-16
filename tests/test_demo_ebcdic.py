"""Tests for EBCDIC demo."""
import os
import pytest
import re
import subprocess
import sys
from pathlib import Path


@pytest.fixture(scope="module")
def t1_faulty_run(tmp_path_factory):
    """Module-scoped fixture: one faulty T1 run with 200 cases for all fast tests."""
    from coroner.cli import run_verify
    
    tmp_dir = tmp_path_factory.mktemp("t1_faulty")
    trap_dir = Path.cwd() / "samples" / "traps" / "T1-ebcdic-match-merge"
    
    verdict, run_dir = run_verify(
        cobol_path=str(trap_dir / "MATCH-MERGE.cob"),
        copybooks_dir=str(trap_dir / "copybooks"),
        java_path=str(trap_dir / "java" / "faulty" / "MatchMerge.java"),
        schema_path=str(trap_dir / "schema.json"),
        num_cases=200,
        seed=42,
        base_dir=str(tmp_dir),
        timings=False
    )
    
    return run_dir


def test_demo_step1_fails_on_alive():
    """Test that demo exits 1 and reports step 1 failure when step 1 gives ALIVE."""
    from coroner.demo_ebcdic import main
    
    trap_dir = Path.cwd() / "samples" / "traps" / "T1-ebcdic-match-merge"
    correct_java = str(trap_dir / "java" / "correct" / "MatchMerge.java")
    
    try:
        main(faulty_java_override=correct_java, cases=200)
        assert False, "Expected sys.exit(1)"
    except SystemExit as e:
        assert e.code == 1, f"Expected exit code 1, got {e.code}"


def test_no_absolute_paths_in_output(capsys):
    """Test that no printed line contains the home directory path."""
    from coroner.demo_ebcdic import main
    
    try:
        main(cases=200)
    except SystemExit:
        pass
    
    captured = capsys.readouterr()
    home_dir = str(Path.home())
    all_output = captured.out + captured.err
    
    for line in all_output.split('\n'):
        if not line.strip():
            continue
        assert home_dir not in line, f"Line contains home directory path: {line}"
        assert not re.search(r"Run: /", line), f"Line contains absolute run path: {line}"
        for token in line.split():
            if "runs" in token and os.path.isabs(token):
                assert False, f"Line contains absolute run path: {line}"


def test_junit_assertion_parser(t1_faulty_run, tmp_path):
    """Test that the JUnit assertion parser extracts expected and actual outputs correctly."""
    from coroner.diag.junit import verify_junit_test
    
    run_dir = t1_faulty_run
    
    verdict_file = run_dir / "verdict.json"
    assert verdict_file.exists()
    
    junit_test = run_dir / "ZombieRegressionTest.java"
    assert junit_test.exists()
    
    trap_dir = Path.cwd() / "samples" / "traps" / "T1-ebcdic-match-merge"
    faulty_java = str(trap_dir / "java" / "faulty" / "MatchMerge.java")
    junit_jar = str(Path.cwd() / "build" / "junit" / "junit-platform-console-standalone-6.1.3.jar")
    work_dir = str(tmp_path / "junit_work")
    
    result, summary = verify_junit_test(
        test_path=str(junit_test),
        java_path=faulty_java,
        junit_jar=junit_jar,
        work_dir=work_dir
    )
    
    assert result == "failed", f"Expected failed, got {result}"
    
    lines = summary.split('\n')
    expected_lines = []
    actual_lines = []
    capture_expected = False
    capture_actual = False
    
    for i, line in enumerate(lines):
        if '=> org.opentest4j.AssertionFailedError:' in line:
            if 'expected: <' in line:
                parts = line.split('expected: <', 1)
                if len(parts) > 1:
                    expected_lines.append(parts[1])
                    capture_expected = True
                    capture_actual = False
            continue
        
        if capture_expected:
            if '> but was: <' in line:
                parts = line.split('> but was: <', 1)
                if parts[0]:
                    expected_lines.append(parts[0])
                if len(parts) > 1:
                    actual_lines.append(parts[1])
                capture_expected = False
                capture_actual = True
            elif line.startswith('>'):
                capture_expected = False
                if 'but was: <' in line:
                    parts = line.split('but was: <', 1)
                    if len(parts) > 1:
                        actual_lines.append(parts[1])
                    capture_actual = True
            else:
                expected_lines.append(line)
        elif capture_actual:
            if line.startswith('>'):
                break
            else:
                actual_lines.append(line)
    
    cobol_output_file = run_dir / "minimal_case_cobol_output.csv"
    java_output_file = run_dir / "minimal_case_java_output.csv"
    
    assert cobol_output_file.exists(), "minimal_case_cobol_output.csv should exist"
    assert java_output_file.exists(), "minimal_case_java_output.csv should exist"
    
    cobol_output_lines = cobol_output_file.read_text().strip().split('\n')
    java_output_lines = java_output_file.read_text().strip().split('\n')
    
    assert expected_lines == cobol_output_lines, f"Expected lines should match COBOL output"
    assert actual_lines == java_output_lines, f"Actual lines should match Java output"


def test_faulty_t1_assertions(t1_faulty_run):
    """Test that the faulty T1 port at 200 cases gives ZOMBIE with expected properties."""
    import json
    
    run_dir = t1_faulty_run
    verdict_file = run_dir / "verdict.json"
    
    assert verdict_file.exists(), "verdict.json must exist"
    
    verdict_data = json.loads(verdict_file.read_text())
    
    assert verdict_data["status"] == "ZOMBIE", f"Expected ZOMBIE, got {verdict_data['status']}"
    assert verdict_data["cases_divergent"] >= 1, f"Expected at least 1 divergent case, got {verdict_data['cases_divergent']}"
    assert verdict_data["grand_total_matches"] is True, f"Expected grand_total_matches: true, got {verdict_data['grand_total_matches']}"
    
    trap_dir = Path.cwd() / "samples" / "traps" / "T1-ebcdic-match-merge"
    faulty_java = str(trap_dir / "java" / "faulty" / "MatchMerge.java")
    
    result = subprocess.run(
        [
            ".venv/bin/python",
            "-m",
            "coroner",
            "verify",
            "--cobol",
            str(trap_dir / "MATCH-MERGE.cob"),
            "--copybooks",
            str(trap_dir / "copybooks"),
            "--java",
            faulty_java,
            "--schema",
            str(trap_dir / "schema.json"),
            "--cases",
            "200",
            "--seed",
            "42"
        ],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 1, f"Expected exit code 1 (ZOMBIE), got {result.returncode}"
    
    stdout = result.stdout
    
    zombie_line_found = False
    grand_total_matches_found = False
    
    for line in stdout.split('\n'):
        if line.startswith("ZOMBIE:"):
            zombie_line_found = True
        if "grand total matches: yes" in line:
            grand_total_matches_found = True
    
    assert zombie_line_found, f"Expected a line starting with 'ZOMBIE:' in stdout:\n{stdout}"
    assert grand_total_matches_found, f"Expected 'grand total matches: yes' in stdout:\n{stdout}"
    
    expected_run_id = run_dir.name
    assert expected_run_id in stdout, f"Expected run directory {expected_run_id} in CLI output (deterministic run_id):\n{stdout}"


@pytest.mark.slow
def test_demo_ebcdic_integration(tmp_path):
    """Slow integration test: runs make demo-ebcdic and asserts all steps pass."""
    result = subprocess.run(
        ["make", "demo-ebcdic"],
        capture_output=True,
        text=True,
        timeout=600
    )
    
    assert result.returncode == 0, f"make demo-ebcdic failed with exit code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    
    output = result.stdout + result.stderr
    assert "Demo: all 5 steps behaved as expected" in output, f"Expected success message not found in output:\n{output}"
