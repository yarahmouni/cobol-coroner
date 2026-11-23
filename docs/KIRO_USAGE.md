# How Kiro was used to build COBOL Coroner

This file is for the hackathon judges. Every statement points to a file in this repository. Where a number appears, it is quoted from the file named next to it.

## Answers to the judges' topics

Kiro wrote the code, specs, designs, tasks and tests. The operator (Claude Code) wrote the prompts, checked every result on real runs, sent back what was wrong and kept the review log. Section 1 lists the exceptions where the operator edited files directly.

**1. Kiro IDE and Kiro CLI.** All build work went through kiro-cli, driven with the custom agent `coroner-builder` ([section 1](#1-how-the-work-was-split)). The Kiro IDE 1.4.178 ran only the coroner-audit power, on Windows 10, because the IDE does not run on the project Mac (macOS 12.7.6) ([section 8](#8-kiro-powers)). The two products read hooks differently: kiro-cli takes hooks declared inside the agent JSON ([section 4](#4-hooks-and-the-gate)), while the IDE takes standalone files in `.kiro/hooks/` (v1 format), which have not been run in the IDE. The power installed with kiro-cli, but its MCP server never appeared in a CLI session; it worked in the IDE. Evidence: [`docs/evidence/kiro-power-run.md`](evidence/kiro-power-run.md).

**2. Custom agents.** `coroner-builder` is configured outside the repository. The review log header records its limits: file writes auto-approved inside this workspace only, a shell limited to an allowlist, and `rm`, `git`, `sudo`, `brew`, `curl` and `wget` denied ([section 1](#1-how-the-work-was-split)). `coroner-auditor` is in the repository and audits Java ports with the Coroner tools ([section 5](#5-mcp-and-the-coroner-auditor-agent)). Its first run had no tools list, so the model printed an invented verdict, "Branch coverage (Coroner definition): 42/70". After the tools list was added, the second run made real `@coroner` calls and reported 41/70 on 200 cases. Evidence: [run 1](evidence/kiro-mcp-auditor-run1.txt) and [run 2](evidence/kiro-mcp-auditor-run2.txt).

**3. Hooks.** The `preToolUse` gate runs before shell commands and acts only on `git commit`, `git push` and `git merge`; it blocks unless the scope certificate replays as ALIVE ([section 4](#4-hooks-and-the-gate)). The stop hook was measured on two engines. It re-prompts the agent, but it does not keep the agent working until ALIVE: engine v2 continued without delivering the reason, and v3 delivered it and blocked once per turn. The Git pre-commit hook blocks a ZOMBIE commit; a real commit of the HALF_EVEN port was refused with 21 divergent cases on 500. The repository holds five standalone IDE hook files in `.kiro/hooks/`, which were not run in the IDE. Evidence: [`kiro-hooks-verification.md`](evidence/kiro-hooks-verification.md) and [`git-precommit-block-then-allow.md`](evidence/git-precommit-block-then-allow.md).

**4. Specs versus prompts.** `.kiro/specs/` holds 16 folders, and each has `requirements.md`, `design.md` and `tasks.md` ([section 2](#2-specs)). Not all work was driven by a spec. The static fallback page (R-168), the video scripts `scripts/record_demo.py` and `scripts/make_srt.py` (R-111, R-160) and the README edits (R-159, R-179, R-182) have no spec folder; each was a single prompt recorded as a call in the review log. The ports under audit in `samples/independence/` were written from a prompt alone, on purpose: the fresh Kiro session ran in a worktree with the repository's docs, Java ports and trap files removed, while session 1 could read the whole repository ([section 6](#6-kiro-as-the-migration-tool-under-audit)). R-121 records that the first CardDemo spec drafts asked for hand-computed expected values and would have overwritten the probe driver, so they were sent back.

**5. Steering strategy.** The seven steering files in `.kiro/steering/` are all `inclusion: always` ([section 3](#3-steering-and-skills)). Two rules came from failures. After R-31, a Kiro call wrote `parity-expected.csv` by hand, and `quality.md` gained the rule "Reference outputs come only from executing the COBOL program" ([section 1](#1-how-the-work-was-split)). After auditor run 1 printed an invented verdict, the agent prompt and the three skills gained the rule to report only values a Coroner tool returned in the session ([section 3](#3-steering-and-skills), [section 5](#5-mcp-and-the-coroner-auditor-agent)).

**6. MCP.** `coroner/mcp/server.py` is the MCP server `coroner`, with seven tools: `run_differential_check`, `get_verdict`, `get_failure_report`, `get_detection_matrix`, `export_junit_test`, `generate_certificate` and `verify_certificate` ([section 5](#5-mcp-and-the-coroner-auditor-agent)). The `coroner-auditor` agent calls them through `@coroner` in the repository. The coroner-audit power exposes the same tools in the Kiro IDE, where its server started from the published image ([section 8](#8-kiro-powers)).

**7. Property-based testing.** The generator is seeded: it draws only with `random.Random(seed).random()`, so the same seed gives the same cases, and golden SHA-256 values fix two credit-fees seeds ([section 9](#9-property-based-testing)). The engine checks that every output field matches exactly, with no tolerance, and reports whether the Case 1 grand total matches. Four Hypothesis tests in `tests/test_compare.py` cover the normalizer. Three jqwik properties in `MatchMergeProperties.java` run the two Case 1 Java ports through `make pbt`, and they assert that branch subtotals plus suspense equal the grand total. The section also states a limit: an audit does not generate deliberate boundary values.

**8. Powers.** The power `coroner-audit` is in [`powers/coroner-audit/`](../powers/coroner-audit/) ([section 8](#8-kiro-powers)). On 2026-11-21, the Kiro IDE 1.4.178 on Windows 10 x64 installed it, and Kiro called `run_differential_check`, `get_verdict`, `get_failure_report` and `verify_certificate` on Case 1. The run was `f584d5f35228`, ZOMBIE on 682 of 2000 cases, and the certificate verified as valid. The same power did not appear in a kiro-cli session ([section 1](#1-how-the-work-was-split)). Evidence: [`docs/evidence/kiro-power-run.md`](evidence/kiro-power-run.md).

## 1. How the work was split

Source: [`docs/reviews.md`](reviews.md), header and entries R-01 to R-185.

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
| [`case-6-cursed-modulo`](../.kiro/specs/case-6-cursed-modulo/requirements.md) | Case 6, The Cursed Modulo: `FUNCTION MOD` of a negative day offset in COBOL against Java `%`, turning the reserved sixth slot of the trap catalog into a measured case. |

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

Kiro IDE hook files, in the standalone v1 format of `.kiro/hooks/` (one hook per file). They were not run in the Kiro IDE on this Mac (the IDE does not run on macOS 12), so their behaviour inside the IDE is not measured. Only the files (`tests/test_kiro_hooks_files.py`) and the commands they call are tested:

- [`coroner-commit-gate.json`](../.kiro/hooks/coroner-commit-gate.json): PreToolUse on shell commands, runs the same `gate` command as the agent configuration above.
- [`coroner-stop-check.json`](../.kiro/hooks/coroner-stop-check.json): Stop, runs the same `stop` command (measured 9.9 s on the first run, 3.7 s on the second).
- [`fast-tests-on-save.json`](../.kiro/hooks/fast-tests-on-save.json): after a Python file under `coroner/` or `tests/` is saved, runs the matching test file or a fixed set of fast ones (`scripts/kiro_hook_fast_tests.py`), cut after 25 s.
- [`public-repo-check.json`](../.kiro/hooks/public-repo-check.json): before a `git commit`, blocks a staged diff with an added em dash or en dash, a home path, or an unlisted root or scripts file (`scripts/kiro_hook_public_repo.py`, which reuses `scripts/precommit_guard.py`).
- [`trap-catalog-refresh.json`](../.kiro/hooks/trap-catalog-refresh.json): after a trap sample under `samples/traps/` is saved, asks the agent to run `make traps` and report the figures it reads in `runs/trap_catalog.txt`.

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
| Kiro agent, session 1 (rules in prompt, full repository readable) | Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5) | ZOMBIE | 682 of 2000 | a4709d638df5 | 3f2b2d38933c | sum 3995184.38, max 2025606.03, 2 branches | no |
| Kiro agent, fresh isolated session | Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5), fresh session | ALIVE | 0 of 2000 | 7af943198226 | 37fc82b6d5d6 | sum 0.00 | no |

Notes, from [`samples/independence/README.md`](../samples/independence/README.md), the `SOURCE.md` file of each port and R-112, R-118:

- The Kiro session 1 port has the same count and exposure as the faulty demo port (682 of 2000, 3995184.38) but is a different file (SHA-256 3f2b2d38... against 8d9bb18a...). Both use `String.compareTo` instead of the EBCDIC order, and both audits use the same generated cases.
- The fresh isolated session ran in a worktree with every tracked `.java` file, `docs/`, `README.md`, `.kiro/`, every `trap.json` and `runs/` removed. The diffs of the inputs it was given are in `samples/independence/ports/kiro-fresh/cobol-input.diff` and `schema-input.diff`. The agent ran no audit. Its prompt and transcript are in `samples/independence/ports/kiro-fresh/`.
- That fresh port formats amounts with `String.format("%+010.2f")`. In the project image its verdict is ALIVE. On the operator's Mac, whose JVM default locale is `fr_FR`, the same port gave ZOMBIE on 2000 of 2000 cases (decimal comma). R-118 records the engine fix: the Java run now uses a fixed locale and the certificate records `java_locale`.
- No port written by hand is included: none was written before the deadline (owner decision Q3, 2026-11-23, recorded in `docs/reviews.md`). The table has three rows.
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
- Latest balance written in the log, R-185 (2026-11-23, the last review entry with a Kiro balance line): "plan 405.95 of 531 used; kiroween2026 3359.42 of 4000 used."
- Models from other vendors were listed by `kiro-cli chat --list-models` on 2026-11-21 (Q4 in the log). No port from them exists.

## 8. Kiro powers

The power `coroner-audit` is in [`powers/coroner-audit/`](../powers/coroner-audit/). It works in the Kiro IDE 1.4.178 on Windows 10 x64. On 2026-11-21 Kiro installed it from the Powers panel, its MCP server started from the published image pinned by digest, and Kiro called `run_differential_check`, `get_verdict`, `get_failure_report` and `verify_certificate` on Case 1 (run `f584d5f35228`, ZOMBIE on 682 of 2000 cases; `verify_certificate` returned valid). The evidence is in [`docs/evidence/kiro-power-run.md`](evidence/kiro-power-run.md). Kiro adapted the power files in the IDE. The example values in `POWER.md` were later replaced with values measured through the same image.

The Kiro IDE could not be installed on the project Mac (macOS 12.7.6). Homebrew refuses the current cask ("does not run on macOS versions older than Ventura"), and the oldest official IDE build still offered on the Kiro downloads page (1.2.56) shows "requires macOS 13.0 or later". With kiro-cli 3.5.0 the power installed, but its MCP server never appeared in a session. All other Kiro work was done through kiro-cli 3.5.0.

## 9. Property-based testing

What is true in the code, with the file for each statement.

**The generator is seeded.** [`coroner/gen/__init__.py`](../coroner/gen/__init__.py) builds every case from `random.Random(seed)` and uses `random()` only (D-30 in `docs/decisions.md`, rule in `.kiro/steering/quality.md`). The same seed gives the same cases: `tests/test_gen.py::test_generate_cases_deterministic` and the golden SHA-256 values of credit-fees seeds 42 and 123 in `tests/test_gen_regression.py`, keyed by `GENERATOR_VERSION`. What it generates:

- numeric values drawn by magnitude (the number of integer digits first, then the digits), so small and large values both appear;
- for schemas with `PRINCIPAL` and `FEE-RATE` (credit-fees) or the `product_pairs` strategy (Case 2), rounding ties: `tie_share` of the cases, 6 % by default, two thirds with an even preceding digit (they diverge under HALF_EVEN) and one third with an odd digit as control;
- string values from the schema `domain`, with optional `domain_weights` (Case 1 branch codes);
- batches of 5 to 25 rows per CASE-ID for schemas with `case_rows` (Case 1);
- special formats on request: packed hex, zoned overpunch, dirty numeric text.

It does not generate deliberate boundary values in an audit. `generate_limits`, `generate_boundaries` and `generate_string_values` exist in the module, but `generate_cases` does not call them, and no test calls them.

**Property 1, on every generated case.** The Java output equals the COBOL output, field by field, with no tolerance, and the exit status is the same (`.kiro/steering/comparison-rules.md`, D-09, D-31). Normalization only pads a value to the schema scale and trims trailing spaces; a value with extra non-zero decimals is divergent, never rounded (`coroner/compare/__init__.py`).

**Property 2, Case 1 (control-break batches).** For one batch, the branch subtotals plus the suspense line equal the grand total. The faulty port keeps this property while it moves the amounts of branches 001 and 9ZZ to suspense. That is why a total-only reconciliation does not see Case 1. Coroner compares every output row, the TOTAL row included, and reports `grand_total_matches` (`compute_exposure` in `coroner/compare/__init__.py`); it does not assert the conservation law itself at run time. The jqwik test below asserts it on the two Java ports. It does not run the COBOL program and asserts no COBOL output.

**Hypothesis tests.** Four properties in [`tests/test_compare.py`](../tests/test_compare.py), all on the normalizer:

| Test | Property |
|---|---|
| `test_normalize_decimal_idempotent` | normalizing a decimal with 2 places twice gives the same result |
| `test_normalize_string_idempotent` | normalizing a string twice gives the same result |
| `test_extra_decimals_divergent` | a value with non-zero digits beyond the schema scale is divergent, any other value is not |
| `test_string_trim_trailing_only` | only trailing spaces are trimmed, leading spaces are kept |

[`tests/conftest.py`](../tests/conftest.py) loads a profile with `derandomize=True` and no example database, so the tests are reproducible. Hypothesis never generates certificate cases (D-30).

**jqwik test on the Java side.** [`samples/traps/T1-ebcdic-match-merge/java/property/MatchMergeProperties.java`](../samples/traps/T1-ebcdic-match-merge/java/property/MatchMergeProperties.java), run by `make pbt` with jqwik 1.10.2 on the JUnit Platform console launcher (jars downloaded and SHA-256 checked by `scripts/download_junit.py`). It runs the compiled faulty and correct `MatchMerge` classes as they are used by the engine (file in, file out, one JVM per batch). Batches have 1 to 25 transactions, amounts at scale 2 from -9999.99 to 9999.99, and branch codes from the schema domain plus random 3-character codes. 30 tries per property, seed 42.

| Property | What it states |
|---|---|
| `correctPortConservesTheTotal` | correct port: subtotals plus suspense equal the grand total, and the grand total equals the sum of the input amounts |
| `totalIsConservedEvenByTheFaultyPort` | the same law holds for the faulty port |
| `faultyPortPostsBranch001ToSuspense` | for a batch with a transaction for branch 001, the correct port posts the 001 amount to branch 001 and the faulty port to suspense (9ZZ the same way); this compares the two ports with each other and states what the faulty code does, not an expected business output |

The pytest test [`tests/test_property_t1.py`](../tests/test_property_t1.py) runs `make pbt` and checks that the three properties passed (slow marker).
