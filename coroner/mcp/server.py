"""MCP server for Coroner with 7 tools."""
import json
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# Initialize server using high-level MCPServer API
server = MCPServer(
    name="coroner",
    title="COBOL Coroner",
    description="Independent regression auditor for COBOL-to-Java migrations",
    version="0.2.0"
)

# Determine repository root
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()


def validate_run_id(run_id: str) -> None:
    """Validate run_id format.
    
    Args:
        run_id: Run identifier to validate
        
    Raises:
        ToolError: If run_id is not 12 lowercase hex characters
    """
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise ToolError(f"Invalid run_id: must be 12 lowercase hex characters, got {run_id!r}")


def validate_path(path_str: str) -> Path:
    """Validate and resolve a path, ensuring it's inside the repository.
    
    Args:
        path_str: Path string to validate
        
    Returns:
        Resolved Path object
        
    Raises:
        ToolError: If path escapes the repository
    """
    # Handle relative and absolute paths
    if Path(path_str).is_absolute():
        path = Path(path_str).resolve()
    else:
        path = Path(REPO_ROOT, path_str).resolve()
    
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        raise ToolError(f"Path outside repository: {path_str}")
    return path


@server.tool(description="Run differential verification on COBOL and Java programs")
def run_differential_check(
    cobol: str,
    copybooks: str,
    java: str,
    schema: str,
    cases: int = 2000,
    seed: int = 42
) -> dict:
    """Run differential check and return verdict summary.
    
    Args:
        cobol: Path to COBOL source file
        copybooks: Path to copybooks directory
        java: Path to Java source file
        schema: Path to schema.json
        cases: Number of test cases (default 2000)
        seed: Random seed (default 42)
        
    Returns:
        Dictionary with run_id, status, coverage and certificate path
        
    Raises:
        ToolError: If paths are outside repository or parameters are invalid
    """
    import sys
    from coroner.cli import run_verify
    
    # Validate and resolve paths
    cobol_path = str(validate_path(cobol))
    copybooks_path = str(validate_path(copybooks))
    java_path = str(validate_path(java))
    schema_path = str(validate_path(schema))
    
    # Validate parameters
    if not (1 <= cases <= 10000):
        raise ToolError(f"cases must be between 1 and 10000, got {cases}")
    if seed < 0:
        raise ToolError(f"seed must be non-negative, got {seed}")
    
    # Run verification, catching SystemExit for broken reference
    try:
        verdict, run_dir = run_verify(cobol_path, java_path, schema_path, copybooks_path, cases, seed, timings=False, base_dir=str(REPO_ROOT))
    except SystemExit as e:
        if e.code == 2:
            # Broken reference: read error from run directory if available
            # We need to find the run_id to read the error file
            # Since run_verify exited early, we need to reconstruct or read stderr
            raise ToolError("ERROR: reference did not run. Check COBOL program for file errors, libcob errors, or timeouts.")
        else:
            raise
    
    # Read coverage report
    with open(run_dir / "coverage_report.json", 'r') as f:
        coverage = json.load(f)
    
    # Read certificate
    certificate_path = run_dir / "certificate.json"
    
    # Prepare response with relative path
    return {
        "run_id": run_dir.name,
        "status": verdict.status,
        "sub_label": verdict.sub_label,
        "cases_total": verdict.cases_total,
        "cases_divergent": verdict.cases_divergent,
        "paragraph_coverage": f"{coverage['paragraphs_covered']}/{coverage['paragraphs_total']}",
        "branch_coverage": f"{coverage['branches_covered']}/{coverage['branches_total']}",
        "certificate_path": str(certificate_path.resolve().relative_to(REPO_ROOT))
    }


@server.tool(description="Get verdict for a run")
def get_verdict(run_id: str) -> dict:
    """Get verdict for a completed run.
    
    Args:
        run_id: Run identifier (12 hex characters)
        
    Returns:
        Verdict data including status, cases, and validation notice
        
    Raises:
        ToolError: If run_id format is invalid or run does not exist
    """
    validate_run_id(run_id)
    
    verdict_path = REPO_ROOT / "runs" / run_id / "verdict.json"
    if not verdict_path.exists():
        raise ToolError(f"Verdict not found for run_id {run_id}")
    
    with open(verdict_path, 'r') as f:
        return json.load(f)


@server.tool(description="Get failure report for a ZOMBIE run")
def get_failure_report(run_id: str) -> dict:
    """Get failure report showing minimal case and divergent outputs.
    
    Args:
        run_id: Run identifier (12 hex characters)
        
    Returns:
        Failure report with case details, COBOL output, Java output
        
    Raises:
        ToolError: If run_id format is invalid or the run was ALIVE
    """
    validate_run_id(run_id)
    
    # Check verdict first
    verdict_path = REPO_ROOT / "runs" / run_id / "verdict.json"
    if verdict_path.exists():
        with open(verdict_path, 'r') as f:
            verdict_data = json.load(f)
            if verdict_data.get("status") == "ALIVE":
                raise ToolError("No failure report: the run was ALIVE")
    
    failure_path = REPO_ROOT / "runs" / run_id / "failure_report.json"
    if not failure_path.exists():
        raise ToolError("No failure report: the run was ALIVE")
    
    with open(failure_path, 'r') as f:
        return json.load(f)


@server.tool(description="Get the trap catalog detection matrix")
def get_detection_matrix() -> dict:
    """Get detection matrix for the trap catalog.
    
    Returns:
        Detection matrix with trap counts and rates
        
    Raises:
        ToolError: Detection matrix not yet available (catalog not built)
    """
    raise ToolError("Detection Matrix not available yet: the trap catalog has not been run")


@server.tool(description="Export JUnit regression test for a ZOMBIE run")
def export_junit_test(run_id: str) -> dict:
    """Export JUnit 5 source test that reproduces the divergence.
    
    Args:
        run_id: Run identifier (12 hex characters)
        
    Returns:
        Dictionary with path and content of ZombieRegressionTest.java
        
    Raises:
        ToolError: If run_id format is invalid or the run was ALIVE
    """
    validate_run_id(run_id)
    
    test_path = REPO_ROOT / "runs" / run_id / "ZombieRegressionTest.java"
    if not test_path.exists():
        raise ToolError("No JUnit test: the run was ALIVE or the test was not generated")
    
    with open(test_path, 'r') as f:
        test_content = f.read()
    
    return {
        "path": str(test_path.relative_to(REPO_ROOT)),
        "content": test_content
    }


@server.tool(description="Generate or regenerate certificate for a run")
def generate_certificate(run_id: str) -> dict:
    """Generate or regenerate the Coroner Certificate for a run.
    
    Args:
        run_id: Run identifier (12 hex characters)
        
    Returns:
        Dictionary with certificate path and SHA-256 hash
        
    Raises:
        ToolError: If run_id format is invalid, run does not exist, or inputs.json is missing
    """
    from coroner.certificate import generate_certificate as gen_cert
    
    validate_run_id(run_id)
    
    run_dir = REPO_ROOT / "runs" / run_id
    if not run_dir.exists():
        raise ToolError(f"Run directory not found for run_id {run_id}")
    
    # Read inputs.json to get the file paths
    inputs_path = run_dir / "inputs.json"
    if not inputs_path.exists():
        raise ToolError(f"inputs.json not found for run_id {run_id}")
    
    with open(inputs_path, 'r') as f:
        inputs_data = json.load(f)
    
    # Get original file paths from inputs
    cobol_file = inputs_data.get("cobol_file", "")
    copybook_dir = inputs_data.get("copybook_dir", "")
    java_file = inputs_data.get("java_file", "")
    schema_file = inputs_data.get("schema_file", "")
    
    # Regenerate certificate
    gen_cert(run_id, cobol_file, copybook_dir, java_file, schema_file, str(REPO_ROOT))
    
    certificate_path = run_dir / "certificate.json"
    
    # Read certificate to get hash
    with open(certificate_path, 'r') as f:
        cert_data = json.load(f)
    
    return {
        "path": str(certificate_path.relative_to(REPO_ROOT)),
        "certificate_sha256": cert_data.get("certificate_sha256", "")
    }


@server.tool(description="Verify and replay a certificate offline")
def verify_certificate(path: str) -> dict:
    """Verify a Coroner Certificate by replaying it offline.
    
    Args:
        path: Path to certificate.json
        
    Returns:
        Verification result with valid flag, status, coverage
        
    Raises:
        ToolError: If path is outside repository
    """
    from coroner.certificate import replay_certificate
    
    cert_path = str(validate_path(path))
    
    result = replay_certificate(cert_path)
    
    return {
        "valid": result.valid,
        "reasons": [] if result.valid else [result.reason],
        "status": result.verdict.status if result.valid else None,
        "cases": result.cases_total if result.valid else None,
        "divergences": result.cases_divergent if result.valid else None,
        "paragraph_coverage": f"{result.paragraph_coverage_reached}/{result.paragraph_coverage_total}" if result.valid else None,
        "branch_coverage": f"{result.branch_coverage_reached}/{result.branch_coverage_total}" if result.valid else None
    }


if __name__ == "__main__":
    asyncio.run(main())
