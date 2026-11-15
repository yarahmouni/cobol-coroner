# MCP Server with Agent and Skills - Design

## 1. Architecture

```
Kiro agent (coroner-auditor)
    |
    +-- read tool (built-in)
    +-- 7 MCP tools from coroner server (stdio)
    |       |
    |       +-- run_differential_check  --> coroner.cli.run_verify()
    |       +-- get_verdict             --> reads verdict.json
    |       +-- get_failure_report      --> reads failure_report.json
    |       +-- get_detection_matrix    --> error until priority 8
    |       +-- export_junit_test       --> reads ZombieRegressionTest.java
    |       +-- generate_certificate    --> coroner.certificate.generate()
    |       +-- verify_certificate      --> coroner.certificate.verify()
    |
    +-- resources: steering files, 3 skills
```

## 2. CLI Refactoring (coroner/cli.py)

### 2.1 New function `run_verify`

Signature:
```python
def run_verify(
    cobol_path: str,
    java_path: str,
    schema_path: str,
    copybooks_dir: str,
    num_cases: int = 2000,
    seed: int = 42,
    timings: bool = False
) -> tuple[Verdict, Path]:
    """Run the differential verification pipeline.
    
    Returns:
        (verdict, run_dir): The verdict object and the run directory Path.
    """
```

Steps:
1. Parse schema, COBOL structures, branch map.
2. Generate cases.
3. Run COBOL reference, Java, instrumented COBOL.
4. Compare outputs.
5. Compute verdict.
6. Generate failure report and JUnit test if ZOMBIE.
7. Store all artifacts in runs/<run_id>/.
8. Generate certificate.
9. Return (verdict, run_dir).

The existing `verify()` CLI command calls `run_verify()` and formats the output for the terminal.

### 2.2 Timing output

When `timings=True`, the function prints step durations to stderr (not included in the return value).

## 3. MCP Server (coroner/mcp/server.py)

### 3.1 Server initialization

```python
from mcp import MCPServer
import mcp.types as types

server = MCPServer("coroner")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    # Return 7 tool definitions

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    # Route to handler functions

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run())
```

### 3.2 Input validation helpers

```python
def validate_run_id(run_id: str) -> None:
    """Raise ValueError if run_id is not 12 lowercase hex chars."""
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise ValueError(f"Invalid run_id: must be 12 lowercase hex characters")

def validate_path(path_str: str, repo_root: Path) -> Path:
    """Resolve path and ensure it's inside repo_root.
    
    Raises ValueError if path escapes the repository.
    """
    path = Path(path_str).resolve()
    if not path.is_relative_to(repo_root):
        raise ValueError(f"Path outside repository: {path_str}")
    return path
```

Repository root is determined once at server startup from the server script location.

### 3.3 Tool: run_differential_check

Parameters:
- `cobol` (string, required)
- `copybooks` (string, required)
- `java` (string, required)
- `schema` (string, required)
- `cases` (integer, optional, default 2000)
- `seed` (integer, optional, default 42)

Implementation:
1. Validate and resolve all paths.
2. Validate cases (1 to 10000) and seed (non-negative).
3. Call `run_verify(cobol, java, schema, copybooks, cases, seed, timings=False)`.
4. Read certificate from run_dir.
5. Return structured content (JSON):
```json
{
  "run_id": "a26c32ac9519",
  "status": "ALIVE",
  "sub_label": "PASS: business behavior preserved on 2000 cases",
  "cases_total": 2000,
  "cases_divergent": 0,
  "paragraph_coverage": "12/12",
  "branch_coverage": "42/70",
  "certificate_path": "runs/a26c32ac9519/certificate.json"
}
```

### 3.4 Tool: get_verdict

Parameters:
- `run_id` (string, required)

Implementation:
1. Validate run_id format.
2. Read `runs/<run_id>/verdict.json`.
3. Return structured content with all verdict fields.

### 3.5 Tool: get_failure_report

Parameters:
- `run_id` (string, required)

Implementation:
1. Validate run_id format.
2. Check if `runs/<run_id>/verdict.json` has status ZOMBIE.
3. Read `runs/<run_id>/failure_report.json`.
4. Return structured content with the failure report.

If the verdict is ALIVE or the file does not exist, raise an MCP error: "No failure report: the run was ALIVE".

### 3.6 Tool: get_detection_matrix

No parameters.

Implementation:
1. Check if the detection matrix file exists (exact path TBD, reserved for priority 8).
2. Until priority 8 is built, always raise an MCP error: "Detection Matrix not available yet: the trap catalog has not been run".

### 3.7 Tool: export_junit_test

Parameters:
- `run_id` (string, required)

Implementation:
1. Validate run_id format.
2. Read `runs/<run_id>/ZombieRegressionTest.java`.
3. Return structured content:
```json
{
  "path": "runs/a26c32ac9519/ZombieRegressionTest.java",
  "content": "...full Java source..."
}
```

If the file does not exist, raise an MCP error: "No JUnit test: the run was ALIVE or the test was not generated".

### 3.8 Tool: generate_certificate

Parameters:
- `run_id` (string, required)

Implementation:
1. Validate run_id format.
2. Call `coroner.certificate.generate_certificate(run_id)` (existing function from R-58).
3. Return structured content:
```json
{
  "path": "runs/a26c32ac9519/certificate.json",
  "certificate_sha256": "abc123..."
}
```

### 3.9 Tool: verify_certificate

Parameters:
- `path` (string, required)

Implementation:
1. Validate and resolve path.
2. Call the certificate replay function (existing from R-58).
3. Return structured content:
```json
{
  "valid": true,
  "reasons": [],
  "status": "ALIVE",
  "cases": 2000,
  "divergences": 0,
  "paragraph_coverage": "12/12",
  "branch_coverage": "42/70"
}
```

For invalid certificates, `valid` is false and `reasons` lists validation failures.

### 3.10 Error handling

Every tool handler is wrapped in try/except. On any error (ValueError, FileNotFoundError, etc.), the handler raises an MCP error with a clear message derived from the exception.

## 4. Agent Configuration (.kiro/agents/coroner-auditor.json)

Structure:
```json
{
  "name": "coroner-auditor",
  "description": "Audits Java ports of COBOL programs using Coroner differential verification",
  "prompt": "You audit Java 17 ports of COBOL programs using Coroner MCP tools. You run differential checks, read verdicts, and on ZOMBIE you get the failure report and export the JUnit test. You never claim more than the measured verdict (no proven, guaranteed, or formal proof). Your claims are limited to what Coroner outputs: ALIVE means business behavior preserved on N cases, ZOMBIE means diverged on M cases. You reference the three skills: banking-trap-recognition, cobol-semantics-safety, coroner-audit-workflow.",
  "resources": [
    "file://.kiro/steering/**/*.md",
    "skill://.kiro/skills/*/SKILL.md"
  ],
  "includeMcpJson": true,
  "allowedTools": [
    "read",
    "coroner/run_differential_check",
    "coroner/get_verdict",
    "coroner/get_failure_report",
    "coroner/get_detection_matrix",
    "coroner/export_junit_test",
    "coroner/generate_certificate",
    "coroner/verify_certificate"
  ]
}
```

The `includeMcpJson: true` field includes all servers from `.kiro/settings/mcp.json`.

## 5. Skills

### 5.1 banking-trap-recognition

File: `.kiro/skills/banking-trap-recognition/SKILL.md`

Front matter:
```yaml
---
name: banking-trap-recognition
description: Recognize six banking migration traps in COBOL and Java ports
---
```

Content:
- Trap 1: EBCDIC vs ASCII collating sequence (SORT COLLATING SEQUENCE IS EBCDIC, different order for control breaks).
- Trap 2: Rounding (ROUNDED vs HALF_EVEN, truncation vs DOWN).
- Trap 3: COMP-3 sign nibble (C positive, D negative, F unsigned).
- Trap 4: Zoned sign overpunch in input files.
- Trap 5: REDEFINES and invalid numeric data.
- Trap 6: Reserved for owner field trap (placeholder).

Procedure:
1. Scan COBOL for these patterns (SORT ... COLLATING, ROUNDED, COMP-3, REDEFINES).
2. Scan Java for common mistakes (HALF_EVEN, wrong sign handling, no validation).
3. Use `run_differential_check` to verify.
4. On ZOMBIE, use `get_failure_report` to see which COBOL lines diverged.

### 5.2 cobol-semantics-safety

File: `.kiro/skills/cobol-semantics-safety/SKILL.md`

Front matter:
```yaml
---
name: cobol-semantics-safety
description: COBOL semantic rules a Java port must preserve
---
```

Content:
- ROUNDED (no MODE) means NEAREST-AWAY-FROM-ZERO: Java `RoundingMode.HALF_UP`.
- Without ROUNDED, COBOL truncates: Java `RoundingMode.DOWN`.
- BigDecimal with explicit scale for all amounts. No double, no float.
- SIGN LEADING SEPARATE: explicit sign handling in Java.
- EBCDIC collating sequence: Java must use a Comparator with the same order.
- Output formatting: `setScale(scale).toPlainString()`.

Reference: `.kiro/steering/cobol-semantics.md`

Procedure:
1. Check every COMPUTE and MOVE for ROUNDED clauses.
2. Check Java for BigDecimal scale and rounding mode.
3. Verify with `run_differential_check`.

### 5.3 coroner-audit-workflow

File: `.kiro/skills/coroner-audit-workflow/SKILL.md`

Front matter:
```yaml
---
name: coroner-audit-workflow
description: End-to-end workflow for auditing a Java port with Coroner
---
```

Procedure:
1. Call `run_differential_check` with the COBOL program, copybooks, Java port, schema, and a suitable number of cases (200 for fast check, 2000 for full audit).
2. Call `get_verdict` with the run_id.
3. If ALIVE: done. Call `generate_certificate` and `verify_certificate`.
4. If ZOMBIE:
   a. Call `get_failure_report` to see the minimal failing case and COBOL lines.
   b. Call `export_junit_test` to get the regression test.
   c. Fix the Java port based on the failure report.
   d. Go to step 1.
5. When ALIVE is reached, call `generate_certificate` and `verify_certificate` to produce the replayable certificate.

Tools used: `run_differential_check`, `get_verdict`, `get_failure_report`, `export_junit_test`, `generate_certificate`, `verify_certificate`.

## 6. Tests (tests/test_mcp_server.py)

### 6.1 Test setup

Spawn the MCP server as a subprocess:
```python
proc = subprocess.Popen(
    [".venv/bin/python", "-m", "coroner.mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
```

Use the mcp SDK client to communicate (initialize, list_tools, call_tool).

### 6.2 Test cases

1. `test_list_tools`: List tools, assert exactly 7 names.
2. `test_run_differential_check_alive`: Call on demo sample, 200 cases, assert status ALIVE.
3. `test_get_verdict`: Use run_id from previous test, assert verdict fields match.
4. `test_verify_certificate`: Use certificate path from test 2, assert valid True.
5. `test_get_detection_matrix_not_available`: Assert MCP error with expected message.
6. `test_run_differential_check_zombie`: Call on legacy variant, 200 cases, assert status ZOMBIE.
7. `test_get_failure_report`: Use ZOMBIE run_id, assert failure report returned.
8. `test_export_junit_test`: Use ZOMBIE run_id, assert test content returned.
9. `test_path_validation`: Call run_differential_check with `cobol="../etc/passwd"`, assert rejected.

Each test has a 60 s timeout.

### 6.3 Shared session

One shared MCP session for all tests (start server once, call multiple tools, then stop).

## 7. Documentation Updates

### 7.1 README

Add section after "What a run writes":

```markdown
## Kiro skills

Three skills guide the coroner-auditor agent:
- `banking-trap-recognition`: Recognize the six banking migration traps in COBOL and Java.
- `cobol-semantics-safety`: COBOL semantic rules a Java port must preserve (rounding, BigDecimal, signs, collation).
- `coroner-audit-workflow`: End-to-end workflow from run_differential_check to certificate verification.
```

### 7.2 .kiro/steering/product.md

Add after the "Hackathon" line:

```markdown
- Agent: coroner-auditor uses 7 MCP tools (run_differential_check, get_verdict, get_failure_report, get_detection_matrix, export_junit_test, generate_certificate, verify_certificate) and 3 skills (banking-trap-recognition, cobol-semantics-safety, coroner-audit-workflow).
```

## 8. Implementation Order

1. Refactor coroner/cli.py: extract `run_verify()` function.
2. Update coroner/mcp/server.py: remove stub, add 7 tools.
3. Create .kiro/skills/ with 3 SKILL.md files.
4. Create .kiro/agents/coroner-auditor.json.
5. Replace tests/test_mcp_stub.py with tests/test_mcp_server.py.
6. Run validation and tests.
7. Update README and product.md.

## 9. Edge Cases

- Run directory does not exist: clear error.
- Certificate file missing: tool returns error.
- Invalid JSON in verdict or certificate: caught and reported.
- Server dies: tests have timeouts and cleanup.
- Path with symlinks: resolved before validation.

## 10. Performance

- Server startup: under 1 s (imports only, no heavy initialization).
- Tool calls: under 30 s for 200 cases (measured in R-55 acceptance: 4 to 6 s for 2000 cases).
- All tool responses are synchronous (no streaming).
