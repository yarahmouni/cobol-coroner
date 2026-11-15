# MCP Server with Agent and Skills - Requirements

## 1. Overview

Build a production MCP server exposing 7 tools that wrap the differential engine, a Kiro agent configuration (coroner-auditor) that uses these tools to audit Java ports of COBOL programs, and 3 skills that encode banking-trap recognition, COBOL semantics safety rules, and the audit workflow.

## 2. Functional requirements

### 2.1 MCP Server (coroner/mcp/server.py)

The server uses the mcp 2.3.0 MCPServer class with stdio transport.

**Req 2.1.1**: The server exposes exactly 7 tools:
- `run_differential_check`: runs the verification pipeline
- `get_verdict`: reads a stored verdict
- `get_failure_report`: reads a failure report
- `get_detection_matrix`: reads the trap catalog detection matrix
- `export_junit_test`: returns the JUnit regression test
- `generate_certificate`: writes or rewrites a certificate
- `verify_certificate`: offline certificate replay

**Req 2.1.2**: Each MCP tool is a thin wrapper. Business logic stays in coroner/ modules. The CLI pipeline (coroner/cli.py) is refactored into a reusable function `run_verify(cobol_path, java_path, schema_path, copybooks_dir, num_cases, seed, timings)` that returns a tuple `(verdict: Verdict, run_dir: Path)`. Both the CLI and the MCP tool `run_differential_check` call this function. No duplicated logic.

**Req 2.1.3**: Tool `run_differential_check` accepts parameters:
- `cobol` (string, required): path to COBOL file
- `copybooks` (string, required): path to copybooks directory
- `java` (string, required): path to Java file
- `schema` (string, required): path to schema.json
- `cases` (integer, optional, default 2000): number of cases
- `seed` (integer, optional, default 42): random seed

Returns structured content with fields: `run_id`, `status` (ALIVE or ZOMBIE), `sub_label`, `cases_total`, `cases_divergent`, `paragraph_coverage`, `branch_coverage`, `certificate_path`.

**Req 2.1.4**: Tool `get_verdict` accepts `run_id` (string, required), reads `runs/<run_id>/verdict.json`, returns the verdict fields.

**Req 2.1.5**: Tool `get_failure_report` accepts `run_id` (string, required), reads `runs/<run_id>/failure_report.json`. Returns an MCP error with message "No failure report: the run was ALIVE" when the file does not exist or the verdict is ALIVE.

**Req 2.1.6**: Tool `get_detection_matrix` accepts no parameters. Until the trap catalog (priority 8) is built, it returns an MCP error with message "Detection Matrix not available yet: the trap catalog has not been run". Never invents numbers.

**Req 2.1.7**: Tool `export_junit_test` accepts `run_id` (string, required), returns structured content with `path` and `content` of `ZombieRegressionTest.java`. Returns an MCP error when the file does not exist.

**Req 2.1.8**: Tool `generate_certificate` accepts `run_id` (string, required), calls the engine function that writes or rewrites `certificate.json` for the run, returns `path` and `certificate_sha256`.

**Req 2.1.9**: Tool `verify_certificate` accepts `path` (string, required), calls the offline replay function, returns structured content with `valid` (boolean), `reasons` (list of strings), `status`, `cases`, `divergences`, `paragraph_coverage`, `branch_coverage`.

**Req 2.1.10**: Input validation:
- `run_id` must be exactly 12 lowercase hexadecimal characters.
- Every file path must resolve to a location inside the repository root (no `..` escapes). Reject with a clear MCP error otherwise.
- Size limits from the engine (cases, file sizes) are enforced.

**Req 2.1.11**: All errors are returned as MCP errors with clear messages. The server never crashes on invalid input.

**Req 2.1.12**: The stub `get_verdict(project_id)` from S0 is removed.

### 2.2 Kiro Agent Configuration

**Req 2.2.1**: File `.kiro/agents/coroner-auditor.json` is a valid Kiro agent configuration.

**Req 2.2.2**: The agent prompt says it audits Java ports of COBOL programs with Coroner MCP tools and never claims more than the measured verdict (no "proven", "guaranteed", etc.).

**Req 2.2.3**: The agent resources include:
- `file://.kiro/steering/**/*.md` (all steering files)
- `skill://.kiro/skills/*/SKILL.md` (all skill files)

**Req 2.2.4**: The agent includes the coroner MCP server from `.kiro/settings/mcp.json` (via `mcpServers` or `includeMcpJson`).

**Req 2.2.5**: The agent tools are restricted to the 7 coroner MCP tools plus the read tool. No shell, write, or other tools.

**Req 2.2.6**: The configuration passes `kiro-cli agent validate --path .kiro/agents/coroner-auditor.json`.

### 2.3 Kiro Skills

**Req 2.3.1**: Skill `banking-trap-recognition` (`.kiro/skills/banking-trap-recognition/SKILL.md`):
- YAML front matter with `name` and `description`.
- Procedure: how to recognize the six banking migration traps of D-46 (EBCDIC collation, rounding, COMP-3 sign, zoned sign overpunch, REDEFINES, reserved for owner field trap) in COBOL and Java code.
- References the Coroner MCP tools it uses (run_differential_check, get_failure_report).

**Req 2.3.2**: Skill `cobol-semantics-safety` (`.kiro/skills/cobol-semantics-safety/SKILL.md`):
- YAML front matter.
- Procedure: COBOL rules a Java port must preserve (ROUNDED to HALF_UP, truncation to DOWN, BigDecimal with explicit scale, sign handling, EBCDIC collating sequence).
- Points to `.kiro/steering/cobol-semantics.md`.

**Req 2.3.3**: Skill `coroner-audit-workflow` (`.kiro/skills/coroner-audit-workflow/SKILL.md`):
- YAML front matter.
- Procedure: run_differential_check, read verdict, on ZOMBIE get_failure_report and export_junit_test, fix the Java port, rerun until ALIVE, generate_certificate, verify_certificate.
- Names every MCP tool used.

**Req 2.3.4**: Each skill is short (under 50 lines), concrete, and actionable.

### 2.4 Documentation

**Req 2.4.1**: README gains a "Kiro skills" section with one line per skill.

**Req 2.4.2**: `.kiro/steering/product.md` gains one line referencing the three skills.

### 2.5 Tests

**Req 2.5.1**: File `tests/test_mcp_stub.py` is replaced by `tests/test_mcp_server.py` (the old file may be left if needed; no file deletion by Kiro).

**Req 2.5.2**: The test spawns the real stdio MCP server as a subprocess.

**Req 2.5.3**: Test cases:
- List tools: exactly 7 tool names.
- Call `run_differential_check` on the demo sample (samples/credit-fees/) with 200 cases, seed 42: returns ALIVE.
- Call `get_verdict` with the run_id from the previous call: returns the verdict.
- Call `verify_certificate` on the certificate from the run: returns valid True.
- Call `get_detection_matrix`: returns an MCP error "Detection Matrix not available yet: the trap catalog has not been run".
- Call `run_differential_check` on the legacy variant (samples/credit-fees-halfeven/) with 200 cases: returns ZOMBIE.
- Call `get_failure_report` with the ZOMBIE run_id: returns failure report.
- Call `export_junit_test` with the ZOMBIE run_id: returns the test content.
- Path validation: call `run_differential_check` with a path containing `..` outside the repository: rejected with a clear error.

**Req 2.5.4**: Every subprocess call has a timeout (60 s per call).

**Req 2.5.5**: Tests run with `.venv/bin/pytest -q`.

## 3. Non-functional requirements

**Req 3.1**: The MCP server uses mcp 2.3.0 (already installed).

**Req 3.2**: The server starts in under 1 s.

**Req 3.3**: Tool calls return in under 30 s for 200 cases, under 120 s for 2000 cases.

**Req 3.4**: The agent configuration is valid JSON and passes Kiro validation.

**Req 3.5**: No em dash character in any file.

**Req 3.6**: No words "first", "unique", "novel", "proves", "proven", "guaranteed" in agent prompts or skills.

## 4. Constraints

**Req 4.1**: Business logic stays in `coroner/` modules. MCP handlers are thin wrappers (quality.md).

**Req 4.2**: No helper scripts. No file deletion by Kiro (public-repo.md, owner autonomy rule).

**Req 4.3**: Commands use `.venv/bin/python`, never plain `python` or `python3`.

**Req 4.4**: No git commands.

**Req 4.5**: Follow public-repo.md (no company names, no competitor names) and no-formal-proof.md (honest claims).

## 5. Acceptance criteria

1. The MCP server lists exactly 7 tools.
2. `run_differential_check` on the demo sample (200 cases) returns ALIVE in under 30 s.
3. `run_differential_check` on the legacy variant (200 cases) returns ZOMBIE in under 30 s.
4. `get_detection_matrix` returns the "not available yet" error.
5. Certificate replay returns valid True for a real certificate.
6. Path validation rejects `..` escapes.
7. `kiro-cli agent validate` passes on coroner-auditor.json.
8. `.venv/bin/pytest -q` runs the new tests and all tests pass.
