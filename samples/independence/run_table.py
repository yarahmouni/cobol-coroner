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
import re
import subprocess
import sys
from pathlib import Path


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 of a file, return first 12 hex characters."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()[:12]


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


def run_audit(port_dir: Path, repo_root: Path, cases: int) -> dict | None:
    """
    Run coroner verify on a port and return results.
    
    Returns dict with keys: run_id, status, cases_divergent, cases_total,
    java_sha256, exposure_summary
    
    Returns None if the port has no MatchMerge.java.
    """
    java_file = port_dir / "MatchMerge.java"
    if not java_file.exists():
        return None
    
    # Compute Java SHA-256
    java_sha256 = compute_sha256(java_file)
    
    # Run the engine
    t1_dir = repo_root / "samples" / "traps" / "T1-ebcdic-match-merge"
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
    }


def generate_table(repo_root: Path, cases: int) -> str:
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
        source_label = read_source_label(port_dir / "SOURCE.md")
        
        # Check if MatchMerge.java exists
        result = run_audit(port_dir, repo_root, cases)
        
        if result is None:
            # Port is pending
            rows.append({
                "port": port_name,
                "source": "pending",
                "verdict": "pending",
                "divergent": "pending",
                "total": "pending",
                "run_id": "pending",
                "java_sha256": "pending",
                "exposure": "pending",
            })
        else:
            rows.append({
                "port": port_name,
                "source": source_label,
                "verdict": result["status"],
                "divergent": str(result["cases_divergent"]),
                "total": str(result["cases_total"]),
                "run_id": result["run_id"],
                "java_sha256": result["java_sha256"],
                "exposure": result["exposure_summary"],
            })
    
    # Build the markdown table
    lines = [
        "# Independence Track Results",
        "",
        "| Port | Source | Verdict | Divergent cases | Run ID | Java SHA-256 | Branch exposure |",
        "|------|--------|---------|-----------------|--------|--------------|-----------------|",
    ]
    
    for row in rows:
        if row["verdict"] == "pending":
            # Pending row has "pending" in every column
            line = (
                f"| {row['port']} "
                f"| pending "
                f"| pending "
                f"| pending "
                f"| pending "
                f"| pending "
                f"| pending |"
            )
        else:
            line = (
                f"| {row['port']} "
                f"| {row['source']} "
                f"| {row['verdict']} "
                f"| {row['divergent']} of {row['total']} "
                f"| {row['run_id']} "
                f"| {row['java_sha256']} "
                f"| {row['exposure']} |"
            )
        lines.append(line)
    
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
    table_md = generate_table(repo_root, args.cases)
    
    # Write TABLE.md
    table_path = repo_root / "samples" / "independence" / "TABLE.md"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write(table_md)
    
    print(f"Table written to {table_path}")
    print("\n" + table_md)


if __name__ == "__main__":
    main()
