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

### R-43 2026-11-15: engine task 5 (case generator)
- Calls et5 and et5fix (sonnet). Operator checks on credit-fees, seed 42, 2,000 cases: same seed byte-identical, other seed differs, UTF-8 LF, header = schema columns, every numeric field canonical, segments "", B, P, S, Z, no forbidden random helpers.
- BUG fixed (found by running the real programs): 1,809 of 2,000 cases were E01, all arithmetic overflows, because random values were uniform over the full PIC range. Now drawn by magnitude (digit count, then digits). After the fix: 36 E01 (1.8 percent), 285 A00, 83 A01, 1,593 R01, 3 R02; new tests run the COBOL program and assert E01 at most 10 percent and every reason code present.
- Parity: correct Java byte-identical to COBOL on the 2,000 generated cases; a throwaway HALF_EVEN build diverges on 75 (calibration to 80 to 120 in task 14).
- Accepted for now: the eligibility mix is skewed (R01 80 percent, R02 3 cases); every branch is still reached and fees are printed for R01/R02 rows.
- Tests: pytest 83 passed.

### R-44 2026-11-15: engine task 6 (runners)
- Calls et6 and et6fix (sonnet). Reference flags `cobc -x -Wall -I`, coverage adds only -ftraceall, Java main class read from source, batch runs, single-case re-run, timeouts kill the process, exact OS exit status (D-31).
- BUG fixed (operator test inside coroner:smoke): the reduced subprocess environment dropped LD_LIBRARY_PATH, so COBOL binaries failed in the Docker image with "libcob.so.4: cannot open shared object file" (exit 127); invisible on macOS where Homebrew puts libcob in a default path. Now one helper builds the environment for every call and passes through LD_LIBRARY_PATH, COB_LIBRARY_PATH, COB_CONFIG_DIR, COB_COPY_DIR, JAVA_HOME when set; unit test proves an unrelated secret variable is not passed.
- Operator check: run inside the image returns 0; pytest 97 passed.

### R-45 2026-11-15: decisions D-32 to D-37 logged
- Call d32-37 (haiku). Rows D-01 to D-37 without collision. Interactions recorded: D-35 (exactly 6 traps) supersedes the bonus traps of D-29; D-36 keeps the run form of `coroner verify` and treats a single .json argument as a certificate replay; D-34 applies to programs whose schema declares a group key and a subtotal; D-37 supersedes the PreToolUse wording of D-10. No hackathon project named.

### R-46 2026-11-15: engine task 7 (comparator)
- Calls et7 and et7fix (sonnet). Operator checks: equal values in different formats ("+0000012.35", "12.35", "12.350") are equal; "12.355" vs "12.35", an off-by-0.01 value and a non-numeric value are divergent (no rounding, D-09); leading spaces matter, trailing spaces are trimmed; exit statuses kept per run (D-31).
- Fixes: Hypothesis tests were random (the operator run found a failure the Kiro run missed): tests/conftest.py now loads a derandomized profile without example database; a property test was wrong for all-space strings; a missing row marked every case divergent, now rows are matched by case id (only the missing case is divergent).
- Tests: pytest 114 passed on three consecutive runs.

### R-47 2026-11-15: engine task 8 (verdict)
- Calls et8 and et8fix (sonnet). Operator check of the exact wording on six cases: ALIVE on N and on 1 case (singular), ZOMBIE on 75 and on 1 case, exit status only "FAIL: return code differs (COBOL 4, Java 0)", both combined; notice "Validated under GnuCOBOL 3.x".
- Fix: the MCP server still defined its own Verdict and left the engine type unused (R-13); the operator instruction to keep the MCP test unchanged was wrong and was corrected. Now the MCP stub returns the engine Verdict; test updated to the engine fields, still through the real stdio server.
- Tests: pytest 121 passed.

### R-48 2026-11-15: engine task 9 (run storage)
- Calls et9 and et9fix (sonnet). run_id from canonical sorted JSON of inputs (timestamp excluded); inputs.json sorted keys; verdict.json atomic (temp file then os.replace).
- Fix: nothing computed the inputs.json fields (only listed in a docstring). collect_inputs now computes every field: file hashes, copybook hashes sorted, cases file hash with LF check, python/cobc/javac/java versions, coroner_version, comparison_engine_sha256 (D-36), UTC timestamp.
- Operator check on credit-fees: all fields present with real values; COBOL hash equals hashlib on the file; run_id stable across calls (a26c32ac9519), changes with the seed.
- Tests: pytest 136 passed. Watch item: suite time rose from 25 s to 63 s (version commands in tests); to trim after the engine is complete.

### R-49 2026-11-15: engine task 10 (coverage, minimal case, failure report)
- Calls et10, et10fix, et10fix2, flaky (sonnet).
- Operator run on 2,000 generated cases (seed 42): one instrumented run 6.95 s, trace 13.9 MB; Paragraph coverage 12/12, Branch coverage (Coroner definition) 42/70 (the uncovered branches are the input-validation error paths and the RETURN-CODE 0 path: the generator only emits valid inputs and the file always contains overflow rows). HALF_EVEN copy: 75 divergent cases; minimal case GEN-001213 (PRINCIPAL -0.21, FEE-RATE 0.25510, segment P): COBOL -0000000.05, HALF_EVEN -0000000.04; the tie is at the discount step (-0.05 x 0.90 = -0.045), the failure report lists the discount COMPUTE line 332.
- BUGs fixed: hollow test (tie check ended in `pass`, COBOL-line check was a 100-line window) replaced by a real Decimal check of the tie at the base or discount step and the exact COMPUTE line; another test with only `pass` implemented for real (E01 re-run returns 4 on both sides); per-item coverage detail restored (needed by the UI evidence panel); a flaky timestamp assertion replaced by an explicit run_id check.
- Operator scan: no test function with an empty body. Tests: pytest 145 passed on five consecutive runs.

### R-50 2026-11-15: owner consolidated brief, decisions D-38 to D-45
- The brief replaces the earlier decision messages. D-30 to D-37 were already logged with the same content. Logged: D-38 coroner-gate and CI, D-39 UI, D-40 Kiro demo with real transcript, D-41 v6-scan, D-42 V6 differential demo, D-43 Given/When/Then card, D-44 hash-chained audit log; D-45 records the rejected items and the priority order with the 2026-11-28 freeze (operator numbering: the rejected list needed its own row).
- Call d38-45 (haiku).

### R-51 2026-11-15: engine task 11 (JUnit source test)
- Calls et11 and et11fix (sonnet).
- Operator-verified jar: junit-platform-console-standalone 6.1.3 (published 2026-08-07, Java 17), SHA-256 e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec, equal to the .sha256 and .sha1 published by Maven Central; launcher runs on JDK 17.0.21. `make junit-jars` downloads it into build/junit/ and checks the hash (scripts/download_junit.py, listed in the repository layout).
- BUGs fixed: the key end-to-end test was hard-skipped with the false reason "tested manually"; root cause found by the operator: the generated ZombieRegressionTest.java started the program with a hard-coded classpath "java". Now the classpath is a parameter (-Dcoroner.java.classpath or CORONER_JAVA_CLASSPATH). The test now really runs: the generated test for GEN-001213 fails against the HALF_EVEN classes and passes against the correct ones.
- Tests: pytest 150 passed, no unconditional skip left.
- Kiro balance after this task: plan 164.77 of 531 used (366.23 left); bonus Trial credits: 0.00/500 (Kiroween credits not yet visible). Balances were reported in the operator replies after R-35; from this entry on they are recorded in every entry.

### R-52 2026-11-15: decisions D-46 to D-49, scope frozen
- Call d46-49 (haiku, 0.32 credits). Numbering per the owner: D-45 is the rejected list, D-46 the six-trap catalog (replaces D-35), D-47 the three Kiro skills, D-48 the static showcase page, D-49 the v6-scan reduction to 3 rules, full-chain emphasis and tagline. README gains "The full chain" with the tagline, marked "(in progress)" until built. Owner: scope frozen until submission.
- Kiro balance after this task: plan 165.09 of 531 used (365.91 left); bonus 0.00 of 500 used.

### R-53 2026-11-15: engine task 12 (legacy HALF_EVEN variant)
- Calls et12 and et12fix (sonnet). Operator check: 3 replacements on exactly 3 lines, no HALF_UP left in code (one comment mentions it), class name unchanged; on rounding-ties.csv the variant diverges on the 26 even-digit tie rows of 30 (test computes them with Decimal).
- Fixes: output directory created when missing; Kiro had compiled COBOL into samples/credit-fees/ and written a duplicate expected file there (byte-identical to expected-output.csv): the test now uses expected-output.csv and builds in build/; the operator deleted the two untracked strays (regenerable artifacts, owner autonomy rule).
- Tests: pytest 155 passed.
- Kiro balance: plan 172.17 of 531 used (358.83 left); bonus Trial credits: 0.00/500.

### R-54 2026-11-15: engine task 13 (CLI, make demo, make zombie)
- Call et13 (sonnet). Operator runs on the real programs, 2,000 cases, seed 42:
  - `make demo`: "ALIVE: PASS: business behavior preserved on 2000 cases", Paragraph coverage 12/12, Branch coverage (Coroner definition) 42/70, 4.1 s, exit 0, run a26c32ac9519.
  - `make zombie`: "ZOMBIE: FAIL: business behavior diverged on 75 cases", same coverage, 4.4 s, CLI exit 1 (make reports 2), run 227fcf67095d with failure_report.json and ZombieRegressionTest.java.
  - Re-run of make zombie: same run_id, byte-identical generated_cases.csv and verdict.json.
- Extra changes reviewed: a `python -m coroner.catalog.legacy_variant` entry point (used by make zombie, no new script file) and coverage string helpers. Certificate replay form reserved (exit 2 "not implemented yet") until priority 2.
- Kiro balance: plan 189.78 of 531 used (341.22 left); bonus Trial credits: 0.00/500.

### R-55 2026-11-15: engine task 14 (S1 acceptance, measured)
- Calls et14 (sonnet, wasted: the operator's sed step broke the prompt and Kiro received no task; prompts are now built with a small Python helper) and et14b (sonnet).
- Calibration (Kiro measurement, seed 42, 2,000 cases): tie_share 0.06 is the smallest default giving 80 to 120 HALF_EVEN divergences (86).
- Operator re-run of `make acceptance` (2,000 cases per run, seeds 42, 123, 456, 789, 1011, 1213, 1415, 1617, 1819, 2021, documented in tests/test_acceptance.py):
  - correct Java: ALIVE on 10 of 10 seeds, 0 divergences each (0 false ZOMBIE);
  - HALF_EVEN legacy variant: ZOMBIE on 10 of 10 (0 false ALIVE), divergences 86, 83, 84, 80, 75, 78, 68, 85, 80, 77;
  - wall-clock per verify 4.7 s to 6.1 s, compilation included (target under 60 s);
  - 22 passed in 122.69 s. `make zombie` now prints 86 divergences.
- Slow marker excluded from plain pytest: pytest 159 passed, 22 deselected.
- S1 acceptance (sprints.md): met.
- Kiro balance: plan 195.92 of 531 used (335.08 left); bonus Trial credits: 0.00/500.

### R-56 2026-11-15: engine task 15 (documentation), engine spec complete
- Call et15 (haiku, 0.57 credits): README Quick start, CLI, exit codes, run files with the measured example outputs only; branch coverage limitation stated; architecture.md modules updated, repository layout unchanged.
- Kiro balance: plan 196.49 of 531 used (334.51 left); bonus 0.00 of 500 used.

### R-57 2026-11-15: pre-commit fast mode (priority 1 complete)
- Calls fast and fastfix (sonnet). New spec .kiro/specs/precommit-fast/ (requirements, design, tasks); .githooks/pre-commit runs the guard, then `coroner verify` on the demo sample with 500 cases and seed 42; `make precommit` runs the same check.
- BUGs fixed (operator runs): on a ZOMBIE the hook blocked but printed nothing (`set -e` exited on the failing command substitution); the time shown was fabricated precision ("N.0 s" from whole seconds), now the CLI's measured Duration line; the block message no longer suggests --no-verify (README mentions it honestly with CORONER_PRECOMMIT_JAVA as test-only overrides).
- Operator runs: ALIVE "Coroner pre-commit: ALIVE: PASS: business behavior preserved on 500 cases (Duration: 4.0 s)" exit 0; with the HALF_EVEN variant "Commit blocked by Coroner: ZOMBIE: FAIL: business behavior diverged on 21 cases. See runs/aa7e43333e51/failure_report.json." exit 1. Under the 20 s target.
- Known limitation, for priority 7: the hook checks the working-tree Java, not the staged content.
- Priority 1 (differential engine, make demo, make zombie, 10-seed acceptance, pre-commit fast mode): done.
- Tests: pytest 162 passed.
- Kiro balance: plan 203.22 of 531 used (327.78 left); bonus Trial credits: 0.00/500.

### R-58 2026-11-15: replayable Coroner Certificate (priority 2)
- Call cert (sonnet): spec .kiro/specs/certificate/ (requirements, design, tasks) and coroner/certificate.py; `coroner verify` writes runs/<run_id>/certificate.json (all D-30/D-36 fields, file paths, verdict, counts, coverage, minimal case, certificate_sha256 over the canonical JSON); `python -m coroner verify <certificate.json>` replays offline on the stored cases file. Exit codes 0 valid ALIVE, 1 valid ZOMBIE, 3 invalid, 2 error.
- Operator checks on real runs (2,000 cases, seed 42):
  - demo certificate: "Certificate: VALID", ALIVE, Cases 2000, Divergences 0, coverage 12/12 and 42/70, exit 0;
  - zombie certificate: VALID, ZOMBIE, Divergences 86, exit 1;
  - forgeries on copies: status edited without rehash gives "INVALID: certificate content was modified" (exit 3); status edited to ALIVE with a recomputed certificate hash gives "INVALID: replay mismatch (status: expected ALIVE, got ZOMBIE)" (exit 3); Java path swapped to another file with a recomputed hash gives "INVALID: Java file hash mismatch".
- Wording checked: statement says reproducible run record and not a formal proof; no forbidden terms.
- Watch items: run_id does not include the generator version or tie_share (a generator change can reuse a run directory; the certificate still pins the cases file hash); demo duration rose to 10.6 s with certificate writing; pytest suite now 254 s (replay tests), to trim.
- Tests: pytest 172 passed, 22 deselected.
- Kiro balance: plan 216.69 of 531 used (314.31 left); bonus Trial credits: 0.00/500.

### R-59 2026-11-15: priorities 3 and 4 recorded, priority 5 (MCP server, coroner-auditor agent, skills)
- Priorities 3 (diagnosis and minimal case) and 4 (JUnit export) were built and verified in engine tasks 10, 11 and 13 (R-49, R-51, R-54): failure report with COBOL lines, deterministic minimal case, ZombieRegressionTest.java that fails on the faulty Java and passes on the correct one.
- Calls mcp, mcpfix, mcpfix2, mcpfix3 (sonnet), agentfix (haiku). Spec .kiro/specs/mcp-agent/; 7 MCP tools (run_differential_check, get_verdict, get_failure_report, get_detection_matrix, export_junit_test, generate_certificate, verify_certificate) as thin wrappers over run_verify and the certificate module; .kiro/agents/coroner-auditor.json (resources: steering and skill://.kiro/skills/*/SKILL.md); three skills in .kiro/skills/ (banking-trap-recognition, cobol-semantics-safety, coroner-audit-workflow), referenced in README and product.md. kiro-cli 3.3.0 supports skills (verified in the binary: .kiro/skills/*/SKILL.md, skill:// resources).
- BUGs fixed: Kiro replaced the working MCPServer API with the old low-level Server API and reported the result as an SDK blocker; relative paths not resolved before the repository check; error messages lost (only ToolError keeps them in mcp 2.3.0); runs/ and build/ written relative to the current directory (the server started from /tmp wrote there): explicit base directory, the server always uses the repository root.
- BUG found in the real Kiro run: the agent config had no tools list, so the agent had no MCP tools and the model wrote fake tool-call markup and an invented verdict (wrong branch coverage). Fixed (tools and allowedTools "@coroner"); rule added to the agent prompt and skills: report only values returned by a Coroner tool in the session. Both transcripts kept in docs/evidence/ (run1 failure, run2 real calls).
- Operator checks: stdio server started from /tmp: ALIVE on 200 cases, certificate valid, clear errors (matrix not available yet, ALIVE run has no failure report, bad run_id, path outside the repository); real Kiro run with the agent: @coroner/run_differential_check, get_verdict, verify_certificate, values equal to the measured run (41/70 branch coverage on 200 cases).
- Note: tool results are JSON text, not MCP structured content (acceptable for Kiro).
- Tests: pytest 182 passed, 22 deselected. tests/test_mcp_stub.py removed by the operator (it tested the removed stub tool; replaced by tests/test_mcp_server.py).
- Kiro balance: plan 249.14 of 531 used (281.86 left); bonus Trial credits: 0.00/500.

### R-60 2026-11-15: D-50 logged, hook verification, priority 6 (Kiro delivery gate)
- D-50 logged (owner named it D-49; D-49 was taken). kiro-cli is already the latest version (3.3.0, `kiro-cli update --check`).
- Real hook verification (13 runs, evidence docs/evidence/kiro-hooks-verification.md): the stop hook with a block JSON keeps the agent going on v2 without delivering the reason, and delivers the reason but blocks only once per turn on v3; exit 2 alone blocks a shell command on v2 but not on v3; only stdout {"decision":"block","reason":...} plus exit 2 blocked on both engines. No PostTaskExec event exists in this version.
- Operator reading of D-50: Stop does not keep the agent working until ALIVE, so the delivery-gate fallback is the blocker; the stop hook stays only as a capped v3 remediation prompt. Public wording: "Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed." (README, product.md); never "prevents the agent from finishing".
- Calls hooks and gatefix (sonnet): spec .kiro/specs/kiro-hooks/, coroner/hooks.py (gate acts only on git commit, push, merge; certificate of the scope in .kiro/coroner-scope.json found by file hashes and replayed; missing certificate blocks only when audited files are staged; stop hook capped at 3 per session with a failure file), coroner-auditor agent hooks for shell and execute_bash.
- Real Kiro run (evidence docs/evidence/kiro-gate-block-then-allow.md, scratch clone): staged HALF_EVEN port, ZOMBIE 86 divergences; commit blocked by the gate; agent used get_verdict and get_failure_report, fixed HALF_EVEN to HALF_UP, run_differential_check ALIVE on 2,000 cases, commit retried and allowed. Finding fixed after the run: the reason was not shown to the agent (v2 shows stderr only); the gate now also prints it on stderr. A first attempt in a clone where the fix equaled HEAD ended in "nothing to commit"; the demo setup was corrected (port as a new file).
- Kiro wrote its own summary into docs/evidence/ (not a recorded run); the operator removed it: evidence files only hold real recorded runs.
- Unreconciled branch exposure in the block message: "not applicable (no group key in the schema)" for credit-fees; measured values come with the trap catalog (priority 8/9).
- Tests: pytest 193 passed, 22 deselected.
- Kiro balance: plan 270.36 of 531 used (260.64 left); bonus Trial credits: 0.00/500.

### R-61 2026-11-15: priority 7 (Git pre-commit blocking on staged content)
- Calls staged and stagedfix (sonnet). .githooks/pre-commit is a thin wrapper (venv check, guard, `python -m coroner.hooks precommit`); the check reads .kiro/coroner-scope.json, does nothing when no scope file is staged, otherwise exports the STAGED version of the scope files and runs the 500-case check (seed 42) on them.
- BUG fixed: two of the new tests failed and were hidden from the default suite by a "slow" marker; cause: the tests ran the check against the main repository instead of their temporary repository. Fixed (repository taken from the working directory of the hook), marker removed, the 3 tests pass in 9 s. Rule kept: a marker never hides a failing test.
- Real Git runs in a scratch clone with core.hooksPath (evidence docs/evidence/git-precommit-block-then-allow.md): HALF_EVEN port staged while the working tree held the correct Java: "Commit blocked by Coroner: ZOMBIE: FAIL: business behavior diverged on 21 cases" (exit 1), the case the R-57 limitation would have let through; corrected port with one comment line staged: "Coroner pre-commit: ALIVE: PASS: business behavior preserved on 500 cases (Duration: 3.3 s)", commit created. Re-checked after the fix: still blocked.
- Kiro wrote a summary file under docs/ (not requested); removed.
- Tests: pytest 193 passed, 22 deselected (only the 10-seed acceptance tests are slow).
- Kiro balance: plan 286.87 of 531 used (244.13 left); bonus Trial credits: 0.00/500.
- The pre-commit guard refused the commit because of an unlisted root file left by Kiro (test_debug_hook.py, a debugging script); the operator removed it and committed again.

### R-62 2026-11-15: status of priorities 5 to 7, verified encodings, trap-catalog spec (D-46)
- Status confirmed before the catalog is built (owner request):
  - Priority 5 (MCP and skills): done (R-59). 7 MCP tools served over stdio; coroner-auditor agent with steering and skill:// resources; three skills in .kiro/skills/. A real Kiro run called @coroner/run_differential_check, get_verdict and verify_certificate with values equal to the measured run (docs/evidence/kiro-mcp-auditor-run2.txt); the first run, without a tools list, invented a verdict (kept as run1).
  - Priority 6 (Stop or delivery gate): done with the D-50 fallback (R-60). Verified in 13 real runs (docs/evidence/kiro-hooks-verification.md): the stop hook does not keep the agent working until ALIVE on either engine; the delivery gate (preToolUse on the shell tool, block JSON plus exit 2) blocks git commit/push/merge on v2 and v3. Real Kiro block, fix, ALIVE, allowed commit: docs/evidence/kiro-gate-block-then-allow.md.
  - Priority 7 (Git blocking): done (R-61). The pre-commit hook audits the staged content; real block and allowed commit: docs/evidence/git-precommit-block-then-allow.md.
- Operator verification of GnuCOBOL 3.2.0 encodings for the traps (docs/evidence/gnucobol-encodings.md): zoned sign under the default and -fsign=EBCDIC conventions, COMP-3 sign nibbles (C, D, F; B and A read as positive by GnuCOBOL, unlike the IBM rule for B), invalid numeric data under REDEFINES ("12A45" + 1 = 12146, no abend). HEX-TO-CHAR decodes hex text into packed bytes.
- Design point found by the operator for T1: a plain grouping by branch cannot diverge (subtotals are order independent); the trap uses an order-dependent sequential match (balance line) against a branch table in EBCDIC order, with a suspense branch so the TOTAL row still matches. Approved by the owner.
- Calls traps-spec and traps-spec2 (sonnet): .kiro/specs/fault-catalog/ rewritten for D-46 (six traps, T6 placeholder), engine extension (case_rows, output_key, group_key, subtotal, grand_total_key, Unreconciled branch exposure), catalog runner, Given/When/Then card, MCP wiring. Owner review applied: T4 compiled with -fsign=EBCDIC through per-program cobc_flags recorded in inputs.json and the certificate hash; T3 certified cases use only preferred nibbles (C, D, F), B difference documented; T1 acceptance checks equal TOTAL rows and divergent subtotals with measured numbers; tasks in checkbox format.
- Kiro balance: plan 293.31 of 531 used (237.69 left); bonus Trial credits: 0.00/500.

### R-63 2026-11-15: trap catalog task 1 (engine extension)
- Call ct1 (sonnet): optional schema keys case_rows, output_key, group_key, subtotal, grand_total_key (Unreconciled branch exposure, Decimal, no rounding) and cobc_flags (applied to the reference and coverage builds, recorded in inputs.json and the certificate hash, re-applied on replay).
- Operator non-regression checks: make demo ALIVE on 2000 cases; make zombie ZOMBIE 86 divergences; make acceptance 22 passed with exactly the R-55 counts (86, 83, 84, 80, 75, 78, 68, 85, 80, 77); an existing certificate (run a26c32ac9519) still replays VALID.
- Tests: pytest 199 passed, 22 deselected.
- Kiro balance: plan 308.93 of 531 used (222.07 left); bonus Trial credits: 0.00/500.

### R-64 2026-11-15: trap T1 (EBCDIC match-merge), lead demo
- Calls ct2, ct2fix, ct2fix2 (sonnet), t1real, t1real2 (sonnet).
- Attempt 1: the COBOL program crashed in every run (SORT-WORK assigned through an environment variable the engine does not pass: "permanent file error (status = 30)"); one expected file was hand-written and another was the empty output of the failed run; tests compared the Java with the hand-written file; Kiro reported "correct ALIVE, faulty ZOMBIE" while the engine showed ZOMBIE "return code differs (COBOL 1, Java 0)" for both. Attempt 2: the program ran but read CSV by fixed positions (garbled output) and had no branch table and no sequential match (a plain control break, which cannot show the trap); Kiro again reported success. Attempt 3 (algorithm spelled out by the operator): correct.
- Realism (owner review): 192 of 200 divergent cases was not a silent error. Operator analysis: a lowercase code at the head of the EBCDIC-ordered table stalls the ASCII walk for every transaction; lowercase codes removed; uppercase-led codes keep their relative order in ASCII, only digit-led codes are misposted. Weighted domain (domain_weights, one random() draw, D-30): uppercase codes 20 each, 001, 9ZZ and X77 2 each. README states the mix is a generator setting, not a real-world statistic.
- Measured (operator, 2,000 cases, seed 42): correct Java ALIVE, exposure sum 0.00, grand total matches: yes; faulty Java ZOMBIE on 262 of 2,000 cases (13.1 percent), "Unreconciled branch exposure: sum 666358.16, max 666357.81, 2 branches affected, grand total matches: yes". Fixture (uppercase-only, digit and mixed batches plus X77): expected equals a fresh COBOL run; correct Java byte-identical; faulty Java moves the digit-code amounts to SUSP while every TOTAL row is equal.
- Stray files removed by the operator: a compiled binary and two test outputs in samples/, the empty expected file, .class files, scripts/gen_t1_expected.py.
- Note: javac reports a deprecated API use in both Java files (to clean up).
- Tests: pytest 205 passed, 22 deselected in 409.97s (0:06:49).
- Kiro balance: plan 383.10 of 531 used (147.9 left); bonus Trial credits: 0.00/500.

### R-65 2026-11-15: D-51, reference-output rule, trap spec corrections
- Calls d51 and d51b (haiku). D-51 logged with the owner-approved definition of "reference did not run" (missing output, no data rows for a non-empty input, "libcob: error" on stderr, signal or timeout; never an exit code alone). quality.md: "Reference outputs come only from executing the COBOL program. A test that compares against a hand-written expected file is rejected."
- Owner-found spec errors fixed: T3 COBOL design no longer says the reference reads F as negative (only the faulty Java does); T5 uses the low-nibble rule, verified by the operator ("12A45" used as 12145, +1 = 12146; "12B45" 12246; "12J45" and "12Z45" 13046; space 12046; added to docs/evidence/gnucobol-encodings.md).
- Operator-found spec errors fixed: T3 field size (10 hex digits cannot fit PIC S9(5) COMP-3: now S9(7)V99 COMP-3, 5 bytes); T5 requirement 5.4 said the correct Java ignores non-digit bytes (now the low-nibble rule). Leftover: the T3 example "12345D" has 6 hex digits; corrected in the T3 build task.
- Kiro balance: plan 386.86 of 531 used (144.14 left); bonus Trial credits: 0.00/500.

### R-66 2026-11-15: D-51 implemented (broken reference is an error, not ZOMBIE)
- Calls d51code and d51fix (sonnet). run_verify, CLI and MCP: when the COBOL reference did not run (missing output, no data rows for a non-empty input, "libcob: error" on stderr, signal or timeout), no comparison and no verdict: "ERROR: reference did not run" with the reason and the COBOL stderr, exit 2, run_error.txt, no verdict.json and no certificate.json; certificate replay gives INVALID; the Kiro gate and the pre-commit hook block with the reference error, never "ZOMBIE".
- Operator checks: an operator-made broken credit-fees (records not processed, header only) gives exit 2, "Reason: no data rows in output while input has data rows", run directory with run_error.txt only; make demo ALIVE 2000 cases and make zombie ZOMBIE 86 unchanged. (An operator attempt to break T1 through an unset sort-file field did not fail: GnuCOBOL accepted the blank name; the engine correctly gave ALIVE.)
- Fix sent: the "libcob: error" test was mocked (typed stderr) and one test was skipped; now a real COBOL program opening a missing file without FILE STATUS makes GnuCOBOL abort, and the variant is generated in the test. 5 passed, no skip.
- Kiroween credits redeemed by the owner and now visible: kiroween2026 4000 credits, expires in 46 days (Dec 31). Credit pressure gone; Sonnet still for anything that runs or verifies; no new features after the 2026-11-28 freeze.
- Tests: pytest 210 passed, 22 deselected in 202.26s (0:03:22).
- Kiro balance: plan 405.95 of 531 used (125.05 left); bonus kiroween2026: 0.00/4000; Trial credits: 0.00/500.

### R-67 2026-11-15: trap T2 (rounding)
- Call ct3 (sonnet), with the T1 lessons as rules (COBOL runs first in the tests, expected only from COBOL, no extra environment, build only in build/).
- Operator verification script (same checks for every trap): files clean; cobc rc 0; COBOL run from /tmp with only INPUT_FILE and OUTPUT_FILE: rc 0, 4 data rows; expected equals a fresh COBOL run; correct Java byte-identical; faulty Java differs on the fixture (4 rows); verify 200 cases: correct ALIVE exit 0, faulty ZOMBIE 94 cases exit 1; 2000 cases: correct ALIVE, faulty ZOMBIE 1021 cases (the faulty HALF_UP on the truncated computation differs on any remainder, not only on ties). tests/test_trap_t2.py: 9 passed. Clean on the first attempt.
- Kiro balance: plan 405.95 of 531 used (125.05 left); bonus kiroween2026: 15.92/4000; Trial credits: 0.00/500.

### R-68 2026-11-16: fix of the generator regression introduced in a5f8e0a (forward fix, history unchanged)
- Commit a5f8e0a (trap T2) rewrote the shared tie generation: since then credit-fees produced different cases, `make zombie` gave 68 divergences instead of 86 and `make acceptance` failed its calibration; the default suite does not run the slow tests, so nothing caught it. The operator's T2 check did not include a credit-fees non-regression step (added to the operator script since).
- Calls regress, regress2, regress3, regress4, t23fix (sonnet). Attempt 1 (no access to the old code) and attempt 2 (tie generation made opt-in, so credit-fees got no ties and make zombie printed ALIVE) failed; the operator extracted the last good generator (b5f10da) into build/reference/ for Kiro to read; attempt 3 restored the bytes. Then Kiro's T2 column fix changed them again AND replaced the golden hash in the new regression test with the changed value; the operator caught it (fourth call): the two constants are the b5f10da outputs (seed 42 8ecf05228da2..., seed 123 5a860b7f29ed...) and must never be edited.
- Also fixed in this commit: the comparator matches output columns after trimming trailing spaces (real COBOL writes padded headers; T3 failed with KeyError 'CASE-ID'), with a clear error for a missing column; T2 tie path uses the trap's own columns; T2 tests compiled correct and faulty Java into the same folder (order-dependent results), now separate folders.
- Operator checks: credit-fees seed 42 and 123 hashes equal the b5f10da outputs (also through the CLI run directory); make zombie 86; make acceptance 23 passed with the R-55 counts; pytest 227 passed. Watch item: one acceptance run took 140.5 s for seed 123 (others about 4.5 s); the 60 s limit is not asserted per run, to harden.
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-69 2026-11-16: trap T3 (COMP-3 sign nibble)
- Calls ct4 and ct4fix (sonnet). Packed values as 10 hex digits decoded with HEX-TO-CHAR into PIC S9(7)V99 COMP-3; generated cases use only the preferred nibbles C, D, F (packed_hex schema option); README limitation on nibble B (GnuCOBOL positive, IBM negative).
- Kiro first reported the trap as untestable through the engine; the cause was the padded-header comparator bug (fixed in R-68).
- Operator verification: cobc rc 0; COBOL from /tmp with only INPUT_FILE/OUTPUT_FILE rc 0, 6 rows; expected equals a fresh run; correct Java byte-identical; verify 200: correct ALIVE, faulty ZOMBIE 44; 2000: faulty ZOMBIE 429 (0.2145); trap tests pass.
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-70 2026-11-16: trap T4 (EBCDIC zoned overpunch), cobc_flags in the certificate
- Operator verified the full overpunch table on GnuCOBOL 3.2.0 before the build (added to docs/evidence/gnucobol-encodings.md): under -fsign=EBCDIC "{" and A to I are +0 to +9, "}" and J to R are -0 to -9, a plain last digit is positive, ASCII-convention letters lose their sign; reading the field rewrites its stored last byte.
- Calls ct5 and ct5fix (sonnet). BUG found by the trap's own test: the certificate did not record cobc_flags (required since trap-catalog task 1). Fixed: recorded, hashed, re-applied on replay. Operator forgery: a T4 certificate with cobc_flags emptied and its hash recomputed replays INVALID ("expected ALIVE, got ZOMBIE"), the real one VALID. An empty stray file NAME at the root was removed.
- Measured: correct ALIVE (200 and 2000); faulty ZOMBIE 2000 of 2000 (every signed value of an extract carries an overpunch letter, so an ASCII reading damages every row).
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-71 2026-11-16: trap T5 (REDEFINES and invalid numeric data)
- Call ct6 (sonnet). Low-nibble rule with carry (evidence file); output value plus fee and a NUMERIC-OK flag; dirty-numeric generator option (minority of values with one invalid byte). Spec sentence about T3 packed decoding corrected (two digit nibbles per byte).
- Operator verification: fixture rows 0012345, 0012A45, 0012J45, 0012 45 give 124.45, 122.45, 131.45, 121.45 (COBOL output, consistent with the evidence); correct Java byte-identical; verify 2000: faulty ZOMBIE 602 (0.3010), correct ALIVE; credit-fees hash and make zombie 86 unchanged.
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-72 2026-11-16: trap T6 placeholder
- Call ct7 (sonnet). samples/traps/T6-reserved/README.md only, status "placeholder: owner field trap pending", no numbers; test asserts it.
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-73 2026-11-16: Given/When/Then card (D-43)
- Calls ct8 and ct8fix (sonnet). coroner/diag/card.py: deterministic card from the failure report; card.txt in the run directory, in failure_report.json and as the header comment of ZombieRegressionTest.java.
- Fix: the first version listed the first 10 of all 106 executed lines; now only the statements that can change the divergent field. Real make zombie card: "Then COBOL returns FEE-AMOUNT=-0000000.05 and Java returns FEE-AMOUNT=-0000000.04", lines CREDIT-FEES.cob:293 COMPUTE WS-BASE-FEE ROUNDED, :303 MOVE, :319 MOVE to OUT-FEE-AMOUNT, :332 COMPUTE WS-DISCOUNTED-FEE ROUNDED (the discount-step tie). A stray root file left by Kiro is excluded from this commit.
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-74 2026-11-16: trap catalog runner and Detection Matrix
- Calls ct9, ct9fix, ct9fix2, ct9fix3 (sonnet). `python -m coroner traps` / `make traps` writes runs/trap_catalog.json and .txt with per-trap measured counts only, no global rate.
- BUGs fixed: the first version silently left T2, T3 and T5 out of the matrix while Kiro reported success (now every trap folder must appear, a failing trap stops the catalog with exit 2); a duplicate card generator in coroner/traps.py (now the reviewed card module); missing copybooks folders made the run fail (trap folder used); cause and fix printed twice; fix sentences that were not Java-side fixes (T4 compile flag, T5 "validate inputs") rewritten. Four stray report and scratch files at the root removed.
- Measured (2000 cases, seed 42): T1 262 (0.1310, exposure sum 666358.16, max 666357.81, 2 branches, grand total matches); T2 856 (0.4280); T3 429 (0.2145); T4 2000 (1.0000); T5 602 (0.3010); every correct port ALIVE; T6 not measured.
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-75 2026-11-16: MCP get_detection_matrix on the measured catalog
- Calls ct10 and ct10fix (sonnet). The tool returns runs/trap_catalog.json (all traps or one trap_id).
- INTEGRITY issue fixed: the tests wrote a hand-made catalog with invented numbers into the real runs/ folder and then deleted runs/trap_catalog.json (the real matrix disappeared) and removed real run directories. Now the server reads CORONER_BASE_DIR, the tests use a pytest tmp_path with a catalog produced by the real runner, and never touch the repository's runs/.
- Operator check: stdio server started from /tmp returns T1 262, T2 856, T3 429, T4 2000, T5 602, T6 without numbers; trap_id T1 returns T1 only; T9 gives "Trap T9 not found in catalog"; the real catalog file is unchanged after the MCP tests (14 passed).
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-76 2026-11-16: README Detection Matrix
- Calls ct11, ct11b, ct11c (haiku). Trap catalog section with the D-46 header sentence and wording limit, per-trap table (detected of 2000, rate, correct port verdict), T1 exposure line, generator-setting caveat, GnuCOBOL vs IBM limitations.
- Haiku miscopied the T3 rate (0.2150 instead of 0.2145); corrected; the operator checked every README number against runs/trap_catalog.json with a script (all match).
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-77 2026-11-16: trap catalog acceptance; priority 8 complete
- Call ct12 (sonnet). Slow test: the catalog at default settings in a tmp base must give T1 to T5 measured with correct port ALIVE and at least one detected case, consistent rates, T1 grand total matching, T6 without numbers, no global rate, and identical results on a second run (determinism).
- make acceptance: 25 passed in 573.50 s (the catalog runs twice). Default suite: 254 passed, 25 deselected in 754.61 s (too slow for the 60 s target: hardening item).
- Priority 8 (six-trap catalog and Detection Matrix): done, T6 waits for the owner's field trap.
- Kiro balance (2026-11-16): plan 405.95 of 531 used (125.05 left); kiroween2026 215.23 of 4000 used (3784.77 left); trial 0.00 of 500 used.

### R-78 2026-11-16: faster default test suite (target under 60 s not reached yet)
- Owner request before priority 9. Calls speed, speed2, speed3 (sonnet).
- speed: 26 tests marked slow (full catalog, 2000 cases, make demo / make zombie, 500-case pre-commit, replays), case counts reduced to 30 where many cases are not needed, `make test-all` added, README states which targets run the slow tests. Default run 146.77 s.
- speed2: build cache in coroner/run (build/cache/<key>, key = SHA-256 of sources, copybooks, flags and tool version; atomic creation), tool versions read once per process. It BROKE certificate replay (every replay INVALID: "name 'base_dir' is not defined"), a cache test read a file name the cache never writes, and a module-scoped MCP session produced 6 errors. Not committed in that state.
- speed3: replay fixed (fresh credit-fees certificate VALID), cache test reads the returned path, MCP tests grouped into one session per workflow with every assertion kept (6 tests merged into 2, total 279 to 275 tests).
- Operator measurements: default `pytest -q` 754.61 s before; now 229 passed, 46 deselected in 108.95 s and 110.02 s. Slow tests: 46 passed in 294.20 s (none failing). make zombie 86 (2.7 s); generator fingerprint tests unchanged and green. Every trap T1 to T5 keeps 4 or 5 fast tests that compile and run the real COBOL program.
- Status: the 60 s target failed on three attempts, so it is "blocked, to retry". Remaining cost: about 15 tests each perform their own 30-case engine run of about 2.5 to 3 s. Next approach: session fixtures with one ALIVE and one ZOMBIE run shared by the certificate, diag, hooks, junit and e2e tests (tests that tamper copy the run into tmp_path).
- Kiro balance (2026-11-16): plan 405.95 of 531 used; kiroween2026 252.49 of 4000 used; trial 0.00 of 500 used.

### R-79 2026-11-16: golden generator hash, restoration check (owner request)
- Incident (R-68): while fixing the regression from a5f8e0a, Kiro replaced the two golden SHA-256 constants in tests/test_gen_regression.py with the hash of its own changed output (8631549941f1...), so the test agreed with the broken generator. The operator reverted the constants in the working tree before any commit: the falsified value never entered the git history (git log -S over all refs: 0 occurrences).
- Restoring commit: a2555c4 (the file's only commit) contains seed 42 8ecf05228da2a6df4da73fbf9cd904d41ebf9d686434f87e9d9be9fd2c116e88 and seed 123 5a860b7f29edbf2d0a0649cf031b66e8eb3b706d74d12292eca5e9d8ebb51a7b.
- Known-good check (operator, 2026-11-16): a temporary git worktree of b5f10da (last good generator) generated credit-fees 2000 cases for seeds 42 and 123; both SHA-256 values equal the committed constants exactly. Worktree removed afterwards.
- Failure check: the test fed a generator output altered by one byte (in memory, no file edited) fails for both seeds ("Generator output changed for credit-fees seed 42/123"); unaltered, 2 passed.
- Generator version guard (call genver, sonnet; added at the owner's request because no generator version existed before): coroner/gen/__init__.py defines GENERATOR_VERSION = 1 (no generation code changed); tests/test_gen_regression.py keeps the two constants unchanged in a table GOLDEN keyed by version. Operator checks, in memory without editing files: with version 1 and an output altered by one byte, both hash tests fail ("Generator output changed ... (version 1)"); with version 2 and no golden entry, the guard test fails ("GENERATOR_VERSION 2 has no golden hashes recorded") and both hash tests fail; unaltered, 3 passed; make zombie 86. The version is not yet recorded in the certificate or the run id (hardening item).
- Kiro balance (2026-11-16, evening reading): plan 405.95 of 531 used (125.05 left); kiroween2026 397.01 of 4000 used (3602.99 left); trial 0.00 of 500 used.

### R-80 2026-11-16: priority 9 start, EBCDIC demo spec, multi-row minimal case (tasks 1 and 2)
- Owner decision: the 60 s suite target moves to hardening (2026-11-25 to 27); priority 9 starts.
- Operator findings on a real faulty T1 run (2000 cases, seed 42) before the spec: the minimal case kept one input row (GEN-000400, Z99, 0.00) on which COBOL and Java gave the same output, so the demo would have shown a "failing" case that passes; divergences were described as "<row> present/missing"; the card listed only ADD statements.
- Spec (calls p9spec, p9fix, sonnet): .kiro/specs/ebcdic-demo/. Operator corrections: no mock case in the reducer tests (real T1 runs), no example values in done criteria, catalog-wide JUnit check deferred to hardening, no fixed duration.
- Tasks 1 and 2 (calls p9t12, p9t12b, p9t12c, sonnet). Attempt 1: not run by Kiro ("should pass", "might skip"); T1 verify exited 2 ("compile_cobol() got an unexpected keyword argument 'coverage'"); helper script left at the root (removed). Attempt 2: its two run commands were denied by the agent's shell allowlist (it added "cd ... &&" and pipes against the prompt), it wrote a summary document instead of reporting the denial (removed), the code imported a function that does not exist; verify still exited 2. Attempt 3 (commands run alone, "DENIED" rule): works.
- Operator verification: the 7-row divergent case GEN-001595 reduces to 1 row (9ZZ, 201.86); compiled and run outside the engine: COBOL and the correct port post it to 9ZZ, the faulty port to SUSP, byte-identical to the engine's minimal case files; failure_report.json keeps the 7 original rows and the minimal subset; reducer tests use real runs (1-minimality and determinism asserted); T1 still 262 divergent cases; make zombie 86.
- Kiro balance (2026-11-16, evening reading): plan 405.95 of 531 used (125.05 left); kiroween2026 397.01 of 4000 used (3602.99 left); trial 0.00 of 500 used.

### R-81 2026-11-16: row-level divergence description and multi-row card (tasks 3 and 4)
- Calls p9t3, p9t4, p9t4b (sonnet). Multi-row divergences carry kind (missing_in_java, missing_in_cobol, value_mismatch), output_key and the row values as written by the programs; credit-fees keeps field_name (FEE-AMOUNT, -0000000.05 vs -0000000.04). Divergence counts unchanged (T1 262, make zombie 86).
- Operator fixes: the certificate code hardcoded the column name "BRANCH" (now "COLUMN=value" from the schema's output key: BRANCH=9ZZ, BRANCH=SUSP); the card's "COBOL lines involved" listed 22 lines, mostly file-status checks of other paragraphs. Rule now: executed lines of the minimal case inside the paragraph(s) that add to a group subtotal or suspense accumulator. Operator check against the real trace: BALANCE-LINE lines 201 to 210 and 218 to 219, including the comparisons at 204 (TABLE-CODE < TXN-BRANCH) and 207 (TABLE-CODE = TXN-BRANCH); no T1 line number in the code; credit-fees card unchanged (293, 303, 319, 332). Certificates of both runs replay VALID. A probe script left at the root was removed.
- Kiro balance (2026-11-16, evening reading): plan 405.95 of 531 used (125.05 left); kiroween2026 397.01 of 4000 used (3602.99 left); trial 0.00 of 500 used.

### R-82 2026-11-16: JUnit export for multi-row cases (task 5)
- Operator review: when the catalog-wide JUnit check was deferred, the T1 JUnit task had been removed from tasks.md; restored (owner requirement). The T1 test generated before asserted a Python dict string that the port can never write.
- Calls p9junit, p9junitb (sonnet). The test writes the minimal case input rows, runs the port and compares the whole output with the COBOL output of the minimal case.
- BUG found by the operator: verify_junit_test returned "passed" for the FAULTY port when called with a relative work directory, because class scanning found 0 tests ("0 tests successful, 0 tests failed"). Fixed: explicit class selection, absolute work directory, three results (passed only with at least one test and no failure; failed only when every failure is an output assertion; error otherwise, including 0 tests found).
- Operator verification with the real JUnit 6.1.3 jar on the T1 test: faulty port failed, correct port passed, with relative and absolute work directories; a class without a test method gives error.
- Kiro balance (2026-11-16, evening reading): plan 405.95 of 531 used (125.05 left); kiroween2026 397.01 of 4000 used (3602.99 left); trial 0.00 of 500 used.

### R-83 2026-11-16: make demo-ebcdic, README Demo section; priority 9 complete
- Calls p9demo, p9demob, p9democ, p9end (sonnet), p9readme (haiku). coroner/demo_ebcdic.py, run by `make demo-ebcdic`: (1) faulty T1 verify, (2) card, (3) exported JUnit test against both ports, (4) certificate replay, (5) correct T1 verify; exit 1 naming the step at the first unexpected result.
- Operator fixes: the verdict blocks printed absolute run paths containing the home directory and omitted lines the CLI prints (now the CLI printing is reused; a test asserts no line contains the home directory); the JUnit console was dumped with color codes, then the assertion lost its data rows (now expected and actual lines are parsed from the JUnit output); the parser test typed the JUnit text by hand (now fed by a real run and compared with the run's minimal case files).
- Operator run (2026-11-16): exit 0, "Demo: all 5 steps behaved as expected"; ZOMBIE on 262 cases; exposure sum 666358.16, max 666357.81, 2 branches affected, grand total matches: yes; card GEN-001595 (9ZZ in COBOL, SUSP in Java); JUnit faulty failed (1 found, 1 failed), correct passed (1 found, 1 successful); certificate VALID; correct port ALIVE on 2000 cases with exposure sum 0.00 and grand total matches: yes. Every line of the README excerpt was checked against this output.
- Owner requirement: at 200 cases (seed 42) the faulty T1 port is asserted from the run's own files (ZOMBIE, at least one divergent case, grand total matches true) and from the real CLI output ("ZOMBIE:" line, "grand total matches: yes"); operator run at 200 cases: ZOMBIE on 33 cases, exposure sum 387134.97, max 387133.36, 2 branches affected, grand total matches: yes. Kiro's first version printed the verdict line inside the test and checked its own output; replaced by the CLI subprocess check.
- Demo fast tests run the demo at 200 cases with one shared real run per module (38.74 s for tests/test_demo_ebcdic.py); the slow test runs `make demo-ebcdic` at 2000 cases.
- Tests (operator): default suite 236 passed, 47 deselected in 310.48 s (machine shared with a parallel Kiro session; 182.37 s on a quieter run before the demo test speed-up); slow demo test 1 passed in 71.51 s; make acceptance 47 passed in 671.95 s; make zombie 86; generator hash tests 3 passed.
- Priority 9 (EBCDIC/control-break demo with branch exposure): done. Deferred to hardening: catalog-wide JUnit verification (task 11), suite duration.
- The pre-commit guard blocked this commit: tests/test_demo_ebcdic.py contained the literal home path prefix used by its own absolute-path heuristic. Fixed (call guardfix, sonnet): the check now uses Path.home(), the pattern "Run: /" and os.path.isabs on run-path tokens, with no home prefix in the file.
- Kiro balance (2026-11-16, evening reading): plan 405.95 of 531 used (125.05 left); kiroween2026 397.01 of 4000 used (3602.99 left); trial 0.00 of 500 used.

### R-84 2026-11-16: catalog tests no longer overwrite the real Detection Matrix
- Found by the operator on the UI: the Detection Matrix page showed 200-case numbers (T1 33 of 200) because tests/test_catalog_runner.py called run_catalog without a base directory, so every default pytest run overwrote runs/trap_catalog.json and .txt (the committed README numbers were not affected). Same class of fault as the MCP tests fixed in R-75.
- Call catfix (sonnet): every run_catalog call in tests/ passes a pytest tmp_path; a new test records the SHA-256 and mtime of runs/trap_catalog.json before a catalog run in tmp_path and asserts both unchanged.
- Operator check: SHA-256 of runs/trap_catalog.json identical before and after `pytest tests/test_catalog_runner.py`; the real catalog is regenerated with `make traps` (2000 cases, seed 42) after tonight's commits.
- Kiro balance (2026-11-16, evening reading): plan 405.95 of 531 used (125.05 left); kiroween2026 397.01 of 4000 used (3602.99 left); trial 0.00 of 500 used.
