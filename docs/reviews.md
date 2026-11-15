# Reviews log

Every Kiro step is reviewed by the operator (Claude Code) against `.kiro/steering/` and `docs/` before commit. Kiro writes all code, specs, designs and tasks; fixes are sent back to Kiro until clean.

Kiro is driven with `kiro-cli chat --no-interactive --agent lazarus-builder` (agent config outside the repo: file writes auto-approved inside this workspace only, shell limited to an allowlist, `rm`, `git`, `sudo`, `brew`, `curl`, `wget` denied).

## S0

### R-01 2026-11-15: s0-toolchain design.md (first pass)
- Result: 7 fixes applied by Kiro before this log existed (details not recorded).
- Leftovers found: 2.

### R-02 2026-11-15: s0-toolchain design.md (leftovers)
- Fix 1: line 70, base image said "Alpine or Debian slim". Now "Debian slim base pinned by digest", no Alpine (consistent with Component 2).
- Fix 2: diagram label `lazarus_mcp` renamed `lazarus/mcp` (matches `docs/architecture.md` module name).
- Checks: no other Alpine mention, no em dash in the repo.
- Status: clean.

### R-03 2026-11-15: s0-toolchain tasks.md
- Generated: 19 tasks, checkbox + `_Requirements_` + `Done when`, coverage table (all 9 criteria covered).
- Fixes sent (10): push task turned into an owner step (git push needs owner approval, branch protection moved there); build outputs under `build/` only; objective Done when for trace capture (note yes/no in tasks.md); pytest as dev extra with `pip install -e ".[dev]"` and pytest config; Dockerfile task checks package versions in the Debian slim base first, Python 3.12 + JDK 17 image pinned by digest, GnuCOBOL 3.2.0 from tarball with sha256 if needed, copies `lazarus/`; run_smoke.sh must pass on host; MCP tests via a real stdio client incl. missing `project_id` error; Kiro MCP check made non-interactive; CI adds a license-free secret scan (quality.md), pinned actions, `make test`; task 19 no longer claims "cobc compiles the sample" (that is the cobol-sample spec).
- Accepted as is: task 12 Done when still mentions "waits for stdin input" (harmless, task 13 tests are the real check).
- Status: clean.

### R-04 2026-11-15: s0-toolchain task 1 (pyproject.toml)
- Fixes sent (3): `mcp==0.9.0` was an obsolete pre-1.0 SDK, now `mcp==2.3.0` (pytest 9.2.0, pyyaml 6.0.3); setuptools discovery restricted to `lazarus*` (flat layout with smoke/ and tests/); build requirement pinned (`setuptools==75.6.0`).
- Status: clean.

### R-05 2026-11-15: s0-toolchain task 2 (.venv)
- Checked: Python 3.12.16, `mcp` 2.3.0 imports, pytest 9.2.0.
- Fix sent (1): `*.egg-info/` added to `.gitignore` (editable install artifact).
- Status: clean.

### R-06 2026-11-15: privacy cleanup (owner request)
- Private names, bonus and contract mentions removed from README, steering, checklist and decisions (D-16 deleted). New steering file `public-repo.md`.
- Edited directly by the operator under an explicit owner exception. History rewritten to a single commit.
- LICENSE left untouched (its "contract" wording is Apache-2.0 legal text).

### R-07 2026-11-15: s0-toolchain task 3 (smoke/toy.cob)
- Checked: one IF/ELSE with explicit ELSE, no GO TO, compiles to build/toy, prints branch A, RETURN-CODE 0.
- Status: clean (trailing spaces on blank lines accepted).

### R-08 2026-11-15: s0-toolchain task 4 (trace fixture)
- Checked: `tests/fixtures/sample_trace.txt` is a real GnuCOBOL 3.2.0 `-ftraceall` trace with `Line: N` per statement; lines 9, 10, 11, 16, 17 executed, line 13 (ELSE) absent as expected. Line numbers present: yes, D-07 DISPLAY fallback not needed.
- Status: clean.

### R-09 2026-11-15: s0-toolchain task 5 (trace parser)
- Checked: `parse_trace` reads only the `Line: N` field, returns {9, 10, 11, 16, 17} on the fixture, FileNotFoundError and ValueError as designed.
- Fix sent (1): missing `lazarus/__init__.py` (regular package discovery would drop `lazarus` in a non-editable install, i.e. Docker).
- Follow-up for S1 (not S0 scope): with copybooks the trace has several `Source:` files, so line numbers must be keyed by source file.
- Status: clean.

### R-10 2026-11-15: s0-toolchain task 6 (parser tests)
- Checked: 4 tests (exact set {9, 10, 11, 16, 17} with line 13 absent, empty file, missing file, duplicates).
- Fixes sent (4): wrong comment for line 9, fixture path made independent of the working directory, no-op assertion removed, redundant comments removed.
- Tests: `pytest` 4 passed, from repo root and from another directory.
- Status: clean.

### R-11 2026-11-15: s0-toolchain task 7 (smoke/Toy.java)
- Checked: prints `java.version`, compiled to build/, host output "Java version: 17.0.21", exit 0.
- Status: clean.

### R-12 2026-11-15: s0-toolchain task 9 (smoke/run_smoke.sh)
- Fixes sent (5): run from any directory, stale trace cannot pass (truncate + non-empty check), ERR trap prints "Smoke test FAILED", Java check on the "17." prefix, single FAILED message per failure.
- Tests: host run PASSED (5 line numbers, Java 17.0.21), also from another directory; negative run without cobc prints FAILED and exits non-zero (127, accepted).
- Note: Docker daemon down (corrupted libnetwork bolt db in the Docker Desktop VM), tasks 8, 10, 11 postponed; owner approval needed to reset it.
- Status: clean.

### R-13 2026-11-15: s0-toolchain task 12 (MCP stub server)
- Checked: mcp 2.3.0 `MCPServer` API, stdio initialize answered, logs on stderr only, fixed stub verdict.
- Fixes sent (4): `server.run()` instead of an asyncio wrapper, typed `Verdict` dataclass return (output schema), one-line package docstring, redundant comments removed.
- Follow-up for S1: `Verdict` moves to the engine (quality.md: no business logic in MCP handlers) once a real verdict exists.
- Status: clean.

### R-14 2026-11-15: s0-toolchain task 13 (MCP stdio tests)
- First run interrupted by Kiro service throttling; resumed.
- Fixes sent (2 rounds): BUG, the missing project_id test caught `except Exception` and swallowed its own `assert False`, so it could never fail; now asserts the observed SDK behavior (`is_error` True, "Field required"). Success test asserts full equality of `structured_content`; output schema required fields checked; one shared session helper.
- Tests: `pytest` 7 passed.
- Status: clean.

### R-15 2026-11-15: s0-toolchain task 14 (.kiro/settings/mcp.json)
- Checked: matches design (command `.venv/bin/python`, args `-m lazarus.mcp`), valid JSON.
- Status: clean.

### R-16 2026-11-15: s0-toolchain task 15 (Kiro lists and calls get_verdict)
- Verified by the operator: `kiro-cli mcp list` shows `lazarus` from the workspace mcp.json; a non-interactive Kiro chat called `@lazarus/get_verdict` (project_id "test") and got the exact stub verdict, isError false. Evidence note added under task 15.
- Status: clean. S0 acceptance item "Kiro lists and calls get_verdict": met.

### R-17 2026-11-15: s0-toolchain task 16 (CI workflow)
- Checked: test job (Python 3.12, .venv, `make test`) and gitleaks secret-scan job (full history), actions pinned by commit SHA (checkout v7.0.1, setup-python v7.1.0, gitleaks-action v3.0.0), read-only permissions. Minimal Makefile with `test` (real tab), `smoke` added in task 10.
- Fixes sent (2): `branches: ["*"]` missed names with "/", now `on: [push, pull_request]`; secret-scan job gets `pull-requests: read`.
- Tests: YAML parses, `make test` 7 passed. CI itself not run yet (needs the owner push, task 17).
- Status: clean.

### R-18 2026-11-15: cobol-sample design.md (first pass, open)
- Generated by Kiro (733 lines); the run ended on service throttling. Not committed until fixed.
- Blocking findings: most fixture "ties" are not exact ties; the 10.00 minimum fee masks every tie (demo trap would never fire); wrong HALF_EVEN statement (divergence needs an even preceding digit, D-06); UNSTRING into numeric DISPLAY fields ignores the decimal point and sign (use TEST-NUMVAL/NUMVAL); requirement 1.5 validation declared out of scope; REASON-CODE X(3) with longer values and no priority; SIGN LEADING SEPARATE on an edited picture; silent S9(7)V99 overflow without ON SIZE ERROR; make target overwrites the committed expected-output.csv; obsolete AUTHOR paragraph (warning); program too short for requirement 2.2.
- 10 fixes sent (also a Python Decimal oracle test independent of the COBOL output). Not applied yet: Kiro returned "request was throttled by the service" on 5 consecutive calls, including a trivial one.
- Status: open.

### R-19 2026-11-15: push and CI (task 17)
- Commit email switched to the GitHub noreply address; all commits rewritten (author and committer); `git log -p` grep for private names, personal email and local paths: 0 matches. decisions.md replaced by the owner's version.
- Single approved force-push: `main` at b23b339, 14 commits, one author email.
- CI run 43655751273: both jobs not started, "account is locked due to a billing issue" (GitHub account, not the code). Task 17 open until the owner resolves billing.
- Local equivalent on a fresh clone of `main` (macOS): venv, `pip install -e ".[dev]"`, `make test` 7 passed. Secret scan not reproduced locally.

### R-20 2026-11-15: cobol-sample design.md (rounds 1 to 3, closes R-18)
- Round 1 (10 fixes of R-18): applied once the Kiro throttle cleared.
- Round 2 (9 fixes): BUG stale state between records (no INITIALIZE, a valid record left A00 so the next record skipped validation and reused old numbers); BUG overflow E01 overwritten by eligibility; BUG silent truncation by MOVE of NUMVAL made range and decimal checks useless (now: moved value must equal NUMVAL of the text); UNSTRING ON OVERFLOW for extra fields; CASE-ID longer than 10 is E01; FILE STATUS bound; empty input file handled; every IF has an ELSE; verified tie examples (computed with Python Decimal); byte-exact regression test; one validation fixture row per E01 cause plus a no-leak check.
- Round 3 (3 fixes): segment length tested on the 1-character field (never true); CASE-ID cut at an embedded space; OUTPUT-LINE not cleared before STRING.
- Status: clean.
