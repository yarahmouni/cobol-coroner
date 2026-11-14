# Architecture (V1)

```
COBOL + copybooks + Java 17 + schema.json
        |
        v
  parse (PIC clauses, branches)  -->  generate cases (Lazarus generator + Hypothesis)
        |
        v
  run GnuCOBOL (reference)   run Java 17 (one JVM, batch)   run instrumented COBOL (coverage only)
        |                           |                               |
        v                           v                               v
  normalize (schema.json, exact)  ---------->  compare  <------  trace / markers
        |
        v
  verdict VIVANT / ZOMBIE + coverage + failure report  ->  runs/<run_id>/*.json
        |
        +--> FastAPI: GET /, POST /api/run, GET /api/report/{run_id}
        +--> MCP server: run_differential_check, get_verdict, get_failure_report, get_coverage_report
        +--> Git pre-commit hook (fast mode) and Kiro PreToolUse hook
        +--> optional advisory AI explanation (Bedrock + Claude, D-13)
```

## Modules
- `lazarus/parse`: copybooks and branch map. No business logic elsewhere.
- `lazarus/gen`: targeted cases (limits, boundaries, branches, rounding ties) and Hypothesis random cases, fixed seed.
- `lazarus/run`: subprocess runners with timeouts; COBOL reference binary never instrumented.
- `lazarus/compare`: normalization from `schema.json`, exact comparison, return codes, row counts.
- `lazarus/diag`: failure report and coverage report.
- `lazarus/api`: FastAPI routes only, no logic.
- `lazarus/mcp`: MCP server, thin layer over the engine.
- `web/`: one HTML page with htmx.

## Security
- Container: no network, non-root user, read-only filesystem, CPU, memory and time limits.
- Public mode: bundled samples only. Upload in local mode only, with size limit and strict validation.
- No secrets in code; secret scan in CI.
