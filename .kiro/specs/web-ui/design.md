# Web UI Design

## Architecture

FastAPI application with Jinja2 templates and htmx 2.0.4 for interactive elements. No CDN, no build step. The UI reads run artifacts from CORONER_BASE_DIR (default: repository root).

## Module structure

```
coroner/ui/
├── __init__.py
├── app.py          # FastAPI application, routes
├── templates/
│   ├── base.html   # Base template with dark theme, htmx script
│   ├── index.html  # Landing page with links
│   ├── run.html    # Run detail page
│   └── matrix.html # Detection Matrix page
└── static/
    └── (CSS inline in base.html for simplicity)
```

## Routes

### GET /
Landing page with:
- Project title and tagline
- Links to Detection Matrix
- Recent runs: up to 10, newest first, shown as runs/<id> with verdict and date

### GET /run/{run_id}
Run detail page:
- Reads verdict.json, certificate.json (if present), failure_report.json (if ZOMBIE), card.txt (if ZOMBIE)
- Displays verdict, counts, coverage, duration
- Displays Unreconciled branch exposure if inputs.json shows a group_key in the schema
- Displays Given/When/Then card and COBOL lines for ZOMBIE
- Displays error reason and stderr for ERROR
- Certificate panel with Verify button (htmx post to /api/verify)

### POST /api/verify
Accepts JSON: `{"run_id": "<run_id>"}`
- Calls `coroner.certificate.replay_certificate` on runs/<run_id>/certificate.json
- Returns JSON: `{"status": "VALID", "verdict": "ALIVE", ...}` or `{"status": "INVALID", "reason": "..."}`
- htmx swaps the certificate panel content

### GET /matrix
Detection Matrix page:
- Reads runs/trap_catalog.json if present
- Displays per-trap table: ID, Description, Detected (of N), Rate, Correct port verdict
- T6 shown as placeholder without numbers
- If file absent: "Detection Matrix not available yet: run make traps"

## Visual design

### Color scheme (dark theme)
- Background: #1a1a1a (dark gray, near black)
- Text: #e0e0e0 (light gray)
- Contrast ratio: 13.18:1 (computed with WCAG 2 relative luminance)

Verdict colors:
- ALIVE: background #1b4d3e (dark green), text #4ade80 (light green), contrast 5.53:1
- ZOMBIE: background #4d1b1b (dark red), text #f87171 (light red), contrast 5.10:1
- ERROR: background #4d3d1b (dark orange), text #fbbf24 (light orange), contrast 6.29:1

All ratios computed with the WCAG 2 relative-luminance formula and verified to be at least 4.5:1.

Verdict always includes text label (ALIVE, ZOMBIE, ERROR) for accessibility.

Monospace: `font-family: 'Monaco', 'Menlo', 'Consolas', monospace` for COBOL lines and CSV rows only.

Body text: `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`

### Layout
- Max width 1200px, centered
- Verdict box: large (min 200px height), centered text, 2rem font size
- Sections: white border, padding 1.5rem, margin 1rem
- COBOL lines: monospace, line-height 1.4, left-aligned

## Data flow

1. User requests /run/<run_id>
2. app.py validates run_id (12 lowercase hex)
3. Read CORONER_BASE_DIR, construct runs/<run_id> path
4. Load verdict.json (required)
5. Check verdict.status: "ALIVE", "ZOMBIE", or absent (ERROR from run_error.txt)
6. Load certificate.json (optional), failure_report.json (ZOMBIE), card.txt (ZOMBIE), run_error.txt (ERROR)
7. Load inputs.json to check for group_key in schema
8. Render run.html with context

For /api/verify:
1. Receive JSON with run_id
2. Validate run_id
3. Call replay_certificate(base_dir / "runs" / run_id / "certificate.json")
4. Return replay result as JSON

For /matrix:
1. Check if runs/trap_catalog.json exists
2. If yes: load and parse, render matrix.html with traps
3. If no: render matrix.html with "not available" message

## Path sanitization

Run ids: compiled regex `^[0-9a-f]{12}$`, validated before constructing any path.

File paths shown to user:
- Run directory: always `runs/<run_id>`
- Source files: `pathlib.Path(abs_path).relative_to(base_dir)` with exception handling (fallback: filename only)
- Never show absolute paths or home directory prefix

Test helper: `assert os.path.expanduser("~") not in response_text`

## Error handling

- Invalid run_id: HTTP 404
- Missing verdict.json: HTTP 404
- File read errors: HTTP 500 with generic message (never leak paths)
- Certificate replay errors: return JSON with status INVALID and reason

## Integration with existing modules

- `coroner.certificate.replay_certificate(path)` returns a dict with status (VALID/INVALID), verdict, and reason
- No new CLI or MCP changes needed
- `make serve` in Makefile: `uvicorn coroner.ui.app:app --host 127.0.0.1 --port 8000`

## Security

- Bind 127.0.0.1 only (local access)
- Run id validation prevents path traversal
- Read-only (no execution endpoints)
- No user file upload in V1

## Dependencies (pyproject.toml)

```toml
[project]
dependencies = [
    # ... existing ...
    "fastapi==0.163.1",
    "uvicorn==0.54.0",
    "jinja2==3.1.6",
    "python-multipart==0.0.33",
]

[project.optional-dependencies]
dev = [
    # ... existing ...
    "httpx==0.28.1",  # TestClient
]
```

## htmx integration

Vendored file: coroner/ui/static/htmx.min.js
- Version: 2.0.4
- License: 0BSD
- SHA-256: e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447
- Size: 50917 bytes

Operator downloaded to build/vendor/htmx.min.js, then copied to coroner/ui/static/htmx.min.js (committed).

Served as static file at /static/htmx.min.js

Base template includes: `<script src="/static/htmx.min.js"></script>`

Verify button example:
```html
<button hx-post="/api/verify" 
        hx-vals='{"run_id": "{{ run_id }}"}' 
        hx-target="#cert-result">
  Verify
</button>
<div id="cert-result"></div>
```

## Test structure

```python
from fastapi.testclient import TestClient
from coroner.ui.app import app
import tempfile
import os

def test_alive_run(tmp_path):
    # Generate ALIVE run at 30 cases in tmp_path
    # Set CORONER_BASE_DIR = tmp_path
    client = TestClient(app)
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    assert "ALIVE" in response.text
    assert os.path.expanduser("~") not in response.text

def test_zombie_run_with_card(tmp_path):
    # Generate ZOMBIE run (legacy variant)
    # ...
    assert "Given" in response.text
    assert "When" in response.text
    assert "Then" in response.text
    assert "COBOL" in response.text  # lines section

def test_zombie_t1_exposure(tmp_path):
    # Generate ZOMBIE T1 run at 30 cases
    # ...
    assert "Unreconciled branch exposure" in response.text
    assert "grand total matches: yes" in response.text

def test_error_run(tmp_path):
    # Generate ERROR run (broken reference)
    # ...
    assert "ERROR" in response.text
    assert "reference did not run" in response.text

def test_verify_forged_certificate(tmp_path):
    # Generate ALIVE run, forge certificate
    # ...
    response = client.post("/api/verify", json={"run_id": run_id})
    data = response.json()
    assert data["status"] == "INVALID"

def test_matrix_with_catalog(tmp_path):
    # Generate trap catalog
    # ...
    response = client.get("/matrix")
    assert "T1" in response.text
    assert "placeholder" in response.text  # T6

def test_matrix_without_catalog(tmp_path):
    # No catalog file
    # ...
    assert "not available yet" in response.text

def test_invalid_run_id():
    client = TestClient(app)
    response = client.get("/run/invalid")
    assert response.status_code == 404
```

All tests use a tmp_path fixture and set CORONER_BASE_DIR to isolate from the real repository.

## Done when
- FastAPI app in coroner/ui/app.py with routes /, /run/{run_id}, /api/verify, /matrix
- Jinja2 templates in coroner/ui/templates/ (base, index, run, matrix)
- htmx 2.0.4 vendored at build/vendor/htmx.min.js with SHA-256 test
- Dark theme with specified color values and contrast ratios
- Verdict displayed with text label (not color only)
- Monospace only for COBOL lines and CSV rows
- Run id validation (12 lowercase hex)
- CORONER_BASE_DIR support
- Certificate Verify button with htmx POST
- Detection Matrix page with per-trap table
- All displayed numbers read from run files
- No absolute paths or home directory in responses
- Tests with TestClient cover ALIVE, ZOMBIE (card, T1 exposure), ERROR, forged cert, matrix, 404
- Dependencies added to pyproject.toml
- `make serve` target runs uvicorn
