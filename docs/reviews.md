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
