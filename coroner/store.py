"""Run storage module for Coroner."""
import json
import os
import tempfile
from pathlib import Path
import hashlib
import platform
import subprocess
from datetime import datetime, timezone
import importlib.metadata

from coroner.verdict import Verdict
from coroner.compare import ComparisonResult
from coroner.run import _build_subprocess_env


def compute_run_id(inputs: dict) -> str:
    """
    Compute deterministic run_id from inputs.
    Returns first 12 hex chars of SHA-256.
    
    Ignores timestamp field to ensure deterministic run_id
    for same logical inputs.
    
    Args:
        inputs: The inputs dict (from collect_inputs)
        
    Returns:
        12-character hex run_id
    """
    hasher = hashlib.sha256()
    
    # Extract relevant fields, excluding timestamp
    data = {
        "cobol_source_sha256": inputs["cobol_source_sha256"],
        "java_source_sha256": inputs["java_source_sha256"],
        "schema_sha256": inputs["schema_sha256"],
        "copybook_hashes": sorted(
            [(cb["name"], cb["sha256"]) for cb in inputs["copybook_hashes"]]
        ),
        "seed": inputs["seed"],
        "case_count": inputs["case_count"],
        "tool_versions": {
            "cobc": inputs["cobc_version"],
            "javac": inputs["javac_version"],
            "java": inputs["java_version"],
            "python": inputs["python_version"],
            "coroner": inputs["coroner_version"]
        }
    }
    
    # Include cobc_flags if present (D-36: part of certificate content)
    if "cobc_flags" in inputs:
        data["cobc_flags"] = inputs["cobc_flags"]
    
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
    hasher.update(canonical.encode('utf-8'))
    
    return hasher.hexdigest()[:12]


def collect_inputs(
    cobol_source: str,
    copybook_dir: str,
    java_source: str,
    schema_path: str,
    cases_file: str,
    seed: int,
    case_count: int,
    cobc_flags: list[str] | None = None
) -> dict:
    """
    Collect all metadata for inputs.json.
    
    Returns dict with: cobol_source_sha256, java_source_sha256, schema_sha256,
    copybook_hashes, seed, random_seed, case_count, cases_file_sha256,
    cases_file_encoding, cases_file_line_ending, python_version,
    cobc_version, javac_version, java_version, coroner_version,
    comparison_engine_sha256, timestamp, and optionally cobc_flags.
    
    Args:
        cobol_source: Path to COBOL source file
        copybook_dir: Path to copybook directory
        java_source: Path to Java source file
        schema_path: Path to schema.json
        cases_file: Path to generated cases CSV
        seed: Random seed
        case_count: Number of cases
        cobc_flags: Optional list of additional COBOL compiler flags
        
    Returns:
        Complete inputs.json dict
        
    Raises:
        ValueError: If cases_file contains CR (not LF line endings)
    """
    # Compute file SHA-256 hashes
    def file_sha256(path: str) -> str:
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    
    cobol_hash = file_sha256(cobol_source)
    java_hash = file_sha256(java_source)
    schema_hash = file_sha256(schema_path)
    cases_hash = file_sha256(cases_file)
    
    # Collect copybook hashes (sorted by name)
    copybook_hashes = []
    copybook_path = Path(copybook_dir)
    if copybook_path.exists() and copybook_path.is_dir():
        for pattern in ['*.cpy', '*.cbl']:
            for cb_file in sorted(copybook_path.glob(pattern)):
                copybook_hashes.append({
                    "name": cb_file.name,
                    "sha256": file_sha256(str(cb_file))
                })
    
    # Verify cases file line ending (must be LF, no CR)
    with open(cases_file, 'rb') as f:
        cases_bytes = f.read()
        if b'\r' in cases_bytes:
            raise ValueError(f"Cases file {cases_file} contains CR; only LF line endings are allowed")
    
    # Python version
    python_version = platform.python_version()
    
    # Tool versions (first line from --version output)
    def get_tool_version(cmd: list[str]) -> str:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5.0,
                env=_build_subprocess_env()
            )
            # Get first non-empty line from stdout or stderr
            output = result.stdout or result.stderr
            for line in output.split('\n'):
                line = line.strip()
                if line:
                    return line
            return "unknown"
        except Exception:
            return "unknown"
    
    cobc_version = get_tool_version(['cobc', '--version'])
    javac_version = get_tool_version(['javac', '-version'])
    java_version = get_tool_version(['java', '-version'])
    
    # Coroner version
    try:
        coroner_version = importlib.metadata.version("cobol-coroner")
    except importlib.metadata.PackageNotFoundError:
        coroner_version = "dev"
    
    # Comparison engine SHA-256
    import coroner.compare
    compare_module_path = Path(coroner.compare.__file__)
    comparison_engine_sha256 = file_sha256(str(compare_module_path))
    
    # Timestamp UTC ISO 8601
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    result = {
        "cobol_source_sha256": cobol_hash,
        "java_source_sha256": java_hash,
        "schema_sha256": schema_hash,
        "copybook_hashes": copybook_hashes,
        "seed": seed,
        "random_seed": seed,
        "case_count": case_count,
        "cases_file_sha256": cases_hash,
        "cases_file_encoding": "utf-8",
        "cases_file_line_ending": "LF",
        "python_version": python_version,
        "cobc_version": cobc_version,
        "javac_version": javac_version,
        "java_version": java_version,
        "coroner_version": coroner_version,
        "comparison_engine_sha256": comparison_engine_sha256,
        "timestamp": timestamp
    }
    
    if cobc_flags:
        result["cobc_flags"] = cobc_flags
    
    return result


def store_inputs(run_dir: str, inputs_data: dict) -> None:
    """
    Write inputs.json with all metadata.
    Fields: cobol_source_sha256, java_source_sha256, schema_sha256,
    copybook_hashes, seed, random_seed, case_count, cases_file_sha256,
    cases_file_encoding, cases_file_line_ending, python_version,
    cobc_version, javac_version, java_version, coroner_version,
    comparison_engine_sha256, timestamp.
    """
    os.makedirs(run_dir, exist_ok=True)
    
    inputs_path = os.path.join(run_dir, "inputs.json")
    with open(inputs_path, 'w', encoding='utf-8') as f:
        json.dump(inputs_data, f, indent=2, sort_keys=True)
        f.write('\n')


def store_verdict(run_dir: str, verdict: Verdict) -> None:
    """
    Atomically write verdict.json.
    Write to temp file in same directory, then rename.
    """
    os.makedirs(run_dir, exist_ok=True)
    
    verdict_data = {
        "status": verdict.status,
        "sub_label": verdict.sub_label,
        "cases_total": verdict.cases_total,
        "cases_divergent": verdict.cases_divergent,
        "run_return_codes": verdict.run_return_codes,
        "validation_notice": verdict.validation_notice
    }
    
    # Add exposure fields if present
    if verdict.exposure_sum is not None:
        verdict_data["exposure_sum"] = str(verdict.exposure_sum)
        verdict_data["exposure_max"] = str(verdict.exposure_max)
        verdict_data["affected_branches"] = verdict.affected_branches
        verdict_data["grand_total_matches"] = verdict.grand_total_matches
    
    verdict_path = os.path.join(run_dir, "verdict.json")
    
    # Atomic write: temp file then rename
    fd, temp_path = tempfile.mkstemp(dir=run_dir, prefix=".verdict_", suffix=".json.tmp")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(verdict_data, f, indent=2, sort_keys=True)
            f.write('\n')
        os.replace(temp_path, verdict_path)
    except:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except:
            pass
        raise


def store_comparison(run_dir: str, comparison: ComparisonResult) -> None:
    """Write comparison_results.json."""
    os.makedirs(run_dir, exist_ok=True)
    
    cases_data = []
    for case in comparison.cases:
        case_data = {
            "case_id": case.case_id,
            "divergent": case.divergent,
            "divergent_fields": [
                {"field_name": fname, "cobol_value": cval, "java_value": jval}
                for fname, cval, jval in case.divergent_fields
            ]
        }
        cases_data.append(case_data)
    
    comparison_data = {
        "cases": cases_data,
        "run_return_codes": comparison.run_return_codes,
        "row_count_match": comparison.row_count_match,
        "total_divergent": comparison.total_divergent
    }
    
    comparison_path = os.path.join(run_dir, "comparison_results.json")
    with open(comparison_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_data, f, indent=2, sort_keys=True)
        f.write('\n')
