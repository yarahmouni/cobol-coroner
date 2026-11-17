# Web UI Requirements

## Overview

A dark, modern, readable web interface for viewing Coroner differential verification results and the trap catalog Detection Matrix.

## Requirements (EARS format)

### Req 1: Technology stack
**WHILE** serving the web UI, the system **SHALL** use FastAPI with uvicorn, Jinja2 templates and htmx 2.0.4 for interactivity.

**WHERE** htmx is required, the system **SHALL** vendor htmx.min.js 2.0.4 as a static file (SHA-256 e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447, 0BSD license) at build/vendor/htmx.min.js with no CDN dependency and no build step.

### Req 2: Server binding
**WHERE** the UI server is started, the system **SHALL** bind to 127.0.0.1 only (local access only).

**WHERE** `make serve` is invoked, the system **SHALL** start the FastAPI server with uvicorn.

### Req 3: Data directory
**WHERE** the UI needs the data directory, the system **SHALL** read CORONER_BASE_DIR (default: repository root), consistent with the MCP server.

### Req 4: Run page structure
**WHERE** a run page is requested for a valid run_id, the system **SHALL** display:
- Large central verdict (ALIVE, ZOMBIE, or ERROR with the verdict message or error reason)
- Cases count
- Divergences count
- Paragraph coverage (X/Y format)
- Branch coverage (Coroner definition) (X/Y format)
- Duration
- "Validated under GnuCOBOL 3.x"

**WHERE** the run's schema declares a group key, the system **SHALL** also display the Unreconciled branch exposure line: sum, max, branches affected, and grand total matches status.

**WHERE** the verdict is ZOMBIE, the system **SHALL** display:
- The Given/When/Then card from card.txt
- The COBOL lines involved (from failure_report.json)
- The divergent field with COBOL and Java values

**WHERE** the verdict is ERROR, the system **SHALL** display the error reason and reference stderr.

### Req 5: Certificate panel
**WHERE** a run page has a certificate, the system **SHALL** display a Certificate panel with:
- Certificate fields: run_id, status, cases, divergences, coverage
- A Verify button

**WHERE** the Verify button is clicked, the system **SHALL** replay the certificate via an htmx POST request and display the replay result: VALID or INVALID with the replay reason.

### Req 6: Detection Matrix page
**WHERE** the Detection Matrix page is requested, **IF** runs/trap_catalog.json exists, the system **SHALL** display a table with columns: Trap ID, Description, Detected (of N), Rate, Correct port verdict.

**WHERE** the Detection Matrix page is requested, **IF** runs/trap_catalog.json does not exist, the system **SHALL** display "Detection Matrix not available yet: run make traps".

**WHERE** trap T6 is displayed, the system **SHALL** show it as a placeholder without numbers.

### Req 7: Measured values only
**WHERE** any page displays a number or metric, the system **SHALL** read that value from the run files (verdict.json, failure_report.json, card.txt, certificate.json, trap_catalog.json) or from a certificate replay.

**WHERE** any page displays a file path, the system **SHALL** show repository-relative paths for sources and runs/<run_id> for run directories, never absolute paths or home directory prefixes.

### Req 8: Visual design
**WHERE** the UI is rendered, the system **SHALL** use a dark, modern, readable design with:
- Dark background
- High contrast text (at least 4.5:1 ratio)
- No terminal-emulator aesthetics (no monospace walls, no green-on-black, no blinking cursor)
- Monospace font only for COBOL lines and CSV rows

**WHERE** the verdict is displayed, the system **SHALL** use:
- ALIVE: green background or border with text label "ALIVE"
- ZOMBIE: red background or border with text label "ZOMBIE"
- ERROR: orange or yellow background or border with text label "ERROR"
- Verdict not conveyed by color only (text label always present for accessibility)

### Req 9: Input validation
**WHERE** a run_id is received in a URL, the system **SHALL** validate it as exactly 12 lowercase hexadecimal characters before any file access.

**WHERE** an invalid run_id is received, the system **SHALL** return HTTP 404.

### Req 10: Read-only mode
**WHERE** the UI is running in V1, the system **SHALL** provide no endpoint that starts a COBOL or Java run (read-only except certificate replay).

### Req 11: Dependencies
**WHERE** the system is installed, pyproject.toml **SHALL** declare:
- fastapi (tested with 0.163.1)
- uvicorn (tested with 0.54.0)
- jinja2 (tested with 3.1.6)
- python-multipart (tested with 0.0.33)
- httpx (tested with 0.28.1) as a dev dependency for tests

### Req 12: Tests
**WHERE** the UI is tested, the system **SHALL** include tests with FastAPI TestClient that:
- Request an ALIVE run page (credit-fees correct)
- Request a ZOMBIE run page (credit-fees legacy variant) and assert the card and COBOL lines are present
- Request a ZOMBIE run page (T1 faulty) and assert the Unreconciled branch exposure line with "grand total matches: yes"
- Request an ERROR run page (broken reference) and assert the error reason
- POST to the Verify endpoint with a forged certificate and assert INVALID with a reason
- Request the Detection Matrix page with and without a catalog file
- Request a page with an invalid run_id and assert 404
- Assert no response contains the home directory prefix

All tests use real runs produced by the engine at small case counts in a tmp base directory.

## Done when
- EARS requirements cover the technology stack, run page, Detection Matrix page, visual design, validation and tests.
- Only measured values: every displayed number is read from run files or replay, never typed in templates.
- The dark design is accessible (text label for verdict, contrast ratio specified).
- CORONER_BASE_DIR used for data directory.
- Read-only mode stated (no run execution in V1).
