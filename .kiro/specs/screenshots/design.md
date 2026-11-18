# Screenshots design

## Architecture
scripts/make_screenshots.py is a standalone script that:
1. Creates a temporary workspace with its own CORONER_BASE_DIR
2. Runs the real engine to produce T1 faulty, T1 correct, and the catalog
3. Starts the real UI server with that base dir
4. Drives Playwright to capture screenshots and animated GIF
5. Creates a temporary git clone for the commit-blocked screenshot
6. Cleans up and reports results

## Implementation plan

### Module: scripts/make_screenshots.py

**Main workflow**:
```python
def main():
    temp_dir = setup_temp_workspace()
    try:
        run_ids = produce_runs(temp_dir)
        port = start_ui_server(temp_dir)
        try:
            capture_screenshots(port, run_ids, temp_dir)
            capture_commit_blocked()
        finally:
            stop_ui_server()
    finally:
        cleanup(temp_dir)
    report_results()
```

**Key functions**:
- `setup_temp_workspace()`: Creates temp dir, returns path
- `produce_runs(base_dir)`: Runs `python -m coroner verify` for T1 faulty and T1 correct, `python -m coroner traps` for catalog; returns dict of run_ids
- `start_ui_server(base_dir)`: Starts uvicorn with CORONER_BASE_DIR env var, finds free port, waits for /health or /, returns port
- `capture_screenshots(port, run_ids, base_dir)`: Playwright browser context, captures all images
- `capture_commit_blocked()`: git clone --local, replace Java, stage, commit, capture output, render HTML, screenshot
- `sanitize_output(text, clone_path)`: Replace clone_path with "repo", check for home paths
- `render_terminal_html(output)`: Simple HTML with dark background, monospace, prompt line
- `capture_demo_gif(page, port, run_id)`: Navigate and record frames, build GIF
- `stop_ui_server()`: Terminate uvicorn process
- `cleanup(temp_dir)`: shutil.rmtree
- `report_results()`: Print each file with size

**Playwright usage**:
```python
from playwright.sync_api import sync_playwright

def launch_browser(playwright):
    """Launch browser with optional channel."""
    channel = os.environ.get("SCREENSHOT_CHANNEL", "")
    if channel:
        return playwright.chromium.launch(headless=True, channel=channel)
    else:
        return playwright.chromium.launch(headless=True)

with sync_playwright() as p:
    browser = launch_browser(p)
    context = browser.new_context(viewport={'width': 1280, 'height': 800}, device_scale_factor=1)
    page = context.new_page()
    
    # Dark theme (default)
    page.goto(f"http://127.0.0.1:{port}/run/{run_id}")
    page.screenshot(path="docs/screenshots/t1-zombie-dark.png")
    
    # Light theme
    page.evaluate("localStorage.setItem('coronerTheme', 'light')")
    page.goto(f"http://127.0.0.1:{port}/run/{run_id_alive}")
    page.reload()  # Ensure theme applied
    page.screenshot(path="docs/screenshots/alive-light.png")
```

The SCREENSHOT_CHANNEL environment variable can specify a browser channel (e.g., "chrome" for installed Google Chrome) when Playwright's bundled Chromium is not available on the platform.

**GIF creation with Pillow**:
```python
from PIL import Image

frames = []
for screenshot_bytes in frame_screenshots:
    img = Image.open(io.BytesIO(screenshot_bytes))
    img = img.resize((960, int(img.height * 960 / img.width)))
    frames.append(img)

# Remove duplicate frames
unique_frames = [frames[0]]
for frame in frames[1:]:
    if not images_equal(frame, unique_frames[-1]):
        unique_frames.append(frame)

unique_frames[0].save(
    "docs/screenshots/demo.gif",
    save_all=True,
    append_images=unique_frames[1:],
    duration=int(1000 / 8),  # 8 fps
    loop=0,
    optimize=True
)
```

**Tamper simulation** (until web-ui task 14):
```python
def tamper_certificate(base_dir, run_id):
    """Copy run dir, modify certificate, return new run_id."""
    original_dir = Path(base_dir) / "runs" / run_id
    new_run_id = f"{run_id}_tampered"
    tampered_dir = Path(base_dir) / "runs" / new_run_id
    
    shutil.copytree(original_dir, tampered_dir)
    
    cert_path = tampered_dir / "certificate.json"
    with open(cert_path) as f:
        cert = json.load(f)
    
    cert["cases_divergent"] += 1
    
    with open(cert_path, "w") as f:
        json.dump(cert, f, indent=2)
    
    return new_run_id
```

**Terminal HTML template**:
```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {
    background: #1a1a1a;
    color: #e0e0e0;
    font-family: 'Courier New', monospace;
    padding: 20px;
    margin: 0;
    font-size: 14px;
    line-height: 1.5;
}
.prompt { color: #4CAF50; }
.command { color: #fff; }
</style>
</head>
<body>
<span class="prompt">$ </span><span class="command">git commit -m "Port credit fees"</span>
<pre>{output}</pre>
</body>
</html>
```

### pyproject.toml changes
Add to `[project.optional-dependencies]`:
```toml
screenshots = [
    "playwright==1.64.1",
    "pillow==13.0.0",
]
```

### Makefile
```makefile
SCREENSHOT_CHANNEL ?=

screenshots:
	SCREENSHOT_CHANNEL=$(SCREENSHOT_CHANNEL) $(PYTHON) scripts/make_screenshots.py
```

Use `make screenshots SCREENSHOT_CHANNEL=chrome` with an installed Google Chrome when Playwright's Chromium is not available.

### README structure
```markdown
# COBOL Coroner

**The independent regression auditor for COBOL-to-Java migrations.**

![Demo: Run audit on T1 faulty trap](docs/screenshots/demo.gif)

It checks whether a migration kept the business behavior...

## Screenshots

All screenshots produced by `make screenshots` from real runs.

![T1 ZOMBIE page showing branch subtotal mismatch](docs/screenshots/t1-zombie-dark.png)
*T1 ZOMBIE page showing branch subtotal mismatch*

![T1 ALIVE page showing business behavior preserved](docs/screenshots/alive-light.png)
*T1 ALIVE page showing business behavior preserved*

...
```

### Static tests: tests/test_screenshots_static.py
```python
def test_readme_images_exist():
    """Every image referenced in README exists."""
    readme = Path("README.md").read_text()
    # Parse markdown image syntax ![alt](path)
    for match in re.finditer(r'!\[([^\]]+)\]\(([^)]+)\)', readme):
        alt_text, path = match.groups()
        if path.startswith("docs/screenshots/"):
            assert Path(path).exists(), f"Image {path} not found"
            assert alt_text.strip(), f"Image {path} has empty alt text"

def test_demo_gif_size():
    """demo.gif is under 5 MB."""
    gif_path = Path("docs/screenshots/demo.gif")
    if gif_path.exists():
        size_mb = gif_path.stat().st_size / (1024 * 1024)
        assert size_mb < 5, f"demo.gif is {size_mb:.2f} MB, must be under 5 MB"

def test_no_hardcoded_numbers():
    """Screenshot script has no hardcoded verdict numbers."""
    script = Path("scripts/make_screenshots.py").read_text()
    # Check for common patterns like "682 cases" or "ZOMBIE on 682"
    forbidden = ["682", "856", "429", "87", "602"]
    for num in forbidden:
        assert num not in script, f"Hardcoded number {num} found in script"
```

## Data flow
1. temp_dir = /tmp/coroner_screenshots_XXXXXX
2. Run T1 faulty: `CORONER_BASE_DIR=temp_dir python -m coroner verify --cobol samples/traps/T1-ebcdic-sort-mismatch/BRANCH-TOTALS.cob ...`
3. Parse run_id from CLI output ("Run: runs/<run_id>")
4. Run T1 correct with /correct/BranchTotals.java
5. Run catalog: `CORONER_BASE_DIR=temp_dir python -m coroner traps`
6. Start UI: `CORONER_BASE_DIR=temp_dir uvicorn coroner.ui.app:app --host 127.0.0.1 --port <free>`
7. Playwright screenshots
8. Git clone, tamper, commit
9. Cleanup

## Error handling
- If engine run exits non-zero, print stderr and exit
- If UI doesn't start in 10 seconds, fail
- If GIF >= 5 MB, fail with size
- If home path in sanitized output, fail with the line
- All subprocess commands capture stdout/stderr
