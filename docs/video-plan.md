# Video Plan

## 1. Requirements

**Duration:** Under 3 minutes (this plan: 2:55, last shot ends at 2:55)

**Platform:** YouTube only, public

**Music:** No music. No third-party trademarks or copyrighted music without permission (rules); the cut has no audio stream and no logo (operator check of every 2nd second, 2026-11-23).

**Language:** English

**Checked against the official rules on:** 2026-11-23 (the owner read the official rules page, updated 2026-11-16)

## 2. Story and positioning

Banks ran the old and the new system side by side for months before switching. Coroner brings that practice back for migrations, in seconds, whoever wrote the Java.

**Positioning (verbatim):** Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result.

Shot 2 card to be recorded again after this change (2026-11-23).

**Tagline:** "AI accelerates. Coroner certifies."

**Key quote:** "The grand total balances. The branches don't." (Both values are true for the measured Case 1 run: the grand total matches, and 2 branches do not reconcile.)

**Case:** "Case 1: The Missing Branch" (samples/traps/cases.json, trap T1: EBCDIC versus ASCII collating order in a control-break batch).

**Video shape:** the first cut has subtitles and no voice. The finished cut has the owner's voice over the same pictures. Every number on screen comes from a run file or from the cited source in section 3.

## 3. Shot list

Shots 1 to 18 run in order. "Live page" means a real page of the local stack at http://127.0.0.1:8000, recorded in the browser. Text cards are simple HTML pages that the recording script renders; their exact text is in section 3.1. The first cut burns in the Subtitle column, inside a black band of 120 px at the bottom of the frame, on live-page and still-image shots only. Text-card shots get no burned subtitle, because the card already shows the same words. For the finished cut, the .srt for YouTube captions is built from the Voice-over column.

Local stack for every live page: `docker compose -f docker-compose.yml -f docker-compose.build.yml up --build`, then wait for the log line `Bundled demo runs generated.` from coroner-init.

| Shot | Start | End | Duration | Source of the picture | Subtitle (first cut) | Voice-over (finished cut) | Source of the numbers |
|---|---|---|---|---|---|---|---|
| 1 | 0:00 | 0:04 | 4 s | Text card: title card (section 3.1, card 1). No logo: none exists in the repository. | COBOL Coroner. Parallel run, resurrected. | COBOL Coroner. Parallel run, resurrected. | None (no number). |
| 2 | 0:04 | 0:19 | 15 s | Text card: problem and positioning (section 3.1, card 2). | Banks migrating COBOL to Java need proof the business logic survived. Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result. | Banks migrating COBOL to Java need proof the business logic survived. Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result. | None (no number). Wording from section 2. |
| 3 | 0:19 | 0:27 | 8 s | Live page: http://127.0.0.1:8000/story/step/1?view=business. Action: open the page and wait 1 s. No scroll. | Case 1: The Missing Branch. Every night the bank reconciles branch subtotals to catch posting errors before opening. | Case 1: The Missing Branch. Every night the bank reconciles branch subtotals to catch posting errors before opening. | Name: samples/traps/cases.json, key T1, field name. Sentence: coroner/ui/templates/story_step_1.html. No number. |
| 4 | 0:27 | 0:39 | 12 s | Live page: http://127.0.0.1:8000/story/step/2?view=business. Action: open the page, scroll to the table caption "Subtotals posted by the COBOL program", wait 2 s. | The COBOL program posts 31071 transactions in 2000 test batches. Branch 001 gets 2025606.03. Branch 9ZZ gets 1969578.35. Suspense gets 1865002.53. The grand total is 139844166.11. | The COBOL program posts its transactions in 2000 test batches. Branch 001 and branch 9ZZ get their subtotals. The grand total is at the bottom. | 31071: docs/reviews.md R-89. Re-checked on 2026-11-21: runs/f584d5f35228/generated_cases.csv has 31072 lines including the header. 2000: runs/f584d5f35228/verdict.json, cases_total. 2025606.03 and 1969578.35: runs/f584d5f35228/branch_reconciliation.json, branches, cobol_subtotal. 1865002.53: same file, suspense.cobol. 139844166.11: same file, grand_total.cobol. |
| 5 | 0:39 | 0:48 | 9 s | Live page: http://127.0.0.1:8000/story/step/3?view=business. Action: open the page, wait 1 s. | A developer ported this to Java. The grand total still matches. Both sides show 139844166.11. | A developer ported this to Java. The grand total still matches. It is the same on both sides. | runs/f584d5f35228/branch_reconciliation.json, grand_total.java and grand_total.cobol (same value). |
| 6 | 0:48 | 0:58 | 10 s | Live page: http://127.0.0.1:8000/run/f584d5f35228. Action: open the page, wait for the ZOMBIE badge and its sentence, no scroll. | Coroner ran both programs on 2000 cases. Verdict: ZOMBIE. 682 of them diverge. | Coroner ran both programs on 2000 cases. Verdict: ZOMBIE. 682 of them diverge. | runs/f584d5f35228/verdict.json: cases_total 2000, status ZOMBIE, cases_divergent 682. |
| 7 | 0:58 | 1:08 | 10 s | Live page: http://127.0.0.1:8000/run/f584d5f35228. Action: scroll to the three figures and the heading "Branch Reconciliation", wait 2 s. | Exposure is 3995184.38 across 2 branches, 001 and 9ZZ. The grand total balances. The branches don't. | Two branches, 001 and 9ZZ, do not reconcile with COBOL. The grand total balances. The branches don't. | runs/f584d5f35228/verdict.json: exposure_sum 3995184.38, affected_branches 2, grand_total_matches true. Branch names 001 and 9ZZ: branch_reconciliation.json, status MISMATCH. Key quote: section 2. |
| 8 | 1:08 | 1:17 | 9 s | Live page: http://127.0.0.1:8000/story/step/4?view=business. Action: scroll to the heading "The gate", click "Check the gate", wait for the answer (the replay takes about 16 s; trim the wait in editing), keep the answer on screen 2 s. | The gate replays the certificate. Exit code 1. This ZOMBIE migration cannot be committed. | The gate replays the certificate. Exit code 1. This ZOMBIE migration cannot be committed. | "This ZOMBIE migration cannot be committed": coroner/ui/app.py, GATE_MESSAGE_ZOMBIE. "Exit code 1": docs/reviews.md R-137 (measured on the story page). |
| 9 | 1:17 | 1:29 | 12 s | Live page: http://127.0.0.1:8000/story/step/5?view=business. Action: scroll to the heading "Cause of death", wait 2 s. | Control-break logic processes branches in the wrong order, misposting amounts to suspense while grand totals still balance. The example is one transaction: branch 001, amount 6253.54. | Control-break logic processes branches in the wrong order, misposting amounts to suspense while grand totals still balance. The smallest failing case is a single transaction for branch 001. | Cause: samples/traps/T1-ebcdic-match-merge/trap.json, business_cause. Example: runs/f584d5f35228/failure_report.json, minimal_case_rows (one row: BRANCH 001, AMOUNT 6253.54). |
| 10 | 1:29 | 1:37 | 8 s | Live page: http://127.0.0.1:8000/story/step/6?view=business. Action: open the page, wait 1 s. | The fix: make the Java migration sort and match branch codes in the same order as the COBOL program. | The fix: make the Java migration sort and match branch codes in the same order as the COBOL program. | samples/traps/T1-ebcdic-match-merge/trap.json, business_fix (the business view shows this value). No number. |
| 11 | 1:37 | 1:54 | 17 s | Text card: Kiro clip placeholder (section 3.1, card 3). In the finished cut this slot is the owner's Windows recording (section 4), trimmed to 17 s. | Kiro on Windows: specs, hooks and steering. Through the coroner-audit power, Kiro audits Case 6: run e3919aefc333, ZOMBIE, 636 of 2000 cases, certificate valid. | In the Kiro IDE: specs, five hooks, steering. Kiro reads the Case 6 spec and calls Coroner through the coroner-audit power: ZOMBIE, 636 of 2000 cases, certificate valid. Then the stop hook runs. | docs/reviews.md R-190 (the MCP server of the 03e6dfc image: run_id e3919aefc333, status ZOMBIE, cases_divergent 636, cases_total 2000; verify_certificate valid true). The owner's clip shows the same values. |
| 12 | 1:54 | 2:04 | 10 s | Live page: http://127.0.0.1:8000/run/29c15f04407b. Action: open the page, wait for the ALIVE badge, no scroll. | Coroner re-runs the corrected port on 2000 cases. Verdict: ALIVE. Business behavior preserved on 2000 cases, with zero divergence. | Coroner re-runs the corrected port on 2000 cases. Verdict: ALIVE. Business behavior preserved on 2000 cases, with zero divergence. | runs/29c15f04407b/verdict.json: status ALIVE, cases_total 2000, cases_divergent 0, exposure_sum 0. |
| 13 | 2:04 | 2:11 | 7 s | Live page: http://127.0.0.1:8000/story/step/7?view=business. Action: scroll to the heading "The gate", click "Check the gate", keep the answer on screen 2 s. | The gate allows the commit. Exit code 0. | The gate allows the commit. Exit code 0. | "Commit allowed" and exit code 0: coroner/ui/app.py, GATE_MESSAGE_ALLOWED; docs/reviews.md R-137 (measured on the story page). |
| 14 | 2:11 | 2:20 | 9 s | Live page: http://127.0.0.1:8000/tamper?run_id=f584d5f35228. Action: set Status to ALIVE, set Cases Divergent to 0, click "Verify Tampered Certificate", wait for the result. | Certificate: INVALID, replay mismatch (status: expected ALIVE, got ZOMBIE). | Change the status to ALIVE and divergent count to zero. Coroner replays it: INVALID. Editing a certificate makes it INVALID. | The result text: docs/reviews.md R-104 (Tamper, same message). Prefilled status ZOMBIE: runs/f584d5f35228/verdict.json. |
| 15 | 2:20 | 2:26 | 6 s | Still image: docs/screenshots/commit-blocked.png (a real git commit of the HALF_EVEN variant in a temporary clone, made by make screenshots). Check the image for a home path before use (section 7). | Commit blocked by Coroner: ZOMBIE: FAIL: business behavior diverged on 21 cases. | The Git pre-commit hook refuses a ZOMBIE commit. | docs/evidence/git-precommit-block-then-allow.md (500-case check, seed 42, count 21 as recorded there). |
| 16 | 2:26 | 2:39 | 13 s | Text card: full chain (section 3.1, card 4). | Kiro's preToolUse gate blocks git commit, push and merge when the certificate is ZOMBIE, missing or invalid. The Git pre-commit hook blocks a ZOMBIE commit. The CI gate enforces the same verdict. | Kiro's preToolUse gate blocks git commit, push and merge when the certificate is ZOMBIE, missing or invalid. The Git pre-commit hook blocks a ZOMBIE commit. The CI gate enforces the same verdict. | docs/KIRO_USAGE.md section 4 (the three enforcement points and the evidence files). No number. |
| 17 | 2:39 | 2:47 | 8 s | Live page: http://127.0.0.1:8000/matrix. Action: scroll to the table, wait 2 s, keep the T1 row and the T6 row visible. | Six banking traps are measured, each with a faulty port and a correct port, including Case 6, The Cursed Modulo. | Six banking traps are measured, each with a faulty port and a correct port, including Case 6, The Cursed Modulo. | samples/traps/cases.json (T1 to T6 measured). Per-trap counts shown on the page come from runs/trap_catalog.json (rebuilt by coroner-init); Case 6: 636 of 2000 (R-183, R-190). No count is spoken. |
| 18 | 2:47 | 2:55 | 8 s | Text card: final card (section 3.1, card 5, with the placeholder note). Recorded after the redeploy on 2026-11-22 (section 5). | Try it live: coroner.iqoba.com. Open source: github.com/yarahmouni/cobol-coroner. AI accelerates. Coroner certifies. | Try it live at coroner dot iqoba dot com. Open source on GitHub. AI accelerates. Coroner certifies. | Live URL: docs/deploy.md. Repository name: README.md. No measured number. |

Totals: 18 shots, sum of durations 175 s (2:55). Text cards: shots 1, 2, 11, 16 and 18 (five). Live pages: shots 3 to 10, 12, 13, 14 and 17 (twelve). Still image: shot 15. In the finished cut, shot 11 is the owner's Windows clip (section 4); the recording script still renders card 3 as its placeholder.

### 3.1 Text cards

Each card is an HTML page with a dark background, the text centered, and nothing else.

**Card 1 (shot 1):**
- COBOL Coroner
- Parallel run, resurrected.

**Card 2 (shot 2):**
- Banks migrating COBOL to Java need proof the business logic survived.
- Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result.

**Card 3 (shot 11, first cut only):**
- Kiro IDE, coroner-audit power
- Placeholder: the owner records this clip on Windows (section 4).

**Card 4 (shot 16):**
- Kiro's preToolUse gate blocks git commit, push and merge when the certificate is ZOMBIE, missing or invalid.
- The Git pre-commit hook blocks a ZOMBIE commit.
- The CI gate enforces the same verdict.

**Card 5 (shot 18, first cut only the last line):**
- Try it live: https://coroner.iqoba.com
- Open source: github.com/yarahmouni/cobol-coroner
- AI accelerates. Coroner certifies.
- Placeholder note, first cut only: final card recorded after the redeploy

## 4. Kiro IDE power clip (owner records on Windows)

This is the only clip not recorded by the recording script. It shows the coroner-audit power working in the Kiro IDE, as recorded in docs/evidence/kiro-power-run.md.

Recorded by the owner on 2026-11-24 in the Kiro IDE on Windows (2:51 raw, 1920x1020), on Case 6 instead of Case 1. Trimmed and sped up to 17 s by the operator: the Kiro panel (specs, hooks, steering) 3 s, the Case 6 spec 4 s, the power run 6 s, then 4 s on the result (valid true, status ZOMBIE, cases 2000, divergences 636) and the card "Run Command Hook: Coroner stop check". The status bar is cropped and the icon of another extension is masked. The audio track is removed.

**What to record:**
1. The Powers panel with `coroner-audit` under INSTALLED (about 2 s).
2. The chat, with a prompt that asks Kiro to run `run_differential_check` through the coroner-audit power on samples/traps/T1-ebcdic-match-merge, the faulty port, seed 42, 2000 cases. Use relative paths only.
3. The tool call title `@coroner-audit/coroner/run_differential_check` and its result on screen: `run_id` f584d5f35228, status ZOMBIE, sub_label "FAIL: business behavior diverged on 682 cases", cases_total 2000, cases_divergent 682.

The result must show exactly those values. If the power returns other values, stop and report them; do not edit the clip.

**Length:** 11 s (allowed range 10 to 15 s). No audio track.

**Framing:** a 1280x720 crop of the Kiro IDE panes only (Powers panel and chat). No taskbar, no window title bar with a path, no status bar.

**Redaction rules (the clip must show none of these):**
- no user name, PC name, e-mail address or account name;
- no local path (no drive letter, no `C:\Users\...`, no workspace path); tool-call titles and results use the repository-relative paths above, so keep them that way;
- no IP address or network name;
- no other installed powers, no notifications, no system tray;
- no chat history from another session; open a new chat for the take.

Check every frame before export. If one frame shows a rule-breaking item, record again.

**Output:** MP4, 1280x720, 30 fps, file name `kiro-power-clip.mp4`, saved to `~/dev/lazarus-recordings` (outside the repository). Never commit it.

**Check before use:** the run id, the status and both counts in the clip equal the values in shot 11 and in docs/evidence/kiro-power-run.md section 2. For the recorded clip (Case 6) the values are run e3919aefc333, ZOMBIE, 636 of 2000, as in shot 11 and R-190.

## 5. Final card

**Text:** the card 5 text in section 3.1, with the live URL https://coroner.iqoba.com.

**When:** recorded only after the redeploy with the batched image. In the first cut, shot 18 is a placeholder card with the same text and the note "final card recorded after the redeploy".

**Check before recording it:**
1. The batched image is published by `.github/workflows/publish-image.yml` and the compose files pin its digest.
2. The server runs that image (`docker compose -f docker-compose.yml -f docker-compose.server.yml pull`, then `up -d`, as in docs/deploy.md).
3. `make deploy-check URL=https://coroner.iqoba.com` exits 0 and every check prints PASS, with the batched image.

If the check fails, the final card waits. The first cut is not published with the old site as its ending.

**Command (the operator runs it; the card needs no running stack):**

```
.venv/bin/python scripts/record_demo.py --shots 18 --final-card --out-dir <folder outside the repository> --ffmpeg <path of ffmpeg>
```

With `--final-card`, the card line that starts with "Placeholder" is left out of the rendered card. Without the option nothing changes.

Final card recorded on 2026-11-22 after the live check passed (R-176).

## 6. Voice-over sheet for the owner

Target: under 2.6 words per second for every shot. The word count counts the words of the voice-over text as written in section 3. Read the text as written. Text cards with no voice-over have no line here.

| Shot | Time window | Voice-over text (exact) | Words | Words per second |
|---|---|---|---|---|
| 1 | 0:00 to 0:04 | COBOL Coroner. Parallel run, resurrected. | 5 | 1.25 |
| 2 | 0:04 to 0:19 | Banks migrating COBOL to Java need proof the business logic survived. Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result. | 33 | 2.20 |
| 3 | 0:19 to 0:27 | Case 1: The Missing Branch. Every night the bank reconciles branch subtotals to catch posting errors before opening. | 18 | 2.25 |
| 4 | 0:27 to 0:39 | The COBOL program posts its transactions in 2000 test batches. Branch 001 and branch 9ZZ get their subtotals. The grand total is at the bottom. | 25 | 2.08 |
| 5 | 0:39 to 0:48 | A developer ported this to Java. The grand total still matches. It is the same on both sides. | 18 | 2.00 |
| 6 | 0:48 to 0:58 | Coroner ran both programs on 2000 cases. Verdict: ZOMBIE. 682 of them diverge. | 13 | 1.30 |
| 7 | 0:58 to 1:08 | Two branches, 001 and 9ZZ, do not reconcile with COBOL. The grand total balances. The branches don't. | 17 | 1.70 |
| 8 | 1:08 to 1:17 | The gate replays the certificate. Exit code 1. This ZOMBIE migration cannot be committed. | 14 | 1.56 |
| 9 | 1:17 to 1:29 | Control-break logic processes branches in the wrong order, misposting amounts to suspense while grand totals still balance. The smallest failing case is a single transaction for branch 001. | 28 | 2.33 |
| 10 | 1:29 to 1:37 | The fix: make the Java migration sort and match branch codes in the same order as the COBOL program. | 19 | 2.38 |
| 11 | 1:37 to 1:54 | In the Kiro IDE: specs, five hooks, steering. Kiro reads the Case 6 spec and calls Coroner through the coroner-audit power: ZOMBIE, 636 of 2000 cases, certificate valid. Then the stop hook runs. | 33 | 1.94 |
| 12 | 1:54 to 2:04 | Coroner re-runs the corrected port on 2000 cases. Verdict: ALIVE. Business behavior preserved on 2000 cases, with zero divergence. | 19 | 1.90 |
| 13 | 2:04 to 2:11 | The gate allows the commit. Exit code 0. | 8 | 1.14 |
| 14 | 2:11 to 2:20 | Change the status to ALIVE and divergent count to zero. Coroner replays it: INVALID. Editing a certificate makes it INVALID. | 20 | 2.22 |
| 15 | 2:20 to 2:26 | The Git pre-commit hook refuses a ZOMBIE commit. | 8 | 1.33 |
| 16 | 2:26 to 2:39 | Kiro's preToolUse gate blocks git commit, push and merge when the certificate is ZOMBIE, missing or invalid. The Git pre-commit hook blocks a ZOMBIE commit. The CI gate enforces the same verdict. | 32 | 2.46 |
| 17 | 2:39 to 2:47 | Six banking traps are measured, each with a faulty port and a correct port, including Case 6, The Cursed Modulo. | 20 | 2.50 |
| 18 | 2:47 to 2:55 | Try it live at coroner dot iqoba dot com. Open source on GitHub. AI accelerates. Coroner certifies. | 17 | 2.12 |

Shot 1 (title) and the text cards of shots 2 and 18 use the same words as their voice-over. Shot 11 has its voice-over over the owner's clip.

## 7. Production

- **Recordings:** each shot is recorded on its own by the recording script, from the local stack, in the browser. Output goes to `~/dev/lazarus-recordings`, outside the repository. Nothing is written into the repository or into `runs/` by the recording.
- **Format:** 1280x720, 30 fps. Live pages are recorded at 1280x600 and placed at the top of the frame; the bottom 120 px are a black band that holds the burned subtitles (at most 2 lines). Text cards and the still image keep the same 120 px band free at the bottom.
- **Page chrome:** The recording hides the Light/Dark toggle button, which is page chrome and overlaps content at 1280x600; no figure or text of the page is hidden.
- **Subtitles:** an .srt file built from the shot table (the subtitle column, with the start and end times) and burned into the first cut inside the band, except on text-card shots (`make_srt.py --skip-kind card`). `voiceover.srt` keeps every shot. The finished cut replaces the burned-in subtitles with the owner's voice and keeps the .srt for YouTube captions.
- **Music:** none. **Logo:** none in the first cut (no logo file exists in the repository; cards are text only).
- **Live site:** not used for any shot until the redeploy. Shots come from the local stack built from current main.
- **Privacy check before publishing:** no home path, user name, PC name, e-mail address or IP address in any frame, including the still image of shot 15 and the Windows clip of shot 11.
- **Before recording:** the local stack shows the rebuilt catalog (coroner-init rebuilds it at each start, docs/deploy.md); the four bundled runs (f584d5f35228, 29c15f04407b, df4d7929ce44, 08d14a07bcdb) are present; the Tamper page of shot 14 shows the status ZOMBIE for f584d5f35228.
- **Dates:** plan and script by 2026-11-25, recordings by 2026-11-27, draft by 2026-11-29 (D-57).
