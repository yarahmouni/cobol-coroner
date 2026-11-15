# Reviews log

Every Kiro step is reviewed by the operator (Claude Code) against `.kiro/steering/` and `docs/` before commit. Kiro writes all code, specs, designs and tasks; fixes are sent back to Kiro until clean.

Names in entries before R-21 use the post-rename names (D-19: COBOL Coroner, package `coroner`).

Kiro is driven with `kiro-cli chat --no-interactive --agent coroner-builder` (agent config outside the repo: file writes auto-approved inside this workspace only, shell limited to an allowlist, `rm`, `git`, `sudo`, `brew`, `curl`, `wget` denied).

## S0

### R-01 2026-11-15: s0-toolchain design.md (first pass)
- Result: 7 fixes applied by Kiro before this log existed (details not recorded).
- Leftovers found: 2.

### R-02 2026-11-15: s0-toolchain design.md (leftovers)
- Fix 1: line 70, base image said "Alpine or Debian slim". Now "Debian slim base pinned by digest", no Alpine (consistent with Component 2).
- Fix 2: diagram label `coroner_mcp` renamed `coroner/mcp` (matches `docs/architecture.md` module name).
- Checks: no other Alpine mention, no em dash in the repo.
- Status: clean.

### R-03 2026-11-15: s0-toolchain tasks.md
- Generated: 19 tasks, checkbox + `_Requirements_` + `Done when`, coverage table (all 9 criteria covered).
- Fixes sent (10): push task turned into an owner step (git push needs owner approval, branch protection moved there); build outputs under `build/` only; objective Done when for trace capture (note yes/no in tasks.md); pytest as dev extra with `pip install -e ".[dev]"` and pytest config; Dockerfile task checks package versions in the Debian slim base first, Python 3.12 + JDK 17 image pinned by digest, GnuCOBOL 3.2.0 from tarball with sha256 if needed, copies `coroner/`; run_smoke.sh must pass on host; MCP tests via a real stdio client incl. missing `project_id` error; Kiro MCP check made non-interactive; CI adds a license-free secret scan (quality.md), pinned actions, `make test`; task 19 no longer claims "cobc compiles the sample" (that is the cobol-sample spec).
- Accepted as is: task 12 Done when still mentions "waits for stdin input" (harmless, task 13 tests are the real check).
- Status: clean.

### R-04 2026-11-15: s0-toolchain task 1 (pyproject.toml)
- Fixes sent (3): `mcp==0.9.0` was an obsolete pre-1.0 SDK, now `mcp==2.3.0` (pytest 9.2.0, pyyaml 6.0.3); setuptools discovery restricted to `coroner*` (flat layout with smoke/ and tests/); build requirement pinned (`setuptools==75.6.0`).
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
- Fix sent (1): missing `coroner/__init__.py` (regular package discovery would drop `coroner` in a non-editable install, i.e. Docker).
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
- Checked: matches design (command `.venv/bin/python`, args `-m coroner.mcp`), valid JSON.
- Status: clean.

### R-16 2026-11-15: s0-toolchain task 15 (Kiro lists and calls get_verdict)
- Verified by the operator: `kiro-cli mcp list` shows `coroner` from the workspace mcp.json; a non-interactive Kiro chat called `@coroner/get_verdict` (project_id "test") and got the exact stub verdict, isError false. Evidence note added under task 15.
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

### R-21 2026-11-15: rename to COBOL Coroner (D-19, D-20), part 1 and part of part 2
- Repo renamed on GitHub to `yarahmouni/cobol-coroner` (owner approved), local remote updated. Operator agent renamed `coroner-builder` (trusts `@coroner`).
- Code (Kiro, verified): package folder renamed to `coroner/`, imports, pyproject name `cobol-coroner`, MCP server `coroner`, verdict `ALIVE` with "PASS: business behavior preserved on 1 case (stub)", mcp.json, tests, smoke script, Dockerfile user `coroner`. Tests: `pytest` 7 passed, `smoke/run_smoke.sh` PASSED, no old project name or old verdict label left in code.
- Dockerfile review (task 8, still open): Kiro's GnuCOBOL sha256 was invented (its download had failed); the operator downloaded gnucobol-3.2.tar.xz and computed 3bb48af46ced4779facf41fdc2ee60e4ccb86eaa99d010b36685315df39c2ee2, now in the Dockerfile. Pin libdb5.3 corrected to 5.3.28+dfsg2-1 (checked with apt-cache in the pinned base image). Debian bookworm only has gnucobol3 3.1.2, so the source build is justified. Image not built yet.
- Docs (Kiro, verified): README (title, subtitle, description, slogan, ALIVE/ZOMBIE sub-labels), product.md (D-18 rules), no-formal-proof.md, quality.md, architecture.md, sprints.md, s0-checklist.md, s0 requirements, part of s0 design; D-18, D-19, D-20 logged.
- Not done: Kiro hit "monthly usage limit has been reached" (50/50 credits, reset 2026-12-01) before finishing decisions D-02/D-07/D-08/D-13 wording, the rest of s0-toolchain design.md and tasks.md, and cobol-sample design.md.

### R-22 2026-11-15: Docker image build check (task 8, operator test run)
- `docker build -t coroner:smoke .`: success (674 MB), one warning (undefined `$LD_LIBRARY_PATH` in ENV, line 45).
- Task 8 Done when: `id` uid=1000(coroner); `cobc --version` 3.2.0; `java -version` 17.0.21; `python3 --version` 3.12.16. All met.
- Task 11 blocker: `docker run --rm coroner:smoke` fails with "gcc: not found". `cobc -x` needs a C compiler and libc headers at runtime; the final stage must install gcc and libc6-dev (pinned) and the GMP headers if cobc needs them. Fix pending (Kiro out of credits).
- Status: open.

### R-23 2026-11-15: rename completion (non-code work by the operator, owner exception)
- Owner approved the operator finishing the text-only rename while Kiro is out of credits; code and the gcc fix stay with Kiro.
- Edited by the operator: decisions D-02 (name; "IBM" replaced by "commercial tools"), D-07, D-08, D-13 ("AI accelerates. Coroner certifies."); s0-toolchain design.md and tasks.md (paths, user, image tag, server name, ALIVE stub message); cobol-sample design.md (positioning wording).
- Task 15 unchecked: its evidence was captured before the rename (server under the old name); it must be re-run against server `coroner` when Kiro credits are back.
- Steering: public-repo.md now says the no-competitor rule covers other hackathon projects only; migration tools whose output is audited (AWS Transform) may be named. product.md aligned.
- Kept on purpose: "IBM Enterprise COBOL" in README and cobol-semantics.md (a compiler, not a migration tool); the D-19 rationale and the D-20 row (it records the removal of the old verdict label).
- Check: grep -ri for the old project name and old verdict label returns only the D-19 and D-20 rows. Tests: `pytest` 7 passed.

### R-24 2026-11-15: owner review findings
- GitHub Action SHAs verified against the real tags (`gh api repos/<repo>/git/ref/tags/<tag>`, annotated tags dereferenced): actions/checkout v7.0.1, actions/setup-python v7.1.0, gitleaks/gitleaks-action v3.0.0 all match. They were supplied to Kiro by the operator from the GitHub API, not generated. No change.
- Task 15 marked done (owner request): Kiro listed and called get_verdict before the rename; after the rename `kiro-cli mcp list` shows server `coroner` and the stdio tests list and call it (3 passed). The Kiro chat call against `coroner` is re-run when credits are back.
- Runtime image check (operator, as root in a throwaway container from coroner:smoke): with gcc 4:12.2.0-3 and libc6-dev 2.36-9+deb12u14 installed, the smoke test PASSED; libgmp-dev not needed. Kiro prompt prepared for the gcc fix, the LD_LIBRARY_PATH warning and Makefile targets smoke, demo, zombie, serve (demo, zombie and serve exit 2 with "not available yet" until S1/S2 exist).

### R-25 2026-11-15: Kiro Pro, gcc fix and Makefile (S0 tasks 8, 10, 11)
- Plan: KIRO PRO, 531 credits, reset 2026-12-01. Test call (claude-haiku-4.5): READY, no throttling.
- Credits per call are logged from here on (from `/usage` before and after each call).
- Call a-gcc-makefile (claude-haiku-4.5, 0.81 credits): runtime stage adds gcc=4:12.2.0-3 and libc6-dev=2.36-9+deb12u14 with apt list cleanup; LD_LIBRARY_PATH warning removed; Makefile targets smoke, demo, zombie, serve (the last three exit 2 with "not available yet" until S1/S2).
- Verified by the operator: `make smoke` exit 0 (toy executed, 5 trace line numbers, Java 17.0.21, Smoke test PASSED); `make demo|zombie|serve` exit 2 with the message; `make test` 7 passed; image runs as uid=1000(coroner), 893 MB (the 674 MB in the task 8 note is the size before gcc).
- Status: clean. S0 acceptance "make smoke green": met.

### R-26 2026-11-15: cobol-sample tasks.md and tasks 1 to 8
- Credits per call (KIRO PRO): t15 re-check (haiku) about 0.06; cs-tasks (sonnet) 1.54; cs-t1-3 (sonnet) 7.50; cs-t4-5 (sonnet) 5.95; cs-t6-8 (sonnet) 5.69. Total used so far: 21.55 of 531.
- Task 15 re-check against server `coroner`: the log shows a real `@coroner/get_verdict` call returning ALIVE. Haiku also listed three tools that do not exist (taken from architecture.md, planned for S2): a tool listing must come from the MCP server, not from the docs.
- tasks.md fixes sent (3): task 5 and task 8 Done when made objective; task 6 checks EVERY tie row against the oracle, not a manual sample.
- CREDIT-FEES.cob (390 lines, 3 copybooks): compiles with `-Wall`, empty stderr. Operator run on 17 hand-made cases: ties away from zero (+12.35, -12.35), odd control 10.24, every E01 cause, overflow E01, A01 minimum fee, R01/R02 priority, S discount 19.00, no state leak, missing env 16. All correct.
- BUG 1 (fixed): empty input returned 16 with libcob "implicit CLOSE" warnings instead of header only and 0.
- BUG 2 (introduced by the fix of bug 1, fixed): empty input looped forever (read past end of file after READ-HEADER); found by the operator, process killed after 10 minutes. Now an EOF switch; every COBOL run in the tests has a timeout.
- Verified by the operator: empty input exit 0 with header only; rounding-ties run is byte-identical to expected-output.csv; independent oracle: 30/30 rows equal ROUND_HALF_UP, 26 would diverge under HALF_EVEN (8 negative), 4 odd controls; rules check 0 GO TO, 33 IF / 33 ELSE, 1 EVALUATE / 1 WHEN OTHER; `pytest` 25 passed.
- Note for CI: the COBOL tests skip on the CI runner (no GnuCOBOL 3.2 there; Debian/Ubuntu packages are 3.1.2). Running them in CI needs the coroner image; proposed for S1.
- Status: clean. S0 acceptance "cobc compiles the sample": met.

### R-27 2026-11-15: S0 tasks 18 and 19, S0 closed
- Call s0-18-19 (haiku, 1.26 credits): tie generator writes LF (comparison-rules.md); D-21 records the S0 results (trace has line numbers, D-07 fallback not needed, working mcp.json); task 19 note lists each S0 acceptance item with its evidence.
- Verified: rounding-ties.csv content unchanged (only line endings), expected-output.csv untouched, `pytest` 25 passed, no em dash.
- Kiro left two untracked helper scripts at the repository root (one hardcodes a local absolute path); not committed, removal pending owner approval.
- S0 acceptance (docs/sprints.md): cobc compiles the sample, the trace lists executed lines, Kiro lists and calls get_verdict, make smoke green: all met. Task 17 (green CI) open: GitHub Actions still refuses to start jobs ("account is locked due to a billing issue"), runs 43667297533 (re-run, attempt 2) and 43669244196.
- Credits used so far: 22.81 of 531.

### R-28 2026-11-15: S1 start, requirements for java-credit-fees and fault-catalog
- Call s1-reqs (sonnet, about 1.55 credits including reporting lag): both requirements files. Call s1-reqs-fix (haiku, 0.61 credits).
- fault-catalog fixes (3): per-fault detection rate added (owner list), still no global rate; F01/F02/F03 no longer overlap (F02 is scale only, F03 is DOWN instead of HALF_UP); deterministic minimal failing case (smallest absolute PRINCIPAL, then FEE-RATE, then CASE-ID). Certificate, JUnit export and suggested fix explicitly excluded until the owner vote.
- java-credit-fees fixes (4): trailing-only trim for CASE-ID and CUSTOMER-SEGMENT (a two-sided trim would accept " B", which COBOL rejects); invalid example (-100.005 is an E01 input) replaced by -1234.50 x 0.01000 = -12.345 gives -0000012.35; range check after rounding (ON SIZE ERROR with ROUNDED); CSV split keeps trailing empty fields, more than 6 fields is E01.
- The HALF_EVEN demo variant is produced by fault F01 injection, not hand-written.
- Status: java-credit-fees requirements clean; fault-catalog requirements waiting for owner review before design.

### R-29 2026-11-15: owner decisions D-22 to D-28 recorded
- Call decisions-22-28 (haiku, credits not yet reported by `/usage`): D-22 improvements list, D-23 to D-28 (votes V1 to V6 as validated by the owner, with simulated vote counts); no-formal-proof.md (no "first", "unique", "novel"; certificate and suggested-fix wording) and scope-v1.md (certificate, JUnit source test, suggested fix, fixed-width after the S1 core, GitHub Action bonus, line count for the demo sample only) updated.
- Checked: rows D-01 to D-28 without collision, text matches the owner validation, no em dash.
- The owner's commit-hours rule is applied by the operator from now on; its row is held until the owner confirms it may be published (public-repo.md).
- Two untracked helper scripts left by Kiro deleted with owner approval.

### R-30 2026-11-15: java-credit-fees design.md
- Call java-design (sonnet, 2.61 credits); call java-design-fix (sonnet, 7.44 credits).
- Parity points given to Kiro from the COBOL code: by-value decimal checks, NUMVAL text form, field split, PIC X(200) record cut and CR removal, CASE-ID raw 20 / valid 10 / output cut to 10, segment trailing trim, edited sign output, negative zero, range checks, header, exit codes.
- Fixes sent (8): BUG `BigDecimal.equals` compares scale, so "10.5" would have become E01 (now `setScale(n, DOWN).compareTo(value) == 0`); BUG textual scale checks rejected "10.500", valid by value (with a false claim about its scale); DURATION "12.0" valid by value; " B" segment is E01 with trailing trim (the design said valid); numeric regex marked provisional until the parity test; formatting by setScale(2).toPlainString with zero padding (cobol-semantics.md) instead of String.format, stream-of-thought lines removed; no AtomicInteger; overflow note after discount.
- The COBOL output on the parity fixture is the specification for every uncertain point (".5", "5.", "+", negative zero).
- Status: clean.

### R-31 2026-11-15: java-credit-fees tasks 1 to 5 (Java 17 port)
- Calls: java-tasks-impl (sonnet, 11.61 credits), parity-more (haiku, 2.19 credits), parity-fix (sonnet, see the running total). The operator widened the Kiro shell allowlist (environment prefixes, `java`, `2>&1`) after Kiro wrote wrapper scripts to get around refused commands; four such scripts (two with a local absolute path) are left uncommitted, removal pending owner approval.
- Parity fixture (24 rows) pinned the COBOL behavior: "10.500" valid, "10.505" E01, " 100.00 " and "+100.00" valid, "1E2" E01, "5." and ".50" valid, 7 and 5 fields E01, 201+ character line cut, CASE-ID output cut to 10, " B" E01, empty segment valid, negative zero prints +0000000.00, DURATION "12.0" and " 24 " valid, INCOME "50000.000" valid, an empty line gives ",+0000000.00,N,E01".
- DIVERGENCE caught by the added parity rows: COBOL accepts ".01000" and ".50", the Java regex rejected them (E01). Fixed to `^[+-]?(\d+\.?\d*|\.\d+)$`.
- BUG: haiku wrote parity-expected.csv by hand (a CASE-ID "PAR-22" that is not in the input) after its commands were refused, and reported guessed results. Regenerated from the COBOL program. Rule kept: expected files only come from the COBOL reference; complex verification steps go to sonnet.
- Verified by the operator: `javac -Xlint:all` clean; COBOL and Java byte-identical with equal exit codes on rounding-ties (0), edge-cases (4), validation-errors (4), parity-cases (4); parity-expected.csv equals a fresh COBOL run; no double, float, long or Math.round in CreditFees.java; `pytest` 32 passed.
- Status: clean. S1 item "Java 17 version" done.

### R-32 2026-11-15: keep the CRLF parity row in Git
- `.gitattributes` (`* text=auto eol=lf`) had turned the deliberate CRLF row of parity-cases.csv into LF on commit, so a fresh clone no longer tested CRLF input. Call gitattr (haiku): the fixture is marked `-text`; file renormalized; the committed bytes now keep the CR.
- Status: clean (fresh-clone check below).

### R-33 2026-11-15: pre-commit guard, no helper scripts, fault-catalog review fixes
- Owner approved deleting the five wrapper scripts left by Kiro (done). The commit-hours rule stays private, outside the repository.
- Call guard-faultcat (sonnet): `scripts/precommit_guard.py` + `.githooks/pre-commit` refuse any staged file containing the macOS home prefix and any added file at the root or in scripts/ not listed in docs/architecture.md (new "Repository layout" section); the guard source never contains the prefix literally. Steering quality.md: never leave helper or wrapper scripts. Makefile `hooks` prints the enable command.
- Verified by the operator: hook enabled (`core.hooksPath .githooks`); a stray root file and a test file with a home path were both refused (exit 1) while the real staged changes passed; `pytest` 39 passed.
- fault-catalog requirements (owner review, 5 fixes): Req 9 is now the deterministic probable cause plus a one-sentence fix, Coroner never repairs code (D-26); Req 10: certificate is a separate spec, the JUnit source test comes from the minimal-case module (D-25), JUnit XML later; F05 exact rewrite (long cents, truncated); F01 and F03 must be detected on credit-fees; JSON report mandatory (Detection Matrix) plus text; minimal case reused from the engine module, no duplicated logic.
- Model policy confirmed by the owner: Sonnet for any run or verification; reference outputs only from the COBOL program.

### R-34 2026-11-15: engine requirements (S1)
- Calls: engine-reqs (sonnet, 1.56 credits), engine-reqs-fix (sonnet, 3.97 credits). Total 59.41 of 531.
- Fixes sent (12): batch execution (one COBOL run, one JVM), no per-case timeouts; return codes per run plus per re-run case (conflict with comparison-rules.md "every case" flagged for owner validation); reference build flags kept (`cobc -x -Wall -I`, no `-std=`, which could change semantics); exact coverage from one instrumented run on all cases (no sampling) plus single-case traces; schema.json is the source of input domains; CASE-ID values fit X(10); generic minimal-case rule (numeric inputs in schema order by absolute value, then case id); JUnit source test runs the Java as a subprocess (main calls System.exit), JUnit jars pinned with SHA-256 in build/junit/, never committed (EPL-2.0 used as a tool); COBOL path fixed; 60 s defined as wall-clock of one verify with 2,000 cases including compilation; deterministic run_id from input hashes, seed, case count and tool versions; Hypothesis pinned as a dev dependency.
- Leftover for the design step: Req 5.5 still lists per-case return codes in the comparison output.
- Status: clean except the owner question on return codes.

### R-35 2026-11-15: pivot to the veteran's catalog (D-29)
- Operator verification on GnuCOBOL 3.2.0 before the design (owner request): SORT ... COLLATING SEQUENCE IS <alphabet> with ALPHABET ... IS EBCDIC, OBJECT-COMPUTER PROGRAM COLLATING SEQUENCE, and `-fdefault-colseq=EBCDIC` all apply the EBCDIC order (space, lowercase, uppercase, digits; ASCII baseline: space, digits, uppercase, lowercase). GnuCOBOL's EBCDIC table matches the byte order of IBM037, IBM1047, IBM500 and IBM1140 on letters, digits, space and hyphen, but no JDK charset on all printable punctuation (IBM1047 closest, 10 positions differ). The JDK in coroner:smoke provides these charsets. Recommendation applied: in-source clauses (engine compile flags unchanged), branch codes limited to letters, digits, space and hyphen.
- Calls: veteran (sonnet, 3.74 credits), veteran-format (haiku, 0.39), veteran-fix2 (haiku, below reporting resolution).
- fault-catalog/requirements.md rewritten as the veteran's catalog: T01 to T06 mandatory, T07 to T11 bonus, hero demo branch totals (T04 + T05, `make hero`), per-trap counts and rate, no global rate, probable cause plus one-sentence fix, certificate separate, JUnit test from the minimal-case module, JSON trap_catalog.json, trap programs exempt from the line count, legacy HALF_EVEN variant kept for the unchanged engine.
- Fixes sent: Kiro dropped the EARS format (restored); the reformat invented a "detection rate at least 50%" pass threshold that the owner never asked for (replaced by at least one detected case, rate reported only).
- Scope conflicts resolved in text: EBCDIC-encoded data stays out of scope, only the collating sequence trap is in scope (README, scope-v1.md); engine spec wording only (HALF_EVEN legacy variant name, Req 5.5 return codes leftover).
- D-29 logged; README tagline added; public catalog wording in no-formal-proof.md.

### R-36 2026-11-15: engine design
- Calls: engine-design (sonnet, 2.24 credits), engine-design-fix (sonnet, 3.47 credits). Total 69.39 of 531.
- Operator verification on GnuCOBOL 3.2.0 (-ftraceall): CONTINUE is traced as a statement; WHEN lines are traced when their condition is tested even if not taken, so branch markers are the first statement inside each arm.
- Fixes sent (8): BUG decimal normalization used quantize (rounding), which would hide a divergence such as Java 12.355 vs COBOL 12.36 (D-09): now pad only, extra non-zero decimals are divergent, plus Hypothesis properties; tie construction from products of input pairs with the correct even-digit arithmetic and a measured calibration target (80 to 120 HALF_EVEN divergences on 2,000 cases), not a guess; a return-code-only mismatch no longer prints "diverged on 0 cases"; branch map includes EVALUATE arms and uses first statements; parser scope stated, unsupported constructs give "not measured"; Decimal ordering for the minimal case; streaming trace parser and per-step timings; two owner questions kept.
- Open for the owner: Hypothesis at runtime vs random.Random(seed); return codes per run in batch mode.
- Status: clean.

### R-37 2026-11-15: D-30 and D-31 applied
- Calls: d30-31 (haiku, 2.11 credits), d30-31b (haiku, 0.27 credits).
- D-30 and D-31 logged; quality.md (random.Random(seed).random() only, Hypothesis for property tests only); comparison-rules.md (exact OS exit status 0 to 255, per run and per re-run case, "FAIL: return code differs (COBOL x, Java y)"); README note on the 0 to 255 limit; engine requirements and design updated (draw helpers from random() only, inputs.json gains cases_file_sha256, cases_file_encoding, cases_file_line_ending, python_version, random_seed; open questions closed).
- Fix sent: a leftover "owner validation pending" in the design flow, and the draw helpers the first call omitted. Operator check: draw_int over 100,000 draws stays within [lo, hi].
- Status: clean.

### R-38 2026-11-15: engine tasks.md
- Call engine-tasks (haiku, 0.58 credits): 15 tasks, each with Requirements and Done when, coverage table maps every criterion. Constraints given: hypothesis pinned at 6.170.14 (2026-10-30; the latest release was 9 days old), parse_trace kept as a wrapper because smoke/run_smoke.sh and the S0 tests use it, real two-source trace fixture, structure counts checked by hand, grep test against non-random() draws, JUnit jar version and checksum filled by the operator from a real download.
- Status: clean.

### R-39 2026-11-15: engine task 1 (dependencies and skeleton)
- Call et1 (sonnet): hypothesis 6.170.14 installed; package skeleton per the design.
- Scope slip accepted: Kiro also rewrote coroner/parse/trace.py cosmetically and dropped the package-level re-export (nothing imports it; smoke and S0 tests pass).
- Tests: pytest 39 passed; smoke PASSED.

### R-40 2026-11-15: engine task 2 (schema loading)
- Call et2 (sonnet). Operator check: parse_pic correct on S9(9)V99, V9(5), 9(3), X(1), 9(9)V99, +9(7).99, S9V9, 99V9(3); credit-fees schema gives the right types, signs and scales; invalid JSON and missing fields raise clear errors. Kiro correctly followed the real schema (6 input columns) where the task text was wrong.
- Tests: pytest 52 passed.

### R-41 2026-11-15: engine task 3 (trace keyed by source file and line)
- Call et3 (sonnet). Real two-source trace captured from GnuCOBOL (program, copybook, back to program: 3 Source: records); parse_trace_counts keys (source, line) correctly; parse_trace wrapper unchanged ({9, 10, 11, 16, 17}); smoke PASSED; pytest 59 passed.
- Notes for later tasks: the trace names the copybook HELPER.CPY while the file is HELPER.cpy (case-insensitive macOS filesystem): coverage matching (task 10) must resolve paths, not compare strings. parse_trace_counts reads the whole file instead of streaming (design); fix sent with task 4.

### R-42 2026-11-15: engine task 4 (COBOL structure parser)
- Calls et4 and et4fix (sonnet). Operator ground truth (counted from the source): 12 paragraphs, 33 IF, 33 ELSE, 1 EVALUATE with 4 arms (70 branches), constants 10.00, 25000.00, 12, 0.10, 0.05. Parser matches.
- BUG fixed: an arm starting with a nested IF was marked by the next non-IF statement, so 14 marker lines were shared by two branches and outer arms were only counted when their inner true arm ran. Now a nested IF/EVALUATE is the first statement of the arm; tests: no shared marker, CHECK-ELIGIBILITY outer ELSE 362 and inner true 363.
- Also done: parse_trace_counts streams the file.
- Operator check: 70 branches, no shared markers, no marker on ELSE/END-IF/WHEN lines; pytest 66 passed.
