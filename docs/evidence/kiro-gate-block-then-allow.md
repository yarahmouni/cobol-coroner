# Real Kiro block, then allowed commit (D-50 demo sequence), 2026-11-15

kiro-cli 3.3.0, agent coroner-auditor (.kiro/agents/coroner-auditor.json), model claude-sonnet-4.5, non-interactive (v2 engine). Scratch clone of the repository: HEAD has no CreditFees.java; the staged new file is the HALF_EVEN legacy variant; its run 227fcf67095d is ZOMBIE (86 divergences on 2,000 cases). The Git pre-commit hook was not enabled in the clone, so only the Kiro delivery gate (preToolUse, coroner.hooks gate) acts here.

Sequence observed: commit attempt blocked by the gate (tool status Failed), agent reads the verdict and the failure report through MCP, fixes HALF_EVEN to HALF_UP with sed, stages, run_differential_check gives ALIVE on 2,000 cases (run a26c32ac9519), commit retried and allowed (commit 7a17e2c in the clone, 465 lines added).

Finding: in this run the block reason was not shown to the agent (v2 displays the hook's stderr; the gate wrote the reason only as JSON on stdout), so the agent had to investigate. Fixed afterwards: the gate also writes the message on stderr.

## Clone log after the run
```
7a17e2c Deliver CreditFees Java port
a965075 Demo baseline: Java port not delivered yet, hooks and agent in place
d400bc1 Priority 5: MCP server with 7 tools, coroner-auditor agent, three Kiro skills, evidence of a real Kiro audit
 samples/credit-fees/java/CreditFees.java | 465 +++++++++++++++++++++++++++++++
 1 file changed, 465 insertions(+)
```

## Agent transcript
```
I'll execute this workflow step by step, committing the Java port and handling any pre-commit gate blocks.

## Step 1: Attempting the commit
[tool] status: Failed
Let me check the git status and try to understand what's happening:
[tool] Running: git status
[tool] status: Completed
The file is staged. Let me check if there's a pre-commit hook that might be running:
[tool] status: Failed

[tool] Running: ls -la .git/hooks/
[tool] status: Completed
There's no active pre-commit hook. The block appears to be from Kiro's PreToolHook. Let me check the Kiro hook configuration:
[tool] status: Failed

[tool] Reading listing .kiro
[tool] status: Completed
The block is coming from Kiro's PreToolHook system. Based on the context about the Git pre-commit hook running a 500-case check, let me check if there's information about how this works:
[tool] Running: find . -name "*hook*" -o -name "*pre-commit*" | grep -v ".git" | head -20
[tool] status: Completed
[tool] Reading hooks.py:1
[tool] status: Completed
Now I understand. The Kiro PreToolHook is running the gate command which is checking for a certificate. The gate blocks git commits when the certificate is ZOMBIE, missing, or invalid. Let me check the scope file:
[tool] Reading coroner-scope.json:1
[tool] status: Completed
Perfect. The Java file is staged and matches the scope. Let me check if there's an existing certificate:
[tool] Running: find runs -name "certificate.json" 2>/dev/null | head -5
[tool] status: Completed
There's a certificate. Let me get the verdict for this run:
[tool] Running: @coroner/get_verdict
[tool] status: Completed
**Step 1 Result:** The commit is blocked by the Kiro gate hook. The existing certificate for run `227fcf67095d` shows:

```
ZOMBIE: FAIL: business behavior diverged on 86 cases
```

Status: ZOMBIE
Cases divergent: 86 out of 2000
Validated under GnuCOBOL 3.x

## Step 2: Getting failure report and fixing the Java
[tool] Running: @coroner/get_failure_report
[tool] status: Completed
**Failure report:**
- Minimal failing case: GEN-001218
- Divergent field: FEE-AMOUNT
- COBOL output: -0000000.05
- Java output: -0000000.04
- Difference: rounding divergence

The issue is a rounding problem. COBOL produced -0.05 but Java produced -0.04. This is a classic HALF_EVEN vs HALF_UP rounding trap. Let me read the relevant sections of the COBOL to understand the calculation, then read and fix the Java:
[tool] Reading CREDIT-FEES.cob:119-133
[tool] status: Completed
[tool] Reading CREDIT-FEES.cob:291-320
[tool] status: Completed
I can see the COBOL uses `COMPUTE ... ROUNDED` which means HALF_UP rounding. Now let me read the Java file to find the rounding issue:
[tool] Reading CreditFees.java:1
[tool] status: Completed
Found the bugs! There are **three instances** of `RoundingMode.HALF_EVEN` that should be `RoundingMode.HALF_UP`:

1. Line ~171: Base fee calculation
2. Line ~185: Premium segment discount rounding
3. Line ~190: Standard segment discount rounding

According to the cobol-semantics-safety steering, COBOL `ROUNDED` without a mode means NEAREST-AWAY-FROM-ZERO (HALF_UP in Java), not HALF_EVEN.

Let me fix all three occurrences:
[tool] Running: sed -i '' 's/RoundingMode\.HALF_EVEN/RoundingMode.HALF_UP/g' samples/credit-fees/java/CreditFees.java
[tool] status: Completed
Now let me verify the fix was applied:
[tool] Running: grep -n "RoundingMode\." samples/credit-fees/java/CreditFees.java | head -10
[tool] status: Completed
Perfect! All three HALF_EVEN have been changed to HALF_UP. The DOWN rounding modes are correct (those are for truncation validation). Now let me stage the fixed file:
[tool] Running: git add samples/credit-fees/java/CreditFees.java
[tool] status: Completed
Now run the differential check with 2000 cases:
[tool] Running: @coroner/run_differential_check
[tool] status: Completed
Excellent! The differential check now shows:

**Run ID:** a26c32ac9519
**Status:** ALIVE
**Verdict:** PASS: business behavior preserved on 2000 cases
**Cases divergent:** 0 out of 2000
**Paragraph coverage:** 12/12
**Branch coverage (Coroner definition):** 42/70
**Certificate path:** runs/a26c32ac9519/certificate.json

Now let me retry the commit:
[tool] Running: git commit -m 'Deliver CreditFees Java port'
[tool] status: Completed
Perfect! The commit succeeded.

## Summary

**Step 1:** Initial commit was blocked by Kiro gate hook. Existing certificate run `227fcf67095d` showed ZOMBIE verdict with 86 divergent cases out of 2000.

**Step 2:** 
- Retrieved failure report showing rounding divergence: COBOL output -0000000.05 vs Java output -0000000.04 on case GEN-001218
- Identified root cause: Three instances of `RoundingMode.HALF_EVEN` in Java file (lines 321, 337, 341) should be `RoundingMode.HALF_UP` per COBOL semantics (ROUNDED means HALF_UP, not HALF_EVEN)
- Fixed all three instances with sed command
- Re-ran differential check with 2000 cases
- New run `a26c32ac9519` result: **ALIVE: PASS: business behavior preserved on 2000 cases** (0 divergences, paragraph coverage 12/12, branch coverage 42/70)
- Commit succeeded with the ALIVE certificate
```
