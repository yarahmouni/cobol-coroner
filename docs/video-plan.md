# Video Plan

## Requirements

**Duration:** Under 3 minutes

**Platform:** YouTube, public

**Music:** No music (no unlicensed music unless a licence file is added to the repository)

**Language:** English

**Checked against the official rules on:** <!-- OPERATOR: date and link of the rules page -->

## Story

Banks ran the old and the new system side by side for months before switching. Coroner brings that practice back, in seconds, for AI-made migrations.

**Parallel run, resurrected.**

**Taglines:**
- "Migrate. Audit. Certify."
- "AI accelerates. Coroner certifies."

**Positioning (verbatim):** AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result.

**Key quote:** "The grand total balances. The branches don't."

**Case study:** The Missing Branch (T1: EBCDIC versus ASCII sort order)

Coroner never translates COBOL.

## Timed Script

Total duration: at most 2:50

| Start | End | Scene | On Screen | Narration | Subtitle |
|-------|-----|-------|-----------|-----------|----------|
| 0:00 | 0:05 | Title card | Logo, "COBOL Coroner" title, "Parallel run, resurrected." subtitle | (silence or minimal ambient sound) | COBOL Coroner<br>Parallel run, resurrected. |
| 0:05 | 0:13 | The problem | Dark background, text: "The Problem: Banks migrating COBOL to Java need proof the business logic survived." | Banks are migrating decades of COBOL to Java. They need proof the business logic survived. | Banks are migrating decades of COBOL to Java. They need proof the business logic survived. |
| 0:13 | 0:23 | Case 1: The bank process | Text slide: "Case 1: The Missing Branch", "Every night, the bank reconciles branch subtotals to catch posting errors before opening." | Here's what can go wrong. Every night, the bank runs a control-break batch to reconcile branch subtotals. | Case 1: The Missing Branch<br>Every night, the bank runs a control-break batch to reconcile branch subtotals. |
| 0:23 | 0:33 | COBOL reference | Terminal or UI showing COBOL run with output rows (branches 001, 9ZZ with subtotals, TOTAL matches) | The COBOL reference posts <!-- MEASURED: number of transactions, from runs/f584d5f35228/generated_cases.csv --> transactions correctly. Branch 001 gets <!-- MEASURED: branch 001 COBOL subtotal, from runs/f584d5f35228/branch_reconciliation.json -->. Branch 9ZZ gets <!-- MEASURED: branch 9ZZ COBOL subtotal, from runs/f584d5f35228/branch_reconciliation.json -->. Grand total: <!-- MEASURED: grand total COBOL, from runs/f584d5f35228/branch_reconciliation.json -->. | COBOL posts transactions correctly. Branch 001, 9ZZ, grand total. |
| 0:33 | 0:46 | Java migration (faulty) | UI showing Java output with same TOTAL but branch amounts posted to SUSP (suspense) | A developer ported this to Java. The grand total still matches. But look at the branches. Java posted <!-- MEASURED: branch 001 Java subtotal (zero), from runs/f584d5f35228/branch_reconciliation.json --> to branch 001, and <!-- MEASURED: suspense Java value, from runs/f584d5f35228/branch_reconciliation.json --> went to suspense. The error is hidden. | Java migration: grand total matches. But branch amounts went to suspense. The error is hidden. |
| 0:46 | 1:01 | Run audit ZOMBIE | UI showing Run audit form filled (T1 faulty, 2000 cases, seed 42), then verdict page: ZOMBIE badge, "<!-- MEASURED: divergent cases count, from runs/f584d5f35228/verdict.json --> of <!-- MEASURED: total cases, from runs/f584d5f35228/verdict.json --> cases diverge", exposure sum and max | Coroner runs both programs on <!-- MEASURED: cases count, from runs/f584d5f35228/verdict.json --> generated test cases. Verdict: ZOMBIE. <!-- MEASURED: divergent cases, from runs/f584d5f35228/verdict.json --> cases diverge. Unreconciled branch exposure: <!-- MEASURED: exposure sum, from runs/f584d5f35228/verdict.json --> across <!-- MEASURED: branches affected, from runs/f584d5f35228/verdict.json --> branches. | Coroner runs both on 2000 cases. ZOMBIE. Branches don't reconcile. |
| 1:01 | 1:16 | Where and why | Branch reconciliation chart showing COBOL vs Java bars, MATCH/MISMATCH labels, then card or failure report with business cause | Where did it break? Branches 001 and 9ZZ. Why? <!-- MEASURED: business_cause from samples/traps/T1-ebcdic-match-merge/trap.json -->. The faulty Java sorted by ASCII. The COBOL sorts by EBCDIC. | Where: branches 001 and 9ZZ. Why: control-break logic processed them in the wrong order. |
| 1:16 | 1:26 | The gate blocks | Terminal or UI showing "This ZOMBIE migration cannot be committed" with gate status from /api/gate-check exit code 1 | The delivery gate blocks the commit. This ZOMBIE migration cannot be promoted. The agent must fix it first. | The delivery gate blocks this ZOMBIE migration. |
| 1:26 | 1:36 | The fix | Text slide or code diff snippet: "The fix: <!-- MEASURED: business_fix from samples/traps/T1-ebcdic-match-merge/trap.json -->", then UI showing correct Java port | The developer applies the fix. <!-- MEASURED: business_fix from samples/traps/T1-ebcdic-match-merge/trap.json -->. Coroner re-runs with the corrected port. | The fix: <!-- MEASURED: business_fix from samples/traps/T1-ebcdic-match-merge/trap.json -->. Coroner re-runs. |
| 1:36 | 1:46 | ALIVE certificate | UI showing ALIVE badge, "business behavior preserved on <!-- MEASURED: cases_total from runs/29c15f04407b/verdict.json --> cases", exposure sum 0.00, certificate panel | Verdict: ALIVE. Business behavior preserved on <!-- MEASURED: cases_total, from runs/29c15f04407b/verdict.json --> cases. Zero divergence. The certificate records the proof. | ALIVE. Zero divergence. Certificate records the proof. |
| 1:46 | 1:56 | Gate allows | Terminal or UI showing "Commit allowed" with gate status from /api/gate-check exit code 0 on the correct run | The gate now allows the commit. The migration is certified. | The gate allows the commit. Migration certified. |
| 1:56 | 2:08 | Tamper proves integrity | UI showing Tamper page, certificate fields edited (cases_divergent changed), Tamper result "Certificate: INVALID, replay mismatch" | Can you fool the certificate? No. Editing any field makes it INVALID. The audit result cannot be faked. | Can you fool it? No. Tampering makes it INVALID. The audit cannot be faked. |
| 2:08 | 2:23 | Kiro's role (after guided story ships) | Screenshots or screen recording: .kiro/specs, .kiro/agents/coroner-auditor.json, .kiro/skills, MCP tools list, evidence transcript showing @coroner/run_differential_check | Kiro built Coroner through spec-driven development. Seven MCP tools. Three skills. The coroner-auditor agent uses them to verify any Java port. | Kiro built Coroner. MCP tools, skills, agent. |
| 2:23 | 2:38 | The full chain | Diagram or animation: Kiro agent ports COBOL, Coroner MCP audits, Stop hook blocks ZOMBIE, Git pre-commit blocks, Jenkins/GitHub Actions gate enforces, certificate verifies | Here's the full chain. Kiro translates. Coroner certifies. Git and Jenkins enforce the verdict. From port to promotion, the migration is audited at every step. | Kiro translates. Coroner certifies. Git and Jenkins enforce the verdict. |
| 2:38 | 2:50 | Closing card | Logo, text: "Try it live: https://coroner.iqoba.com", "Open source: github.com/yarahmouni/cobol-coroner", tagline "AI accelerates. Coroner certifies." | Try it live at coroner dot iqoba dot com. Open source on GitHub. | Try it live: coroner.iqoba.com<br>github.com/yarahmouni/cobol-coroner<br>AI accelerates. Coroner certifies. |

## Narration Sheet for Owner

Scene-by-scene narration with time windows and words per second.

**Target:** Under 2.7 words per second

**Scene 1 (0:05-0:13, 8 seconds):**
Banks are migrating decades of COBOL to Java. They need proof the business logic survived.
(16 words, 2.0 wps)

**Scene 2 (0:13-0:23, 10 seconds):**
Here's what can go wrong. Every night, the bank runs a control-break batch to reconcile branch subtotals.
(17 words, 1.7 wps)

**Scene 3 (0:23-0:33, 10 seconds):**
The COBOL reference posts transactions correctly. Branch 001, branch 9ZZ, grand total.
(12 words, 1.2 wps)

**Scene 4 (0:33-0:46, 13 seconds):**
A developer ported this to Java. The grand total still matches. But look at the branches. Java posted zero to branch 001, and amounts went to suspense. The error is hidden.
(31 words, 2.4 wps)

**Scene 5 (0:46-1:01, 15 seconds):**
Coroner runs both programs on two thousand generated test cases. Verdict: ZOMBIE. Hundreds of cases diverge. Unreconciled branch exposure across two branches.
(24 words, 1.6 wps)

**Scene 6 (1:01-1:16, 15 seconds):**
Where did it break? Branches 001 and 9ZZ. Why? Control-break logic processed them in the wrong order. The faulty Java sorted by ASCII. The COBOL sorts by EBCDIC.
(30 words, 2.0 wps)

**Scene 7 (1:16-1:26, 10 seconds):**
The delivery gate blocks the commit. This ZOMBIE migration cannot be promoted. The agent must fix it first.
(18 words, 1.8 wps)

**Scene 8 (1:26-1:36, 10 seconds):**
The developer applies the fix. Sort in the same order as the mainframe. Coroner re-runs with the corrected port.
(19 words, 1.9 wps)

**Scene 9 (1:36-1:46, 10 seconds):**
Verdict: ALIVE. Business behavior preserved on two thousand cases. Zero divergence. The certificate records the proof.
(16 words, 1.6 wps)

**Scene 10 (1:46-1:56, 10 seconds):**
The gate now allows the commit. The migration is certified.
(10 words, 1.0 wps)

**Scene 11 (1:56-2:08, 12 seconds):**
Can you fool the certificate? No. Editing any field makes it INVALID. The audit result cannot be faked.
(18 words, 1.5 wps)

**Scene 12 (2:08-2:23, 15 seconds, after guided story ships):**
Kiro built Coroner through spec-driven development. Seven MCP tools. Three skills. The coroner-auditor agent uses them to verify any Java port.
(23 words, 1.5 wps)

**Scene 13 (2:23-2:38, 15 seconds):**
Here's the full chain. Kiro translates. Coroner certifies. Git and Jenkins enforce the verdict. From port to promotion, the migration is audited at every step.
(27 words, 1.8 wps)

**Scene 14 (2:38-2:50, 12 seconds):**
Try it live at coroner dot iqoba dot com. Open source on GitHub.
(12 words, 1.0 wps)

## Production

**Recordings:** Automatic by scripts/record_demo.py, written to ~/dev/lazarus-recordings (outside the repository), never into the repository.

**Title card:** Uses project logo once it exists. <!-- OPERATOR: logo path -->

**Subtitles:** Generated as .srt from the script table by scripts/make_srt.py

**Narration track:** Empty track in the draft for the owner to record over

**Format:** 1280x720, 30 fps recommended

## Measured Values Reference

All numbers shown on screen must come from real run files. Use these markers in the script:

- `<!-- MEASURED: number of transactions, from runs/f584d5f35228/generated_cases.csv -->`: Read from the generated_cases.csv line count or inputs.json
- `<!-- MEASURED: branch 001 COBOL subtotal, from runs/f584d5f35228/branch_reconciliation.json -->`: From branch_reconciliation.json, branches array, branch "001", cobol_subtotal
- `<!-- MEASURED: branch 9ZZ COBOL subtotal, from runs/f584d5f35228/branch_reconciliation.json -->`: From branch_reconciliation.json, branches array, branch "9ZZ", cobol_subtotal
- `<!-- MEASURED: grand total COBOL, from runs/f584d5f35228/branch_reconciliation.json -->`: From branch_reconciliation.json, grand_total.cobol
- `<!-- MEASURED: branch 001 Java subtotal (zero), from runs/f584d5f35228/branch_reconciliation.json -->`: From branch_reconciliation.json, branches array, branch "001", java_subtotal
- `<!-- MEASURED: suspense Java value, from runs/f584d5f35228/branch_reconciliation.json -->`: From branch_reconciliation.json, suspense.java
- `<!-- MEASURED: divergent cases count, from runs/f584d5f35228/verdict.json -->`: From verdict.json, cases_divergent
- `<!-- MEASURED: total cases, from runs/f584d5f35228/verdict.json -->`: From verdict.json, cases_total
- `<!-- MEASURED: cases count, from runs/f584d5f35228/verdict.json -->`: From verdict.json, cases_total
- `<!-- MEASURED: divergent cases, from runs/f584d5f35228/verdict.json -->`: From verdict.json, cases_divergent
- `<!-- MEASURED: exposure sum, from runs/f584d5f35228/verdict.json -->`: From verdict.json, unreconciled_exposure.sum
- `<!-- MEASURED: branches affected, from runs/f584d5f35228/verdict.json -->`: From verdict.json, unreconciled_exposure.branches_affected
- `<!-- MEASURED: business_cause from samples/traps/T1-ebcdic-match-merge/trap.json -->`: From samples/traps/T1-ebcdic-match-merge/trap.json, business_cause
- `<!-- MEASURED: business_fix from samples/traps/T1-ebcdic-match-merge/trap.json -->`: From samples/traps/T1-ebcdic-match-merge/trap.json, business_fix
- `<!-- MEASURED: cases_total, from runs/29c15f04407b/verdict.json -->`: From the T1 correct run verdict.json, cases_total
