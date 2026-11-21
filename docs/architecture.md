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
- `coroner/engine_worker.py`: Engine worker that polls exchange directory and executes verification jobs in isolated container (D-54).
- `coroner/gate.py`: CI gate that checks verdict and certificate validity.

## Repository layout

### Root files
- `.dockerignore`
- `.env.example`: example environment variables for Cloudflare tunnel (server only)
- `.gitattributes`: Git attributes, line endings, byte-exact fixture, GitHub language statistics
- `.gitignore`
- `CHANGELOG.md`: changes grouped by date from the commit history and the review log
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `cloudflared-config.yml`: Cloudflare tunnel ingress configuration
- `docker-compose.build.yml`: Docker Compose override that builds the image from the Dockerfile as coroner-local:latest (developers)
- `docker-compose.server.yml`: Docker Compose override for live server (removes published port, adds cloudflared)
- `docker-compose.yml`: Docker Compose for local and tester mode (API, engine, init services)
- `Dockerfile`
- `Jenkinsfile`: example declarative Jenkins pipeline (Groovy) running the coroner gate in the image; not run by this repository
- `LICENSE`
- `Makefile`
- `README.md`
- `SECURITY.md`: how to report a vulnerability (GitHub private vulnerability reporting) and the live demo security controls
- `THIRD_PARTY_NOTICES.md`
- `pyproject.toml`

### Scripts
- `scripts/check_cobol_rules.py`
- `scripts/clean_context.sh`: exports tracked and untracked-not-ignored files to a temporary build context (used by make smoke-ui, so no ignored local file reaches the image)
- `scripts/check_cobol_rules.py`
- `scripts/clean_context.sh`: exports tracked and untracked-not-ignored files to a temporary build context (used by make smoke-ui, so no ignored local file reaches the image)
- `scripts/deploy_check.py`: deployment check script (D-53, web-ui Task 19), builds from clean git clone and runs automated checks against a URL
- `scripts/download_junit.py`
- `scripts/gen_parity_cases.py`
- `scripts/gen_rounding_ties.py`
- `scripts/init_demo_runs.sh`: generates bundled demo runs for Docker Compose start only when their folder is missing, never touches an existing run folder, and always rebuilds the derived catalog files from the runs on disk (`python -m coroner traps --from-runs`); checks each exit code against expected (0 ALIVE, 1 ZOMBIE)
- `scripts/make_screenshots.py`: make screenshots: README screenshots and demo GIF from real runs through the real UI (D-58)
- `scripts/make_srt.py`: builds an .srt (subtitle or voice-over column) from the shot table in docs/video-plan.md; refuses an output path inside the repository
- `scripts/precommit_guard.py`
- `scripts/record_demo.py`: records the first cut of the video from the shots of docs/video-plan.md (Playwright and ffmpeg), writes only outside the repository, refuses when less than 5 GB would remain free

## Security
- Container: no network, non-root user, read-only filesystem, CPU, memory and time limits.
- Public mode: bundled samples only. Upload in local mode only, with size limit and strict validation.
- No secrets in code; secret scan in CI.
