# MCP Server with Agent and Skills - Tasks

## Task 1: Refactor CLI to extract run_verify()

**Requirements**: Req 2.1.2

**Done when**:
- Function `run_verify(cobol_path, java_path, schema_path, copybooks_dir, num_cases, seed, timings)` exists in coroner/cli.py.
- Returns `(verdict: Verdict, run_dir: Path)`.
- The existing `verify()` CLI command calls `run_verify()` and formats output.
- No duplicated logic between CLI and the function.
- All existing tests pass.

## Task 2: Implement MCP server with 7 tools

**Requirements**: Req 2.1.1, 2.1.3 to 2.1.12

**Done when**:
- coroner/mcp/server.py implements 7 tools using mcp 2.3.0 MCPServer.
- `run_differential_check` calls `run_verify()` and returns structured content with run_id, status, sub_label, cases, divergences, coverage, certificate path.
- `get_verdict` reads verdict.json and returns its content.
- `get_failure_report` reads failure_report.json and returns an MCP error when ALIVE.
- `get_detection_matrix` returns MCP error "Detection Matrix not available yet: the trap catalog has not been run".
- `export_junit_test` reads ZombieRegressionTest.java and returns path and content.
- `generate_certificate` calls the certificate generation function and returns path and hash.
- `verify_certificate` calls the replay function and returns valid, reasons, status, cases, divergences, coverage.
- Input validation: run_id format, path escapes rejected.
- The stub `get_verdict(project_id)` is removed.
- The server starts with `python -m coroner.mcp`.

## Task 3: Create three Kiro skills

**Requirements**: Req 2.3.1 to 2.3.4

**Done when**:
- `.kiro/skills/banking-trap-recognition/SKILL.md` exists with YAML front matter and procedure for recognizing the six banking traps (D-46).
- `.kiro/skills/cobol-semantics-safety/SKILL.md` exists with procedure for COBOL semantic rules (ROUNDED, BigDecimal, signs, collation) and references cobol-semantics.md.
- `.kiro/skills/coroner-audit-workflow/SKILL.md` exists with procedure for the full workflow (run_differential_check to certificate).
- Each skill is under 50 lines, concrete, and names the MCP tools it uses.
- No words "first", "unique", "novel", "proves", "proven", "guaranteed".

## Task 4: Create coroner-auditor agent configuration

**Requirements**: Req 2.2.1 to 2.2.6

**Done when**:
- `.kiro/agents/coroner-auditor.json` exists.
- Prompt says it audits Java ports with Coroner and never claims more than the measured verdict.
- Resources include `file://.kiro/steering/**/*.md` and `skill://.kiro/skills/*/SKILL.md`.
- `includeMcpJson: true` or explicit coroner server reference.
- allowedTools lists the 7 coroner tools plus read.
- `kiro-cli agent validate --path .kiro/agents/coroner-auditor.json` exits 0.

## Task 5: Write MCP server tests

**Requirements**: Req 2.5.1 to 2.5.5

**Done when**:
- `tests/test_mcp_server.py` exists.
- Tests spawn the real stdio server.
- Test list_tools: exactly 7 names.
- Test run_differential_check on demo sample (200 cases): ALIVE.
- Test get_verdict: returns verdict.
- Test verify_certificate: valid True.
- Test get_detection_matrix: error "not available yet".
- Test run_differential_check on legacy variant (200 cases): ZOMBIE.
- Test get_failure_report: returns failure report.
- Test export_junit_test: returns test content.
- Test path validation: rejects `..` escapes.
- Every call has a 60 s timeout.
- `.venv/bin/pytest -q` runs the tests and all pass.

## Task 6: Update documentation

**Requirements**: Req 2.4.1, 2.4.2

**Done when**:
- README gains "Kiro skills" section with one line per skill.
- `.kiro/steering/product.md` gains one line referencing the agent and skills.

## Coverage

| Criterion | Tasks |
|-----------|-------|
| Req 2.1.1 (7 tools) | 2 |
| Req 2.1.2 (thin wrappers, run_verify) | 1, 2 |
| Req 2.1.3 (run_differential_check) | 2 |
| Req 2.1.4 (get_verdict) | 2 |
| Req 2.1.5 (get_failure_report) | 2 |
| Req 2.1.6 (get_detection_matrix) | 2 |
| Req 2.1.7 (export_junit_test) | 2 |
| Req 2.1.8 (generate_certificate) | 2 |
| Req 2.1.9 (verify_certificate) | 2 |
| Req 2.1.10 (input validation) | 2 |
| Req 2.1.11 (error handling) | 2 |
| Req 2.1.12 (remove stub) | 2 |
| Req 2.2.1 to 2.2.6 (agent config) | 4 |
| Req 2.3.1 to 2.3.4 (skills) | 3 |
| Req 2.4.1, 2.4.2 (docs) | 6 |
| Req 2.5.1 to 2.5.5 (tests) | 5 |
| Req 3.1 to 3.4 (non-functional) | 2, 5 |
| Req 4.1 to 4.5 (constraints) | 1, 2, 3, 4, 6 |
