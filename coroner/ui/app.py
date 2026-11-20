"""FastAPI web UI for Coroner."""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from coroner.certificate import replay_certificate

app = FastAPI(title="COBOL Coroner")

# Static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_base_dir() -> Path:
    """
    Get the base directory (repository root).
    Reads CORONER_BASE_DIR at call time, defaults to repository root.
    """
    return Path(os.environ.get("CORONER_BASE_DIR", Path(__file__).parent.parent.parent))


def detect_trap_id(inputs_data: dict) -> str | None:
    """
    Detect trap ID from run's recorded COBOL path.
    Returns trap ID (T1, T2, T3, T4, T5) or None.
    """
    cobol_path = inputs_data.get("cobol_file")
    if not cobol_path:
        return None
    
    # COBOL path is like samples/traps/T1-ebcdic-match-merge/...
    # Extract trap directory name
    path_parts = Path(cobol_path).parts
    
    # Find samples/traps/<trap_dir>
    try:
        traps_idx = path_parts.index("traps")
        if traps_idx + 1 < len(path_parts):
            trap_dir = path_parts[traps_idx + 1]
            # trap_dir is like "T1-ebcdic-match-merge"
            # Extract T1, T2, etc.
            if trap_dir.startswith("T") and len(trap_dir) >= 2:
                trap_id = trap_dir[:2]  # T1, T2, T3, T4, T5
                return trap_id
    except ValueError:
        pass
    
    return None
    return None

# Templates
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# run_id validation: exactly 12 lowercase hexadecimal characters
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def validate_run_id(run_id: str) -> str:
    """Validate run_id format. Raises HTTPException 404 if invalid."""
    if not RUN_ID_PATTERN.match(run_id):
        raise HTTPException(status_code=404, detail="Invalid run_id")
    return run_id


def get_recent_runs(limit: int = 10) -> list[dict]:
    """Get up to `limit` most recent runs, newest first."""
    runs_dir = get_base_dir() / "runs"
    if not runs_dir.exists() or not runs_dir.is_dir():
        return []
    
    runs = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        
        run_id = run_dir.name
        if not RUN_ID_PATTERN.match(run_id):
            continue
        
        verdict_file = run_dir / "verdict.json"
        inputs_file = run_dir / "inputs.json"
        
        # Determine verdict
        verdict = "ERROR"
        if verdict_file.exists():
            try:
                verdict_data = json.loads(verdict_file.read_text())
                verdict = verdict_data.get("status", "UNKNOWN")
            except (json.JSONDecodeError, OSError):
                pass
        
        # Get timestamp
        timestamp = None
        if inputs_file.exists():
            try:
                inputs_data = json.loads(inputs_file.read_text())
                timestamp = inputs_data.get("timestamp")
            except (json.JSONDecodeError, OSError):
                pass
        
        if timestamp is None:
            # Fallback to directory modification time
            timestamp = datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat()
        
        runs.append({
            "id": run_id,
            "verdict": verdict,
            "date": timestamp,
            "timestamp_sort": timestamp,
        })
    
    # Sort by timestamp, newest first
    runs.sort(key=lambda r: r["timestamp_sort"], reverse=True)
    
    return runs[:limit]


@app.get("/favicon.ico")
async def favicon():
    """Return 204 No Content for favicon requests (inline SVG is used in HTML)."""
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Index page."""
    runs = get_recent_runs(limit=10)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"runs": runs}
    )


@app.get("/run/{run_id}/download/{file_name}")
async def download_file(run_id: str, file_name: str):
    """
    Download a file from a run.
    
    Allowed files: ZombieRegressionTest.java, certificate.json
    """
    validate_run_id(run_id)
    
    # Validate file_name against allowed list
    allowed_files = ["ZombieRegressionTest.java", "certificate.json"]
    if file_name not in allowed_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if run directory exists
    run_dir = get_base_dir() / "runs" / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Check if file exists
    file_path = run_dir / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Return file with appropriate Content-Disposition
    return FileResponse(
        path=str(file_path),
        filename=file_name,
        media_type="application/octet-stream"
    )


async def render_error_page(request: Request, run_id: str, run_dir: Path):
    """Render ERROR page for broken reference (D-51)."""
    from coroner.ui.pages import format_timestamp
    
    # Read error file
    error_file = run_dir / "run_error.txt"
    error_text = error_file.read_text()
    
    # Parse error text
    # Format is:
    # ERROR: reference did not run
    # Reason: <reason>
    #
    # COBOL stderr:
    # <stderr lines>
    lines = error_text.strip().split('\n')
    
    # Extract reason (line after "Reason:")
    reason = "not recorded"
    stderr_excerpt = ""
    
    in_stderr = False
    stderr_lines = []
    
    for line in lines:
        if line.startswith("Reason:"):
            reason = line[len("Reason:"):].strip()
        elif line.startswith("COBOL stderr:"):
            in_stderr = True
        elif in_stderr:
            stderr_lines.append(line)
    
    if stderr_lines:
        # Join stderr lines, sanitize home directory paths
        stderr_text = '\n'.join(stderr_lines)
        
        # Remove any absolute paths containing home directory
        home_dir = str(Path.home())
        stderr_text = stderr_text.replace(home_dir, "<home>")
        
        # Keep only first 20 lines
        stderr_excerpt_lines = stderr_text.split('\n')[:20]
        stderr_excerpt = '\n'.join(stderr_excerpt_lines)
    
    # Read inputs for timestamp and version (might not exist for very early errors)
    inputs_file = run_dir / "inputs.json"
    inputs_data = {}
    if inputs_file.exists():
        try:
            inputs_data = json.loads(inputs_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    
    timestamp_str = inputs_data.get("timestamp", "")
    audit_datetime = format_timestamp(timestamp_str) if timestamp_str else "not recorded"
    
    coroner_version = inputs_data.get("coroner_version", "not recorded")
    
    # Duration from timing.json if exists
    timing_file = run_dir / "timing.json"
    duration = "not recorded"
    if timing_file.exists():
        try:
            timing_data = json.loads(timing_file.read_text())
            duration_str = timing_data.get("duration_seconds", "")
            if duration_str:
                duration = f"{duration_str} s"
        except (json.JSONDecodeError, OSError):
            pass
    
    return templates.TemplateResponse(
        request=request,
        name="run.html",
        context={
            "run_id": run_id,
            "audit_datetime": audit_datetime,
            "coroner_version": coroner_version,
            "verdict_class": "error",
            "badge_line1": "ERROR",
            "badge_line2": "reference did not run",
            "verdict_sentence": "",
            "sub_label": "",
            "cases": "not recorded",
            "divergences": "not recorded",
            "paragraph_coverage": "not recorded",
            "branch_coverage": "not recorded",
            "duration": duration,
            "exhibit": None,
            "reconciliation": None,
            "trap": None,
            "example_sentence": None,
            "minimal_case_evidence": None,
            "card": None,
            "has_certificate": False,
            "certificate": None,
            "error_reason": reason,
            "error_stderr": stderr_excerpt,
        }
    )


@app.get("/run/{run_id}", response_class=HTMLResponse)
async def run_page(request: Request, run_id: str):
    """Run details page."""
    from coroner.ui.pages import format_timestamp, compute_exhibit_data
    from coroner.ui.sentences import generate_zombie_sentence
    
    validate_run_id(run_id)
    
    # Check if run directory exists
    run_dir = get_base_dir() / "runs" / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Read verdict
    verdict_file = run_dir / "verdict.json"
    
    # Check for ERROR case (D-51: reference did not run)
    if not verdict_file.exists():
        error_file = run_dir / "run_error.txt"
        if error_file.exists():
            # This is an ERROR run (broken reference)
            return await render_error_page(request, run_id, run_dir)
        else:
            raise HTTPException(status_code=404, detail="Verdict not found")
    
    try:
        verdict_data = json.loads(verdict_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to read verdict: {e}")
    
    # Read coverage report
    coverage_file = run_dir / "coverage_report.json"
    coverage_data = {}
    if coverage_file.exists():
        try:
            coverage_data = json.loads(coverage_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    
    # Read inputs for additional info
    inputs_file = run_dir / "inputs.json"
    inputs_data = {}
    if inputs_file.exists():
        try:
            inputs_data = json.loads(inputs_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    
    # Extract verdict fields
    status = verdict_data.get("status", "UNKNOWN")
    sub_label = verdict_data.get("sub_label")
    
    # Cases and divergences
    cases_total = verdict_data.get("cases_total")
    cases_divergent = verdict_data.get("cases_divergent")
    
    cases = str(cases_total) if cases_total is not None else "not recorded"
    divergences = str(cases_divergent) if cases_divergent is not None else "not recorded"
    
    # Coverage from coverage_report.json
    if coverage_data:
        paragraph_covered = coverage_data.get("paragraphs_covered")
        paragraph_total = coverage_data.get("paragraphs_total")
        branch_covered = coverage_data.get("branches_covered")
        branch_total = coverage_data.get("branches_total")
        
        if paragraph_covered is not None and paragraph_total is not None:
            paragraph_coverage = f"{paragraph_covered}/{paragraph_total}"
        else:
            paragraph_coverage = "not recorded"
        
        if branch_covered is not None and branch_total is not None:
            branch_coverage = f"{branch_covered}/{branch_total}"
        else:
            branch_coverage = "not recorded"
    else:
        paragraph_coverage = "not recorded"
        branch_coverage = "not recorded"
    
    # Duration from timing.json
    timing_file = run_dir / "timing.json"
    duration = "not recorded"
    if timing_file.exists():
        try:
            timing_data = json.loads(timing_file.read_text())
            duration_str = timing_data.get("duration_seconds", "")
            if duration_str:
                duration = f"{duration_str} s"
        except (json.JSONDecodeError, OSError):
            pass
    
    # Header: timestamp from inputs.json
    timestamp_str = inputs_data.get("timestamp", "")
    audit_datetime = format_timestamp(timestamp_str) if timestamp_str else "not recorded"
    
    # Coroner version from certificate if exists, else from inputs
    coroner_version = "not recorded"
    certificate_file = run_dir / "certificate.json"
    if certificate_file.exists():
        try:
            cert_data = json.loads(certificate_file.read_text())
            coroner_version = cert_data.get("coroner_version", "not recorded")
        except (json.JSONDecodeError, OSError):
            pass
    
    if coroner_version == "not recorded" and inputs_data:
        coroner_version = inputs_data.get("coroner_version", "not recorded")
    
    # Verdict class for CSS and badge text
    verdict_class = status.lower()
    
    if status == "ZOMBIE":
        badge_line1 = "ZOMBIE"
        badge_line2 = "MIGRATION REJECTED"
    elif status == "ALIVE":
        badge_line1 = "ALIVE"
        badge_line2 = "MIGRATION CERTIFIED"
    else:
        badge_line1 = status
        badge_line2 = ""
    
    # Sentence: try to generate trap-specific, fallback to sub_label
    verdict_sentence = ""
    if status == "ZOMBIE":
        # Detect trap ID from inputs
        trap_id = detect_trap_id(inputs_data)
        
        if trap_id and trap_id in ["T1", "T2", "T3", "T4", "T5"]:
            try:
                verdict_sentence = generate_zombie_sentence(trap_id, run_dir)
            except Exception:
                # Fallback to sub_label if generation fails
                verdict_sentence = sub_label if sub_label else ""
        else:
            # Not a trap run, use sub_label
            verdict_sentence = sub_label if sub_label else ""
    else:
        verdict_sentence = sub_label if sub_label else ""
    
    # Exhibit 1: Unreconciled branch exposure
    exhibit = compute_exhibit_data(run_dir, verdict_data, inputs_data)
    
    # Check for certificate
    has_certificate = certificate_file.exists()
    certificate = None
    
    if has_certificate:
        try:
            cert_data = json.loads(certificate_file.read_text())
            
            # Read certificate fields
            cert_status = cert_data.get("status")
            cert_case_count = cert_data.get("case_count")
            cert_cases_divergent = cert_data.get("cases_divergent")
            cert_paragraph_reached = cert_data.get("paragraph_coverage_reached")
            cert_paragraph_total = cert_data.get("paragraph_coverage_total")
            cert_branch_reached = cert_data.get("branch_coverage_reached")
            cert_branch_total = cert_data.get("branch_coverage_total")
            
            certificate = {
                "run_id": cert_data.get("run_id", run_id),
                "status": cert_status if cert_status else "not recorded",
                "cases": str(cert_case_count) if cert_case_count is not None else "not recorded",
                "divergences": str(cert_cases_divergent) if cert_cases_divergent is not None else "not recorded",
                "paragraph_coverage": f"{cert_paragraph_reached}/{cert_paragraph_total}" if cert_paragraph_reached is not None and cert_paragraph_total is not None else "not recorded",
                "branch_coverage": f"{cert_branch_reached}/{cert_branch_total}" if cert_branch_reached is not None and cert_branch_total is not None else "not recorded",
            }
        except (json.JSONDecodeError, OSError):
            has_certificate = False
    
    # Read trap metadata if this is a trap run (BEFORE reconciliation processing)
    trap_id = detect_trap_id(inputs_data)
    trap = None
    example_sentence = None
    minimal_case_evidence = None
    
    if trap_id and trap_id in ["T1", "T2", "T3", "T4", "T5"]:
        # Find trap.json
        cobol_path = inputs_data.get("cobol_file", "")
        if cobol_path:
            # Extract trap directory from COBOL path
            path_parts = Path(cobol_path).parts
            try:
                traps_idx = path_parts.index("traps")
                if traps_idx + 1 < len(path_parts):
                    trap_dir_name = path_parts[traps_idx + 1]
                    # Use actual repository root for samples (not tmp_path from tests)
                    repo_root = Path(__file__).resolve().parent.parent.parent
                    trap_dir = repo_root / "samples" / "traps" / trap_dir_name
                    trap_json = trap_dir / "trap.json"
                    
                    if trap_json.exists():
                        try:
                            trap = json.loads(trap_json.read_text())
                            # Add the repository-relative source path
                            trap["_source_path"] = f"samples/traps/{trap_dir_name}/trap.json"
                        except (json.JSONDecodeError, OSError):
                            pass
            except ValueError:
                pass
    
    # Read reconciliation data if exists (for T1 and other control-break programs)
    reconciliation_file = run_dir / "branch_reconciliation.json"
    reconciliation = None
    if reconciliation_file.exists():
        try:
            from decimal import Decimal
            reconciliation = json.loads(reconciliation_file.read_text())
            
            # Sort branches numerically by absolute_difference (descending)
            # and compute bar widths in Python before rendering
            branches = reconciliation.get("branches", [])
            
            # Convert string amounts to Decimal for sorting
            for branch in branches:
                branch["_abs_diff_decimal"] = abs(Decimal(branch["absolute_difference"]))
                branch["_cobol_decimal"] = Decimal(branch["cobol_subtotal"])
                branch["_java_decimal"] = Decimal(branch["java_subtotal"])
            
            # Sort by absolute difference (largest first)
            branches.sort(key=lambda b: b["_abs_diff_decimal"], reverse=True)
            
            # Compute maximum for bar scaling (include suspense in the max calculation)
            max_abs = Decimal("0")
            for branch in branches:
                cobol_abs = abs(branch["_cobol_decimal"])
                java_abs = abs(branch["_java_decimal"])
                diff_abs = branch["_abs_diff_decimal"]
                
                if cobol_abs > max_abs:
                    max_abs = cobol_abs
                if java_abs > max_abs:
                    max_abs = java_abs
                if diff_abs > max_abs:
                    max_abs = diff_abs
            
            # Process suspense if present
            suspense = reconciliation.get("suspense")
            if suspense:
                susp_cobol = Decimal(suspense["cobol"])
                susp_java = Decimal(suspense["java"])
                susp_diff = Decimal(suspense["difference"])
                
                # Update max_abs to include suspense values
                if abs(susp_cobol) > max_abs:
                    max_abs = abs(susp_cobol)
                if abs(susp_java) > max_abs:
                    max_abs = abs(susp_java)
                
                # Compute bar widths for suspense
                if max_abs > 0:
                    suspense["_cobol_pct"] = float(abs(susp_cobol) / max_abs * 100)
                    suspense["_java_pct"] = float(abs(susp_java) / max_abs * 100)
                else:
                    suspense["_cobol_pct"] = 0
                    suspense["_java_pct"] = 0
                
                # Add status based on difference
                suspense["status"] = "MATCH" if susp_diff == 0 else "MISMATCH"
                
                # Add trap labels if available
                if trap:
                    reconciliation["_suspense_label"] = trap.get("suspense_label", "Suspense")
                    reconciliation["_suspense_code"] = trap.get("suspense_code", "SUSP")
            
            # Compute bar widths as percentages for branches
            for branch in branches:
                if max_abs > 0:
                    branch["_cobol_pct"] = float(abs(branch["_cobol_decimal"]) / max_abs * 100)
                    branch["_java_pct"] = float(abs(branch["_java_decimal"]) / max_abs * 100)
                else:
                    branch["_cobol_pct"] = 0
                    branch["_java_pct"] = 0
            
            reconciliation["branches"] = branches
            reconciliation["_max_abs"] = str(max_abs)
            
        except (json.JSONDecodeError, OSError):
            pass
    
    # Generate example sentence for ZOMBIE runs with minimal case (trap already loaded above)
    if status == "ZOMBIE" and trap_id == "T1":
            failure_file = run_dir / "failure_report.json"
            if failure_file.exists():
                try:
                    failure = json.loads(failure_file.read_text())
                    divergent_fields = failure.get("divergent_fields", [])
                    
                    if divergent_fields and trap:
                        # T1 example: "<amount> posted to <suspense_label> instead of branch <code>"
                        suspense_label = trap.get("suspense_label", "suspense")
                        suspense_code = trap.get("suspense_code", "SUSP")
                        
                        # Find the missing_in_cobol entry (Java posted to suspense)
                        java_suspense_entry = None
                        for div in divergent_fields:
                            if div.get("kind") == "missing_in_cobol":
                                output_key = div.get("output_key", {})
                                branch = output_key.get("BRANCH", "").strip()
                                if branch == suspense_code:
                                    java_suspense_entry = div
                                    break
                        
                        if java_suspense_entry:
                            java_values = java_suspense_entry.get("java_values", {})
                            subtotal = java_values.get("SUBTOTAL", "")
                            
                            # Find the missing_in_java entry with the same SUBTOTAL
                            for div in divergent_fields:
                                if div.get("kind") == "missing_in_java":
                                    cobol_values = div.get("cobol_values", {})
                                    cobol_subtotal = cobol_values.get("SUBTOTAL", "")
                                    
                                    if cobol_subtotal == subtotal:
                                        output_key = div.get("output_key", {})
                                        cobol_branch = output_key.get("BRANCH", "").strip()
                                        
                                        # Parse amount with Decimal, quantize to column scale (2 decimals for SUBTOTAL)
                                        from decimal import Decimal, ROUND_DOWN
                                        amount = Decimal(subtotal.strip())
                                        # Quantize to 2 decimal places (column scale)
                                        amount_quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                                        # Format with absolute value
                                        amount_str = f"{abs(amount_quantized):.2f}"
                                        
                                        # New format: "<amount> was posted to <suspense_label> instead of branch <code>."
                                        example_sentence = f"{amount_str} was posted to {suspense_label} instead of branch {cobol_branch}."
                                        
                                        # Build evidence text with input rows and output rows
                                        minimal_case_rows = failure.get("minimal_case_rows", [])
                                        
                                        evidence_lines = []
                                        if minimal_case_rows:
                                            evidence_lines.append("Input rows:")
                                            for row in minimal_case_rows:
                                                evidence_lines.append(f"  {row}")
                                            evidence_lines.append("")
                                        
                                        evidence_lines.append(f"COBOL output: BRANCH={cobol_branch} with SUBTOTAL={cobol_subtotal}")
                                        evidence_lines.append(f"Java output: BRANCH={suspense_code} with SUBTOTAL={subtotal}")
                                        
                                        minimal_case_evidence = "\n".join(evidence_lines)
                                        break
                except (json.JSONDecodeError, OSError) as e:
                    import logging
                    logging.warning(f"Failed to read failure_report.json for exhibit 4: {e}")
    
    # Read card data from card.txt if exists
    card = None
    if status == "ZOMBIE":
        card_file = run_dir / "card.txt"
        if card_file.exists():
            try:
                card_text = card_file.read_text().strip()
                if card_text:
                    # Parse card.txt format:
                    # Given the following input rows:
                    #   ...
                    # When the COBOL reference and the Java port process this case
                    # Then ...
                    # COBOL lines involved: path:line statement; path:line statement; ...
                    lines = card_text.split("\n")
                    given_lines = []
                    when_lines = []
                    then_lines = []
                    cobol_lines = []
                    
                    section = None
                    for line in lines:
                        if line.startswith("Given"):
                            section = "given"
                            given_lines.append(line)
                        elif line.startswith("When"):
                            section = "when"
                            when_lines.append(line)
                        elif line.startswith("Then"):
                            section = "then"
                            then_lines.append(line)
                        elif line.startswith("COBOL lines involved:"):
                            section = "cobol"
                            # Extract lines after the colon
                            rest = line[len("COBOL lines involved:"):].strip()
                            if rest:
                                # Split by "; " for inline format
                                for part in rest.split("; "):
                                    if part:
                                        # Extract just filename:line statement
                                        # part is like: "full/path/file.cob:123 STATEMENT TEXT"
                                        # or "full/path/file.cob:123 STATEMENT TEXT."
                                        # We want "file.cob:123 STATEMENT TEXT"
                                        if ":" in part:
                                            path_part, rest_part = part.split(":", 1)
                                            filename = Path(path_part).name
                                            cobol_lines.append(f"{filename}:{rest_part}")
                                        else:
                                            cobol_lines.append(part)
                        elif section == "given" and line.strip():
                            given_lines.append(line)
                        elif section == "when" and line.strip():
                            when_lines.append(line)
                        elif section == "then" and line.strip():
                            then_lines.append(line)
                    
                    card = {
                        "given": "\n".join(given_lines),
                        "when": "\n".join(when_lines),
                        "then": "\n".join(then_lines),
                        "cobol_lines": cobol_lines
                    }
            except OSError:
                pass
    
    return templates.TemplateResponse(
        request=request,
        name="run.html",
        context={
            "run_id": run_id,
            "audit_datetime": audit_datetime,
            "coroner_version": coroner_version,
            "verdict_class": verdict_class,
            "badge_line1": badge_line1,
            "badge_line2": badge_line2,
            "verdict_sentence": verdict_sentence,
            "sub_label": sub_label,
            "cases": cases,
            "divergences": divergences,
            "paragraph_coverage": paragraph_coverage,
            "branch_coverage": branch_coverage,
            "duration": duration,
            "exhibit": exhibit,
            "reconciliation": reconciliation,
            "trap": trap,
            "example_sentence": example_sentence,
            "minimal_case_evidence": minimal_case_evidence,
            "card": card,
            "has_certificate": has_certificate,
            "certificate": certificate,
        }
    )




@app.post("/api/verify")
async def verify_certificate(run_id: str = Form(...)):
    """
    Verify certificate endpoint.
    
    Replays the certificate and returns validation status.
    Returns htmx-compatible HTML fragment.
    Accepts application/x-www-form-urlencoded (htmx default).
    """
    validate_run_id(run_id)
    
    # Check if run directory exists
    run_dir = get_base_dir() / "runs" / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Check if certificate exists
    certificate_file = run_dir / "certificate.json"
    if not certificate_file.exists():
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    # Replay certificate
    result = replay_certificate(str(certificate_file))
    
    # Build HTML fragment
    if result.valid:
        html = f'''
        <div style="padding: 1rem; background: #1b4d3e; color: #4ade80; border-radius: 4px;">
            <div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 0.5rem;">Certificate: VALID</div>
            <div>Status: {result.verdict.status if result.verdict else "not recorded"}</div>
            <div>Cases: {result.cases_total}</div>
            <div>Divergences: {result.cases_divergent}</div>
            <div>Paragraph coverage: {result.paragraph_coverage_reached}/{result.paragraph_coverage_total}</div>
            <div>Branch coverage (Coroner definition): {result.branch_coverage_reached}/{result.branch_coverage_total}</div>
        </div>
        '''
    else:
        html = f'''
        <div style="padding: 1rem; background: #4d1b1b; color: #f87171; border-radius: 4px;">
            <div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 0.5rem;">Certificate: INVALID</div>
            <div>{result.reason}</div>
        </div>
        '''
    
    return HTMLResponse(content=html)


@app.get("/matrix", response_class=HTMLResponse)
async def matrix_page(request: Request):
    """Detection Matrix page."""
    catalog_file = get_base_dir() / "runs" / "trap_catalog.json"
    
    has_catalog = catalog_file.exists()
    traps = []
    
    if has_catalog:
        try:
            catalog_data = json.loads(catalog_file.read_text())
            
            # Process each trap from the traps list
            for trap_data in catalog_data.get("traps", []):
                trap_id = trap_data.get("id", "")
                
                # T6 is a placeholder without numbers
                if trap_id == "T6":
                    traps.append({
                        "id": trap_id,
                        "description": trap_data.get("title", ""),
                        "detected": "not measured",
                        "rate": "not measured",
                        "correct_port": "not measured"
                    })
                else:
                    # Read from the measured trap data
                    detected = trap_data.get("cases_detected")
                    total = trap_data.get("cases_generated")
                    rate = trap_data.get("detection_rate")  # Already a string "X.XXXX"
                    correct_port = trap_data.get("correct_verdict")
                    
                    detected_text = f"{detected} of {total}" if detected is not None and total is not None else "not recorded"
                    rate_text = rate if rate is not None else "not recorded"
                    correct_port_text = correct_port if correct_port else "not recorded"
                    
                    traps.append({
                        "id": trap_id,
                        "description": trap_data.get("title", ""),
                        "detected": detected_text,
                        "rate": rate_text,
                        "correct_port": correct_port_text
                    })
            
            # Already sorted by trap ID in the catalog
            
        except (json.JSONDecodeError, OSError):
            has_catalog = False
            traps = []
    
    return templates.TemplateResponse(
        request=request,
        name="matrix.html",
        context={
            "has_catalog": has_catalog,
            "traps": traps
        }
    )


def main():
    """
    Entry point that checks CORONER_ENGINE_MODE.
    
    When CORONER_ENGINE_MODE=worker, runs the engine worker.
    When CORONER_ENGINE_MODE=api (or unset), runs FastAPI (caller starts uvicorn).
    """
    engine_mode = os.environ.get("CORONER_ENGINE_MODE", "api")
    
    if engine_mode == "worker":
        # Run engine worker
        from coroner.engine_worker import worker_loop
        worker_loop()
    elif engine_mode == "api":
        # FastAPI mode: do nothing, let uvicorn start the app
        # This main() is not called when uvicorn starts the app object
        pass
    else:
        print(f"Unknown CORONER_ENGINE_MODE: {engine_mode}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
