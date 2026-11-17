"""EBCDIC/control-break demo script."""
import sys
import json
import re
from pathlib import Path

from coroner.cli import run_verify, format_verdict_block
from coroner.certificate import replay_certificate
from coroner.diag.junit import verify_junit_test


def main(faulty_java_override=None, correct_java_override=None, cases=2000):
    """Run the EBCDIC/control-break demo."""
    import time
    
    base_dir = Path.cwd()
    trap_dir = base_dir / "samples" / "traps" / "T1-ebcdic-match-merge"
    
    cobol_path = str(trap_dir / "MATCH-MERGE.cob")
    copybooks_path = str(trap_dir / "copybooks")
    schema_path = str(trap_dir / "schema.json")
    faulty_java = faulty_java_override or str(trap_dir / "java" / "faulty" / "MatchMerge.java")
    correct_java = correct_java_override or str(trap_dir / "java" / "correct" / "MatchMerge.java")
    
    junit_jar = str(base_dir / "build" / "junit" / "junit-platform-console-standalone-6.1.3.jar")
    
    # Step 1: Run faulty T1 verify
    print(f"=== Step 1: Faulty T1 verify ({cases} cases, seed 42) ===")
    print()
    
    start_time = time.time()
    try:
        verdict, run_dir = run_verify(
            cobol_path=cobol_path,
            java_path=faulty_java,
            schema_path=schema_path,
            copybooks_dir=copybooks_path,
            num_cases=cases,
            seed=42,
            base_dir=str(base_dir)
        )
    except SystemExit:
        print("Demo: step 1 failed: expected ZOMBIE verdict but got error", file=sys.stderr)
        sys.exit(1)
    
    duration1 = time.time() - start_time
    
    # Check verdict is ZOMBIE
    if verdict.status != "ZOMBIE":
        print(f"Demo: step 1 failed: expected ZOMBIE / got {verdict.status}", file=sys.stderr)
        sys.exit(1)
    
    # Read coverage report
    with open(run_dir / "coverage_report.json", 'r') as f:
        coverage = json.load(f)
    
    # Print verdict block (use relative path for display)
    verdict_block = format_verdict_block(verdict, coverage, run_dir.relative_to(Path.cwd()), duration1)
    print(verdict_block)
    print()
    
    # Step 2: Print card
    print("=== Step 2: Card ===")
    print()
    
    card_path = run_dir / "card.txt"
    if not card_path.exists():
        print("Demo: step 2 failed: expected card.txt / file not found", file=sys.stderr)
        sys.exit(1)
    
    with open(card_path, 'r') as f:
        card_text = f.read()
    
    # Print card with COBOL lines separated, one per line (indented)
    for line in card_text.split('\n'):
        if line.startswith('COBOL lines involved:'):
            print(line.split(':')[0] + ':')
            # Split the COBOL lines by "; " and print each indented
            cobol_lines_part = ':'.join(line.split(':')[1:]).strip()
            cobol_lines = cobol_lines_part.split('; ')
            for cobol_line in cobol_lines:
                if cobol_line.strip():
                    print(f"  {cobol_line.strip()}")
        else:
            print(line)
    print()
    
    # Step 3: Verify JUnit test against both ports
    print("=== Step 3: JUnit test verification ===")
    print()
    
    junit_test = str(run_dir / "ZombieRegressionTest.java")
    if not Path(junit_test).exists():
        print("Demo: step 3 failed: expected ZombieRegressionTest.java / file not found", file=sys.stderr)
        sys.exit(1)
    
    # Test against faulty port
    faulty_work_dir = str(base_dir / "build" / "demo_junit_faulty")
    Path(faulty_work_dir).mkdir(parents=True, exist_ok=True)
    
    faulty_status, faulty_summary = verify_junit_test(junit_test, faulty_java, junit_jar, faulty_work_dir)
    
    # Parse JUnit output to extract counts and assertion message
    faulty_tests_found = 0
    faulty_successful = 0
    faulty_failed = 0
    
    for line in faulty_summary.split('\n'):
        if 'tests found' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'tests' and i > 0:
                    try:
                        faulty_tests_found = int(parts[i - 1])
                    except ValueError:
                        pass
        elif 'tests successful' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'tests' and i > 0:
                    try:
                        faulty_successful = int(parts[i - 1])
                    except ValueError:
                        pass
        elif 'tests failed' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'tests' and i > 0:
                    try:
                        faulty_failed = int(parts[i - 1])
                    except ValueError:
                        pass
    
    print(f"JUnit against faulty port: {faulty_status} ({faulty_tests_found} tests found, {faulty_successful} successful, {faulty_failed} failed)")
    
    # Extract and print the full assertion details from the "=> org.opentest4j.AssertionFailedError:" block
    if faulty_status == "failed":
        lines = faulty_summary.split('\n')
        expected_lines = []
        actual_lines = []
        capture_expected = False
        capture_actual = False
        
        for i, line in enumerate(lines):
            # Look for the start of the AssertionFailedError details block
            if '=> org.opentest4j.AssertionFailedError:' in line:
                # The expected value starts in this line after "expected: <"
                if 'expected: <' in line:
                    parts = line.split('expected: <', 1)
                    if len(parts) > 1:
                        # Everything after "expected: <" until end of line is part of expected
                        expected_lines.append(parts[1])
                        capture_expected = True
                        capture_actual = False
                continue
            
            if capture_expected:
                # Look for the end of expected (">") and start of actual ("but was: <")
                if '> but was: <' in line:
                    # Split: before "> but was: <" goes to expected, after goes to actual
                    parts = line.split('> but was: <', 1)
                    if parts[0]:
                        expected_lines.append(parts[0])
                    if len(parts) > 1:
                        actual_lines.append(parts[1])
                    capture_expected = False
                    capture_actual = True
                elif line.startswith('>'):
                    # End of expected, start looking for actual
                    capture_expected = False
                    # Check if this line has "but was: <"
                    if 'but was: <' in line:
                        parts = line.split('but was: <', 1)
                        if len(parts) > 1:
                            actual_lines.append(parts[1])
                        capture_actual = True
                else:
                    # Continue capturing expected lines
                    expected_lines.append(line)
            elif capture_actual:
                # Look for the end of actual (">")
                if line.startswith('>'):
                    # End of actual block
                    break
                else:
                    # Continue capturing actual lines
                    actual_lines.append(line)
        
        if expected_lines or actual_lines:
            print("JUnit expected (COBOL output):")
            for exp_line in expected_lines:
                print(f"  {exp_line}")
            print("JUnit actual (Java port output):")
            for act_line in actual_lines:
                print(f"  {act_line}")
    
    if faulty_status != "failed":
        print(f"Demo: step 3 failed: expected failed on faulty port / got {faulty_status}", file=sys.stderr)
        sys.exit(1)
    
    print()
    
    # Test against correct port
    correct_work_dir = str(base_dir / "build" / "demo_junit_correct")
    Path(correct_work_dir).mkdir(parents=True, exist_ok=True)
    
    correct_status, correct_summary = verify_junit_test(junit_test, correct_java, junit_jar, correct_work_dir)
    
    # Parse JUnit output to extract counts
    correct_tests_found = 0
    correct_successful = 0
    correct_failed = 0
    
    for line in correct_summary.split('\n'):
        if 'tests found' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'tests' and i > 0:
                    try:
                        correct_tests_found = int(parts[i - 1])
                    except ValueError:
                        pass
        elif 'tests successful' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'tests' and i > 0:
                    try:
                        correct_successful = int(parts[i - 1])
                    except ValueError:
                        pass
        elif 'tests failed' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'tests' and i > 0:
                    try:
                        correct_failed = int(parts[i - 1])
                    except ValueError:
                        pass
    
    print(f"JUnit against correct port: {correct_status} ({correct_tests_found} tests found, {correct_successful} successful, {correct_failed} failed)")
    
    if correct_status != "passed":
        print(f"Demo: step 3 failed: expected passed on correct port / got {correct_status}", file=sys.stderr)
        sys.exit(1)
    
    print()
    
    # Step 4: Replay certificate
    print("=== Step 4: Certificate replay ===")
    print()
    
    cert_path = run_dir / "certificate.json"
    if not cert_path.exists():
        print("Demo: step 4 failed: expected certificate.json / file not found", file=sys.stderr)
        sys.exit(1)
    
    replay_result = replay_certificate(str(cert_path))
    
    if replay_result.valid:
        print(f"Certificate: VALID")
    else:
        print(f"Certificate: INVALID: {replay_result.reason}")
        print(f"Demo: step 4 failed: expected VALID / got INVALID", file=sys.stderr)
        sys.exit(1)
    
    print()
    
    # Step 5: Run correct T1 verify
    print(f"=== Step 5: Correct T1 verify ({cases} cases, seed 42) ===")
    print()
    
    start_time5 = time.time()
    try:
        verdict2, run_dir2 = run_verify(
            cobol_path=cobol_path,
            java_path=correct_java,
            schema_path=schema_path,
            copybooks_dir=copybooks_path,
            num_cases=cases,
            seed=42,
            base_dir=str(base_dir)
        )
    except SystemExit:
        print("Demo: step 5 failed: expected ALIVE verdict but got error", file=sys.stderr)
        sys.exit(1)
    
    duration5 = time.time() - start_time5
    
    # Check verdict is ALIVE
    if verdict2.status != "ALIVE":
        print(f"Demo: step 5 failed: expected ALIVE / got {verdict2.status}", file=sys.stderr)
        sys.exit(1)
    
    # Read coverage report
    with open(run_dir2 / "coverage_report.json", 'r') as f:
        coverage2 = json.load(f)
    
    # Print verdict block (use relative path for display)
    verdict_block = format_verdict_block(verdict2, coverage2, run_dir2.relative_to(Path.cwd()), duration5)
    print(verdict_block)
    print()
    
    # Final message
    print("Demo: all 5 steps behaved as expected")
    sys.exit(0)


if __name__ == "__main__":
    main()
