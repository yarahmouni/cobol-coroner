"""Certificate generation and replay for Coroner."""
import json
import os
import sys
import hashlib
import csv
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from coroner.verdict import Verdict
from coroner.parse.schema import load_schema
from coroner.parse.copybook import parse_cobol_structure
from coroner.run import compile_cobol, compile_java, run_cobol, run_java, run_cobol_instrumented
from coroner.compare import compare_outputs
from coroner.verdict import compute_verdict
from coroner.parse.trace import parse_trace_counts
from coroner.diag.coverage import compute_coverage
from coroner.diag.minimal_case import select_minimal_case
from coroner.diag.report import generate_failure_report
from coroner.diag.junit import generate_junit_test


@dataclass
class ReplayResult:
    """Result of certificate replay validation."""
    valid: bool
    reason: str  # empty if valid, error message if invalid
    verdict: Optional[Verdict]
    cases_total: int
    cases_divergent: int
    paragraph_coverage_reached: int
    paragraph_coverage_total: int
    branch_coverage_reached: int
    branch_coverage_total: int
    cases_file: str
    warnings: list[str]


def _file_sha256(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def compute_certificate_sha256(cert: dict) -> str:
    """
    Compute SHA-256 hash of certificate content.
    
    Uses canonical JSON representation (sorted keys, no spaces after separators)
    of all fields except certificate_sha256.
    
    Args:
        cert: Certificate dictionary (must not contain certificate_sha256 key)
        
    Returns:
        Hex digest string
    """
    canonical_json = json.dumps(cert, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


def _make_relative_path(file_path: str) -> str:
    """
    Make path relative to repository root if inside it.
    Otherwise return absolute path.
    """
    try:
        abs_path = os.path.abspath(file_path)
        cwd = os.path.abspath(os.getcwd())
        
        # Check if file is under cwd
        if os.path.commonpath([abs_path, cwd]) == cwd:
            return os.path.relpath(abs_path, cwd)
        else:
            return abs_path
    except (ValueError, TypeError):
        # Can't compute common path, use absolute
        return os.path.abspath(file_path)


def generate_certificate(
    run_id: str,
    cobol_file: str,
    copybook_dir: str,
    java_file: str,
    schema_file: str,
    base_dir: str = "."
) -> None:
    """
    Generate certificate.json after a run.
    
    Loads inputs.json, verdict.json, coverage_report.json from runs/<run_id>/.
    When ZOMBIE, loads failure_report.json for minimal_case_id and divergent_fields.
    Constructs statement with verdict sub_label.
    Computes certificate_sha256 from canonical JSON of all other fields.
    Writes to runs/<run_id>/certificate.json with sorted keys and LF.
    
    Args:
        run_id: Run identifier
        cobol_file: Path to COBOL source file
        copybook_dir: Path to copybook directory
        java_file: Path to Java source file
        schema_file: Path to schema.json
        base_dir: Base directory for runs/ (default current directory)
        
    Raises:
        FileNotFoundError: If required run files not found
        ValueError: If required fields missing
    """
    run_dir = str(Path(base_dir) / "runs" / run_id)
    
    # Load run files
    with open(f"{run_dir}/inputs.json", 'r') as f:
        inputs = json.load(f)
    
    with open(f"{run_dir}/verdict.json", 'r') as f:
        verdict_data = json.load(f)
    
    with open(f"{run_dir}/coverage_report.json", 'r') as f:
        coverage = json.load(f)
    
    # Load failure report if ZOMBIE
    minimal_case_id = None
    divergent_fields = None
    if verdict_data["status"] == "ZOMBIE":
        with open(f"{run_dir}/failure_report.json", 'r') as f:
            failure = json.load(f)
            minimal_case_id = failure["case_id"]
            # divergent_fields is now a list of dicts
            divergent_fields = []
            for field_info in failure["divergent_fields"]:
                if isinstance(field_info, dict):
                    # Extract field_name from structured format
                    # For row-level divergences, use output_key columns (excluding case id)
                    if "output_key" in field_info:
                        output_key = field_info.get("output_key", {})
                        # Format as "COLUMN=value" for each non-case-id column
                        key_parts = [f"{k}={v}" for k, v in output_key.items() if k != "CASE-ID"]
                        field_name = ", ".join(key_parts) if key_parts else "<row>"
                    else:
                        field_name = field_info.get("field_name", "<unknown>")
                    divergent_fields.append(field_name)
                else:
                    # Legacy format (shouldn't happen)
                    divergent_fields.append(field_info[0])
    
    # Construct statement
    sub_label = verdict_data["sub_label"]
    statement = f"Reproducible run record: {sub_label}. Validated under GnuCOBOL 3.x. This is not a formal proof of equivalence."
    
    # Build certificate (all fields except certificate_sha256)
    cert = {
        "certificate_format": 1,
        "title": "Coroner Certificate",
        "statement": statement,
        
        # From inputs.json
        "cobol_file_sha256": inputs["cobol_source_sha256"],
        "copybook_hashes": {cb["name"]: cb["sha256"] for cb in inputs["copybook_hashes"]},
        "java_file_sha256": inputs["java_source_sha256"],
        "schema_file_sha256": inputs["schema_sha256"],
        "cases_file_sha256": inputs["cases_file_sha256"],
        "cases_file_encoding": inputs["cases_file_encoding"],
        "cases_file_line_ending": inputs["cases_file_line_ending"],
        "case_count": inputs["case_count"],
        "random_seed": inputs["random_seed"],
        "cobc_flags": inputs.get("cobc_flags", []),
        "python_version": inputs["python_version"],
        "cobc_version": inputs["cobc_version"],
        "javac_version": inputs["javac_version"],
        "java_version": inputs["java_version"],
        "coroner_version": inputs["coroner_version"],
        "comparison_engine_sha256": inputs["comparison_engine_sha256"],
        "timestamp": inputs["timestamp"],
        
        # File paths (relative when inside repository)
        "cobol_file": _make_relative_path(cobol_file),
        "copybook_dir": _make_relative_path(copybook_dir),
        "java_file": _make_relative_path(java_file),
        "schema_file": _make_relative_path(schema_file),
        "cases_file": _make_relative_path(f"{run_dir}/generated_cases.csv"),
        
        # Verdict
        "status": verdict_data["status"],
        "sub_label": verdict_data["sub_label"],
        "cases_total": verdict_data["cases_total"],
        "cases_divergent": verdict_data["cases_divergent"],
        "run_return_codes": {
            "cobol": verdict_data["run_return_codes"][0],
            "java": verdict_data["run_return_codes"][1]
        },
        
        # Coverage
        "paragraph_coverage_reached": coverage["paragraphs_covered"],
        "paragraph_coverage_total": coverage["paragraphs_total"],
        "branch_coverage_reached": coverage["branches_covered"],
        "branch_coverage_total": coverage["branches_total"],
        
        # ZOMBIE only
        "minimal_case_id": minimal_case_id,
        "divergent_fields": divergent_fields
    }
    
    # Compute certificate_sha256
    cert_hash = compute_certificate_sha256(cert)
    cert["certificate_sha256"] = cert_hash
    
    # Write certificate
    cert_path = f"{run_dir}/certificate.json"
    with open(cert_path, 'w', encoding='utf-8') as f:
        json.dump(cert, f, indent=2, sort_keys=True)
        f.write('\n')


def replay_certificate(certificate_path: str) -> ReplayResult:
    """
    Replay and validate a certificate offline.
    
    Steps:
    1. Load certificate and verify content hash
    2. Verify all file hashes (COBOL, copybooks, Java, schema, cases)
    3. Re-run engine on stored cases file
    4. Compare replayed metrics against recorded values
    5. Check tool versions (warnings only)
    
    Args:
        certificate_path: Path to certificate.json
        
    Returns:
        ReplayResult with validation status, verdict, coverage, warnings
    """
    warnings = []
    
    try:
        # Step 1: Load and verify content hash
        with open(certificate_path, 'r') as f:
            cert = json.load(f)
        
        recorded_hash = cert.pop("certificate_sha256")
        computed_hash = compute_certificate_sha256(cert)
        
        if computed_hash != recorded_hash:
            return ReplayResult(
                valid=False,
                reason="certificate content was modified",
                verdict=None,
                cases_total=0,
                cases_divergent=0,
                paragraph_coverage_reached=0,
                paragraph_coverage_total=0,
                branch_coverage_reached=0,
                branch_coverage_total=0,
                cases_file="",
                warnings=[]
            )
        
        # Step 2: Verify file hashes
        cobol_file = cert["cobol_file"]
        if not os.path.isfile(cobol_file):
            return ReplayResult(
                valid=False, reason=f"COBOL file not found: {cobol_file}",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        cobol_hash = _file_sha256(cobol_file)
        if cobol_hash != cert["cobol_file_sha256"]:
            return ReplayResult(
                valid=False, reason="COBOL file hash mismatch",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        # Verify copybooks
        copybook_dir = cert["copybook_dir"]
        for cb_name, cb_hash in cert["copybook_hashes"].items():
            cb_path = os.path.join(copybook_dir, cb_name)
            if not os.path.isfile(cb_path):
                return ReplayResult(
                    valid=False, reason=f"copybook not found: {cb_name}",
                    verdict=None, cases_total=0, cases_divergent=0,
                    paragraph_coverage_reached=0, paragraph_coverage_total=0,
                    branch_coverage_reached=0, branch_coverage_total=0,
                    cases_file="", warnings=[]
                )
            computed = _file_sha256(cb_path)
            if computed != cb_hash:
                return ReplayResult(
                    valid=False, reason=f"copybook hash mismatch for {cb_name}",
                    verdict=None, cases_total=0, cases_divergent=0,
                    paragraph_coverage_reached=0, paragraph_coverage_total=0,
                    branch_coverage_reached=0, branch_coverage_total=0,
                    cases_file="", warnings=[]
                )
        
        # Verify Java file
        java_file = cert["java_file"]
        if not os.path.isfile(java_file):
            return ReplayResult(
                valid=False, reason=f"Java file not found: {java_file}",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        java_hash = _file_sha256(java_file)
        if java_hash != cert["java_file_sha256"]:
            return ReplayResult(
                valid=False, reason="Java file hash mismatch",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        # Verify schema file
        schema_file = cert["schema_file"]
        if not os.path.isfile(schema_file):
            return ReplayResult(
                valid=False, reason=f"schema file not found: {schema_file}",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        schema_hash = _file_sha256(schema_file)
        if schema_hash != cert["schema_file_sha256"]:
            return ReplayResult(
                valid=False, reason="schema file hash mismatch",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        # Verify cases file
        cases_file = cert["cases_file"]
        if not os.path.isfile(cases_file):
            return ReplayResult(
                valid=False, reason=f"cases file not found: {cases_file}",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        cases_hash = _file_sha256(cases_file)
        if cases_hash != cert["cases_file_sha256"]:
            return ReplayResult(
                valid=False, reason="cases file hash mismatch",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        # Step 3: Re-run engine
        schema_obj = load_schema(schema_file)
        cobol_structure = parse_cobol_structure(cobol_file, copybook_dir)
        
        # Get cobc_flags from certificate (default empty list)
        cobol_flags = cert.get("cobc_flags", [])
        
        # Create temporary build directory for replay
        import tempfile
        with tempfile.TemporaryDirectory(prefix="coroner_replay_") as replay_build:
            program_name = schema_obj.program_name
            java_class = Path(java_file).stem
            
            # Compile COBOL reference
            cobol_binary = f"{replay_build}/{program_name}"
            compile_cobol(cobol_file, copybook_dir, cobol_binary, cobol_flags, replay_build)
            
            # Compile COBOL coverage
            os.makedirs(f"{replay_build}/coverage", exist_ok=True)
            cobol_coverage_binary = f"{replay_build}/coverage/{program_name}"
            compile_cobol(cobol_file, copybook_dir, cobol_coverage_binary, cobol_flags + ["-ftraceall"], replay_build)
            
            # Compile Java
            os.makedirs(f"{replay_build}/java", exist_ok=True)
            compile_java(java_file, f"{replay_build}/java", replay_build)
            
            # Run COBOL reference
            cobol_output = f"{replay_build}/cobol_output.csv"
            was_killed = False
            try:
                cobol_result = run_cobol(cobol_binary, cases_file, cobol_output)
            except RuntimeError as e:
                if "timed out" in str(e):
                    was_killed = True
                    # Create dummy result for validation
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
            is_valid, error_reason = validate_reference_output(cobol_result, cases_file, was_killed)
            if not is_valid:
                # Reference did not run during replay
                return ReplayResult(
                    valid=False,
                    reason=f"reference did not run during replay: {error_reason}",
                    verdict=None, cases_total=0, cases_divergent=0,
                    paragraph_coverage_reached=0, paragraph_coverage_total=0,
                    branch_coverage_reached=0, branch_coverage_total=0,
                    cases_file="", warnings=[]
                )
            
            # Run Java
            java_output = f"{replay_build}/java_output.csv"
            java_result = run_java(java_class, f"{replay_build}/java", cases_file, java_output)
            
            # Run instrumented COBOL for coverage
            trace_file = f"{replay_build}/coverage_trace.txt"
            coverage_output = f"{replay_build}/coverage_output.csv"
            run_cobol_instrumented(cobol_coverage_binary, cases_file, coverage_output, trace_file)
            
            # Compare outputs
            comparison = compare_outputs(
                cobol_result.output_path, java_result.output_path,
                schema_obj, cobol_result.return_code, java_result.return_code
            )
            
            # Compute verdict
            verdict = compute_verdict(comparison)
            
            # Compute coverage
            trace = parse_trace_counts(trace_file)
            coverage_report = compute_coverage(trace, cobol_structure, cobol_file, copybook_dir)
        
        # Step 4: Compare metrics
        if verdict.status != cert["status"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (status: expected {cert['status']}, got {verdict.status})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        if verdict.cases_total != cert["cases_total"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (cases_total: expected {cert['cases_total']}, got {verdict.cases_total})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        if verdict.cases_divergent != cert["cases_divergent"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (cases_divergent: expected {cert['cases_divergent']}, got {verdict.cases_divergent})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        cobol_rc, java_rc = verdict.run_return_codes
        if cobol_rc != cert["run_return_codes"]["cobol"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (cobol_return_code: expected {cert['run_return_codes']['cobol']}, got {cobol_rc})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        if java_rc != cert["run_return_codes"]["java"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (java_return_code: expected {cert['run_return_codes']['java']}, got {java_rc})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        if coverage_report.paragraphs_covered != cert["paragraph_coverage_reached"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (paragraph_coverage_reached: expected {cert['paragraph_coverage_reached']}, got {coverage_report.paragraphs_covered})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        if coverage_report.paragraphs_total != cert["paragraph_coverage_total"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (paragraph_coverage_total: expected {cert['paragraph_coverage_total']}, got {coverage_report.paragraphs_total})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        if coverage_report.branches_covered != cert["branch_coverage_reached"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (branch_coverage_reached: expected {cert['branch_coverage_reached']}, got {coverage_report.branches_covered})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        if coverage_report.branches_total != cert["branch_coverage_total"]:
            return ReplayResult(
                valid=False, reason=f"replay mismatch (branch_coverage_total: expected {cert['branch_coverage_total']}, got {coverage_report.branches_total})",
                verdict=None, cases_total=0, cases_divergent=0,
                paragraph_coverage_reached=0, paragraph_coverage_total=0,
                branch_coverage_reached=0, branch_coverage_total=0,
                cases_file="", warnings=[]
            )
        
        # Step 5: Check tool versions (warnings only)
        from coroner.store import collect_inputs
        # Get current versions by collecting inputs
        temp_inputs = collect_inputs(
            cobol_file, copybook_dir, java_file, schema_file,
            cases_file, cert["random_seed"], cert["case_count"],
            cobol_flags if cobol_flags else None
        )
        
        if temp_inputs["python_version"] != cert["python_version"]:
            warnings.append(f"python version differs (recorded: {cert['python_version']}, current: {temp_inputs['python_version']})")
        
        if temp_inputs["cobc_version"] != cert["cobc_version"]:
            warnings.append(f"cobc version differs (recorded: {cert['cobc_version']}, current: {temp_inputs['cobc_version']})")
        
        if temp_inputs["javac_version"] != cert["javac_version"]:
            warnings.append(f"javac version differs (recorded: {cert['javac_version']}, current: {temp_inputs['javac_version']})")
        
        if temp_inputs["java_version"] != cert["java_version"]:
            warnings.append(f"java version differs (recorded: {cert['java_version']}, current: {temp_inputs['java_version']})")
        
        if temp_inputs["coroner_version"] != cert["coroner_version"]:
            warnings.append(f"coroner version differs (recorded: {cert['coroner_version']}, current: {temp_inputs['coroner_version']})")
        
        if temp_inputs["comparison_engine_sha256"] != cert["comparison_engine_sha256"]:
            warnings.append(f"comparison engine differs (recorded: {cert['comparison_engine_sha256']}, current: {temp_inputs['comparison_engine_sha256']})")
        
        # Step 6: Return valid result
        return ReplayResult(
            valid=True,
            reason="",
            verdict=verdict,
            cases_total=verdict.cases_total,
            cases_divergent=verdict.cases_divergent,
            paragraph_coverage_reached=coverage_report.paragraphs_covered,
            paragraph_coverage_total=coverage_report.paragraphs_total,
            branch_coverage_reached=coverage_report.branches_covered,
            branch_coverage_total=coverage_report.branches_total,
            cases_file=cases_file,
            warnings=warnings
        )
        
    except FileNotFoundError as e:
        return ReplayResult(
            valid=False, reason=f"file not found: {e}",
            verdict=None, cases_total=0, cases_divergent=0,
            paragraph_coverage_reached=0, paragraph_coverage_total=0,
            branch_coverage_reached=0, branch_coverage_total=0,
            cases_file="", warnings=[]
        )
    except json.JSONDecodeError as e:
        return ReplayResult(
            valid=False, reason=f"invalid certificate JSON: {e}",
            verdict=None, cases_total=0, cases_divergent=0,
            paragraph_coverage_reached=0, paragraph_coverage_total=0,
            branch_coverage_reached=0, branch_coverage_total=0,
            cases_file="", warnings=[]
        )
    except KeyError as e:
        return ReplayResult(
            valid=False, reason=f"missing field in certificate: {e}",
            verdict=None, cases_total=0, cases_divergent=0,
            paragraph_coverage_reached=0, paragraph_coverage_total=0,
            branch_coverage_reached=0, branch_coverage_total=0,
            cases_file="", warnings=[]
        )
    except Exception as e:
        return ReplayResult(
            valid=False, reason=f"replay error: {e}",
            verdict=None, cases_total=0, cases_divergent=0,
            paragraph_coverage_reached=0, paragraph_coverage_total=0,
            branch_coverage_reached=0, branch_coverage_total=0,
            cases_file="", warnings=[]
        )
