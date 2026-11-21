"""Tests for EBCDIC demo."""
import os
import pytest
import re
import subprocess
import sys
from pathlib import Path


@pytest.fixture
def t1_faulty_run(t1_faulty_200):
    """The shared T1 faulty run at 200 cases (session fixture of tests/conftest.py), read only: its run folder."""
    return t1_faulty_200.run_dir


@pytest.fixture(autouse=True)
def demo_without_base_dir(monkeypatch):
    """The demo and its replay work in the current directory: no base directory from the environment."""
    monkeypatch.delenv("CORONER_BASE_DIR", raising=False)


def _demo_scratch(tmp_path):
    """A scratch working directory for the demo, which works in the current directory.

    The demo reads samples/ and build/junit/ and writes runs/ and build/ in the current directory.
    The scratch folder links to the repository samples and JUnit folder, so the demo runs against the
    real programs while the repository runs/ folder is never written.
    """
    repo = Path(__file__).resolve().parent.parent
    scratch = tmp_path / "demo_cwd"
    (scratch / "build").mkdir(parents=True)
    (scratch / "samples").symlink_to(repo / "samples", target_is_directory=True)
    (scratch / "build" / "junit").symlink_to(repo / "build" / "junit", target_is_directory=True)
    return scratch


def test_demo_step1_fails_on_alive(tmp_path, monkeypatch):
    """Test that demo exits 1 and reports step 1 failure when step 1 gives ALIVE."""
    from coroner.demo_ebcdic import main
    
    trap_dir = Path.cwd() / "samples" / "traps" / "T1-ebcdic-match-merge"
    correct_java = str(trap_dir / "java" / "correct" / "MatchMerge.java")
    monkeypatch.chdir(_demo_scratch(tmp_path))
    
    try:
        main(faulty_java_override=correct_java, cases=200)
        assert False, "Expected sys.exit(1)"
    except SystemExit as e:
        assert e.code == 1, f"Expected exit code 1, got {e.code}"


def test_no_absolute_paths_in_output(capsys, tmp_path, monkeypatch):
    """Test that no printed line contains the home directory path.

    The demo works in the current directory, so it runs in a scratch folder: the repository runs/
    and build/ folders are never written.
    """
    from coroner.demo_ebcdic import main

    monkeypatch.chdir(_demo_scratch(tmp_path))

    try:
        main(cases=200)
    except SystemExit:
        pass
    
    captured = capsys.readouterr()
    home_dir = str(Path.home())
    all_output = captured.out + captured.err
    assert "=== Step 1:" in all_output, f"the demo printed no step header, the check below would be empty:\n{all_output}"
    
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


def test_faulty_t1_assertions(t1_faulty_run, tmp_path):
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
            sys.executable,
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
        timeout=60,
        env={**os.environ, "CORONER_BASE_DIR": str(tmp_path)},
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


def test_demo_step1_block_equals_cli(t1_faulty_run, tmp_path):
    """Test that demo step 1 verdict block equals the CLI output for the same run."""
    from coroner.cli import format_verdict_block
    import json
    import subprocess
    
    run_dir = t1_faulty_run
    
    # Read verdict and coverage from the run
    verdict_file = run_dir / "verdict.json"
    coverage_file = run_dir / "coverage_report.json"
    
    assert verdict_file.exists()
    assert coverage_file.exists()
    
    verdict_data = json.loads(verdict_file.read_text())
    coverage_data = json.loads(coverage_file.read_text())
    
    # Reconstruct verdict object for format_verdict_block
    from coroner.verdict import Verdict
    from decimal import Decimal
    verdict = Verdict(
        status=verdict_data["status"],
        sub_label=verdict_data["sub_label"],
        cases_total=verdict_data["cases_total"],
        cases_divergent=verdict_data["cases_divergent"],
        run_return_codes=tuple(verdict_data["run_return_codes"]),
        exposure_sum=Decimal(str(verdict_data["exposure_sum"])) if verdict_data.get("exposure_sum") else None,
        exposure_max=Decimal(str(verdict_data["exposure_max"])) if verdict_data.get("exposure_max") else None,
        affected_branches=verdict_data.get("affected_branches"),
        suspense_difference=Decimal(str(verdict_data["suspense_difference"])) if verdict_data.get("suspense_difference") else None,
        grand_total_matches=verdict_data.get("grand_total_matches"),
        validation_notice=verdict_data["validation_notice"]
    )
    
    # Format verdict block as CLI would (use str for run_dir, not relative path)
    cli_block = format_verdict_block(verdict, coverage_data, str(run_dir), 0.0)
    
    # Run the demo at 200 cases (the documented `cases` parameter of coroner.demo_ebcdic.main; the
    # command `python -m coroner.demo_ebcdic` runs it at the default 2000 cases) and capture its output.
    # The demo works in the current directory (it reads samples/ and build/junit/ and writes runs/ and
    # build/ there), so it runs in a scratch folder that links to the repository samples and JUnit jar:
    # the repository runs/ folder is never written.
    repo = Path.cwd()
    scratch = _demo_scratch(tmp_path)
    
    result = subprocess.run(
        [sys.executable, "-c", "from coroner.demo_ebcdic import main; main(cases=200)"],
        env={**os.environ, "PYTHONPATH": str(repo)},
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(scratch)
    )
    
    demo_output = result.stdout
    
    # The demo ran at 200 cases: its step 1 header says so
    assert "=== Step 1: Faulty T1 verify (200 cases, seed 42) ===" in demo_output
    
    # Extract step 1 block from demo output (between step 1 header and step 2 header)
    step1_start = demo_output.find("=== Step 1:")
    step2_start = demo_output.find("=== Step 2:")
    
    assert step1_start >= 0, "Step 1 header not found in demo output"
    assert step2_start >= 0, "Step 2 header not found in demo output"
    
    step1_section = demo_output[step1_start:step2_start].strip()
    
    # Extract the verdict block lines (after the header line and empty line)
    lines = step1_section.split('\n')
    verdict_lines = []
    started = False
    for line in lines:
        if not line.strip() and not started:
            started = True
            continue
        if started and line.strip():
            verdict_lines.append(line)
    
    demo_block = '\n'.join(verdict_lines)
    
    # The demo's exposure line must contain "suspense difference"
    assert "suspense difference" in demo_block, f"Demo block missing suspense difference:\n{demo_block}"


@pytest.mark.slow
def test_demo_ebcdic_integration(tmp_path):
    """Slow integration test: runs the make demo-ebcdic target (in a scratch folder) and asserts all steps pass."""
    # The demo works in the current directory: it runs in a scratch folder (links to the repository
    # samples and JUnit jar), so the repository runs/ and build/ folders are never written. The
    # Makefile of the repository is used with `make -f`, and the interpreter and package path are given.
    repo = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["make", "-f", str(repo / "Makefile"), "demo-ebcdic", f"PYTHON={sys.executable}"],
        env={**os.environ, "PYTHONPATH": str(repo)},
        cwd=str(_demo_scratch(tmp_path)),
        capture_output=True,
        text=True,
        timeout=600
    )
    
    assert result.returncode == 0, f"make demo-ebcdic failed with exit code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    
    output = result.stdout + result.stderr
    assert "Demo: all 5 steps behaved as expected" in output, f"Expected success message not found in output:\n{output}"
