"""CLI module for Coroner."""
import sys
import os
import time
import argparse
from pathlib import Path

from coroner.parse.schema import load_schema
from coroner.parse.copybook import parse_cobol_structure
from coroner.gen import generate_cases
from coroner.run import compile_cobol, compile_java, run_cobol, run_java, run_cobol_instrumented
from coroner.compare import compare_outputs
from coroner.verdict import compute_verdict
from coroner.store import collect_inputs, compute_run_id, store_inputs, store_comparison, store_verdict
from coroner.diag.coverage import compute_coverage
from coroner.diag.report import generate_failure_report
from coroner.parse.trace import parse_trace_counts


def validate_inputs(cobol: str, copybooks: str, java: str, schema: str) -> None:
    """
    Validate input files exist and meet size limits.
    
    Size limits per Requirement 1.3:
    - COBOL source: 1 MB
    - Java source: 1 MB
    - Schema: 100 KB
    - Each copybook: 100 KB
    
    Args:
        cobol: Path to COBOL source
        copybooks: Path to copybooks directory
        java: Path to Java source
        schema: Path to schema.json
        
    Raises:
        ValueError: If any validation fails
    """
    # Check existence
    if not os.path.isfile(cobol):
        raise ValueError(f"COBOL source not found: {cobol}")
    if not os.path.isdir(copybooks):
        raise ValueError(f"Copybooks directory not found: {copybooks}")
    if not os.path.isfile(java):
        raise ValueError(f"Java source not found: {java}")
    if not os.path.isfile(schema):
        raise ValueError(f"Schema not found: {schema}")
    
    # Check size limits
    cobol_size = os.path.getsize(cobol)
    if cobol_size > 1024 * 1024:
        raise ValueError(f"COBOL source exceeds 1 MB: {cobol_size} bytes")
    
    java_size = os.path.getsize(java)
    if java_size > 1024 * 1024:
        raise ValueError(f"Java source exceeds 1 MB: {java_size} bytes")
    
    schema_size = os.path.getsize(schema)
    if schema_size > 100 * 1024:
        raise ValueError(f"Schema exceeds 100 KB: {schema_size} bytes")
    
    # Check copybook sizes
    for entry in os.listdir(copybooks):
        copybook_path = os.path.join(copybooks, entry)
        if os.path.isfile(copybook_path):
            size = os.path.getsize(copybook_path)
            if size > 100 * 1024:
                raise ValueError(f"Copybook {entry} exceeds 100 KB: {size} bytes")


def run_verify(
    cobol_path: str,
    java_path: str,
    schema_path: str,
    copybooks_dir: str,
    num_cases: int = 2000,
    seed: int = 42,
    timings: bool = False,
    base_dir: str = "."
) -> tuple:
    """Run the differential verification pipeline.
    
    Args:
        cobol_path: Path to COBOL source file
        java_path: Path to Java source file
        schema_path: Path to schema.json
        copybooks_dir: Path to copybooks directory
        num_cases: Number of test cases (default 2000)
        seed: Random seed (default 42)
        timings: Print per-step timings to stderr (default False)
        base_dir: Base directory for runs/ and build/ (default current directory)
        
    Returns:
        (verdict, run_dir): Verdict object and Path to run directory
        
    Raises:
        ValueError: Input validation failures
        Exception: Compilation, execution or comparison errors
    """
    import json
    import csv
    import shutil
    
    tie_share = 0.06  # Calibrated in R-55
    
    def record_step(name: str, start: float):
        if timings:
            elapsed = time.time() - start
            print(f"  {name}: {elapsed:.2f} s", file=sys.stderr)
    
    # Step 1: Validate inputs
    step_start = time.time()
    validate_inputs(cobol_path, copybooks_dir, java_path, schema_path)
    record_step("Validate inputs", step_start)
    
    # Step 2: Parse schema and structure
    step_start = time.time()
    schema_obj = load_schema(schema_path)
    cobol_structure = parse_cobol_structure(cobol_path, copybooks_dir)
    record_step("Parse schema and structure", step_start)
    
    # Step 3: Generate cases
    step_start = time.time()
    cases_csv_path = generate_cases(schema_obj, cobol_structure, seed, num_cases, tie_share, base_dir)
    record_step(f"Generate {num_cases} cases", step_start)
    
    # Step 4: Collect inputs and compute run_id
    step_start = time.time()
    cobol_flags = schema_obj.cobc_flags or []
    inputs_data = collect_inputs(cobol_path, copybooks_dir, java_path, schema_path, 
                                  cases_csv_path, seed, num_cases, cobol_flags)
    run_id = compute_run_id(inputs_data)
    run_dir = Path(base_dir) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record_step("Collect inputs and compute run_id", step_start)
    
    # Create build directories
    build_dir = Path(base_dir) / "build" / run_id
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "coverage").mkdir(exist_ok=True)
    (build_dir / "java").mkdir(exist_ok=True)
    
    # Extract program name from schema
    program_name = schema_obj.program_name
    
    # Step 5: Compile COBOL reference
    step_start = time.time()
    cobol_binary = str(build_dir / program_name)
    cobol_flags = schema_obj.cobc_flags or []
    compile_cobol(cobol_path, copybooks_dir, cobol_binary, cobol_flags, base_dir)
    record_step("Compile COBOL reference", step_start)
    
    # Step 5b: Compile COBOL coverage
    step_start = time.time()
    cobol_coverage_binary = str(build_dir / "coverage" / program_name)
    compile_cobol(cobol_path, copybooks_dir, cobol_coverage_binary, cobol_flags + ["-ftraceall"], base_dir)
    record_step("Compile COBOL coverage", step_start)
    
    # Step 5c: Compile Java
    step_start = time.time()
    compile_java(java_path, str(build_dir / "java"), base_dir)
    record_step("Compile Java", step_start)
    
    # Extract Java class name from file
    java_class = Path(java_path).stem
    
    # Step 6: Run reference COBOL
    step_start = time.time()
    cobol_output = str(build_dir / "cobol_output.csv")
    was_killed = False
    try:
        cobol_result = run_cobol(cobol_binary, cases_csv_path, cobol_output)
    except RuntimeError as e:
        if "timed out" in str(e):
            was_killed = True
            # Create a dummy result for validation
            cobol_result = type('obj', (object,), {
                'output_path': cobol_output,
                'return_code': -1,
                'stderr': str(e),
                'wall_time': 0.0
            })()
        else:
            raise
    
    # Validate reference output
    from coroner.run import validate_reference_output
    is_valid, error_reason = validate_reference_output(cobol_result, cases_csv_path, was_killed)
    if not is_valid:
        # Reference did not run successfully
        # Print error message and exit 2 without verdict or certificate
        print("ERROR: reference did not run", file=sys.stderr)
        print(f"Reason: {error_reason}", file=sys.stderr)
        
        # Show first few lines of stderr if available
        if cobol_result.stderr:
            stderr_lines = cobol_result.stderr.strip().split('\n')[:10]
            print("COBOL stderr:", file=sys.stderr)
            for line in stderr_lines:
                print(f"  {line}", file=sys.stderr)
        
        # Write error info to run directory
        error_path = run_dir / "run_error.txt"
        with open(error_path, 'w') as f:
            f.write(f"ERROR: reference did not run\n")
            f.write(f"Reason: {error_reason}\n\n")
            if cobol_result.stderr:
                f.write("COBOL stderr:\n")
                f.write(cobol_result.stderr)
        
        # Exit without verdict or certificate
        sys.exit(2)
    
    record_step("Run COBOL reference", step_start)
    
    # Step 6b: Run Java
    step_start = time.time()
    java_output = str(build_dir / "java_output.csv")
    java_result = run_java(java_class, str(build_dir / "java"), cases_csv_path, java_output)
    record_step("Run Java", step_start)
    
    # Step 7: Run instrumented COBOL for coverage
    step_start = time.time()
    trace_file = str(run_dir / "coverage_trace.txt")
    coverage_output = str(build_dir / "coverage_output.csv")
    run_cobol_instrumented(cobol_coverage_binary, cases_csv_path, coverage_output, trace_file)
    record_step("Run COBOL coverage", step_start)
    
    # Step 8: Compare outputs
    step_start = time.time()
    comparison = compare_outputs(cobol_result.output_path, java_result.output_path, 
                                 schema_obj, cobol_result.return_code, java_result.return_code)
    record_step("Compare outputs", step_start)
    
    # Step 9: Compute verdict
    step_start = time.time()
    verdict = compute_verdict(comparison)
    record_step("Compute verdict", step_start)
    
    # Step 10: Generate reports
    step_start = time.time()
    trace = parse_trace_counts(trace_file)
    coverage_report = compute_coverage(trace, cobol_structure, cobol_path, copybooks_dir)
    
    # Store coverage report
    with open(run_dir / "coverage_report.json", 'w') as f:
        json.dump({
            "paragraph_coverage": coverage_report.paragraph_coverage,
            "branch_coverage": coverage_report.branch_coverage,
            "paragraphs_total": coverage_report.paragraphs_total,
            "paragraphs_covered": coverage_report.paragraphs_covered,
            "branches_total": coverage_report.branches_total,
            "branches_covered": coverage_report.branches_covered,
            "uncovered_branches": coverage_report.uncovered_branches
        }, f, indent=2)
    
    # Generate failure report if ZOMBIE
    if verdict.status == "ZOMBIE":
        # Build input_rows dict from cases CSV
        input_rows = {}
        with open(cases_csv_path, 'r') as f:
            reader = csv.DictReader(f)
            
            # Check if this is a multi-row schema
            is_multirow = hasattr(schema_obj, 'case_rows') and schema_obj.case_rows is not None
            
            if is_multirow:
                # Group rows by CASE-ID
                for row in reader:
                    case_id = row.get('CASE-ID', '')
                    if case_id not in input_rows:
                        input_rows[case_id] = []
                    input_rows[case_id].append(row)
            else:
                # Single row per case
                for row in reader:
                    case_id = row.get('CASE-ID', '')
                    input_rows[case_id] = row
        
        # Select minimal case
        from coroner.diag.minimal_case import select_minimal_case
        divergent_cases = [case for case in comparison.cases if case.divergent]
        minimal_case = select_minimal_case(divergent_cases, schema_obj, input_rows)
        
        # Generate failure report
        failure_report = generate_failure_report(
            minimal_case, input_rows, schema_obj,
            cobol_coverage_binary, java_class, str(build_dir / "java"),
            str(run_dir),
            cobol_source_path=cobol_path,
            copybooks_path=copybooks_dir,
            java_source_path=java_path
        )
        
        # Generate Given/When/Then card
        from coroner.diag.card import generate_card
        card_text = generate_card(failure_report, schema_obj, cobol_path, copybooks_dir)
        
        # Write card to card.txt
        with open(run_dir / "card.txt", 'w') as f:
            f.write(card_text)
        
        # Store failure report with card
        report_dict = {
            "case_id": failure_report.case_id,
            "input_row": failure_report.input_row,
            "cobol_output": failure_report.cobol_output,
            "java_output": failure_report.java_output,
            "divergent_fields": failure_report.divergent_fields,
            "cobol_return_code": failure_report.cobol_return_code,
            "java_return_code": failure_report.java_return_code,
            "executed_lines": [(src, line) for src, line in failure_report.executed_lines],
            "card": card_text
        }
        
        # Add multi-row fields if present
        if failure_report.original_case_rows is not None:
            report_dict["original_case_rows"] = failure_report.original_case_rows
        if failure_report.minimal_case_rows is not None:
            report_dict["minimal_case_rows"] = failure_report.minimal_case_rows
        
        with open(run_dir / "failure_report.json", 'w') as f:
            json.dump(report_dict, f, indent=2)
        
        # Generate JUnit regression test with card as header comment
        from coroner.diag.junit import generate_junit_test
        
        # For JUnit test, use the appropriate input
        if is_multirow and failure_report.minimal_case_rows:
            # Use minimal rows for the test
            junit_input = failure_report.minimal_case_rows[0] if failure_report.minimal_case_rows else {}
        else:
            junit_input = input_rows[minimal_case.case_id]
            if isinstance(junit_input, list):
                junit_input = junit_input[0] if junit_input else {}
        
        generate_junit_test(
            minimal_case,
            junit_input,
            failure_report.cobol_output,
            java_class,
            schema_obj,
            str(run_dir / "ZombieRegressionTest.java"),
            card_text
        )
    
    record_step("Generate reports", step_start)
    
    # Step 11: Store results
    step_start = time.time()
    store_inputs(str(run_dir), inputs_data)
    store_comparison(str(run_dir), comparison)
    store_verdict(str(run_dir), verdict)
    
    # Copy generated cases to run directory
    shutil.copy(cases_csv_path, run_dir / "generated_cases.csv")
    
    # Generate certificate
    from coroner.certificate import generate_certificate
    generate_certificate(run_id, cobol_path, copybooks_dir, java_path, schema_path, base_dir)
    
    record_step("Store results", step_start)
    
    return (verdict, run_dir)


def verify_command(cobol: str, copybooks: str, java: str, schema: str, 
                   cases: int = 2000, seed: int = 42, tie_share: float = 0.06, 
                   timings: bool = False) -> int:
    """
    CLI wrapper for run_verify that formats output.
    
    Args:
        cobol: Path to COBOL source file
        copybooks: Path to copybooks directory
        java: Path to Java source file
        schema: Path to schema.json
        cases: Number of test cases to generate (default 2000)
        seed: Random seed (default 42)
        tie_share: Unused, kept for compatibility
        timings: Print per-step timings (default False)
        
    Returns:
        Exit code: 0 (ALIVE), 1 (ZOMBIE), 2 (error)
    """
    import json
    start_time = time.time()
    
    try:
        verdict, run_dir = run_verify(cobol, java, schema, copybooks, cases, seed, timings)
        
        # Read coverage report
        with open(run_dir / "coverage_report.json", 'r') as f:
            coverage = json.load(f)
        
        # Print output
        total_time = time.time() - start_time
        print(f"{verdict.status}: {verdict.sub_label}")
        print(f"Paragraph coverage {coverage['paragraphs_covered']}/{coverage['paragraphs_total']}")
        print(f"Branch coverage (Coroner definition) {coverage['branches_covered']}/{coverage['branches_total']}")
        
        # Print exposure if present
        if verdict.exposure_sum is not None:
            matches_text = "yes" if verdict.grand_total_matches else "no"
            print(f"Unreconciled branch exposure: sum {verdict.exposure_sum:.2f}, max {verdict.exposure_max:.2f}, {verdict.affected_branches} branches affected, grand total matches: {matches_text}")
        
        print(verdict.validation_notice)
        print(f"Run: {run_dir}")
        print(f"Duration: {total_time:.1f} s")
        
        # Return exit code
        return 0 if verdict.status == "ALIVE" else 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="coroner",
        description="COBOL Coroner: independent regression auditor for COBOL-to-Java migrations"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # verify command
    verify_parser = subparsers.add_parser("verify", help="Verify a migration")
    verify_parser.add_argument("certificate", nargs="?", help="Path to certificate.json for replay")
    verify_parser.add_argument("--cobol", help="Path to COBOL source file")
    verify_parser.add_argument("--copybooks", help="Path to copybooks directory")
    verify_parser.add_argument("--java", help="Path to Java source file")
    verify_parser.add_argument("--schema", help="Path to schema.json")
    verify_parser.add_argument("--cases", type=int, default=2000, help="Number of test cases (default: 2000)")
    verify_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    verify_parser.add_argument("--tie-share", type=float, default=0.06, help="Fraction of cases that are rounding ties (default: 0.06)")
    verify_parser.add_argument("--timings", action="store_true", help="Print per-step timings")
    
    # traps command
    traps_parser = subparsers.add_parser("traps", help="Run trap catalog")
    traps_parser.add_argument("--cases", type=int, default=2000, help="Number of test cases (default: 2000)")
    traps_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    
    args = parser.parse_args()
    
    if args.command == "verify":
        # Check for certificate replay (D-36)
        if args.certificate and args.certificate.endswith('.json') and not args.cobol:
            # Certificate replay mode
            from coroner.certificate import replay_certificate
            
            try:
                result = replay_certificate(args.certificate)
                
                # Print warnings to stderr
                for warning in result.warnings:
                    print(f"Warning: {warning}", file=sys.stderr)
                
                # Print result
                if result.valid:
                    print("Certificate: VALID")
                    print(f"{result.verdict.status}: {result.verdict.sub_label}")
                    print(f"Cases: {result.cases_total}")
                    print(f"Divergences: {result.cases_divergent}")
                    print(f"Paragraph coverage {result.paragraph_coverage_reached}/{result.paragraph_coverage_total}")
                    print(f"Branch coverage (Coroner definition) {result.branch_coverage_reached}/{result.branch_coverage_total}")
                    print(f"Replayed offline from {result.cases_file}")
                    
                    # Exit code: 0 for ALIVE, 1 for ZOMBIE
                    return 0 if result.verdict.status == "ALIVE" else 1
                else:
                    print(f"Certificate: INVALID: {result.reason}")
                    return 3
                    
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                return 2
        
        # Run mode
        if not all([args.cobol, args.copybooks, args.java, args.schema]):
            print("Error: --cobol, --copybooks, --java, and --schema are required for run mode", file=sys.stderr)
            parser.print_help()
            return 2
        
        exit_code = verify_command(
            args.cobol, args.copybooks, args.java, args.schema,
            cases=args.cases, seed=args.seed, tie_share=args.tie_share,
            timings=args.timings
        )
        return exit_code
    
    elif args.command == "traps":
        # Run trap catalog
        from coroner.traps import run_catalog, write_catalog_files
        
        try:
            catalog = run_catalog(seed=args.seed, cases=args.cases)
            write_catalog_files(catalog)
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 2
    
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
