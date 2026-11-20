"""Tests for video recording and subtitle tools."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_make_srt_help_exits_zero():
    """Test that make_srt.py --help exits 0 without writing files."""
    result = subprocess.run(
        [sys.executable, "scripts/make_srt.py", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"make_srt.py --help failed: {result.stderr}"
    assert "Generate SRT subtitles" in result.stdout


def test_make_srt_generates_valid_subtitles(tmp_path):
    """Test that make_srt.py generates valid SRT with monotonic, non-overlapping cues."""
    out_file = tmp_path / "test.srt"
    
    result = subprocess.run(
        [sys.executable, "scripts/make_srt.py", "--out", str(out_file)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"make_srt.py failed: {result.stderr}"
    
    # Check SRT file exists
    assert out_file.exists(), "SRT file not created"
    
    # Parse SRT and validate
    content = out_file.read_text(encoding='utf-8')
    
    # SRT format: sequence number, time range, text, blank line
    cues = []
    lines = content.strip().split('\n')
    
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        
        # Sequence number
        seq = int(lines[i])
        i += 1
        
        # Time range
        time_line = lines[i]
        i += 1
        
        # Parse time range: HH:MM:SS,mmm --> HH:MM:SS,mmm
        start_str, end_str = time_line.split(' --> ')
        
        def parse_srt_time(t):
            h, m, s = t.split(':')
            s, ms = s.split(',')
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        
        start = parse_srt_time(start_str)
        end = parse_srt_time(end_str)
        
        # Subtitle text (may be multiple lines)
        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i])
            i += 1
        
        cues.append({
            'seq': seq,
            'start': start,
            'end': end,
            'text': '\n'.join(text_lines)
        })
        
        i += 1  # Skip blank line
    
    assert len(cues) > 0, "No cues found in SRT"
    
    # Check monotonic and non-overlapping
    for i, cue in enumerate(cues):
        # Start < end
        assert cue['start'] < cue['end'], \
            f"Cue {cue['seq']}: start {cue['start']} >= end {cue['end']}"
        
        # Non-overlapping with next
        if i + 1 < len(cues):
            next_cue = cues[i + 1]
            assert cue['end'] <= next_cue['start'], \
                f"Cue {cue['seq']} overlaps with {next_cue['seq']}: " \
                f"ends at {cue['end']} but next starts at {next_cue['start']}"
    
    # Check duration under 2:50 (170 seconds)
    last_end = cues[-1]['end']
    assert last_end <= 170, \
        f"Last cue ends at {last_end}s, exceeds 2:50 (170s)"


def test_make_srt_replaces_business_fix_marker(tmp_path):
    """Test that make_srt.py replaces business_fix marker with real value from trap.json."""
    out_file = tmp_path / "test.srt"
    
    result = subprocess.run(
        [sys.executable, "scripts/make_srt.py", "--out", str(out_file)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    
    # Load expected value from trap.json
    trap_json_path = Path("samples/traps/T1-ebcdic-match-merge/trap.json")
    with open(trap_json_path) as f:
        trap_data = json.load(f)
    
    expected_fix = trap_data["business_fix"]
    
    # Check SRT content contains the actual fix text, not the marker
    content = out_file.read_text()
    assert expected_fix in content, f"Expected business_fix '{expected_fix}' not found in SRT"
    assert "<!-- MEASURED:" not in content, "MEASURED marker left in output"


def test_record_demo_help_exits_zero():
    """Test that record_demo.py --help exits 0."""
    result = subprocess.run(
        [sys.executable, "scripts/record_demo.py", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"record_demo.py --help failed: {result.stderr}"
    assert "Record demo videos" in result.stdout


def test_record_demo_disk_space_guard(tmp_path):
    """Test that disk space guard exits 2 when threshold is exceeded."""
    # Get actual free space of tmp_path
    stat = shutil.disk_usage(tmp_path)
    free_gb = stat.free / (1024 ** 3)
    
    # Set threshold above actual free space
    threshold_gb = free_gb + 1000
    
    # Run script with impossible threshold
    result = subprocess.run(
        [
            sys.executable,
            "scripts/record_demo.py",
            "--out", str(tmp_path),
            "--min-free-gb", str(threshold_gb),
            "--scene", "zombie_verdict",
            "--url", "http://127.0.0.1:9999"  # Won't be reached
        ],
        capture_output=True,
        text=True
    )
    
    # Should exit 2 before trying to launch browser
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}"
    assert "free disk space available" in result.stderr
    assert f"Need at least {threshold_gb:.0f} GB" in result.stderr
    
    # Check nothing was written
    files_created = list(tmp_path.iterdir())
    assert len(files_created) == 0, f"Files were created despite disk space error: {files_created}"


def test_record_demo_visits_existing_routes():
    """Test that every route record_demo.py visits exists in the FastAPI app."""
    from coroner.ui.app import app
    
    # Get all routes from the app
    routes = set()
    for route in app.routes:
        if hasattr(route, 'path'):
            routes.add(route.path)
    
    # Read record_demo.py and extract routes it visits
    script_path = Path("scripts/record_demo.py")
    content = script_path.read_text()
    
    # Extract page.goto(...) calls with f-strings
    import re
    
    # Pattern: page.goto(f"{url}/...") or page.goto(f"{url}/run/{run_id}")
    goto_pattern = r'page\.goto\(f?["\'](?:\{url\})?([^"\']+)'
    
    visited_routes = set()
    for match in re.finditer(goto_pattern, content):
        route = match.group(1)
        # Remove {url} prefix if present
        if route.startswith("{url}"):
            route = route[5:]
        
        # Extract static part before any {variable}
        static_part = re.split(r'\{', route)[0]
        
        # Clean up
        if static_part.startswith("/"):
            visited_routes.add(static_part)
    
    # Check each visited route exists (as a prefix)
    for visited in visited_routes:
        # Check if any app route matches (exact or parameterized)
        found = False
        for app_route in routes:
            # Match /run/{run_id} with /run/
            if app_route.startswith(visited) or visited.startswith(app_route.rstrip("/")):
                found = True
                break
            # Also check if it's a parameterized route like /run/{run_id}
            if "{" in app_route:
                # Extract static prefix
                app_prefix = app_route.split("{")[0]
                if visited.startswith(app_prefix):
                    found = True
                    break
        
        assert found, \
            f"Route '{visited}' visited by record_demo.py does not exist in app. " \
            f"Available routes: {sorted(routes)}"


def test_video_plan_no_em_dash_and_measured_markers():
    """Test that video-plan.md has no em dash and all MEASURED markers reference existing files."""
    plan_path = Path("docs/video-plan.md")
    assert plan_path.exists(), "docs/video-plan.md not found"
    
    content = plan_path.read_text()
    
    # Check no em dash
    assert "\u2014" not in content, "Em dash found in video-plan.md"
    
    # Extract all MEASURED markers and check referenced files exist
    # Pattern: <!-- MEASURED: ... from <path> -->
    marker_pattern = r'<!-- MEASURED: [^>]+ from ([^>]+) -->'
    
    bundled_run_ids = {"f584d5f35228", "29c15f04407b"}
    
    for match in re.finditer(marker_pattern, content):
        path_ref = match.group(1).strip()
        
        # Handle runs/<id> references
        if path_ref.startswith("runs/"):
            # Extract run_id from path like "runs/f584d5f35228/verdict.json"
            parts = path_ref.split("/")
            if len(parts) >= 2:
                run_id = parts[1]
                assert run_id in bundled_run_ids, \
                    f"MEASURED marker references run {run_id} which is not a bundled run ID"
        else:
            # Regular file path - must exist
            file_path = Path(path_ref)
            assert file_path.exists(), \
                f"MEASURED marker references '{path_ref}' which does not exist"
