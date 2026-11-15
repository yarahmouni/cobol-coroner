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


def verify_command(cobol: str, copybooks: str, java: str, schema: str, 
                   cases: int = 2000, seed: int = 42, timings: bool = False) -> int:
    """
    Orchestrate the full verification pipeline.
    
    Steps:
    1. Validate inputs (existence, size limits)
    2. Parse schema and COBOL structure
    3. Generate test cases
    4. Collect inputs and compute run_id
    5. Compile reference and coverage COBOL, and Java
    6. Run batch executions (reference COBOL and Java)
    7. Run instrumented COBOL for coverage
    8. Compare outputs
    9. Compute verdict
    10. Generate reports (coverage, failure if ZOMBIE)
    11. Store all results
    
    Prints:
    - Verdict status and sub_label
    - Paragraph coverage X/Y
    - Branch coverage (Coroner definition) X/Y
    - Validated under GnuCOBOL 3.x
    - Run: runs/<run_id>
    - Duration: N.N s
    - With --timings: one line per step
    
    Args:
        cobol: Path to COBOL source file
        copybooks: Path to copybooks directory
        java: Path to Java source file
        schema: Path to schema.json
        cases: Number of test cases to generate (default 2000)
        seed: Random seed (default 42)
        timings: Print per-step timings (default False)
        
    Returns:
        Exit code: 0 (ALIVE), 1 (ZOMBIE), 2 (error)
    """
    start_time = time.time()
    step_times = {}
    
    def record_step(name: str, start: float):
        elapsed = time.time() - start
        step_times[name] = elapsed
        if timings:
            print(f"  {name}: {elapsed:.2f} s")
    
    try:
        # Step 1: Validate inputs
        step_start = time.time()
        validate_inputs(cobol, copybooks, java, schema)
        record_step("Validate inputs", step_start)
        
        # Step 2: Parse schema and structure
        step_start = time.time()
        schema_obj = load_schema(schema)
        cobol_structure = parse_cobol_structure(cobol, copybooks)
        record_step("Parse schema and structure", step_start)
        
        # Step 3: Generate cases
        step_start = time.time()
        cases_csv_path = generate_cases(schema_obj, cobol_structure, seed, cases)
        record_step(f"Generate {cases} cases", step_start)
        
        # Step 4: Collect inputs and compute run_id
        step_start = time.time()
        inputs_data = collect_inputs(cobol, copybooks, java, schema, 
                                      cases_csv_path, seed, cases)
        run_id = compute_run_id(inputs_data)
        run_dir = f"runs/{run_id}"
        os.makedirs(run_dir, exist_ok=True)
        record_step("Collect inputs and compute run_id", step_start)
        
        # Create build directories
        build_dir = f"build/{run_id}"
        os.makedirs(build_dir, exist_ok=True)
        os.makedirs(f"{build_dir}/coverage", exist_ok=True)
        os.makedirs(f"{build_dir}/java", exist_ok=True)
        
        # Extract program name from schema
        program_name = schema_obj.program_name
        
        # Step 5: Compile COBOL reference
        step_start = time.time()
        cobol_binary = f"{build_dir}/{program_name}"
        compile_cobol(cobol, copybooks, cobol_binary, [])
        record_step("Compile COBOL reference", step_start)
        
        # Step 5b: Compile COBOL coverage
        step_start = time.time()
        cobol_coverage_binary = f"{build_dir}/coverage/{program_name}"
        compile_cobol(cobol, copybooks, cobol_coverage_binary, ["-ftraceall"])
        record_step("Compile COBOL coverage", step_start)
        
        # Step 5c: Compile Java
        step_start = time.time()
        compile_java(java, f"{build_dir}/java")
        record_step("Compile Java", step_start)
        
        # Extract Java class name from file
        java_class = Path(java).stem
        
        # Step 6: Run reference COBOL
        step_start = time.time()
        cobol_output = f"{build_dir}/cobol_output.csv"
        cobol_result = run_cobol(cobol_binary, cases_csv_path, cobol_output)
        record_step("Run COBOL reference", step_start)
        
        # Step 6b: Run Java
        step_start = time.time()
        java_output = f"{build_dir}/java_output.csv"
        java_result = run_java(java_class, f"{build_dir}/java", cases_csv_path, java_output)
        record_step("Run Java", step_start)
        
        # Step 7: Run instrumented COBOL for coverage
        step_start = time.time()
        trace_file = f"{run_dir}/coverage_trace.txt"
        coverage_output = f"{build_dir}/coverage_output.csv"
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
        coverage_report = compute_coverage(trace, cobol_structure, cobol, copybooks)
        
        # Store coverage report
        import json
        with open(f"{run_dir}/coverage_report.json", 'w') as f:
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
            import csv
            input_rows = {}
            with open(cases_csv_path, 'r') as f:
                reader = csv.DictReader(f)
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
                cobol_coverage_binary, java_class, f"{build_dir}/java",
                run_dir
            )
            
            # Store failure report
            with open(f"{run_dir}/failure_report.json", 'w') as f:
                json.dump({
                    "case_id": failure_report.case_id,
                    "input_row": failure_report.input_row,
                    "cobol_output": failure_report.cobol_output,
                    "java_output": failure_report.java_output,
                    "divergent_fields": failure_report.divergent_fields,
                    "cobol_return_code": failure_report.cobol_return_code,
                    "java_return_code": failure_report.java_return_code,
                    "executed_lines": [(src, line) for src, line in failure_report.executed_lines]
                }, f, indent=2)
            
            # Generate JUnit regression test
            from coroner.diag.junit import generate_junit_test
            generate_junit_test(
                minimal_case,
                input_rows[minimal_case.case_id],
                failure_report.cobol_output,
                java_class,
                schema_obj,
                f"{run_dir}/ZombieRegressionTest.java"
            )
        
        record_step("Generate reports", step_start)
        
        # Step 11: Store results
        step_start = time.time()
        store_inputs(run_dir, inputs_data)
        store_comparison(run_dir, comparison)
        store_verdict(run_dir, verdict)
        
        # Copy generated cases to run directory
        import shutil
        shutil.copy(cases_csv_path, f"{run_dir}/generated_cases.csv")
        
        record_step("Store results", step_start)
        
        # Print output
        total_time = time.time() - start_time
        print(f"{verdict.status}: {verdict.sub_label}")
        print(f"Paragraph coverage {coverage_report.paragraphs_covered}/{coverage_report.paragraphs_total}")
        print(f"Branch coverage (Coroner definition) {coverage_report.branches_covered}/{coverage_report.branches_total}")
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
    verify_parser.add_argument("--cobol", required=True, help="Path to COBOL source file")
    verify_parser.add_argument("--copybooks", required=True, help="Path to copybooks directory")
    verify_parser.add_argument("--java", required=True, help="Path to Java source file")
    verify_parser.add_argument("--schema", required=True, help="Path to schema.json")
    verify_parser.add_argument("--cases", type=int, default=2000, help="Number of test cases (default: 2000)")
    verify_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    verify_parser.add_argument("--timings", action="store_true", help="Print per-step timings")
    
    args = parser.parse_args()
    
    if args.command == "verify":
        # Check for certificate replay (D-36)
        if args.cobol.endswith('.json') and not any([
            args.copybooks != "verify",  # Only cobol arg provided
            args.java != "verify",
            args.schema != "verify"
        ]):
            # Single .json argument pattern
            print("Error: certificate replay is not implemented yet", file=sys.stderr)
            return 2
        
        exit_code = verify_command(
            args.cobol, args.copybooks, args.java, args.schema,
            cases=args.cases, seed=args.seed, timings=args.timings
        )
        return exit_code
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
