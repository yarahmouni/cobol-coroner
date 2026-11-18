# Architecture (V1)

```
COBOL + copybooks + Java 17 + schema.json
        |
        v
  parse (PIC clauses, branches)  -->  generate cases (Coroner generator + Hypothesis)
        |
        v
  run GnuCOBOL (reference)   run Java 17 (one JVM, batch)   run instrumented COBOL (coverage only)
        |                           |                               |
        v                           v                               v
  normalize (schema.json, exact)  ---------->  compare  <------  trace / markers
        |
        v
  verdict ALIVE / ZOMBIE + coverage + failure report  ->  runs/<run_id>/*.json
        |
        +--> FastAPI: GET /, POST /api/run, GET /api/report/{run_id}
        +--> MCP server: run_differential_check, get_verdict, get_failure_report, get_coverage_report
        +--> Git pre-commit hook (fast mode) and Kiro PreToolUse hook
        +--> optional advisory AI explanation (Bedrock + Claude, D-13)
```

## Modules
- `coroner/parse`: schema, copybook and trace parsing. No business logic elsewhere.
- `coroner/gen`: targeted case generation (limits, boundaries, branches, rounding ties) and Hypothesis random cases with fixed seed.
- `coroner/run`: subprocess runners with timeouts; COBOL reference binary never instrumented.
- `coroner/compare`: normalization from schema.json, exact comparison, return codes, row counts.
- `coroner/verdict.py`: verdict type definition and computation (ALIVE, ZOMBIE).
- `coroner/store.py`: run storage, inputs.json, verdict.json, comparison results to runs/<run_id>/.
- `coroner/diag`: coverage report, minimal case selection, failure report, JUnit test generation.
- `coroner/diag/card.py`: Given/When/Then card generation from minimal case.
- `coroner/traps.py`: trap catalog runner and detection matrix computation.
- `coroner/catalog/legacy_variant.py`: HALF_EVEN variant generation for test purposes.
- `coroner/cli.py`: command-line interface and pipeline orchestration.
- `coroner/mcp`: MCP server with thin layer over the engine.
- `coroner/ui`: FastAPI web application with Jinja2 templates and htmx. Static assets at `coroner/ui/static/`, templates at `coroner/ui/templates/`.
- `coroner/gate.py`: CI gate that checks verdict and certificate validity.

## Repository layout

### Root files
- `.dockerignore`
- `.gitattributes`: Git attributes, line endings, byte-exact fixture, GitHub language statistics
- `.gitignore`
- `Dockerfile`
- `Jenkinsfile`: example declarative Jenkins pipeline (Groovy) running the coroner gate in the image; not run by this repository
- `LICENSE`
- `Makefile`
- `README.md`
- `pyproject.toml`

### Scripts
- `scripts/check_cobol_rules.py`
- `scripts/download_junit.py`
- `scripts/gen_parity_cases.py`
- `scripts/gen_rounding_ties.py`
- `scripts/make_screenshots.py`: make screenshots: README screenshots and demo GIF from real runs through the real UI (D-58)
- `scripts/precommit_guard.py`

## Security
- Container: no network, non-root user, read-only filesystem, CPU, memory and time limits.
- Public mode: bundled samples only. Upload in local mode only, with size limit and strict validation.
- No secrets in code; secret scan in CI.
