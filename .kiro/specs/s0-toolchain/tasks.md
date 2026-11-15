# Tasks: S0 toolchain and MCP smoke test

- [x] 1. Create Python environment configuration
  - Create `pyproject.toml` with pinned dependencies (MCP Python SDK in main, pytest and pyyaml in dev)
  - Set project name, version, and Apache-2.0 license metadata
  - Add `[tool.pytest.ini_options]` with pythonpath and testpaths configuration

_Requirements: 3.1_

Done when: `pyproject.toml` exists with `[project]`, `[project.optional-dependencies]` (dev section with pytest and pyyaml), `[build-system]`, and `[tool.pytest.ini_options]` sections. File contains pinned versions for all dependencies.

- [x] 2. Initialize Python virtual environment
  - Run `python3.12 -m venv .venv` in repository root
  - Run `.venv/bin/pip install --upgrade pip`
  - Run `.venv/bin/pip install -e ".[dev]"`

_Requirements: 3.1_

Done when: `.venv/bin/python --version` shows Python 3.12.x, `.venv/bin/python -c "import mcp"` succeeds without error, and `.venv/bin/pytest --version` succeeds.

- [x] 3. Create toy COBOL program with conditional logic
  - Create `smoke/toy.cob` with one IF/ELSE structure
  - Program displays a message in both branches
  - Program sets RETURN-CODE to 0
  - Create `build/` directory

_Requirements: 1.1_

Done when: `smoke/toy.cob` exists, compiles with `cobc -x smoke/toy.cob -o build/toy`, and runs successfully.

- [x] 4. Capture real GnuCOBOL trace as test fixture
  - Create `build/` directory if not present
  - Compile toy.cob with `cobc -x -ftraceall smoke/toy.cob -o build/toy`
  - Create `tests/fixtures/` directory
  - Run toy program with `COB_SET_TRACE=Y COB_TRACE_FILE=tests/fixtures/sample_trace.txt ./build/toy`
  - Inspect trace file content and format

_Requirements: 1.1_

Done when: `tests/fixtures/sample_trace.txt` exists, is non-empty, and the result (line numbers present: yes/no) is written as a note line under this task in tasks.md.

Note: Line numbers present: yes. The trace file contains line number annotations in the format "Line: N" for each executed statement (e.g., Line: 9, Line: 10, Line: 11, Line: 16, Line: 17).

- [x] 5. Implement trace parser
  - Create `coroner/parse/__init__.py` (empty or with module exports)
  - Create `coroner/parse/trace.py` with `parse_trace(trace_file_path: str) -> set[int]` function
  - Parse the real trace format from `tests/fixtures/sample_trace.txt`
  - Extract line numbers using regex or text parsing
  - Return deduplicated set of integers

_Requirements: 1.2_

Done when: `from coroner.parse.trace import parse_trace` succeeds and `parse_trace("tests/fixtures/sample_trace.txt")` returns a non-empty set of integers.

- [x] 6. Write unit tests for trace parser
  - Create `tests/test_trace_parser.py`
  - Test: parse_trace with valid fixture returns non-empty set
  - Test: parse_trace with empty file raises ValueError
  - Test: parse_trace with missing file raises FileNotFoundError
  - Test: parse_trace with duplicate line numbers returns deduplicated set

_Requirements: 1.2_

Done when: `.venv/bin/pytest tests/test_trace_parser.py -v` shows all tests passing.

- [x] 7. Create toy Java program
  - Create `smoke/Toy.java` that prints Java version from `System.getProperty("java.version")`
  - Program exits with code 0
  - Create `build/` directory if not present

_Requirements: 2.2_

Done when: `javac -d build/ smoke/Toy.java && java -cp build/ Toy` prints version string containing "17" on host machine.

- [ ] 8. Create Dockerfile with pinned versions
  - Check available versions inside a candidate Debian slim base image using `apt-cache policy gnucobol openjdk-17-jdk python3.12`
  - Pick a Debian slim based image that provides Python 3.12 and JDK 17 (e.g., official python:3.12-slim-<debian release> image) pinned by digest
  - If Debian package for GnuCOBOL is not 3.2.x, build GnuCOBOL 3.2.0 from official release tarball with sha256 checksum verification
  - Install OpenJDK 17
  - Create non-root user `coroner` with UID 1000
  - Copy `coroner/` directory into the image (needed by run_smoke.sh for parse_trace)
  - Copy smoke test files
  - Set USER to coroner

_Requirements: 2.1, 2.3_

Done when: `docker build -t coroner:smoke .` succeeds and image contains all three runtimes. `docker run --rm coroner:smoke id` shows uid=1000(coroner). `docker run --rm coroner:smoke cobc --version` shows 3.2.0, `docker run --rm coroner:smoke java -version` shows 17, and `docker run --rm coroner:smoke python3 --version` shows 3.12.

- [x] 9. Create smoke test runner script
  - Create `smoke/run_smoke.sh`
  - Compile toy.cob with `-ftraceall` to `build/toy` and run with COB_SET_TRACE=Y
  - Parse trace file and count line numbers using parse_trace from coroner/
  - Compile and run Toy.java using build/ for outputs
  - Print summary with PASSED/FAILED status
  - Exit with code 0 if all checks pass, code 1 otherwise
  - Script must work both on host (with .venv) and in container

_Requirements: 2.2_

Done when: `bash smoke/run_smoke.sh` exits 0 on the host (host has cobc 3.2.0, JDK 17, python3.12 and .venv) and prints 'Smoke test PASSED'.

- [ ] 10. Add Makefile targets
  - Create or update `Makefile`
  - Add `test` target: `.venv/bin/pytest tests/ -v`
  - Add `smoke` target: `docker build -t coroner:smoke . && docker run --rm coroner:smoke`

_Requirements: 2.2_

Done when: `make test` runs pytest and `make smoke` builds and runs the Docker smoke test.

- [ ] 11. Verify smoke test end-to-end
  - Run `make smoke`
  - Check output contains COBOL success message
  - Check output shows N > 0 line numbers parsed
  - Check output contains Java version with "17"
  - Check output shows "Smoke test PASSED"
  - Check exit code is 0

_Requirements: 2.2_

Done when: `make smoke` completes with exit code 0 and all expected output lines present.

- [x] 12. Create MCP server stub module
  - Create `coroner/mcp/__init__.py` with server entry point
  - Implement MCP stdio server using official MCP Python SDK
  - Register tool `get_verdict` with input schema (project_id: string)
  - Return fixed stub response: `{"verdict": "ALIVE", "divergences": 0, "test_cases": 1, "message": "PASS: business behavior preserved on 1 case (stub)"}`
  - Add `if __name__ == "__main__"` block calling server main function
  - Make module runnable as `python -m coroner.mcp`

_Requirements: 3.1_

Done when: `.venv/bin/python -m coroner.mcp` starts without error and waits for stdin input. Task 13 tests pass.

- [x] 13. Write unit tests for MCP stub
  - Create `tests/test_mcp_stub.py`
  - Test: stdio integration test that spawns `.venv/bin/python -m coroner.mcp` with MCP SDK client
  - Test: list tools returns `get_verdict`
  - Test: calling `get_verdict` with `{"project_id": "test"}` returns all four fields and exact message 'PASS: business behavior preserved on 1 case (stub)'
  - Test: calling `get_verdict` without project_id returns an MCP error

_Requirements: 3.1_

Done when: `.venv/bin/pytest tests/test_mcp_stub.py -q` shows all tests passing.

- [x] 14. Create Kiro MCP configuration
  - Create `.kiro/settings/` directory if missing
  - Create `.kiro/settings/mcp.json` with `mcpServers.coroner` entry
  - Set command to `.venv/bin/python`
  - Set args to `["-m", "coroner.mcp"]`

_Requirements: 3.2_

Done when: `.kiro/settings/mcp.json` exists with valid JSON syntax and correct server configuration.

- [x] 15. Verify Kiro discovers and calls MCP server
  - Check that `kiro-cli mcp list` (or equivalent command) shows the coroner server
  - Call `get_verdict` with project_id test using `kiro-cli chat --no-interactive`
  - Verify response contains the stub verdict
  - Save output as evidence for task 18

_Requirements: 3.2_

Done when: `kiro-cli mcp list` shows the coroner server, and `kiro-cli chat --no-interactive` asked to call get_verdict with project_id test returns the stub verdict. Output saved as evidence for task 18.

Note: Verified on 2026-11-15 with kiro-cli 3.3.0. Before the D-19 rename, a non-interactive Kiro chat listed the MCP server from .kiro/settings/mcp.json, called its get_verdict tool with project_id 'test' and received the stub verdict, isError false. After the rename, 'kiro-cli mcp list' shows server 'coroner' (.venv/bin/python) and tests/test_mcp_stub.py lists and calls get_verdict on it (verdict ALIVE). A Kiro chat call against 'coroner' is re-run when Kiro credits are back.

- [x] 16. Create GitHub Actions workflow
  - Create `.github/workflows/test.yml`
  - Configure ubuntu-latest runner
  - Pin all action versions
  - Trigger on push and pull_request
  - Set Python version to 3.12
  - Steps: checkout, setup Python, install dependencies, run pytest
  - Test step runs `make test`
  - Add secret scan job using a free open source scanner that needs no license key (e.g., gitleaks, truffleHog)

_Requirements: all (CI validates unit tests)_

Done when: `.github/workflows/test.yml` exists, workflow syntax is valid (verified with `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"`), and file includes both test and secret scan jobs.

- [ ] 17. Owner step: push and confirm green CI
  - Commit all changes
  - Push to GitHub repository (requires project owner approval for git push; not executed by Kiro)
  - Check Actions tab shows workflow running
  - Verify all tests pass in CI
  - Configure GitHub branch protection to block merge on test failure

_Requirements: all (CI validation)_

Done when: GitHub Actions workflow completes successfully with green status, and branch protection is configured.

- [ ] 18. Record S0 results in decisions log
  - Add new row to `docs/decisions.md` table documenting:
    - Working `mcp.json` content (command and args used)
    - Whether trace contains line numbers: yes or no
    - If no line numbers, reference D-07 fallback to DISPLAY markers
  - If line numbers are absent, update D-07 in the table noting that fallback will be used

_Requirements: 1.3, 3.3_

Done when: `docs/decisions.md` contains new entry recording the trace format result and working MCP configuration.

- [ ] 19. Validate S0 acceptance criteria
  - Check trace file lists executed lines: confirmed by parse_trace returning non-empty set
  - Check Kiro lists and calls `get_verdict`: verified in task 15
  - Check `make smoke` completes successfully: includes compilation step
  - Review `docs/sprints.md` S0 acceptance criteria
  - Note: 'cobc compiles the sample' (credit-fees program from .kiro/specs/cobol-sample) is covered by the separate cobol-sample spec, not this toolchain spec

_Requirements: all_

Done when: the three s0-toolchain acceptance criteria are verified and documented (trace with line numbers, Kiro MCP integration, make smoke green).

## Requirements Coverage

| Requirement | Covered by Tasks |
|-------------|------------------|
| 1.1 | 3, 4 |
| 1.2 | 5, 6 |
| 1.3 | 18 |
| 2.1 | 8 |
| 2.2 | 7, 9, 10, 11 |
| 2.3 | 8 |
| 3.1 | 1, 2, 12, 13 |
| 3.2 | 14, 15 |
| 3.3 | 18 |
