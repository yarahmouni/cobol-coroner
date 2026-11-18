#!/usr/bin/env python3
"""Generate screenshots from real runs for README."""
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Check if optional dependencies are installed
try:
    from playwright.sync_api import sync_playwright
    from PIL import Image
except ImportError as e:
    print(f"ERROR: {e}", file=sys.stderr)
    print("Install with: pip install -e '.[screenshots]'", file=sys.stderr)
    print("Then run: python -m playwright install chromium", file=sys.stderr)
    sys.exit(1)


def find_free_port():
    """Find a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def sanitize_output(text, clone_path, venv_path):
    """Replace clone path and venv path with 'repo' and check for home paths."""
    text = text.replace(str(clone_path), "repo")
    text = text.replace(str(venv_path), "repo/.venv")
    
    # Check for remaining home paths (built dynamically, never literal)
    forbidden_patterns = [
        "/" + "Users" + "/",
        "/" + "home" + "/",
        "/" + "var" + "/" + "folders",
        "/" + "tmp" + "/"
    ]
    for pattern in forbidden_patterns:
        if pattern in text:
            lines_with_pattern = [
                line for line in text.split("\n") if pattern in line
            ]
            print(f"ERROR: Output contains {pattern}:", file=sys.stderr)
            for line in lines_with_pattern:
                print(f"  {line}", file=sys.stderr)
            sys.exit(1)
    
    return text


def setup_temp_workspace():
    """Create temporary workspace."""
    temp_dir = tempfile.mkdtemp(prefix="coroner_screenshots_")
    return Path(temp_dir)


def produce_runs(base_dir):
    """Produce real runs for screenshots."""
    print("Producing runs in a temporary directory")
    
    # T1 faulty
    print("  Running T1 faulty...")
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
            "--copybooks", "samples/traps/T1-ebcdic-match-merge/copybooks",
            "--java", "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java",
            "--schema", "samples/traps/T1-ebcdic-match-merge/schema.json",
            "--cases", "2000",
            "--seed", "42"
        ],
        env={**os.environ, "CORONER_BASE_DIR": str(base_dir)},
        capture_output=True,
        text=True
    )
    
    # Parse run_id from output
    match = re.search(r"Run: runs/([a-f0-9]+)", result.stdout + result.stderr)
    if not match:
        print("ERROR: Could not parse T1 faulty run_id", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    t1_zombie_run_id = match.group(1)
    
    # T1 correct
    print("  Running T1 correct...")
    result = subprocess.run(
        [
            sys.executable, "-m", "coroner", "verify",
            "--cobol", "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
            "--copybooks", "samples/traps/T1-ebcdic-match-merge/copybooks",
            "--java", "samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java",
            "--schema", "samples/traps/T1-ebcdic-match-merge/schema.json",
            "--cases", "2000",
            "--seed", "42"
        ],
        env={**os.environ, "CORONER_BASE_DIR": str(base_dir)},
        capture_output=True,
        text=True
    )
    
    match = re.search(r"Run: runs/([a-f0-9]+)", result.stdout + result.stderr)
    if not match:
        print("ERROR: Could not parse T1 correct run_id", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    t1_alive_run_id = match.group(1)
    
    # Catalog
    print("  Running trap catalog...")
    result = subprocess.run(
        [sys.executable, "-m", "coroner", "traps"],
        env={**os.environ, "CORONER_BASE_DIR": str(base_dir)},
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("ERROR: Trap catalog failed", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    
    return {
        "t1_zombie": t1_zombie_run_id,
        "t1_alive": t1_alive_run_id
    }


def start_ui_server(base_dir):
    """Start UI server and return port."""
    port = find_free_port()
    print(f"Starting UI server on port {port}...")
    
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "coroner.ui.app:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning"
        ],
        env={**os.environ, "CORONER_BASE_DIR": str(base_dir)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to be ready
    for i in range(50):  # 10 seconds total
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                print(f"  Server ready on port {port}")
                return process, port
        except Exception:
            pass
        time.sleep(0.2)
    
    print("ERROR: UI server did not start in time", file=sys.stderr)
    process.terminate()
    sys.exit(1)


def tamper_certificate(base_dir, run_id):
    """Copy run dir and modify certificate."""
    import hashlib
    
    original_dir = Path(base_dir) / "runs" / run_id
    
    # Generate a 12-hex id from sha256 of "tampered:" + run_id
    tampered_hash = hashlib.sha256(f"tampered:{run_id}".encode()).hexdigest()[:12]
    
    # Ensure it doesn't collide with existing runs
    runs_dir = Path(base_dir) / "runs"
    existing_runs = {d.name for d in runs_dir.iterdir() if d.is_dir()}
    
    tampered_run_id = tampered_hash
    counter = 0
    while tampered_run_id in existing_runs:
        counter += 1
        tampered_run_id = hashlib.sha256(f"tampered:{run_id}:{counter}".encode()).hexdigest()[:12]
    
    tampered_dir = runs_dir / tampered_run_id
    
    shutil.copytree(original_dir, tampered_dir)
    
    cert_path = tampered_dir / "certificate.json"
    with open(cert_path) as f:
        cert = json.load(f)
    
    cert["cases_divergent"] += 1
    
    with open(cert_path, "w") as f:
        json.dump(cert, f, indent=2)
    
    return tampered_run_id


def launch_browser(playwright):
    """Launch browser with optional channel."""
    channel = os.environ.get("SCREENSHOT_CHANNEL", "")
    if channel:
        return playwright.chromium.launch(headless=True, channel=channel)
    else:
        return playwright.chromium.launch(headless=True)


def render_terminal_html(output):
    """Render terminal output as HTML."""
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{
    background: #1a1a1a;
    color: #e0e0e0;
    font-family: 'Courier New', monospace;
    padding: 0;
    margin: 0;
    font-size: 16px;
    line-height: 1.5;
}}
.terminal {{
    max-width: 1100px;
    padding: 24px;
    white-space: pre-wrap;
    word-break: break-word;
}}
.prompt {{ color: #4CAF50; }}
.command {{ color: #fff; }}
</style>
</head>
<body>
<div class="terminal"><span class="prompt">$ </span><span class="command">git commit -m "Port credit fees"</span>
{output}</div>
</body>
</html>
"""
    return html


def capture_commit_blocked():
    """Capture blocked commit screenshot."""
    print("Capturing commit blocked screenshot...")
    
    # Create temporary clone
    clone_dir = Path(tempfile.mkdtemp(prefix="coroner_clone_"))
    subprocess.run(
        ["git", "clone", "--local", ".", str(clone_dir)],
        capture_output=True,
        check=True
    )
    
    try:
        # Configure git hooks and identity in the clone
        subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=clone_dir,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Coroner demo"],
            cwd=clone_dir,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "demo@example.invalid"],
            cwd=clone_dir,
            capture_output=True,
            check=True
        )
        
        # Create symlink to venv
        venv_path = Path(".venv").resolve()
        clone_venv = clone_dir / ".venv"
        clone_venv.symlink_to(venv_path)
        
        # Get Java file from scope
        with open(".kiro/coroner-scope.json") as f:
            scope = json.load(f)
        java_file = scope["java"]
        
        # Generate HALF_EVEN variant
        variant_dir = clone_dir / "build" / "variants"
        variant_dir.mkdir(parents=True, exist_ok=True)
        variant_path = variant_dir / "CreditFees.java"
        
        subprocess.run(
            [
                sys.executable, "-m", "coroner.catalog.legacy_variant",
                str(clone_dir / java_file),
                str(variant_path)
            ],
            capture_output=True,
            check=True
        )
        
        # Replace the Java file with the variant
        shutil.copy(variant_path, clone_dir / java_file)
        
        # Stage the file
        subprocess.run(
            ["git", "add", java_file],
            cwd=clone_dir,
            capture_output=True,
            check=True
        )
        
        # Try to commit
        result = subprocess.run(
            ["git", "commit", "-m", "Port credit fees"],
            cwd=clone_dir,
            capture_output=True,
            text=True
        )
        
        # Combine stdout and stderr
        output = result.stdout + result.stderr
        
        # Check that commit was blocked by Coroner with ZOMBIE verdict
        if result.returncode == 0:
            print("ERROR: Commit succeeded when it should have been blocked", file=sys.stderr)
            sys.exit(1)
        
        if "ZOMBIE" not in output:
            first_line = output.split("\n")[0] if output else "(no output)"
            print(f"ERROR: Commit failed but not blocked by Coroner ZOMBIE: {first_line}", file=sys.stderr)
            sys.exit(1)
        
        # Sanitize output
        output = sanitize_output(output, clone_dir, venv_path)
        
        # Render HTML
        html = render_terminal_html(output)
        html_path = Path(tempfile.mktemp(suffix=".html"))
        html_path.write_text(html)
        
        # Screenshot with Playwright, cropping to terminal element
        with sync_playwright() as p:
            browser = launch_browser(p)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                device_scale_factor=1
            )
            page = context.new_page()
            page.goto(f"file://{html_path}")
            
            # Take screenshot of terminal element only
            terminal_locator = page.locator(".terminal")
            terminal_locator.screenshot(path="docs/screenshots/commit-blocked.png")
            
            browser.close()
        
        # Optimize the PNG
        img = Image.open("docs/screenshots/commit-blocked.png")
        img.save("docs/screenshots/commit-blocked.png", optimize=True)
        
        html_path.unlink()
        
    finally:
        shutil.rmtree(clone_dir)


def images_equal(img1, img2):
    """Check if two PIL images are equal."""
    if img1.size != img2.size:
        return False
    return img1.tobytes() == img2.tobytes()


def capture_demo_gif(page, port, run_id):
    """Capture demo GIF."""
    print("Capturing demo GIF...")
    
    frames = []
    frame_times = []
    start_time = time.monotonic()
    
    # Navigate from / to run page
    page.goto(f"http://127.0.0.1:{port}/")
    
    # Capture frames during home page (reduced to 0.25s)
    for _ in range(2):
        frame_times.append(time.monotonic())
        frames.append(page.screenshot())
        time.sleep(0.125)
    
    # Navigate to run page and start capturing immediately to catch animation
    page.goto(f"http://127.0.0.1:{port}/run/{run_id}", wait_until="domcontentloaded")
    
    # Capture continuously during the first second to catch animation (300-500ms)
    animation_start = time.monotonic()
    while time.monotonic() - animation_start < 1.0:
        frame_times.append(time.monotonic())
        frames.append(page.screenshot())
        time.sleep(0.05)  # 20 fps during animation
    
    # Capture verdict and example at normal rate (reduced to 2.5s)
    for _ in range(20):
        frame_times.append(time.monotonic())
        frames.append(page.screenshot())
        time.sleep(0.125)
    
    # Find branch chart element and scroll to it smoothly
    chart_element = page.locator("h3:has-text('Branch reconciliation')").first
    chart_y = chart_element.bounding_box()["y"] if chart_element.count() > 0 else 800
    
    # Smooth scroll in steps of 60px
    current_scroll = 0
    target_scroll = int(chart_y)
    scroll_step = 60
    
    while current_scroll < target_scroll:
        current_scroll = min(current_scroll + scroll_step, target_scroll)
        page.evaluate(f"window.scrollTo(0, {current_scroll})")
        frame_times.append(time.monotonic())
        frames.append(page.screenshot())
        time.sleep(0.05)  # Smooth scrolling
    
    # Capture on chart (reduced to 2s)
    for _ in range(16):
        frame_times.append(time.monotonic())
        frames.append(page.screenshot())
        time.sleep(0.125)
    
    # Process frames
    pil_frames = []
    for frame_bytes in frames:
        img = Image.open(io.BytesIO(frame_bytes))
        # Resize to width 960
        new_width = 960
        new_height = int(img.height * new_width / img.width)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        pil_frames.append(img)
    
    # Merge duplicate frames by adding their duration to the previous kept frame
    unique_frames = [pil_frames[0]]
    durations = [frame_times[1] - frame_times[0] if len(frame_times) > 1 else 0.125]
    
    for i in range(1, len(pil_frames)):
        frame_duration = frame_times[i] - frame_times[i-1] if i < len(frame_times) else 0.125
        
        if images_equal(pil_frames[i], unique_frames[-1]):
            # Merge into previous frame by adding duration
            durations[-1] += frame_duration
        else:
            unique_frames.append(pil_frames[i])
            durations.append(frame_duration)
    
    # Convert durations to milliseconds
    durations_ms = [int(d * 1000) for d in durations]
    
    # Total duration in seconds
    total_duration = sum(durations)
    
    if total_duration < 10:
        print(f"ERROR: GIF duration {total_duration:.1f}s is less than 10s", file=sys.stderr)
        sys.exit(1)
    
    if total_duration > 15:
        print(f"ERROR: GIF duration {total_duration:.1f}s exceeds 15s", file=sys.stderr)
        sys.exit(1)
    
    # Quantize to shared 128-color palette for size reduction
    quantized_frames = []
    # Build palette from all frames
    all_pixels = []
    for frame in unique_frames[:50]:  # Sample first 50 frames for palette
        all_pixels.extend(list(frame.convert("RGB").get_flattened_data()))
    
    # Create a palette image
    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette([i for i in range(256*3)])  # Default palette
    
    # Quantize each frame to 128 colors
    for frame in unique_frames:
        quantized = frame.convert("RGB").quantize(colors=128, method=2)
        quantized_frames.append(quantized)
    
    # Save GIF with per-frame durations
    quantized_frames[0].save(
        "docs/screenshots/demo.gif",
        save_all=True,
        append_images=quantized_frames[1:],
        duration=durations_ms,
        loop=0,
        optimize=True
    )
    
    # Check size
    size_mb = Path("docs/screenshots/demo.gif").stat().st_size / (1024 * 1024)
    if size_mb >= 5:
        print(f"ERROR: demo.gif is {size_mb:.2f} MB, must be under 5 MB", file=sys.stderr)
        sys.exit(1)
    
    print(f"  demo.gif: {total_duration:.1f}s, {size_mb:.2f} MB")


def capture_screenshots(port, run_ids, base_dir):
    """Capture all screenshots."""
    print("Capturing screenshots...")
    
    # Ensure output directory exists
    Path("docs/screenshots").mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            device_scale_factor=1
        )
        page = context.new_page()
        
        # T1 zombie dark
        print("  t1-zombie-dark.png...")
        page.goto(f"http://127.0.0.1:{port}/run/{run_ids['t1_zombie']}")
        time.sleep(1)  # Let page fully load
        screenshot_bytes = page.screenshot()
        img = Image.open(io.BytesIO(screenshot_bytes))
        img.save("docs/screenshots/t1-zombie-dark.png", optimize=True)
        
        # T1 alive light
        print("  alive-light.png...")
        page.evaluate("localStorage.setItem('coronerTheme', 'light')")
        page.goto(f"http://127.0.0.1:{port}/run/{run_ids['t1_alive']}")
        page.reload()
        time.sleep(1)
        screenshot_bytes = page.screenshot()
        img = Image.open(io.BytesIO(screenshot_bytes))
        img.save("docs/screenshots/alive-light.png", optimize=True)
        
        # Reset to dark for other screenshots
        page.evaluate("localStorage.setItem('coronerTheme', 'dark')")
        
        # Detection matrix
        print("  matrix.png...")
        page.goto(f"http://127.0.0.1:{port}/matrix")
        time.sleep(1)
        screenshot_bytes = page.screenshot()
        img = Image.open(io.BytesIO(screenshot_bytes))
        img.save("docs/screenshots/matrix.png", optimize=True)
        
        # Tamper certificate and capture verify invalid
        print("  verify-invalid.png...")
        tampered_run_id = tamper_certificate(base_dir, run_ids['t1_zombie'])
        page.goto(f"http://127.0.0.1:{port}/run/{tampered_run_id}")
        time.sleep(0.5)
        
        # Scroll Verify button into view and click by role
        page.locator("role=button[name='Verify']").scroll_into_view_if_needed()
        page.click("role=button[name='Verify']")
        
        # Wait for INVALID status
        page.wait_for_selector("text=Certificate: INVALID", timeout=10000)
        time.sleep(0.5)
        
        screenshot_bytes = page.screenshot()
        img = Image.open(io.BytesIO(screenshot_bytes))
        img.save("docs/screenshots/verify-invalid.png", optimize=True)
        
        # Demo GIF
        capture_demo_gif(page, port, run_ids['t1_zombie'])
        
        browser.close()


def report_results():
    """Report generated files."""
    print("\nGenerated screenshots:")
    screenshots_dir = Path("docs/screenshots")
    for img_path in sorted(screenshots_dir.glob("*")):
        size_kb = img_path.stat().st_size / 1024
        if img_path.suffix == ".gif":
            size_mb = img_path.stat().st_size / (1024 * 1024)
            print(f"  {img_path.name}: {size_mb:.2f} MB")
        else:
            print(f"  {img_path.name}: {size_kb:.1f} KB")


def main():
    """Main workflow."""
    temp_dir = setup_temp_workspace()
    server_process = None
    
    try:
        # Produce runs
        run_ids = produce_runs(temp_dir)
        
        # Start UI server
        server_process, port = start_ui_server(temp_dir)
        
        # Capture screenshots
        capture_screenshots(port, run_ids, temp_dir)
        
        # Capture commit blocked (uses current repo)
        capture_commit_blocked()
        
        # Report
        report_results()
        
    finally:
        # Cleanup
        if server_process:
            server_process.terminate()
            server_process.wait(timeout=5)
        
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
