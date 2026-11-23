#!/usr/bin/env python3
"""
Independence track table generator.

For each port under samples/independence/ports/, runs the Coroner engine
and collects verdict, divergent cases, run id and Java SHA-256.
Writes samples/independence/TABLE.md.
"""

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path


# Port name to label mapping
PORT_LABELS = {
    "kiro": "Kiro agent, session 1 (rules in prompt, full repository readable)",
    "kiro-fresh": "Kiro agent, fresh isolated session",
    "claude": "Claude Opus 5.5",
}


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 of a file, return first 12 hex characters."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()[:12]


def compute_full_sha256(file_path: Path) -> str:
    """Compute full SHA-256 of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_tracked_java_files(repo_root: Path) -> dict[str, str]:
    """
    Get all .java files under samples/, excluding samples/independence/, build/ and runs/.
    
    Returns dict: path relative to repo root -> full SHA-256 hex.
    """
    java_files = {}
    samples_dir = repo_root / "samples"
    
    if not samples_dir.exists():
        return {}
    
    # Walk the samples directory
    for java_file in samples_dir.rglob("*.java"):
        # Get path relative to repo root
        try:
            rel_path = java_file.relative_to(repo_root)
        except ValueError:
            continue
        
        rel_path_str = str(rel_path)
        
        # Exclude samples/independence/, build/ and runs/
        if rel_path_str.startswith("samples/independence/"):
            continue
        if "/build/" in rel_path_str or rel_path_str.startswith("build/"):
            continue
        if "/runs/" in rel_path_str or rel_path_str.startswith("runs/"):
            continue
        
        java_files[rel_path_str] = compute_full_sha256(java_file)
    
    return java_files


def find_matching_repository_file(java_file: Path, repo_root: Path) -> str:
    """
    Check if this Java file matches any tracked .java file in samples/.
    
    Returns the relative path if a match is found, or "no" if not.
    """
    tracked = get_tracked_java_files(repo_root)
    if not tracked:
        return "no"
    
    file_hash = compute_full_sha256(java_file)
    
    for rel_path, tracked_hash in tracked.items():
        if file_hash == tracked_hash:
            return rel_path
    
    return "no"


def get_environment_info(image_name: str | None) -> str:
    """
    Get environment information for the table header.
    
    If image_name is given, returns "image <name> (linux/amd64)".
    Otherwise, returns host platform and Java default locale.
    """
    if image_name:
        return f"image {image_name} (linux/amd64)"
    
    # Get host platform
    host_platform = platform.platform()
    
    # Get Java default locale
    try:
        result = subprocess.run(
            ["java", "-XshowSettings:properties", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        output = result.stderr  # Java prints properties to stderr
        language = None
        country = None
        
        for line in output.split("\n"):
            line = line.strip()
            if "user.language" in line:
                language = line.split("=")[-1].strip()
            elif "user.country" in line:
                country = line.split("=")[-1].strip()
        
        if language and country:
            locale = f"{language}_{country}"
        elif language:
            locale = language
        else:
            locale = "unknown"
    except Exception:
        locale = "unknown"
    
    return f"host {host_platform}, Java default locale {locale}"



def read_source_label(source_md_path: Path) -> str:
    """
    Read the source label from SOURCE.md.
    
    Looks for either:
    - "- Source: ..." (claude format)
    - "- **Producer**: ..." (kiro format)
    
    Returns the text after the colon with markdown bold removed.
    """
    if not source_md_path.exists():
        return "unknown"
    
    with open(source_md_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- Source:"):
                return line.split(":", 1)[1].strip()
            elif line.startswith("- **Producer**:"):
                # Remove markdown bold and extract text after colon
                return line.split(":", 1)[1].strip()
    
    return "unknown"


def parse_run_id_from_output(output: str) -> str | None:
    """Extract run id from 'Run: runs/<id>' line in output."""
    match = re.search(r"Run: runs/([a-f0-9]+)", output)
    if match:
        return match.group(1)
    return None


def read_certificate(run_id: str, base_dir: Path) -> dict:
    """Read certificate.json for a run."""
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    with open(cert_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_branch_reconciliation(run_id: str, base_dir: Path) -> dict:
    """Read branch_reconciliation.json for a run."""
    recon_path = base_dir / "runs" / run_id / "branch_reconciliation.json"
    with open(recon_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_exposure_summary(reconciliation: dict) -> str:
    """
    Compute exposure summary from branch reconciliation.
    
    Returns a string like "sum 3995184.38, max 2025606.03, 2 branches"
    or "sum 0.00" for ALIVE.
    """
    branches = reconciliation.get("branches", [])
    mismatches = [b for b in branches if b.get("status") == "MISMATCH"]
    
    if not mismatches:
        return "sum 0.00"
    
    total = sum(float(b.get("absolute_difference", "0")) for b in mismatches)
    max_val = max(float(b.get("absolute_difference", "0")) for b in mismatches)
    count = len(mismatches)
    
    return f"sum {total:.2f}, max {max_val:.2f}, {count} branches"


def run_audit(port_dir: Path, repo_root: Path, cases: int, image_name: str | None) -> dict | None:
    """
    Run coroner verify on a port and return results.
    
    Returns dict with keys: run_id, status, cases_divergent, cases_total,
    java_sha256, exposure_summary, same_file
    
    Returns None if the folder has no MatchMerge.java (it gets no row).
    """
    java_file = port_dir / "MatchMerge.java"
    if not java_file.exists():
        return None
    
    # Compute Java SHA-256
    java_sha256 = compute_sha256(java_file)
    
    # Check if it matches a repository file
    same_file = find_matching_repository_file(java_file, repo_root)
    
    # Run the engine
    t1_dir = repo_root / "samples" / "traps" / "T1-ebcdic-match-merge"
    
    if image_name:
        # Run inside Docker container
        port_dir_abs = port_dir.resolve()
        
        # Build the verification command
        verify_cmd = (
            f"python3 -m coroner verify "
            f"--cobol /app/samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob "
            f"--copybooks /app/samples/traps/T1-ebcdic-match-merge/copybooks "
            f"--java /port/MatchMerge.java "
            f"--schema /app/samples/traps/T1-ebcdic-match-merge/schema.json "
            f"--cases {cases} --seed 42"
        )
        
        # Extract run_id and read certificate values from inside container
        # We need to:
        # 1. Run verify and capture its output to get run_id
        # 2. Read certificate.json and branch_reconciliation.json from /tmp/b
        # 3. Print them as JSON so we can parse them
        cmd = [
            "docker", "run", "--rm", "--init",
            "--platform", "linux/amd64",
            "-v", f"{port_dir_abs}:/port:ro",
            "-e", "CORONER_BASE_DIR=/tmp/b",
            image_name,
            "sh", "-c",
            # Run verify, extract run_id, then print certificate and reconciliation
            verify_cmd + " 2>&1 | tee /tmp/verify_output.txt && "
            "RUN_ID=$(grep -o 'Run: runs/[a-f0-9]*' /tmp/verify_output.txt | head -1 | cut -d/ -f2) && "
            "python3 -c \""
            "import json, sys; "
            "run_id = sys.argv[1]; "
            "cert = json.load(open(f'/tmp/b/runs/{run_id}/certificate.json')); "
            "recon = json.load(open(f'/tmp/b/runs/{run_id}/branch_reconciliation.json')); "
            "print(json.dumps({'run_id': run_id, 'certificate': cert, 'reconciliation': recon}))"
            "\" $RUN_ID"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"Error running audit for {port_dir.name} in image", file=sys.stderr)
            print(f"Command: {' '.join(cmd)}", file=sys.stderr)
            print(f"Output:\n{result.stdout}", file=sys.stderr)
            print(f"Error:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        
        # Parse the JSON output (last line should be our JSON)
        lines = result.stdout.strip().split("\n")
        json_line = None
        for line in reversed(lines):
            if line.startswith("{") and "run_id" in line:
                json_line = line
                break
        
        if not json_line:
            print(f"Error: Could not find JSON output for {port_dir.name}", file=sys.stderr)
            print(f"Output was:\n{result.stdout}", file=sys.stderr)
            sys.exit(1)
        
        data = json.loads(json_line)
        run_id = data["run_id"]
        cert = data["certificate"]
        recon = data["reconciliation"]
    else:
        # Run on host
        cmd = [
            sys.executable,
            "-m",
            "coroner",
            "verify",
            "--cobol",
            str(t1_dir / "MATCH-MERGE.cob"),
            "--copybooks",
            str(t1_dir / "copybooks"),
            "--java",
            str(java_file),
            "--schema",
            str(t1_dir / "schema.json"),
            "--cases",
            str(cases),
            "--seed",
            "42",
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        
        # Extract run id from output
        output = result.stdout + result.stderr
        run_id = parse_run_id_from_output(output)
        
        if not run_id:
            print(f"Error: Could not find run id in output for {port_dir.name}", file=sys.stderr)
            print(f"Output was:\n{output}", file=sys.stderr)
            sys.exit(1)
        
        # Read certificate
        cert = read_certificate(run_id, repo_root)
        
        # Read branch reconciliation
        recon = read_branch_reconciliation(run_id, repo_root)
    
    exposure = compute_exposure_summary(recon)
    
    return {
        "run_id": run_id,
        "status": cert["status"],
        "cases_divergent": cert["cases_divergent"],
        "cases_total": cert["cases_total"],
        "java_sha256": java_sha256,
        "exposure_summary": exposure,
        "same_file": same_file,
    }


def generate_table(repo_root: Path, cases: int, image_name: str | None) -> str:
    """
    Generate the markdown table.
    
    Scans samples/independence/ports/ for folders with MatchMerge.java,
    runs the audit, and produces a table.
    """
    ports_dir = repo_root / "samples" / "independence" / "ports"
    
    # Collect all port directories
    port_dirs = sorted([d for d in ports_dir.iterdir() if d.is_dir()])
    
    rows = []
    for port_dir in port_dirs:
        port_name = port_dir.name
        source_label_raw = read_source_label(port_dir / "SOURCE.md")
        
        # Use label mapping if available, otherwise use SOURCE.md
        if port_name in PORT_LABELS:
            label = PORT_LABELS[port_name]
            source_column = source_label_raw
        else:
            label = port_name
            source_column = source_label_raw
        
        # Check if MatchMerge.java exists
        result = run_audit(port_dir, repo_root, cases, image_name)
        
        if result is None:
            # No port in this folder: no row
            continue
        rows.append({
            "label": label,
            "source": source_column,
            "verdict": result["status"],
            "divergent": str(result["cases_divergent"]),
            "total": str(result["cases_total"]),
            "run_id": result["run_id"],
            "java_sha256": result["java_sha256"],
            "exposure": result["exposure_summary"],
            "same_file": result["same_file"],
        })
    
    # Get environment info
    env_info = get_environment_info(image_name)
    
    # Build the markdown table
    lines = [
        "# Independence Track Results",
        "",
        f"Environment: {env_info}",
        "",
        "| Port | Source | Verdict | Divergent cases | Run ID | Java SHA-256 | Branch exposure | Same file as a repository Java port? |",
        "|------|--------|---------|-----------------|--------|--------------|-----------------|--------------------------------------|",
    ]
    
    for row in rows:
        lines.append(
            f"| {row['label']} "
            f"| {row['source']} "
            f"| {row['verdict']} "
            f"| {row['divergent']} of {row['total']} "
            f"| {row['run_id']} "
            f"| {row['java_sha256']} "
            f"| {row['exposure']} "
            f"| {row['same_file']} |"
        )
    
    return "\n".join(lines) + "\n"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate independence track results table."
    )
    parser.add_argument(
        "--cases",
        type=int,
        default=2000,
        help="Number of cases to generate per audit (default: 2000)",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Docker image to run audits in (e.g., coroner-local:latest). If not specified, runs on host.",
    )
    args = parser.parse_args()
    
    # Find repository root (has pyproject.toml)
    repo_root = Path(__file__).parent.parent.parent
    if not (repo_root / "pyproject.toml").exists():
        print("Error: Could not find repository root", file=sys.stderr)
        sys.exit(1)
    
    # Check that SOURCE.md files exist and have the required format
    ports_dir = repo_root / "samples" / "independence" / "ports"
    for port_dir in ports_dir.iterdir():
        if not port_dir.is_dir():
            continue
        
        source_md = port_dir / "SOURCE.md"
        if source_md.exists():
            label = read_source_label(source_md)
            if label == "unknown":
                print(
                    f"Error: {source_md} exists but has neither "
                    f"'- Source:' nor '- **Producer**:' line",
                    file=sys.stderr,
                )
                sys.exit(1)
    
    # Generate table
    table_md = generate_table(repo_root, args.cases, args.image)
    
    # Write TABLE.md
    table_path = repo_root / "samples" / "independence" / "TABLE.md"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write(table_md)
    
    print(f"Table written to {table_path}")
    print("\n" + table_md)


if __name__ == "__main__":
    main()
