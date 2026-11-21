# How Kiro was used to build COBOL Coroner

This file is for the hackathon judges. Every statement points to a file in this repository. Where a number appears, it is quoted from the file named next to it.

## 1. How the work was split

Source: [`docs/reviews.md`](reviews.md), header and entries R-01 to R-126.

- A Kiro agent wrote the code, specs, designs, tasks and tests. The review log says: "Kiro writes all code, specs, designs and tasks; fixes are sent back to Kiro until clean." The agent was driven with `kiro-cli chat --no-interactive --agent coroner-builder`. The configuration of `coroner-builder` is outside the repository (reviews.md, header). The only agent configuration in the repository is [`.kiro/agents/coroner-auditor.json`](../.kiro/agents/coroner-auditor.json) (section 5).
- An operator wrote the prompts, ran every result on real runs (real COBOL compiler, real Java, real Git, real containers), kept `docs/reviews.md` and made the commits. The project owner validated each decision, which is logged in [`docs/decisions.md`](decisions.md).
- Exceptions where the operator edited files directly are recorded in the log: R-06 (privacy cleanup, owner exception) and R-23 (text-only part of the project rename while the Kiro credits were used up). R-21 records that a SHA-256 written by Kiro in the Dockerfile was invented, because its download had failed, and that the operator replaced it with a computed value.
- The operator sent work back whenever a result was wrong. Three examples from the log:
  - R-51 (JUnit export): the key end-to-end test had been hard-skipped with the false reason "tested manually". The operator found the cause: the generated test started the program with a hard-coded classpath. After the fix the test ran, and failed against the faulty classes and passed against the correct ones.
  - R-31 (Java port of credit-fees): after its commands were refused, one Kiro call wrote `parity-expected.csv` by hand and reported guessed results. The file was regenerated from the COBOL program. The rule that followed is in [`.kiro/steering/quality.md`](../.kiro/steering/quality.md): "Reference outputs come only from executing the COBOL program."
  - R-121 (CardDemo spec): the first spec drafts "asked for hand-computed expected values, told the porting agent how to round", would have overwritten the probe driver, and carried state between cases. Each was sent back with the code facts. The same entry records that one call "claimed results it had not run".
- Prompts and transcripts kept in the repository: [`docs/evidence/carddemo-cbact04c-port/`](evidence/carddemo-cbact04c-port/) and `samples/independence/ports/*/prompt.txt` (section 6). Other calls are described only in the review entries.
- Kiro Crew was removed from the plan (D-22 in `docs/decisions.md`).

## 2. Specs

Folder `.kiro/specs/`. Each folder has `requirements.md`, `design.md` and `tasks.md`. Lines below summarize the first lines of each `requirements.md`.

| Folder | What it covers |
|---|---|
| [`s0-toolchain`](../.kiro/specs/s0-toolchain/requirements.md) | GnuCOBOL 3.2 trace, Docker image with GnuCOBOL and JDK 17, a local MCP server that Kiro discovers. |
| [`cobol-sample`](../.kiro/specs/cobol-sample/requirements.md) | The synthetic COBOL program `credit-fees` (fees and eligibility). |
| [`java-credit-fees`](../.kiro/specs/java-credit-fees/requirements.md) | The Java 17 version of `credit-fees`, which must give byte-identical output to the COBOL program. |
| [`engine`](../.kiro/specs/engine/requirements.md) | The differential engine: generate cases, run both programs, compare with no numeric tolerance, return ALIVE or ZOMBIE. |
| [`certificate`](../.kiro/specs/certificate/requirements.md) | The Coroner Certificate, a reproducible run record that can be replayed offline. |
| [`precommit-fast`](../.kiro/specs/precommit-fast/requirements.md) | A Git pre-commit hook that runs a fast differential check and blocks ZOMBIE commits. |
| [`mcp-agent`](../.kiro/specs/mcp-agent/requirements.md) | The MCP server with 7 tools, the `coroner-auditor` agent and 3 skills. |
| [`kiro-hooks`](../.kiro/specs/kiro-hooks/requirements.md) | The Kiro delivery gate (preToolUse) and stop hook, based on the measured hook behavior. |
| [`fault-catalog`](../.kiro/specs/fault-catalog/requirements.md) | The catalog of six banking migration traps, each with a COBOL program, a faulty Java port and a correct one. |
| [`ebcdic-demo`](../.kiro/specs/ebcdic-demo/requirements.md) | The demo of trap T1 (EBCDIC against ASCII sort order) with branch exposure, minimal case, JUnit export and certificate replay. |
| [`web-ui`](../.kiro/specs/web-ui/requirements.md) | The web interface (FastAPI, Jinja2, htmx). R-94 records that its tasks 12 to 21 also cover the deployment and the test book. |
| [`coroner-gate`](../.kiro/specs/coroner-gate/requirements.md) | `coroner gate`, a CI gate, with a GitHub Actions workflow and an example Jenkinsfile. |
| [`screenshots`](../.kiro/specs/screenshots/requirements.md) | README screenshots and demo GIF generated from real runs (D-58). |
| [`guided-story`](../.kiro/specs/guided-story/requirements.md) | A guided story of 8 steps on the home page, built on the T1 trap. |
| [`carddemo-cbact04c`](../.kiro/specs/carddemo-cbact04c/requirements.md) | The audit of a Kiro-made Java port of one interest-calculation path of the open-source CardDemo sample. |

## 3. Steering and skills

All seven steering files in [`.kiro/steering/`](../.kiro/steering/) have the front matter `inclusion: always`.

| File | What it tells the agent |
|---|---|
| [`product.md`](../.kiro/steering/product.md) | Coroner verifies a migration and never converts code. The verdict is deterministic and never depends on an AI model. Text, comments and docs are in English. |
| [`quality.md`](../.kiro/steering/quality.md) | Shortest readable code, no helper scripts left behind, business logic in `coroner/` modules only, fixed seeds, tests for every module, property-based tests reserved for the normalizer and comparator, reference outputs only from running the COBOL program. |
| [`public-repo.md`](../.kiro/steering/public-repo.md) | No private names or personal data in any file; other hackathon projects are never named. |
| [`no-formal-proof.md`](../.kiro/steering/no-formal-proof.md) | Wording limits: never "proven equivalent", "formal proof" or "guaranteed"; the exact ALIVE and ZOMBIE sentences. |
| [`cobol-semantics.md`](../.kiro/steering/cobol-semantics.md) | Coding rules for the COBOL sample, COBOL `ROUNDED` maps to `HALF_UP`, truncation maps to `DOWN`, `BigDecimal` only, return code maps to the Java exit code. |
| [`comparison-rules.md`](../.kiro/steering/comparison-rules.md) | No numeric tolerance, exact comparison after normalization, columns matched by name, exact exit status compared. |
| [`scope-v1.md`](../.kiro/steering/scope-v1.md) | What is in scope and what is out of scope. |

Skills in [`.kiro/skills/`](../.kiro/skills/), loaded by the `coroner-auditor` agent through `skill://.kiro/skills/*/SKILL.md`:

| Skill | What it tells the agent |
|---|---|
| [`banking-trap-recognition`](../.kiro/skills/banking-trap-recognition/SKILL.md) | How to recognize the six trap patterns in COBOL and in a Java port, then audit with the Coroner tools. |
| [`cobol-semantics-safety`](../.kiro/skills/cobol-semantics-safety/SKILL.md) | The COBOL rules a Java port must keep: rounding, `BigDecimal` scale, sign output, EBCDIC collating sequence. |
| [`coroner-audit-workflow`](../.kiro/skills/coroner-audit-workflow/SKILL.md) | The six-step workflow from `run_differential_check` to certificate verification. |

The three skill files and the agent prompt share one rule: report a verdict, a count or a coverage value only if a Coroner tool returned it in the session. That rule was added after run 1 in section 5.

## 4. Hooks and the gate

What `coroner/hooks.py` is: a module with three commands, `gate`, `stop` and `precommit` (`python -m coroner.hooks <command>`). It installs nothing by itself. The wiring is in two files:

- [`.kiro/agents/coroner-auditor.json`](../.kiro/agents/coroner-auditor.json): a `preToolUse` hook for the tools `shell` and `execute_bash` running `.venv/bin/python -m coroner.hooks gate`, and a `stop` hook running `.venv/bin/python -m coroner.hooks stop`.
- [`.githooks/pre-commit`](../.githooks/pre-commit): runs `scripts/precommit_guard.py`, then `python -m coroner.hooks precommit`. Git uses it when `core.hooksPath` is set to `.githooks` (the setting appears in [`docs/evidence/git-precommit-block-then-allow.md`](evidence/git-precommit-block-then-allow.md)).

The migration under audit is named in [`.kiro/coroner-scope.json`](../.kiro/coroner-scope.json) (the `credit-fees` COBOL, copybooks, Java and schema paths).

Behavior read from [`coroner/hooks.py`](../coroner/hooks.py):

- `gate` acts only on a command that starts with `git commit`, `git push` or `git merge`. It finds the newest certificate in `runs/` whose recorded file hashes match the files in scope and replays it with `python -m coroner verify <certificate>`. Exit status 0 of the replay allows the command. Any other status blocks it: the gate prints `{"decision":"block","reason":...}` on stdout, the message on stderr, and exits with status 2. With no certificate, it blocks only when the scope COBOL or Java file is staged. If the scope file or the certificate lookup fails, it allows the command.
- `stop` blocks at most 3 times per session id, counted in a file under `build/hooks/`, then writes a failure file and allows.
- `precommit` exports the staged version of the scope files, runs `coroner verify` with 500 cases and seed 42, and exits 1 on ZOMBIE or when the reference did not run.

What the evidence shows:

- [`docs/evidence/kiro-hooks-verification.md`](evidence/kiro-hooks-verification.md): kiro-cli 3.3.0, model claude-sonnet-4.5, non-interactive, engines v2 and v3, with 13 raw transcripts. Only a stdout `{"decision":"block","reason":...}` plus exit status 2 blocked a shell command on both engines. Exit status 2 alone blocked on v2 and not on v3. A stop hook did not keep the agent working until ALIVE on either engine: v2 continued but did not deliver the reason, v3 delivered the reason but blocked once per turn. No `PostTaskExec` event exists in this version. The file concludes: "Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed."
- [`docs/evidence/kiro-gate-block-then-allow.md`](evidence/kiro-gate-block-then-allow.md): kiro-cli 3.3.0, agent `coroner-auditor`, claude-sonnet-4.5, v2 engine, in a scratch clone. The staged HALF_EVEN port was ZOMBIE (run 227fcf67095d, 86 divergences on 2,000 cases). The commit was blocked by the gate. The agent read the verdict and failure report through MCP, changed `HALF_EVEN` to `HALF_UP`, ran `run_differential_check` (ALIVE on 2,000 cases, run a26c32ac9519), and the retried commit was allowed. The file records a finding: the block reason did not reach the agent because the gate wrote it only on stdout. The gate now also writes it on stderr.
- [`docs/evidence/git-precommit-block-then-allow.md`](evidence/git-precommit-block-then-allow.md): a real `git commit` of the staged HALF_EVEN port printed "Commit blocked by Coroner: ZOMBIE: FAIL: business behavior diverged on 21 cases" and exited 1 while the working tree held the correct Java. The corrected port was committed with "Coroner pre-commit: ALIVE: PASS: business behavior preserved on 500 cases (Duration: 3.3 s)".

## 5. MCP and the `coroner-auditor` agent

Server: [`coroner/mcp/server.py`](../coroner/mcp/server.py), an `MCPServer` named `coroner`, started by [`.kiro/settings/mcp.json`](../.kiro/settings/mcp.json) with `.venv/bin/python -m coroner.mcp`. Seven tools:

| Tool | Arguments |
|---|---|
| `run_differential_check` | `cobol`, `copybooks`, `java`, `schema`, `cases` (default 2000, allowed 1 to 10000), `seed` (default 42, not negative). Paths must be inside the repository. Returns `run_id`, `status`, `sub_label`, `cases_total`, `cases_divergent`, `paragraph_coverage`, `branch_coverage`, `certificate_path`. |
| `get_verdict` | `run_id` (12 lowercase hex characters) |
| `get_failure_report` | `run_id` |
| `get_detection_matrix` | `trap_id` (optional) |
| `export_junit_test` | `run_id` |
| `generate_certificate` | `run_id` |
| `verify_certificate` | `path` (inside the repository) |

Agent: [`.kiro/agents/coroner-auditor.json`](../.kiro/agents/coroner-auditor.json). Tools `read`, `shell` and `@coroner`. Resources: all steering files and the three skills. Its prompt limits claims to "what Coroner outputs".

Two recorded runs, both kiro-cli 3.3.0, claude-sonnet-4.5, non-interactive:

- [`docs/evidence/kiro-mcp-auditor-run1.txt`](evidence/kiro-mcp-auditor-run1.txt) is recorded as a failure. The agent configuration had no `tools` list. The model wrote tool-call markup that does not correspond to a real call (no `[tool]` line in the transcript) and printed an invented verdict, "Branch coverage (Coroner definition): 42/70".
- [`docs/evidence/kiro-mcp-auditor-run2.txt`](evidence/kiro-mcp-auditor-run2.txt) after the fix: `[tool]` lines for `@coroner/run_differential_check`, `@coroner/get_verdict` and `@coroner/verify_certificate`. It reports ALIVE on 200 cases, 0 divergent, "Branch coverage (Coroner definition): 41/70", and the certificate of run 3b0794fc91da as valid. R-59 records that these values equal the measured 200-case run.

## 6. Kiro as the migration tool under audit

Coroner does not translate COBOL. It audits a Java port from any source. Two experiments use Kiro as the source.

### Independence table

[`samples/independence/TABLE.md`](../samples/independence/TABLE.md), produced by `samples/independence/run_table.py`. All ports are ports of `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`, audited with 2,000 cases and seed 42. Environment: image `coroner-local:latest` (linux/amd64). Rows as in the file:

| Port | Source | Verdict | Divergent cases | Run ID | Java SHA-256 | Branch exposure | Same file as a repository Java port? |
|------|--------|---------|-----------------|--------|--------------|-----------------|--------------------------------------|
| Claude Opus 5.5 | Claude Opus 5.5 (Anthropic), run as a Claude Code subagent; not a Kiro agent. | ALIVE | 0 of 2000 | 0d1e698359fb | be82c6bdcd5d | sum 0.00 | no |
| hand-written by the author: pending | pending | pending | pending | pending | pending | pending | pending |
| Kiro agent, session 1 (rules in prompt, full repository readable) | Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5) | ZOMBIE | 682 of 2000 | a4709d638df5 | 3f2b2d38933c | sum 3995184.38, max 2025606.03, 2 branches | no |
| Kiro agent, fresh isolated session | Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5), fresh session | ALIVE | 0 of 2000 | 7af943198226 | 37fc82b6d5d6 | sum 0.00 | no |

Notes, from [`samples/independence/README.md`](../samples/independence/README.md), the `SOURCE.md` file of each port and R-112, R-118:

- The Kiro session 1 port has the same count and exposure as the faulty demo port (682 of 2000, 3995184.38) but is a different file (SHA-256 3f2b2d38... against 8d9bb18a...). Both use `String.compareTo` instead of the EBCDIC order, and both audits use the same generated cases.
- The fresh isolated session ran in a worktree with every tracked `.java` file, `docs/`, `README.md`, `.kiro/`, every `trap.json` and `runs/` removed. The diffs of the inputs it was given are in `samples/independence/ports/kiro-fresh/cobol-input.diff` and `schema-input.diff`. The agent ran no audit. Its prompt and transcript are in `samples/independence/ports/kiro-fresh/`.
- That fresh port formats amounts with `String.format("%+010.2f")`. In the project image its verdict is ALIVE. On the operator's Mac, whose JVM default locale is `fr_FR`, the same port gave ZOMBIE on 2000 of 2000 cases (decimal comma). R-118 records the engine fix: the Java run now uses a fixed locale and the certificate records `java_locale`.
- The hand-written row stays "pending". [`samples/independence/ports/hand-written/README.md`](../samples/independence/ports/hand-written/README.md) says only a person writes it and that the row is removed if it has not arrived by 2026-11-26 (also Q3 in `docs/reviews.md`).
- Limits stated in the README: one program, one seed, 2,000 cases; the Claude Opus 5.5 subagent comes from the same vendor as Kiro's default model; the verdicts are not a comparison of models.

### CardDemo CBACT04C, port by an isolated Kiro session

Evidence: [`docs/evidence/carddemo-cbact04c-port/README.md`](evidence/carddemo-cbact04c-port/README.md). The port [`samples/carddemo-cbact04c/java/Cbact04c.java`](../samples/carddemo-cbact04c/java/Cbact04c.java) was written by a Kiro agent (kiro-cli 3.5.0, agent `coroner-builder`, model claude-sonnet-5.5) in one fresh session on 2026-11-21 and committed as written (SHA-256 e16d5d6ce285efb81eafb532a8803a9fda6c43214e1d1ecfc26178c39eda08ea). The session ran in a worktree where every tracked file, including `.kiro/`, `docs/`, `README.md` and `samples/`, had been deleted. Its inputs were the adapted COBOL programs, the upstream copybooks, `schema.json` and one example row with its COBOL output. `inputs.sha256` lists their hashes and `sandbox-files-after-port.txt` lists the files after the session. Files in the folder: `prompt.txt`, `transcript.txt`, `inputs.sha256`, `sandbox-files-after-port.txt`, `audit-200-seed42-image.txt`.

Audit result, from [`audit-200-seed42-image.txt`](evidence/carddemo-cbact04c-port/audit-200-seed42-image.txt) (200 cases, seed 42, in the project image): "ALIVE: PASS: business behavior preserved on 200 cases", run `a5edaf1924a5`, exit 0. R-126 adds that the certificate replays VALID and that the coverage lines (paragraphs 34/34, branches 66/99) measure the harness program the engine compiles, not CBACT04C alone.

Wording: no behavioral difference across the tested scenarios; not a certification for all inputs. Coroner audits a Kiro-generated Java port of one bounded interest-calculation path in AWS's open-source CardDemo sample. Uses AWS's open-source CardDemo sample (Apache 2.0). Not affiliated with or endorsed by AWS. The license and notice are in [`samples/carddemo-cbact04c/LICENSE`](../samples/carddemo-cbact04c/LICENSE) and [`NOTICE`](../samples/carddemo-cbact04c/NOTICE).

## 7. Models and credits

From `docs/reviews.md`:

- The review entries name the model of each call. claude-sonnet-4.5 and claude-haiku-4.5 were used until call p320. R-120 records: "from p321 on, claude-sonnet-5.5 (same 1.30x rate as sonnet-4.5) and claude-haiku-5.5 replace the 4.5 versions". The hook and MCP evidence files above name claude-sonnet-4.5; the CardDemo port names claude-sonnet-5.5.
- R-33 records the model policy: Sonnet for anything that runs or verifies a result.
- Plan history: R-21 records the monthly usage limit reached on the earlier plan (50/50 credits). R-25 records the Kiro Pro plan, 531 credits. R-66 records the Kiroween credits redeemed by the owner (4000 credits).
- Latest balance written in the log, R-126 (2026-11-21): "plan 405.95 of 531 used; kiroween2026 1628.73 of 4000 used at the last reading (R-124)."
- Models from other vendors were listed by `kiro-cli chat --list-models` on 2026-11-21 (Q4 in the log). No port from them exists.

## 8. Kiro powers

The power `coroner-audit` is in [`powers/coroner-audit/`](../powers/coroner-audit/). It works in the Kiro IDE 1.4.178 on Windows 10 x64. On 2026-11-21 Kiro installed it from the Powers panel, its MCP server started from the published image pinned by digest, and Kiro called `run_differential_check`, `get_verdict`, `get_failure_report` and `verify_certificate` on Case 1 (run `f584d5f35228`, ZOMBIE on 682 of 2000 cases; `verify_certificate` returned valid). The evidence is in [`docs/evidence/kiro-power-run.md`](evidence/kiro-power-run.md). Kiro adapted the power files in the IDE. The example values in `POWER.md` were later replaced with values measured through the same image.

The Kiro IDE could not be installed on the project Mac (macOS 12.7.6). Homebrew refuses the current cask ("does not run on macOS versions older than Ventura"), and the oldest official IDE build still offered on the Kiro downloads page (1.2.56) shows "requires macOS 13.0 or later". With kiro-cli 3.5.0 the power installed, but its MCP server never appeared in a session. All other Kiro work was done through kiro-cli 3.5.0.
