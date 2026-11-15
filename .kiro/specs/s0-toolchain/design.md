# Design: S0 toolchain and MCP smoke test

## Overview

This spec establishes the three foundational capabilities required before building the Coroner verification engine: GnuCOBOL 3.2 tracing for coverage computation, a reproducible Docker runtime environment, and integration with Kiro through a local MCP server.

The design validates that GnuCOBOL can produce parseable execution traces, that a single container image can host both the reference COBOL runtime (GnuCOBOL 3.2) and the target Java 17 runtime, and that Kiro can discover and invoke Coroner functionality through the Model Context Protocol.

Success criteria: a toy COBOL program with conditional logic produces a trace listing executed line numbers; a Docker container runs both COBOL and Java smoke tests as a non-root user; Kiro successfully calls a stub MCP tool that returns a fixed verdict.

## Architecture

### High-level flow

```
┌─────────────────────────────────────────────────────────────┐
│ Host                                                         │
│  ┌──────────────┐                                           │
│  │ Kiro CLI     │                                           │
│  │              │                                           │
│  │  reads       │                                           │
│  │  .kiro/settings/mcp.json                                │
│  │              │                                           │
│  │  discovers   │                                           │
│  │  MCP server  │                                           │
│  └──────┬───────┘                                           │
│         │                                                    │
│         │ stdio                                             │
│         v                                                    │
│  ┌──────────────┐                                           │
│  │ coroner/mcp  │ (Python)                                 │
│  │ server       │                                           │
│  │              │                                           │
│  │ tool:        │                                           │
│  │ get_verdict  │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Docker container (coroner:smoke)                            │
│                                                              │
│  GnuCOBOL 3.2     JDK 17        Python 3.12                 │
│                                                              │
│  ┌────────────┐   ┌────────────┐                           │
│  │ toy.cob    │   │ Toy.java   │                           │
│  │            │   │            │                           │
│  │ IF ... ELSE│   │ prints     │                           │
│  │ END-IF     │   │ version    │                           │
│  └────────────┘   └────────────┘                           │
│       │                 │                                   │
│       v                 v                                   │
│  cobc -x            javac + java                           │
│  -ftraceall                                                 │
│       │                                                     │
│       v                                                     │
│  trace.txt                                                  │
│  (line numbers)                                             │
│       │                                                     │
│       v                                                     │
│  parse_trace.py                                             │
│       │                                                     │
│       v                                                     │
│  {2, 3, 5}                                                  │
└─────────────────────────────────────────────────────────────┘
```

### Key decisions

- GnuCOBOL tracing uses `-ftraceall` compile flag and `COB_SET_TRACE=Y` runtime environment variable. If line numbers are not present in the trace output, fallback to DISPLAY-based markers (decision D-07).
- Docker image uses Debian slim base pinned by digest with pinned versions of GnuCOBOL 3.2.0, OpenJDK 17, and Python 3.12. Non-root user `coroner` runs all processes.
- MCP server runs as a stdio process launched by Kiro. Initial stub returns a hardcoded ALIVE verdict with zero divergences.
- Trace parser extracts line numbers using regex or simple text parsing; no complex grammar required at this stage.

## Components and Interfaces

### Component 0: Python environment and dependencies

**Purpose:** Provide a reproducible Python 3.12 virtual environment with pinned dependencies.

**Structure:**
```
.venv/                    # Python 3.12 virtual environment
pyproject.toml            # Project metadata and pinned dependencies
.github/workflows/
  test.yml                # GitHub Actions workflow running unit tests
```

**Dependencies (pinned in pyproject.toml):**
- Official MCP Python SDK
- pytest for unit tests
- Other dependencies as needed (no unnecessary packages)

**Setup:**
```bash
python3.12 -m venv .venv
.venv/bin/pip install -e .
```

**GitHub Actions workflow:**
- Runs on: ubuntu-latest
- Python version: 3.12
- Steps: checkout, setup Python, install dependencies, run pytest
- Blocks merge on test failure (per quality.md)

### Component 1: GnuCOBOL trace parser

**Purpose:** Parse execution trace files produced by GnuCOBOL and return the set of executed line numbers.

**Location:** `coroner/parse/trace.py`

**Interface:**
```python
def parse_trace(trace_file_path: str) -> set[int]:
    """
    Parse a GnuCOBOL trace file and return executed line numbers.
    
    Args:
        trace_file_path: Path to the trace output file
        
    Returns:
        Set of line numbers that were executed
        
    Raises:
        FileNotFoundError: trace file does not exist
        ValueError: trace file is empty or unparseable
    """
```

**Input:** Text file containing GnuCOBOL trace output with line number annotations.

**Output:** Python set of integers representing executed line numbers.

**Behavior:**
- Read trace file line by line
- Extract line numbers using regex pattern matching GnuCOBOL trace format
- Deduplicate line numbers (a line may execute multiple times)
- Return empty set if no line numbers found (triggers fallback investigation)

**Implementation approach:**
- First task captures a real trace from GnuCOBOL compiled with `-ftraceall` and run with `COB_SET_TRACE=Y` and `COB_TRACE_FILE=path`
- Real trace is saved to `tests/fixtures/sample_trace.txt`
- Parser implementation is written against the actual trace format, not assumed format

### Component 2: Dockerfile and smoke test

**Purpose:** Provide a reproducible, hermetic environment containing all runtime dependencies.

**Base image:** Debian slim pinned by digest. Use official Debian package for GnuCOBOL if version is 3.2.x. If Debian package is older than 3.2, build GnuCOBOL 3.2.0 from source with pinned commit or release tag.

**Verification step:** During first task, check `apt-cache policy gnucobol` in the chosen Debian version to determine if source build is needed.

**Structure:**
```
Dockerfile
smoke/
  toy.cob         # COBOL program with IF/ELSE
  Toy.java        # Java program printing version
  run_smoke.sh    # Compiles and runs both, checks output
```

**Makefile target:**
```make
smoke:
    docker build -t coroner:smoke .
    docker run --rm coroner:smoke
```

**Expected output:**
```
[COBOL] toy executed successfully
[COBOL] trace contains N line numbers
[Java] OpenJDK Runtime Environment (build 17.x.x)
Smoke test PASSED
```

**Non-root execution:**
- Dockerfile creates user `lazarus` with UID 1000
- All compiled binaries and scripts owned by `lazarus`
- `USER lazarus` directive before `CMD`

### Component 3: MCP server stub

**Purpose:** Expose Lazarus functionality to Kiro through the Model Context Protocol.

**Location:** `lazarus/mcp/` module

**Interface:**

Tool: `get_verdict`

**Input schema:**
```json
{
  "type": "object",
  "properties": {
    "project_id": {
      "type": "string",
      "description": "Identifier for the verification project"
    }
  },
  "required": ["project_id"]
}
```

**Output schema:**
```json
{
  "verdict": "VIVANT",
  "divergences": 0,
  "test_cases": 1,
  "message": "0 divergence found on 1 case (stub)"
}
```

**MCP configuration:** `.kiro/settings/mcp.json`
```json
{
  "mcpServers": {
    "lazarus": {
      "command": ".venv/bin/python",
      "args": ["-m", "lazarus.mcp"]
    }
  }
}
```

**Behavior:**
- Server listens on stdin/stdout following MCP stdio transport protocol
- Uses official MCP Python SDK
- Registers `get_verdict` tool during initialization
- Returns fixed stub verdict regardless of input
- Logs all invocations to stderr for debugging
- Invoked by Kiro as `.venv/bin/python -m lazarus.mcp` from repository root

## Data Models

### Trace file format (GnuCOBOL output)

**Important:** The actual trace format is not assumed. The first task will:
1. Compile a toy COBOL program with `-ftraceall`
2. Run with `COB_SET_TRACE=Y` and `COB_TRACE_FILE=tests/fixtures/sample_trace.txt`
3. Capture the real trace output as a test fixture
4. Write the parser against the observed format

Example possible format with `-ftraceall`:
```
Source: 'toy.cob'
Program-Id: TOY
    000002 PROGRAM-ID. TOY.
    000005 PROCEDURE DIVISION.
    000006     IF 1 = 1
    000007         DISPLAY "BRANCH A"
    000009     END-IF.
```

If line numbers are missing, fallback strategy: Insert `DISPLAY "MARKER-LINE-007"` statements at key points (decision D-07).

### Verdict structure (MCP stub)

```python
@dataclass
class Verdict:
    verdict: Literal["VIVANT", "ZOMBIE"]
    divergences: int
    test_cases: int
    message: str
```

Stub returns:
```python
Verdict(
    verdict="VIVANT",
    divergences=0,
    test_cases=1,
    message="0 divergence found on 1 case (stub)"
)
```

### Smoke test artifacts

**COBOL toy program (toy.cob):**
- 10-20 lines
- One IF/ELSE to generate branch trace
- Exits with RETURN-CODE 0

**Java toy program (Toy.java):**
- Prints Java version from `System.getProperty("java.version")`
- Exits with code 0

**Trace parser output:**
- Set of integers: `{2, 5, 6, 7, 9}`

## Error Handling

### GnuCOBOL trace parsing

| Error condition | Handling |
|----------------|----------|
| Trace file not found | Raise FileNotFoundError with path |
| Empty trace file | Raise ValueError("Trace file is empty") |
| No line numbers in trace | Return empty set, log warning, trigger D-07 fallback investigation |
| Malformed trace line | Log warning, skip line, continue parsing |

### Docker smoke test

| Error condition | Handling |
|----------------|----------|
| GnuCOBOL compilation fails | Print error, exit code 1 |
| Java compilation fails | Print error, exit code 1 |
| Trace file missing after COBOL run | Print error, exit code 1 |
| Parse result is empty set | Print warning, investigate trace format |
| Container build fails | Surface Docker error to user, check base image availability |

### MCP server

| Error condition | Handling |
|----------------|----------|
| Invalid JSON from Kiro | Log error, return MCP error response |
| Missing required parameter | Return error with message "Missing required field: project_id" |
| Server startup fails | Log to stderr, exit with code 1 |
| Kiro cannot discover server | Verify `.kiro/settings/mcp.json` syntax and path |

All errors are logged to stderr. MCP server errors follow MCP error response format.

## Testing Strategy

### Unit tests

**Test: Python environment setup**
- Given: pyproject.toml with pinned dependencies
- When: `.venv/bin/pip install -e .` runs
- Then: all dependencies install successfully
- Then: MCP SDK is available for import

**Test: parse_trace with valid input**
- Given: real trace file from `tests/fixtures/sample_trace.txt` (captured in first task)
- When: parse_trace is called
- Then: returns set of integers matching the line numbers from the fixture

**Test: parse_trace with empty file**
- Given: empty trace file
- When: parse_trace is called
- Then: raises ValueError

**Test: parse_trace with missing file**
- Given: non-existent file path
- When: parse_trace is called
- Then: raises FileNotFoundError

**Test: parse_trace with duplicate line numbers**
- Given: trace with line 7 appearing 3 times
- When: parse_trace is called
- Then: returns set containing line 7 only once

### Integration tests

**Test: Docker smoke test end-to-end**
- Given: `make smoke` command
- When: Docker builds and runs
- Then: exit code 0, output contains "Smoke test PASSED"
- Then: output shows N > 0 line numbers parsed from trace

**Test: COBOL trace generation**
- Given: toy.cob with one IF/ELSE
- When: compiled with `-ftraceall` and run with `COB_SET_TRACE=Y` and `COB_TRACE_FILE=path`
- Then: trace file created at specified path
- Then: trace file contains parseable content (format validated by parser tests)

**Test: Java version check**
- Given: Toy.java in container
- When: compiled and run
- Then: output contains "17."

### MCP integration test

**Test: Kiro discovers MCP server**
- Given: `.kiro/settings/mcp.json` configured
- When: Kiro CLI starts
- Then: `lazarus` server appears in available tools
- Then: `get_verdict` tool is listed

**Test: Kiro calls get_verdict**
- Given: MCP server running via `.venv/bin/python -m lazarus.mcp`
- When: Kiro invokes `get_verdict` with `{"project_id": "test"}`
- Then: receives JSON response with verdict "VIVANT"
- Then: receives divergences = 0
- Then: receives test_cases = 1
- Then: message is "0 divergence found on 1 case (stub)"

### Acceptance criteria validation

**Requirement 1: GnuCOBOL trace**
- Verified by: toy.cob compiled with `-ftraceall`, trace parsed successfully
- Pass condition: parse_trace returns non-empty set of integers
- Fallback recorded: If empty set, document D-07 DISPLAY marker fallback in `docs/decisions.md`

**Requirement 2: Docker image**
- Verified by: `make smoke` exits 0
- Pass condition: both COBOL and Java programs execute successfully
- Pass condition: container runs as user `lazarus` (UID 1000)

**Requirement 3: MCP smoke test**
- Verified by: Kiro lists and calls `get_verdict`
- Pass condition: tool returns well-formed JSON verdict
- Pass condition: working `mcp.json` committed to repository

### Test execution order

1. Python environment setup (create .venv, install dependencies from pyproject.toml)
2. Capture real GnuCOBOL trace into `tests/fixtures/sample_trace.txt`
3. Unit tests for trace parser (using real fixture)
4. Docker build and smoke test
5. MCP server manual test with stdio
6. MCP integration test with Kiro CLI
7. GitHub Actions workflow validates all unit tests pass

All tests must pass before spec is marked complete. Green CI is required per quality.md steering.
