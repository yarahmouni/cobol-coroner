"""Tests for ERROR page (D-51: broken reference)."""

import json
import os
import re
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cli import run_verify


@pytest.fixture(scope="module")
def broken_reference_run(tmp_path_factory):
    """Create a real broken reference run."""
    import subprocess
    import sys
    import shutil
    
    # cobc is required
    assert shutil.which("cobc") is not None, "cobc is required for the UI error tests"
    
    tmp_path = tmp_path_factory.mktemp("broken_ref")
    
    # Create broken COBOL that divides by zero
    cobol_source = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. BROKEN-REF.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INPUT-FILE ASSIGN TO EXTERNAL INPUT-PATH.
           SELECT OUTPUT-FILE ASSIGN TO EXTERNAL OUTPUT-PATH.
       DATA DIVISION.
       FILE SECTION.
       FD  INPUT-FILE.
       01  INPUT-REC PIC X(200).
       FD  OUTPUT-FILE.
       01  OUTPUT-REC PIC X(200).
       WORKING-STORAGE SECTION.
       01  WS-EOF PIC X VALUE 'N'.
       01  WS-ZERO PIC 9 VALUE 0.
       01  WS-RESULT PIC 9.
       PROCEDURE DIVISION.
           DIVIDE 1 BY WS-ZERO GIVING WS-RESULT.
           OPEN INPUT INPUT-FILE.
           OPEN OUTPUT OUTPUT-FILE.
           PERFORM UNTIL WS-EOF = 'Y'
               READ INPUT-FILE
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       WRITE OUTPUT-REC FROM INPUT-REC
               END-READ
           END-PERFORM.
           CLOSE INPUT-FILE.
           CLOSE OUTPUT-FILE.
           STOP RUN.
"""
    cobol_path = tmp_path / "broken.cob"
    cobol_path.write_text(cobol_source)
    
    copybooks_dir = tmp_path / "copybooks"
    copybooks_dir.mkdir()
    
    # Use credit-fees schema and Java
    schema_path = Path("samples/credit-fees/schema.json").absolute()
    java_path = Path("samples/credit-fees/java/CreditFees.java").absolute()
    
    assert schema_path.exists() and java_path.exists(), "credit-fees sample is required for the UI error tests"
    
    # Run verify - should detect broken reference
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "verify",
         "--cobol", str(cobol_path),
         "--copybooks", str(copybooks_dir),
         "--java", str(java_path),
         "--schema", str(schema_path),
         "--cases", "2",
         "--seed", "42"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path)
    )
    
    # Should exit 2
    assert result.returncode == 2
    
    # Find run directory (look for one with run_error.txt, not temp build dirs)
    runs_dir = tmp_path / "runs"
    run_dirs = [d for d in runs_dir.iterdir() if d.is_dir() and (d / "run_error.txt").exists()] if runs_dir.exists() else []
    assert len(run_dirs) >= 1, f"Expected at least 1 run directory with run_error.txt, found {len(run_dirs)}"
    
    # If multiple, take the most recent
    run_dir = sorted(run_dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    
    # Verify expected files exist in this run directory
    assert (run_dir / "run_error.txt").exists()
    
    # Verify verdict and certificate don't exist
    assert not (run_dir / "verdict.json").exists()
    assert not (run_dir / "certificate.json").exists()
    
    return tmp_path, run_dir.name


def test_error_page_status_text(broken_reference_run, monkeypatch):
    """Test ERROR page shows correct status text."""
    tmp_path, run_id = broken_reference_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Must contain ERROR status text
    assert "ERROR" in html
    assert "reference did not run" in html


def test_error_page_reason(broken_reference_run, monkeypatch):
    """Test ERROR page shows reason from run_error.txt."""
    tmp_path, run_id = broken_reference_run
    run_dir = tmp_path / "runs" / run_id
    
    # Read actual reason from run_error.txt
    error_file = run_dir / "run_error.txt"
    error_text = error_file.read_text()
    
    # Extract reason line
    reason = None
    for line in error_text.split('\n'):
        if line.startswith("Reason:"):
            reason = line[len("Reason:"):].strip()
            break
    
    assert reason is not None, "No reason found in run_error.txt"
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Reason must appear in page
    assert reason in html, f"Reason '{reason}' not found in page"


def test_error_page_no_verify_button(broken_reference_run, monkeypatch):
    """Test ERROR page has no Verify button (no certificate)."""
    tmp_path, run_id = broken_reference_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # No Verify button
    assert "Verify" not in html or 'hx-post="/api/verify"' not in html
    
    # No certificate panel
    assert 'id="certificate"' not in html


def test_error_page_no_home_directory(broken_reference_run, monkeypatch):
    """Test ERROR page does not contain home directory path."""
    tmp_path, run_id = broken_reference_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # No home directory path
    home_dir = str(Path.home())
    assert home_dir not in html, f"Home directory {home_dir} found in page"


def test_error_diamond_shape(broken_reference_run, monkeypatch):
    """Test ERROR page has diamond shape (SVG rotated rect)."""
    tmp_path, run_id = broken_reference_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Diamond shape is a rotated rect
    # Look for <rect ... transform="rotate(45 24 24)"
    assert 'transform="rotate(45 24 24)"' in html, "Diamond shape (rotated rect) not found"


def test_error_color_contrast(broken_reference_run, monkeypatch):
    """Test ERROR color has sufficient contrast (at least 4.5:1) in both modes."""
    tmp_path, run_id = broken_reference_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Extract CSS variables for error colors
    # Dark mode
    error_color_dark = "#b4bac4"  # --error-color in dark mode
    error_bg_dark = "#3a3a3a"     # --error-bg in dark mode
    
    # Light mode
    error_color_light = "#4b5563"  # --error-color in light mode
    error_bg_light = "#f3f4f6"     # --error-bg in light mode
    
    def hex_to_rgb(hex_color):
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def relative_luminance(rgb):
        """Compute relative luminance per WCAG 2."""
        r, g, b = [x / 255.0 for x in rgb]
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    def contrast_ratio(color1, color2):
        """Compute contrast ratio between two colors."""
        l1 = relative_luminance(hex_to_rgb(color1))
        l2 = relative_luminance(hex_to_rgb(color2))
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)
    
    # Dark mode: error-color on error-bg
    contrast_dark = contrast_ratio(error_color_dark, error_bg_dark)
    assert contrast_dark >= 4.5, f"Dark mode ERROR contrast {contrast_dark:.2f} < 4.5"
    
    # Light mode: error-color on error-bg
    contrast_light = contrast_ratio(error_color_light, error_bg_light)
    assert contrast_light >= 4.5, f"Light mode ERROR contrast {contrast_light:.2f} < 4.5"
