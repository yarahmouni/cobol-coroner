"""FastAPI web UI for Coroner."""
import hashlib
import html
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, conint, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from coroner.cases import auditable_trap_ids, case_label, load_cases_registry
from coroner.certificate import replay_certificate, compute_certificate_sha256, ReplayResult
from coroner.gate import certificate_matches_files, gate_decision
from coroner.hooks import get_repo_root


async def _send_413(send: Send):
    """Send 413 Payload Too Large response."""
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            [b"content-type", b"application/json"],
            [b"cache-control", b"no-store, no-cache, must-revalidate"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": b'{"detail":"Request body too large"}',
    })


class CacheControlMiddleware:
    """
    Pure ASGI middleware that sets Cache-Control headers on all responses.
    
    - /api/* responses: no-store, no-cache, must-revalidate (any status)
    - /story and /story/* responses: no-store (any status)
    - /static/* responses: public, max-age=86400
    - Other paths: no Cache-Control header
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """ASGI callable."""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        path = scope.get("path", "")
        
        # Determine header to add
        cache_header = None
        if path.startswith("/api/"):
            cache_header = b"no-store, no-cache, must-revalidate"
        elif path == "/story" or path.startswith("/story/"):
            cache_header = b"no-store"
        elif path.startswith("/static/"):
            cache_header = b"public, max-age=86400"
        
        if cache_header is None:
            # No cache control needed, pass through
            return await self.app(scope, receive, send)
        
        # Intercept send to add header
        async def send_with_cache_control(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                # Remove any existing cache-control header (case-insensitive)
                headers = [
                    (name, value)
                    for name, value in headers
                    if name.lower() != b"cache-control"
                ]
                
                # Add our cache-control header
                headers.append((b"cache-control", cache_header))
                
                message = {**message, "headers": headers}
            
            await send(message)
        
        return await self.app(scope, receive, send_with_cache_control)


class BodySizeLimitMiddleware:
    """
    Pure ASGI middleware that enforces body size limit on /api/* and /story/* endpoints
    (the story fragment routes call the API route functions, so they get the same limit).
    
    Rejects requests with Content-Length > 16384 or actual body > 16384 bytes.
    Returns 413 Payload Too Large.
    """
    
    MAX_SIZE = 16 * 1024  # 16 KB
    LIMITED_PREFIXES = ("/api/", "/story/")
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """ASGI callable."""
        if scope["type"] != "http" or not scope["path"].startswith(self.LIMITED_PREFIXES):
            return await self.app(scope, receive, send)
        
        # Check Content-Length header
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    too_big = int(value) > self.MAX_SIZE
                except ValueError:
                    too_big = True
                if too_big:
                    return await _send_413(send)
        
        # Read and buffer body, counting bytes
        total = 0
        body_parts, more = [], True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                break  # http.disconnect
            total += len(message.get("body", b""))
            if total > self.MAX_SIZE:
                return await _send_413(send)
            body_parts.append(message.get("body", b""))
            more = message.get("more_body", False)
        
        # Replay buffered body to downstream app
        body = b"".join(body_parts)
        sent = False
        
        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        
        return await self.app(scope, replay, send)


app = FastAPI(title="COBOL Coroner")

# Add cache control middleware (applies to all responses)
app.add_middleware(CacheControlMiddleware)

# Add body size limit middleware for /api/* paths
app.add_middleware(BodySizeLimitMiddleware)

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

# run_id validation: exactly 12 lowercase hexadecimal characters (pattern shared with the story data layer)
from coroner.ui.pages import RUN_ID_PATTERN  # noqa: E402


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
    registry = load_cases_registry()
    sample_cases = [
        {"id": trap_id, "label": case_label(trap_id, registry)}
        for trap_id in auditable_trap_ids(registry)
    ]
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"runs": runs, "sample_cases": sample_cases}
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
    from coroner.ui.pages import format_timestamp, compute_exhibit_data, parse_card
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
                card = parse_card(card_file.read_text())
            except OSError:
                pass
    
    return templates.TemplateResponse(
        request=request,
        name="run.html",
        context={
            "run_id": run_id,
            "case_label": case_label(trap_id),
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




# Last replay process group ID (for tests)
_last_replay_pgid = None


def get_last_replay_pgid() -> Optional[int]:
    """Get the last replay process group ID (for tests)."""
    return _last_replay_pgid


def replay_with_timeout(certificate_path: str, base_dir: str, timeout_seconds: int) -> ReplayResult:
    """
    Replay a certificate with a timeout using a child process.
    
    Runs `coroner verify <certificate_path> --json` as a subprocess with timeout.
    If the replay exceeds the timeout, kills the process group and returns an error ReplayResult.
    
    Args:
        certificate_path: Path to certificate file
        base_dir: Base directory for runs
        timeout_seconds: Timeout in seconds
    
    Returns:
        ReplayResult with valid=False and appropriate reason if timeout or other error
    """
    global _last_replay_pgid
    
    # Build command: certificate is a positional argument, not --certificate
    cmd = [
        sys.executable,
        "-m",
        "coroner",
        "verify",
        certificate_path,
        "--json"
    ]
    
    # Set environment
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base_dir)
    
    try:
        # Start subprocess with process group
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=env,
        )
        
        # Record pgid for tests
        _last_replay_pgid = proc.pid
        
        try:
            # Wait for completion with timeout
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Kill the process group
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            
            # Collect output
            proc.communicate()
            
            # Return timeout error
            return ReplayResult(
                valid=False,
                reason="replay timed out",
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
        
        # Parse JSON output
        try:
            result_data = json.loads(stdout)
        except json.JSONDecodeError:
            # Not valid JSON, return error with stderr excerpt
            stderr_excerpt = stderr[:200] if stderr else "(no stderr)"
            return ReplayResult(
                valid=False,
                reason=f"replay failed: {stderr_excerpt}",
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
        
        # Build ReplayResult from JSON
        from coroner.verdict import Verdict
        
        verdict = None
        if result_data.get("verdict_status"):
            # Construct Verdict with all required fields
            run_return_codes_list = result_data.get("run_return_codes", [0, 0])
            verdict = Verdict(
                status=result_data["verdict_status"],
                sub_label=result_data.get("verdict_sub_label", ""),
                cases_total=result_data.get("cases_total", 0),
                cases_divergent=result_data.get("cases_divergent", 0),
                run_return_codes=(run_return_codes_list[0], run_return_codes_list[1])
            )
        
        return ReplayResult(
            valid=result_data["valid"],
            reason=result_data.get("reason", ""),
            verdict=verdict,
            cases_total=result_data.get("cases_total", 0),
            cases_divergent=result_data.get("cases_divergent", 0),
            paragraph_coverage_reached=result_data.get("paragraph_coverage_reached", 0),
            paragraph_coverage_total=result_data.get("paragraph_coverage_total", 0),
            branch_coverage_reached=result_data.get("branch_coverage_reached", 0),
            branch_coverage_total=result_data.get("branch_coverage_total", 0),
            cases_file=result_data.get("cases_file", ""),
            warnings=result_data.get("warnings", [])
        )
        
    except Exception as e:
        # Other error
        return ReplayResult(
            valid=False,
            reason=f"replay failed: {str(e)}",
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


@app.post("/api/verify")
async def verify_certificate(request: Request, run_id: str = Form(...)):
    """
    Verify certificate endpoint.
    
    Replays the certificate and returns validation status.
    Returns htmx-compatible HTML fragment.
    Accepts application/x-www-form-urlencoded (htmx default).
    """
    # Get client address
    client_ip = get_client_address(request)
    
    # Rate limiting: /api/verify 1 per 10 seconds per client (configurable for tests)
    verify_window = int(os.environ.get("CORONER_VERIFY_RATE_WINDOW", "10"))
    retry_after = check_rate_limit(f"endpoint:/api/verify:ip:{client_ip}", 1, verify_window)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded for verify", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Rate limiting: global 100/min
    retry_after = check_rate_limit("global", 100, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Rate limiting: per IP 20/min
    retry_after = check_rate_limit(f"ip:{client_ip}", 20, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    validate_run_id(run_id)
    
    # Check if run directory exists
    run_dir = get_base_dir() / "runs" / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        return JSONResponse(status_code=404, content={"detail": "Run not found"})
    
    # Check if certificate exists
    certificate_file = run_dir / "certificate.json"
    if not certificate_file.exists():
        return JSONResponse(status_code=404, content={"detail": "Certificate not found"})
    
    # Replay certificate off the event loop with timeout
    replay_timeout = int(os.environ.get("CORONER_REPLAY_TIMEOUT", "90"))
    base_dir = get_base_dir()
    result = await run_in_threadpool(
        replay_with_timeout,
        str(certificate_file),
        str(base_dir),
        replay_timeout
    )
    
    # Build HTML fragment
    if result.valid:
        # Escape all dynamic values
        status = html.escape(result.verdict.status if result.verdict else "not recorded")
        cases_total = html.escape(str(result.cases_total))
        cases_divergent = html.escape(str(result.cases_divergent))
        para_reached = html.escape(str(result.paragraph_coverage_reached))
        para_total = html.escape(str(result.paragraph_coverage_total))
        branch_reached = html.escape(str(result.branch_coverage_reached))
        branch_total = html.escape(str(result.branch_coverage_total))
        
        html_content = f'''
        <div style="padding: 1rem; background: #1b4d3e; color: #4ade80; border-radius: 4px;">
            <div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 0.5rem;">Certificate: VALID</div>
            <div>Status: {status}</div>
            <div>Cases: {cases_total}</div>
            <div>Divergences: {cases_divergent}</div>
            <div>Paragraph coverage: {para_reached}/{para_total}</div>
            <div>Branch coverage (Coroner definition): {branch_reached}/{branch_total}</div>
        </div>
        '''
    else:
        # Escape the reason
        escaped_reason = html.escape(result.reason)
        html_content = f'''
        <div style="padding: 1rem; background: #4d1b1b; color: #f87171; border-radius: 4px;">
            <div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 0.5rem;">Certificate: INVALID</div>
            <div>{escaped_reason}</div>
        </div>
        '''
    
    return HTMLResponse(content=html_content)


@app.get("/tamper", response_class=HTMLResponse)
async def tamper_form(request: Request, run_id: str):
    """
    Tamper form page.
    
    Shows a form prefilled with certificate values for editing.
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
    
    # Size limit check: 1 MB
    if certificate_file.stat().st_size > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Certificate too large")
    
    # Load certificate
    try:
        cert_data = json.loads(certificate_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to read certificate: {e}")
    
    # Extract editable fields
    status = html.escape(cert_data.get("status", ""))
    cases_total = cert_data.get("cases_total", 0)
    cases_divergent = cert_data.get("cases_divergent", 0)
    random_seed = cert_data.get("random_seed", 0)
    
    return templates.TemplateResponse(
        request=request,
        name="tamper.html",
        context={
            "run_id": run_id,
            "status": status,
            "cases_total": cases_total,
            "cases_divergent": cases_divergent,
            "random_seed": random_seed
        }
    )


@app.post("/api/tamper")
async def tamper_certificate(
    request: Request,
    run_id: str = Form(...),
    status: str = Form(...),
    cases_total: int = Form(...),
    cases_divergent: int = Form(...),
    random_seed: int = Form(...)
):
    """
    Tamper with certificate values and replay.
    
    Creates a tampered copy, recomputes certificate_sha256, replays it,
    and returns the validation result. The tampered copy is deleted after replay.
    
    Accepts application/x-www-form-urlencoded (htmx default).
    Returns Cache-Control: no-store, no-cache, must-revalidate (via middleware).
    """
    # Get client address
    client_ip = get_client_address(request)
    
    # Rate limiting: /api/tamper 1 per 10 seconds per client (same as verify, configurable for tests)
    tamper_window = int(os.environ.get("CORONER_TAMPER_RATE_WINDOW", "10"))
    retry_after = check_rate_limit(f"endpoint:/api/tamper:ip:{client_ip}", 1, tamper_window)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded for tamper", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Rate limiting: global 100/min
    retry_after = check_rate_limit("global", 100, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Rate limiting: per IP 20/min
    retry_after = check_rate_limit(f"ip:{client_ip}", 20, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    validate_run_id(run_id)
    
    # Validate status
    if status not in ["ALIVE", "ZOMBIE", "ERROR"]:
        return JSONResponse(status_code=422, content={"detail": "status must be ALIVE, ZOMBIE, or ERROR"})
    
    # Validate integer bounds
    if not (0 <= cases_total <= 1000000):
        return JSONResponse(status_code=422, content={"detail": "cases_total must be between 0 and 1000000"})
    if not (0 <= cases_divergent <= 1000000):
        return JSONResponse(status_code=422, content={"detail": "cases_divergent must be between 0 and 1000000"})
    if not (0 <= random_seed <= 1000000):
        return JSONResponse(status_code=422, content={"detail": "random_seed must be between 0 and 1000000"})
    
    # Check if run directory exists
    run_dir = get_base_dir() / "runs" / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        return JSONResponse(status_code=404, content={"detail": "Run not found"})
    
    # Check if certificate exists
    original_cert_path = run_dir / "certificate.json"
    if not original_cert_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Certificate not found"})
    
    # Size limit check: 1 MB
    if original_cert_path.stat().st_size > 1024 * 1024:
        return JSONResponse(status_code=413, content={"detail": "Certificate too large"})
    
    # Read original certificate
    try:
        cert_data = json.loads(original_cert_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return JSONResponse(status_code=500, content={"detail": f"Failed to read certificate: {e}"})
    
    # Generate random tampered copy filename
    import secrets
    tampered_id = secrets.token_hex(6)
    exchange_dir = get_exchange_dir()
    tamper_dir = exchange_dir / "tamper"
    tamper_dir.mkdir(parents=True, exist_ok=True)
    tampered_path = tamper_dir / f"{tampered_id}.json"
    
    try:
        # Apply edits
        cert_data["status"] = status
        cert_data["cases_total"] = cases_total
        cert_data["cases_divergent"] = cases_divergent
        cert_data["random_seed"] = random_seed
        
        # Recompute certificate_sha256 using the same function as the product
        # Remove the old hash first
        cert_data.pop("certificate_sha256", None)
        
        # Compute hash using shared function
        cert_hash = compute_certificate_sha256(cert_data)
        cert_data["certificate_sha256"] = cert_hash
        
        # Write tampered copy
        with open(tampered_path, 'w', encoding='utf-8') as f:
            json.dump(cert_data, f, indent=2, sort_keys=True)
            f.write('\n')
        
        # Replay the tampered certificate off the event loop with timeout
        replay_timeout = int(os.environ.get("CORONER_REPLAY_TIMEOUT", "90"))
        base_dir = get_base_dir()
        result = await run_in_threadpool(
            replay_with_timeout,
            str(tampered_path),
            str(base_dir),
            replay_timeout
        )
        
        # Build HTML fragment
        if result.valid:
            # Escape all dynamic values
            status = html.escape(result.verdict.status if result.verdict else "not recorded")
            cases_total = html.escape(str(result.cases_total))
            cases_divergent = html.escape(str(result.cases_divergent))
            
            response_html = f'''
            <div style="padding: 1rem; background: #1b4d3e; color: #4ade80; border-radius: 4px;">
                <div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 0.5rem;">Certificate: VALID</div>
                <div>Status: {status}</div>
                <div>Cases: {cases_total}</div>
                <div>Divergences: {cases_divergent}</div>
            </div>
            '''
        else:
            # Escape the reason (note: already escaped above, but for consistency)
            escaped_reason = html.escape(result.reason)
            response_html = f'''
            <div style="padding: 1rem; background: #4d1b1b; color: #f87171; border-radius: 4px;">
                <div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 0.5rem;">Certificate: INVALID</div>
                <div>{escaped_reason}</div>
            </div>
            '''
        
        return HTMLResponse(content=response_html)
        
    finally:
        # Delete the tampered copy
        if tampered_path.exists():
            tampered_path.unlink()


# Cache for gate-check responses (keyed by certificate SHA-256)
_gate_check_cache: Dict[str, dict] = {}  # cert_sha256 -> {response, timestamp}
_gate_check_cache_lock = threading.Lock()


def get_cached_gate_check(cert_sha256: str) -> Optional[dict]:
    """Get cached gate check response if not expired (600 s)."""
    with _gate_check_cache_lock:
        if cert_sha256 not in _gate_check_cache:
            return None
        
        entry = _gate_check_cache[cert_sha256]
        timestamp = entry.get("timestamp", 0.0)
        
        # Check if expired (600 s TTL)
        if time.time() - timestamp > 600:
            del _gate_check_cache[cert_sha256]
            return None
        
        return entry.get("response")


def cache_gate_check(cert_sha256: str, response: dict):
    """Cache a gate check response."""
    with _gate_check_cache_lock:
        _gate_check_cache[cert_sha256] = {
            "response": response,
            "timestamp": time.time()
        }


# ReplayResult has no "completed" flag; the reason of a replay that did not reach a
# verdict starts with one of these texts. Sources: replay_with_timeout in this file
# ("replay timed out", "replay failed: ...") and replay_certificate in
# coroner/certificate.py ("replay error: ..." for an unexpected exception,
# "reference did not run during replay: ..." when the COBOL reference produced nothing).
# Every other invalid reason (content modified, hash mismatch, "replay mismatch (...)")
# comes from a replay that compared the certificate with the real files or a real re-run.
_REPLAY_NOT_COMPLETED_PREFIXES = (
    "replay timed out",
    "replay failed:",
    "replay error:",
    "reference did not run during replay",
)


def replay_reached_verdict(result: ReplayResult) -> bool:
    """True when the replay gave a real answer (VALID, or INVALID for a real mismatch)."""
    return result.valid or not result.reason.startswith(_REPLAY_NOT_COMPLETED_PREFIXES)


def clear_gate_check_cache():
    """Clear the gate check cache. Used only in tests."""
    with _gate_check_cache_lock:
        _gate_check_cache.clear()


# Messages of the gate-check answer. The story fragment compares the returned message with
# these constants to pick the badge, so the text lives in one place.
GATE_MESSAGE_ALLOWED = "Commit allowed"
GATE_MESSAGE_ZOMBIE = "This ZOMBIE migration cannot be committed"
GATE_MESSAGE_INVALID = "Certificate invalid or does not match the audited files"
GATE_MESSAGE_UNAVAILABLE = "Replay did not complete, try again"


@app.post("/api/gate-check")
async def gate_check(request: Request, run_id: str = Form(...)):
    """
    Gate check endpoint for guided story.
    
    Checks if a certificate would pass the gate (commit/push allowed).
    Reads certificate from CORONER_BASE_DIR/runs/<run_id>/certificate.json,
    replays it, and returns the gate decision.
    
    Returns JSON: {status: "allowed"|"blocked", exit_code: 0|1, message: string}
    
    Accepts application/x-www-form-urlencoded.
    Returns Cache-Control: no-store via middleware.
    Caches responses by certificate SHA-256 for 600 s.
    """
    # Get client address
    client_ip = get_client_address(request)
    
    # Rate limiting: global 100/min
    retry_after = check_rate_limit("global", 100, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Rate limiting: per IP 20/min
    retry_after = check_rate_limit(f"ip:{client_ip}", 20, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Validate run_id
    validate_run_id(run_id)
    
    # Check if certificate exists
    base_dir = get_base_dir()
    cert_path = base_dir / "runs" / run_id / "certificate.json"
    
    if not cert_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Certificate not found"})
    
    # Size limit: 1 MB
    if cert_path.stat().st_size > 1024 * 1024:
        return JSONResponse(status_code=413, content={"detail": "Certificate too large"})
    
    # Load certificate
    try:
        cert_bytes = cert_path.read_bytes()
        cert_data = json.loads(cert_bytes.decode('utf-8'))
    except (json.JSONDecodeError, OSError) as e:
        return JSONResponse(status_code=500, content={"detail": f"Failed to read certificate: {e}"})
    
    # Check cache by SHA-256 of raw certificate file bytes (not the field inside)
    cert_file_sha256 = hashlib.sha256(cert_bytes).hexdigest()
    cached_response = get_cached_gate_check(cert_file_sha256)
    if cached_response is not None:
        return JSONResponse(content=cached_response)
    
    # Cache miss: will perform replay, so check the gate-check-specific rate limit
    # Rate limiting: /api/gate-check 1 per 10 seconds per client (same as verify)
    gate_check_window = int(os.environ.get("CORONER_GATE_CHECK_RATE_WINDOW", "10"))
    retry_after = check_rate_limit(f"endpoint:/api/gate-check:ip:{client_ip}", 1, gate_check_window)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded for gate-check", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Build scope from certificate
    scope = {
        "cobol": cert_data.get("cobol_file", ""),
        "java": cert_data.get("java_file", ""),
        "schema": cert_data.get("schema_file", ""),
        "copybooks": cert_data.get("copybook_dir", "")
    }
    
    # Check file hashes (treat exceptions as hash_match = False)
    repo_root = get_repo_root()
    try:
        hash_match = certificate_matches_files(cert_data, scope, repo_root)
    except Exception:
        hash_match = False
    
    # Replay certificate off the event loop
    replay_timeout = int(os.environ.get("CORONER_REPLAY_TIMEOUT", "90"))
    result = await run_in_threadpool(
        replay_with_timeout,
        str(cert_path),
        str(base_dir),
        replay_timeout
    )
    
    # A replay that did not run to a verdict (timeout, kill, process error) says
    # nothing about the certificate: answer 503 and cache nothing
    if not replay_reached_verdict(result):
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "message": GATE_MESSAGE_UNAVAILABLE,
                "retry_after": gate_check_window,
            },
            headers={"Retry-After": str(gate_check_window)}
        )
    
    # Get replay status
    replay = "VALID" if result.valid else "INVALID"
    
    # Get verdict status
    status = cert_data.get("status")
    
    # Get gate decision
    exit_code = gate_decision(status, replay, hash_match)
    
    # Build response
    if exit_code == 0:
        response_data = {
            "status": "allowed",
            "exit_code": 0,
            "message": GATE_MESSAGE_ALLOWED
        }
    else:
        # exit_code is 1 or 2
        # Only show "ZOMBIE cannot be committed" when hash matches, replay is VALID, and status is ZOMBIE
        if hash_match and replay == "VALID" and status == "ZOMBIE":
            message = GATE_MESSAGE_ZOMBIE
        else:
            message = GATE_MESSAGE_INVALID
        
        response_data = {
            "status": "blocked",
            "exit_code": exit_code,
            "message": message
        }
    
    # Cache the response by file SHA-256
    cache_gate_check(cert_file_sha256, response_data)
    
    return JSONResponse(content=response_data)


@app.get("/matrix", response_class=HTMLResponse)
async def matrix_page(request: Request):
    """Detection Matrix page."""
    catalog_file = get_base_dir() / "runs" / "trap_catalog.json"
    registry = load_cases_registry()
    
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
                        "case": case_label(trap_id, registry) or "not recorded",
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
                        "case": case_label(trap_id, registry) or "not recorded",
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


# Pydantic models for API

class RunAuditRequest(BaseModel):
    """Request to run an audit."""
    sample: str = Field(..., pattern=r"^(credit-fees|T1|T2|T3|T4|T5)$")
    port: str = Field(..., pattern=r"^(correct|faulty)$")
    seed: int = Field(..., ge=0, le=1000000)
    cases: int = Field(..., ge=10, le=2000)
    
    class Config:
        extra = "forbid"  # Reject unknown fields


# Rate limiting (simple in-app sliding window)


class RateLimiter:
    """
    Thread-safe sliding window rate limiter.
    
    Limits are per API process (one uvicorn worker).
    """
    
    def __init__(self):
        self._windows: Dict[str, list] = {}
        self._lock = threading.Lock()
    
    def reset(self):
        """Reset all rate limit windows (for tests)."""
        with self._lock:
            self._windows.clear()
    
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Check if a request is allowed under the rate limit.
        
        Returns (allowed, retry_after_seconds).
        """
        with self._lock:
            now = time.time()
            
            # Get or create window for this key
            if key not in self._windows:
                self._windows[key] = []
            
            window = self._windows[key]
            
            # Remove expired timestamps
            cutoff = now - window_seconds
            window[:] = [ts for ts in window if ts > cutoff]
            
            # Check limit
            if len(window) >= limit:
                # Calculate retry-after (time until oldest request expires)
                oldest = min(window)
                retry_after = int(oldest + window_seconds - now) + 1
                return False, retry_after
            
            # Allow request
            window.append(now)
            return True, 0


# Global rate limiter
_rate_limiter = RateLimiter()


def reset_rate_limiter():
    """Reset rate limiter state (exposed for tests)."""
    _rate_limiter.reset()
    _active_audits.clear()


def check_rate_limit(key: str, limit: int, window_seconds: int) -> Optional[int]:
    """
    Check rate limit. Returns None if allowed, retry-after seconds if denied.
    """
    allowed, retry_after = _rate_limiter.is_allowed(key, limit, window_seconds)
    if not allowed:
        return retry_after
    return None


def get_client_address(request: Request) -> str:
    """
    Get client address.
    
    Uses CF-Connecting-IP only when the request comes from a trusted proxy
    (CORONER_TRUSTED_PROXY), otherwise the direct peer address.
    
    CORONER_TRUSTED_PROXY is a comma-separated list of proxy IPs.
    """
    peer_address = request.client.host if request.client else "unknown"
    
    # Get trusted proxies from environment
    trusted_proxies_str = os.environ.get("CORONER_TRUSTED_PROXY", "")
    if not trusted_proxies_str:
        # No trusted proxies configured, never trust the header
        return peer_address
    
    # Parse trusted proxies
    trusted_proxies = [p.strip() for p in trusted_proxies_str.split(",") if p.strip()]
    
    if not trusted_proxies:
        return peer_address
    
    # Check if peer is trusted
    if peer_address not in trusted_proxies:
        # Request comes from untrusted peer, ignore the header
        return peer_address
    
    # Request comes from trusted proxy, use CF-Connecting-IP if present
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip
    
    # Header not present, use peer address
    return peer_address


def get_exchange_dir() -> Path:
    """Get exchange directory from environment, default /exchange."""
    return Path(os.environ.get("CORONER_EXCHANGE_DIR", "/exchange"))


def get_run_index() -> Dict[str, str]:
    """
    Read run index from CORONER_BASE_DIR/run_index.json.
    
    Returns a mapping from "sample:port:seed:cases" to run_id.
    Handles both old format (key -> run_id) and new format (key -> {run_id, recorded_at}).
    """
    index_file = get_base_dir() / "run_index.json"
    
    if not index_file.exists():
        return {}
    
    try:
        raw_index = json.loads(index_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    
    # Convert to simple mapping for backward compatibility
    result = {}
    for k, v in raw_index.items():
        if isinstance(v, str):
            # Old format: key -> run_id string
            result[k] = v
        elif isinstance(v, dict):
            # New format: key -> {run_id, recorded_at}
            run_id = v.get("run_id")
            if run_id:
                result[k] = run_id
    
    return result


def update_run_index(sample: str, port: str, seed: int, cases: int, run_id: str, bundled: bool = False):
    """
    Update run index with a new run.
    
    Writes atomically to CORONER_BASE_DIR/run_index.json.
    Enforces visitor run quota by pruning oldest entries.
    Bundled runs (bundled=True) are never counted toward quota or deleted.
    """
    index_file = get_base_dir() / "run_index.json"
    
    # Read existing index
    raw_index = {}
    if index_file.exists():
        try:
            raw_index = json.loads(index_file.read_text())
        except (json.JSONDecodeError, OSError):
            raw_index = {}
    
    # Migrate entries without recorded_at to oldest (epoch 0)
    index = {}
    for k, v in raw_index.items():
        if isinstance(v, str):
            # Old format: key -> run_id string
            index[k] = {"run_id": v, "recorded_at": 0.0}
        elif isinstance(v, dict):
            # New format: key -> {run_id, recorded_at, bundled}
            index[k] = v
        else:
            # Invalid format, skip
            continue
    
    # Add new entry with current timestamp and bundled flag
    key = f"{sample}:{port}:{seed}:{cases}"
    index[key] = {
        "run_id": run_id,
        "recorded_at": time.time(),
        "bundled": bundled
    }
    
    # Enforce quota (count only visitor runs, not bundled)
    max_visitor_runs = int(os.environ.get("CORONER_MAX_VISITOR_RUNS", "100"))
    
    # Count visitor runs only (bundled=False or not present)
    visitor_entries = {k: v for k, v in index.items() if not v.get("bundled", False)}
    
    if len(visitor_entries) > max_visitor_runs:
        # Sort visitor entries by recorded_at (oldest first)
        sorted_visitor_entries = sorted(visitor_entries.items(), key=lambda item: item[1].get("recorded_at", 0.0))
        
        # Keep only the newest max_visitor_runs entries
        entries_to_keep = sorted_visitor_entries[-max_visitor_runs:]
        entries_to_delete = sorted_visitor_entries[:-max_visitor_runs]
        
        # Delete old run directories
        runs_dir = get_base_dir() / "runs"
        for _, entry in entries_to_delete:
            old_run_id = entry.get("run_id")
            if not old_run_id:
                continue
            
            # Validate run_id before building path
            if not RUN_ID_PATTERN.match(old_run_id):
                continue
            
            # Build path and verify it's within runs_dir
            run_dir = runs_dir / old_run_id
            
            # Resolve to absolute path and check it's under runs_dir
            try:
                run_dir_resolved = run_dir.resolve()
                runs_dir_resolved = runs_dir.resolve()
                
                # Check if run_dir is under runs_dir (prevent path traversal)
                if not str(run_dir_resolved).startswith(str(runs_dir_resolved) + os.sep):
                    continue
                
                # Check it's not a symlink pointing outside
                if run_dir.is_symlink():
                    continue
                
                # Delete the directory
                if run_dir_resolved.exists() and run_dir_resolved.is_dir():
                    import shutil
                    shutil.rmtree(run_dir_resolved)
            except (OSError, ValueError):
                # Skip on any error
                continue
        
        # Rebuild index: keep bundled entries + newest visitor entries
        kept_visitor_keys = {k for k, _ in entries_to_keep}
        bundled_entries = {k: v for k, v in index.items() if v.get("bundled", False)}
        kept_visitor_entries = {k: v for k, v in index.items() if k in kept_visitor_keys}
        
        # Merge bundled + kept visitor entries
        index = {**bundled_entries, **kept_visitor_entries}
    
    # Write atomically
    temp_file = index_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(index, indent=2))
    temp_file.replace(index_file)


def find_cached_run(sample: str, port: str, seed: int, cases: int) -> Optional[str]:
    """
    Find a cached run with identical parameters.
    
    Returns the run_id if found and the run folder exists, None otherwise.
    """
    index = get_run_index()
    key = f"{sample}:{port}:{seed}:{cases}"
    
    run_id = index.get(key)
    if not run_id:
        return None
    
    # Check if run folder exists
    run_dir = get_base_dir() / "runs" / run_id
    if not run_dir.exists():
        return None
    
    return run_id


def generate_job_id() -> str:
    """Generate a unique 12-character hex job ID."""
    # Use timestamp + random bytes
    import secrets
    timestamp = int(time.time() * 1000)
    random_bytes = secrets.token_bytes(6)
    
    # Combine and hash
    data = timestamp.to_bytes(8, 'big') + random_bytes
    h = hashlib.sha256(data).hexdigest()
    return h[:12]


# Active audits tracking (per IP)
_active_audits: Dict[str, str] = {}  # ip -> job_id


def has_active_audit(ip: str) -> bool:
    """Check if an IP has an active audit."""
    if ip not in _active_audits:
        return False
    
    # Check if the job is still active
    job_id = _active_audits[ip]
    exchange_dir = get_exchange_dir()
    job_dir = exchange_dir / "jobs" / job_id
    
    if not job_dir.exists():
        # Job completed or deleted
        del _active_audits[ip]
        return False
    
    # Check status
    status_file = job_dir / "status.json"
    if not status_file.exists():
        del _active_audits[ip]
        return False
    
    try:
        status_data = json.loads(status_file.read_text())
        status = status_data.get("status")
        
        if status in ["done", "error"]:
            # Job completed
            del _active_audits[ip]
            return False
        
        return True
    except (json.JSONDecodeError, OSError):
        del _active_audits[ip]
        return False


def mark_audit_active(ip: str, job_id: str):
    """Mark an audit as active for an IP."""
    _active_audits[ip] = job_id


# Queue management
def get_queue_length() -> int:
    """Get current queue length (queued + running jobs)."""
    exchange_dir = get_exchange_dir()
    jobs_dir = exchange_dir / "jobs"
    
    if not jobs_dir.exists():
        return 0
    
    count = 0
    for job_dir in jobs_dir.iterdir():
        if not job_dir.is_dir():
            continue
        
        status_file = job_dir / "status.json"
        if not status_file.exists():
            continue
        
        try:
            status_data = json.loads(status_file.read_text())
            status = status_data.get("status")
            
            if status in ["queued", "running"]:
                count += 1
        except (json.JSONDecodeError, OSError):
            continue
    
    return count


@app.post("/api/run")
async def run_audit(
    request: Request,
    sample: str = Form(None),
    port: str = Form(None),
    seed: int = Form(None),
    cases: int = Form(None),
):
    """
    Submit a Run audit request.
    
    Accepts both JSON and form-encoded data.
    Returns 202 Accepted with job_id (or 200 with run_id if cache hit).
    Returns 413 if body size exceeds 16 KB (enforced by middleware).
    Returns 422 if validation fails.
    Returns 429 if queue is full or IP has active audit.
    All responses include Cache-Control: no-store, no-cache, must-revalidate.
    """
    # Parse and validate request (JSON or form)
    if sample is None:
        # JSON request
        try:
            body = await request.json()
            audit_request = RunAuditRequest(**body)
        except Exception as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
    else:
        # Form request
        try:
            audit_request = RunAuditRequest(
                sample=sample,
                port=port,
                seed=seed,
                cases=cases
            )
        except Exception as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
    
    # Get client address
    client_ip = get_client_address(request)
    
    # Rate limiting: global 100/min
    retry_after = check_rate_limit("global", 100, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Rate limiting: per IP 20/min
    retry_after = check_rate_limit(f"ip:{client_ip}", 20, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Rate limiting: per endpoint /api/run 5/min per IP
    retry_after = check_rate_limit(f"endpoint:/api/run:ip:{client_ip}", 5, 60)
    if retry_after:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded for this endpoint", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)}
        )
    
    # Check if IP has an active audit
    if has_active_audit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "One audit per client at a time", "retry_after": 10},
            headers={"Retry-After": "10"}
        )
    
    # Check queue length (default max 3)
    max_queue_length = int(os.environ.get("CORONER_MAX_QUEUE_LENGTH", "3"))
    if get_queue_length() >= max_queue_length:
        return JSONResponse(
            status_code=429,
            content={"detail": "Queue full, try again later", "retry_after": 30},
            headers={"Retry-After": "30"}
        )
    
    # Check if run already exists (cache hit)
    cached_run_id = find_cached_run(
        audit_request.sample,
        audit_request.port,
        audit_request.seed,
        audit_request.cases
    )
    
    if cached_run_id:
        # Cache hit, return existing run
        return JSONResponse(
            status_code=200,
            content={"run_id": cached_run_id, "cached": True}
        )
    
    # Create job
    job_id = generate_job_id()
    exchange_dir = get_exchange_dir()
    jobs_dir = exchange_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    
    job_dir = jobs_dir / job_id
    job_dir.mkdir()
    
    # Write request.json
    request_data = {
        "job_id": job_id,
        "sample": audit_request.sample,
        "port": audit_request.port,
        "seed": audit_request.seed,
        "cases": audit_request.cases,
        "timestamp": time.time(),
    }
    
    request_file = job_dir / "request.json"
    request_file.write_text(json.dumps(request_data, indent=2))
    
    # Write status.json (queued)
    status_data = {
        "status": "queued",
        "queued_at": time.time(),
    }
    
    status_file = job_dir / "status.json"
    status_file.write_text(json.dumps(status_data, indent=2))
    
    # Mark audit as active for this IP
    mark_audit_active(client_ip, job_id)
    
    # Return 202 Accepted
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id},
        headers={"Location": f"/api/job/{job_id}/status"}
    )


@app.get("/api/job/{job_id}/status")
async def job_status(job_id: str):
    """
    Get status of a job.
    
    Returns {status: queued|running|done|error, run_id: ..., verdict: ..., cases_divergent: ..., cases_total: ...}
    When done, also returns verdict, cases_divergent and cases_total from verdict.json.
    All responses include Cache-Control: no-store, no-cache, must-revalidate (via middleware).
    """
    # Validate job_id
    from coroner.engine_worker import validate_job_id
    
    if not validate_job_id(job_id):
        return JSONResponse(status_code=404, content={"detail": "Invalid job_id"})
    
    # Check job directory
    exchange_dir = get_exchange_dir()
    job_dir = exchange_dir / "jobs" / job_id
    
    if not job_dir.exists():
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    
    # Read status
    status_file = job_dir / "status.json"
    if not status_file.exists():
        return JSONResponse(status_code=404, content={"detail": "Status not found"})
    
    try:
        status_data = json.loads(status_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return JSONResponse(status_code=500, content={"detail": f"Failed to read status: {e}"})
    
    status = status_data.get("status")
    run_id = status_data.get("run_id")
    
    response_content = {
        "status": status,
    }
    
    if run_id:
        response_content["run_id"] = run_id
    
    # If status is error, include reason
    if status == "error":
        reason = status_data.get("reason")
        if reason:
            response_content["reason"] = reason
    
    # If status is done, copy result to CORONER_BASE_DIR and clean up job
    if status == "done" and run_id:
        # Check if result has been copied already
        base_dir = get_base_dir()
        run_dir = base_dir / "runs" / run_id
        
        # Check if run_dir existed BEFORE the job completed (bundled run)
        bundled = run_dir.exists()
        
        if not bundled:
            # Copy result from exchange to base_dir
            job_run_dir = job_dir / "runs" / run_id
            
            if job_run_dir.exists():
                import shutil
                runs_dir = base_dir / "runs"
                runs_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy the run directory
                shutil.copytree(job_run_dir, run_dir)
        
        # Read verdict from the run in CORONER_BASE_DIR
        verdict_file = run_dir / "verdict.json"
        if verdict_file.exists():
            try:
                verdict_data = json.loads(verdict_file.read_text())
                response_content["verdict"] = verdict_data.get("status")
                # For ZOMBIE, also include divergence counts
                if verdict_data.get("status") == "ZOMBIE":
                    response_content["cases_divergent"] = verdict_data.get("cases_divergent")
                    response_content["cases_total"] = verdict_data.get("cases_total")
            except (json.JSONDecodeError, OSError):
                pass
        
        # Update run index (always, whether bundled or not)
        request_file = job_dir / "request.json"
        if request_file.exists():
            try:
                request_data = json.loads(request_file.read_text())
                sample = request_data.get("sample")
                port = request_data.get("port")
                seed = request_data.get("seed")
                cases = request_data.get("cases")
                
                if all([sample, port, seed is not None, cases is not None]):
                    update_run_index(sample, port, seed, cases, run_id, bundled=bundled)
            except (json.JSONDecodeError, OSError):
                pass
        
        # Delete job directory
        import shutil
        shutil.rmtree(job_dir)
    
    return JSONResponse(content=response_content)


# The guided story pages and fragments (coroner/ui/story_routes.py). They call the route
# functions above, so this import stays at the end of the module.
from coroner.ui.story_routes import router as story_router  # noqa: E402

app.include_router(story_router)


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
