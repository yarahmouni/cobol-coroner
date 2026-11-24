#!/usr/bin/env python3
"""Generate screenshots from real runs for README."""
import getpass
import html
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


def private_markers():
    """Strings that must never appear on an image (built at run time, never literal)."""
    markers = [
        "/" + "Users" + "/",
        "/" + "home" + "/",
        "/" + "var" + "/" + "folders",
        "/" + "private" + "/",
        "/" + "tmp" + "/",
        str(Path.home()),
        getpass.getuser(),
        socket.gethostname(),
        socket.gethostname().split(".")[0],
    ]
    return [m for m in dict.fromkeys(markers) if len(m) >= 4]


def check_private(text, label):
    """Exit with the offending lines if text holds a home path, user name or host name."""
    for marker in private_markers():
        if marker.lower() in text.lower():
            print(f"ERROR: {label} contains {marker!r}:", file=sys.stderr)
            for line in text.split("\n"):
                if marker.lower() in line.lower():
                    print(f"  {line[:200]}", file=sys.stderr)
            sys.exit(1)


def sanitize_output(text, clone_path, venv_path):
    """Replace clone path and venv path with 'repo', then check for private strings."""
    # Resolved paths first: a macOS temporary folder is also reachable through /private.
    for path in (Path(clone_path).resolve(), Path(clone_path)):
        text = text.replace(str(path), "repo")
    for path in (Path(venv_path).resolve(), Path(venv_path)):
        text = text.replace(str(path), "repo/.venv")
    check_private(text, "Terminal output")
    return text


def check_page(page, label, expected):
    """Check that a page shows every expected string and nothing private."""
    body = page.inner_text("body")
    missing = [s for s in expected if s not in body]
    if missing:
        print(f"ERROR: {label} does not show {missing}", file=sys.stderr)
        sys.exit(1)
    check_private(page.content() + "\n" + body, label)


def read_run_json(base_dir, run_id, name):
    """Read a JSON file of a run made by this script."""
    return json.loads((Path(base_dir) / "runs" / run_id / name).read_text())


def setup_temp_workspace():
    """Create temporary workspace."""
    temp_dir = tempfile.mkdtemp(prefix="coroner_screenshots_")
    return Path(temp_dir)


def produce_runs(base_dir, only=None):
    """Produce real runs for screenshots (only the T1 faulty run when only is set)."""
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
    if only:
        return {"t1_zombie": t1_zombie_run_id, "t1_alive": None}
    
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
        env={**os.environ, "CORONER_BASE_DIR": str(base_dir),
             "CORONER_EXCHANGE_DIR": str(Path(base_dir) / "exchange")},
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


def capture_verify_invalid(page, base_url, run_id, zombie_verdict):
    """Real Tamper flow on the real T1 faulty run (same steps as video shot 14)."""
    print("  verify-invalid.png...")
    page.goto(f"{base_url}/tamper?run_id={run_id}")
    status = page.get_by_label("Status", exact=True)
    status.wait_for(state="visible")
    if status.input_value() != zombie_verdict["status"]:
        print(f"ERROR: the tamper form is prefilled with {status.input_value()!r}, "
              f"expected {zombie_verdict['status']!r}", file=sys.stderr)
        sys.exit(1)
    status.fill("ALIVE")
    divergent = page.get_by_label("Cases Divergent", exact=True)
    divergent.fill("0")
    page.get_by_role("button", name="Verify Tampered Certificate", exact=True).click()
    page.get_by_text("Certificate: INVALID", exact=False).first.wait_for(
        state="visible", timeout=90000)
    time.sleep(0.5)
    check_page(page, "Tamper page", ["Certificate: INVALID", "replay mismatch"])
    if status.input_value() != "ALIVE" or divergent.input_value() != "0":
        print("ERROR: the edited values are not on the page", file=sys.stderr)
        sys.exit(1)

    # Room below the result (screenshot only, no template change), then scroll so that the
    # Status field and the whole result fit in the 1280x800 view.
    page.add_style_tag(content="body { padding-bottom: 400px; }")
    label_top = page.locator("label[for=status]").evaluate(
        "el => el.getBoundingClientRect().top + window.scrollY")
    page.evaluate(f"window.scrollTo(0, {max(int(label_top) - 24, 0)})")
    time.sleep(0.3)
    viewport_height = page.viewport_size["height"]
    result_box = page.locator("#result").bounding_box()
    status_box = status.bounding_box()
    if status_box["y"] < 0 or result_box["y"] + result_box["height"] > viewport_height:
        print(f"ERROR: the form and the result do not fit in the view "
              f"(status top {status_box['y']:.0f}, result bottom "
              f"{result_box['y'] + result_box['height']:.0f}, view {viewport_height})",
              file=sys.stderr)
        sys.exit(1)
    page.screenshot(path="docs/screenshots/verify-invalid.png")
    img = Image.open("docs/screenshots/verify-invalid.png")
    img.save("docs/screenshots/verify-invalid.png", optimize=True)


def launch_browser(playwright):
    """Launch browser with optional channel."""
    channel = os.environ.get("SCREENSHOT_CHANNEL", "")
    if channel:
        return playwright.chromium.launch(headless=True, channel=channel)
    else:
        return playwright.chromium.launch(headless=True)


def render_terminal_html(output):
    """Render terminal output as HTML."""
    page_html = f"""<!DOCTYPE html>
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
{html.escape(output)}</div>
</body>
</html>
"""
    return page_html

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
    """Capture demo GIF: home page, the ZOMBIE run page, its branch chart, back to the verdict."""
    print("Capturing demo GIF...")
    
    frames = []
    frame_times = []

    def grab():
        frame_times.append(time.monotonic())
        frames.append(page.screenshot())

    def hold(count, pause=0.125):
        for _ in range(count):
            grab()
            time.sleep(pause)

    def smooth_scroll(target, step=60):
        current = page.evaluate("window.scrollY")
        while current != target:
            if current < target:
                current = min(current + step, target)
            else:
                current = max(current - step, target)
            page.evaluate(f"window.scrollTo(0, {current})")
            grab()
            time.sleep(0.05)

    # Home page
    page.goto(f"http://127.0.0.1:{port}/")
    page.wait_for_selector("#run-audit-form")
    hold(8)
    
    # Run page: capture continuously during the first second to catch the badge animation
    page.goto(f"http://127.0.0.1:{port}/run/{run_id}", wait_until="domcontentloaded")
    page.wait_for_selector(".verdict-badge")
    animation_start = time.monotonic()
    while time.monotonic() - animation_start < 1.0:
        grab()
        time.sleep(0.05)
    
    # Verdict, example and figures
    hold(14)
    
    # Scroll to the branch chart and hold
    chart_y = page.locator("h3:has-text('Branch Reconciliation')").first.bounding_box()["y"]
    smooth_scroll(int(chart_y))
    hold(12)
    
    # Back to the verdict, which is the last thing the GIF shows
    smooth_scroll(0)
    hold(12)
    
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
    
    # Quantize each frame to 128 colors
    quantized_frames = [
        frame.convert("RGB").quantize(colors=128, method=2) for frame in unique_frames
    ]
    
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
    
    print(f"  demo.gif: {total_duration:.1f}s, {size_mb:.2f} MB, {len(unique_frames)} distinct frames")


def capture_screenshots(port, run_ids, base_dir, only=None):
    """Capture all screenshots."""
    print("Capturing screenshots...")
    
    # Ensure output directory exists
    Path("docs/screenshots").mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{port}"
    
    # Expected page text comes from each run's own files, never typed here
    zombie_verdict = read_run_json(base_dir, run_ids['t1_zombie'], "verdict.json")
    if only == "verify-invalid":
        with sync_playwright() as p:
            browser = launch_browser(p)
            context = browser.new_context(viewport={'width': 1280, 'height': 800}, device_scale_factor=1)
            capture_verify_invalid(context.new_page(), base_url, run_ids['t1_zombie'], zombie_verdict)
            browser.close()
        return
    alive_verdict = read_run_json(base_dir, run_ids['t1_alive'], "verdict.json")
    registry = json.loads(Path("samples/traps/cases.json").read_text())
    
    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            device_scale_factor=1
        )
        page = context.new_page()
        
        # T1 zombie dark
        print("  t1-zombie-dark.png...")
        page.goto(f"{base_url}/run/{run_ids['t1_zombie']}")
        page.wait_for_selector(".verdict-badge")
        time.sleep(1)  # Let the badge animation end
        t1_name = registry["T1"]["name"]
        check_page(page, "T1 zombie page", [
            zombie_verdict["status"],
            f"diverged on {zombie_verdict['cases_divergent']} cases",
            str(zombie_verdict["exposure_sum"]),
            run_ids['t1_zombie'],
            f"Case 1 {t1_name}",
        ])
        page.screenshot(path="docs/screenshots/t1-zombie-dark.png")
        img = Image.open("docs/screenshots/t1-zombie-dark.png")
        img.save("docs/screenshots/t1-zombie-dark.png", optimize=True)
        
        # T1 alive light
        print("  alive-light.png...")
        page.evaluate("localStorage.setItem('coronerTheme', 'light')")
        page.goto(f"{base_url}/run/{run_ids['t1_alive']}")
        page.reload()
        page.wait_for_selector(".verdict-badge")
        time.sleep(1)
        check_page(page, "T1 alive page", [
            alive_verdict["status"],
            f"preserved on {alive_verdict['cases_total']} cases",
            run_ids['t1_alive'],
        ])
        page.screenshot(path="docs/screenshots/alive-light.png")
        img = Image.open("docs/screenshots/alive-light.png")
        img.save("docs/screenshots/alive-light.png", optimize=True)
        
        # Reset to dark for other screenshots
        page.evaluate("localStorage.setItem('coronerTheme', 'dark')")
        
        # Detection matrix
        print("  matrix.png...")
        page.goto(f"{base_url}/matrix")
        page.wait_for_selector("table")
        time.sleep(1)
        check_page(page, "Detection matrix", [
            f"Case {entry['case']} {entry['name']}"
            for entry in registry.values()
        ])
        page.screenshot(path="docs/screenshots/matrix.png", full_page=True)
        img = Image.open("docs/screenshots/matrix.png")
        img.save("docs/screenshots/matrix.png", optimize=True)
        
        # Demo GIF
        capture_demo_gif(page, port, run_ids['t1_zombie'])
        
        capture_verify_invalid(page, base_url, run_ids['t1_zombie'], zombie_verdict)
        
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
    """Main workflow. `--only verify-invalid` regenerates that one image."""
    only = None
    if len(sys.argv) > 1:
        if sys.argv[1:] != ["--only", "verify-invalid"]:
            print("Usage: make_screenshots.py [--only verify-invalid]", file=sys.stderr)
            sys.exit(2)
        only = "verify-invalid"
    temp_dir = setup_temp_workspace()
    server_process = None
    
    try:
        # Produce runs
        run_ids = produce_runs(temp_dir, only)
        
        # Start UI server
        server_process, port = start_ui_server(temp_dir)
        
        # Capture screenshots
        capture_screenshots(port, run_ids, temp_dir, only)
        
        if only:
            print(f"Run id of the T1 faulty run: {run_ids['t1_zombie']}")
            return
        
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
