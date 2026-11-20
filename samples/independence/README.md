# Independence experiment

This experiment shows that Coroner audits any Java port independently, regardless of who wrote it.

## What this shows

The same COBOL program (`samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`) was ported to Java by different sources:

1. **Kiro agent** (kiro-cli, agent coroner-builder, model claude-sonnet-4.5): written from the COBOL source alone, following standard Java practices
2. **Claude Opus 5.5** (Anthropic), run as a Claude Code subagent: not a Kiro agent, different tool but same vendor as Kiro's default model
3. **Kiro agent, fresh isolated session** (separate git worktree, stronger input isolation): written from the COBOL source alone in a reduced context
4. **Hand-written port** (pending): reserved for a port written by a person without AI assistance

Each port was audited by the same independent auditor: Coroner's differential engine.

## Isolation rules

Each source followed the same isolation rules, documented in each port's SOURCE.md:

- **Allowed inputs**: COBOL source, copybooks, schema.json, fixtures (example inputs and expected outputs), coroner/run/__init__.py (calling convention only)
- **Forbidden inputs**: existing Java ports in samples/traps/T1-ebcdic-match-merge/java/, trap.json, docs/, runs/, any other code in the repository

Links:
- [kiro/SOURCE.md](ports/kiro/SOURCE.md)
- [claude/SOURCE.md](ports/claude/SOURCE.md)
- [kiro-fresh/SOURCE.md](ports/kiro-fresh/SOURCE.md)
- [hand-written/README.md](ports/hand-written/README.md)

## The table

The table below is produced by `python3 samples/independence/run_table.py`. Every value comes from the real audit runs, nothing is typed by hand.

Each audit runs the same command:

```bash
python3 -m coroner verify \
  --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob \
  --copybooks samples/traps/T1-ebcdic-match-merge/copybooks \
  --java <port>/MatchMerge.java \
  --schema samples/traps/T1-ebcdic-match-merge/schema.json \
  --cases 2000 --seed 42
```

The verdict, divergent cases, run ID, Java SHA-256 and branch exposure are all read from the run's certificate and branch reconciliation files.

[View the full table](TABLE.md)

## What the results show

The experiment demonstrates that Coroner provides the same kind of independent evidence for each port, regardless of who wrote it:

- **Same COBOL program**: Every port is auditing the same COBOL reference (MATCH-MERGE.cob)
- **Same test cases**: Every audit uses the same generated cases (see TABLE.md for details)
- **Same schema**: Every audit uses the same schema.json
- **Different results**: See TABLE.md for the verdict and divergence count for each port

The auditor does not depend on who wrote the port. When a port diverges, Coroner shows:
- The exact count of divergent cases
- The run ID for full reproducibility
- The branch exposure (which branches do not reconcile with COBOL)
- The certificate with all input hashes and tool versions

When a port matches, Coroner shows the same evidence: see TABLE.md for the verdict and the certificate.

## How the ports were created

The sources approached the COBOL program differently:

- **Kiro agent**: Read the COBOL source, copybooks and schema.json alone. Did not compile or run the COBOL program before writing the Java port. Wrote the port as a faithful migration engineer would. The port was then audited by Coroner once; the port was not changed after the audit.

- **Claude Opus subagent**: Read the COBOL source, copybooks and schema.json. Before writing the Java port, compiled the COBOL program locally and ran it on hand-made edge-case inputs (CRLF line ends, an empty line, a short record, a blank CASE-ID, a lower-case branch code). Verified that the Java port produced identical output on those cases, so the port was validated before the audit. The port was then audited by Coroner once; the port was not changed after the audit.

Both ran the same Coroner audit command once and did not iterate after the audit. Readers must not take the verdicts as a comparison of the two models: one program, one run each. The Claude subagent invested more upfront validation effort, while the Kiro agent relied on the audit itself to find issues.

## Honest limits

1. **One program**: This experiment uses a single COBOL program (T1, the EBCDIC collating sequence trap). It does not claim to prove behavior across all COBOL programs.

2. **One seed and 2,000 cases**: Each audit uses the same seed (42) and case count (2,000). Other seeds were not run for this table.

3. **Same vendor for the Claude subagent and Kiro's default model**: The Claude Opus 5.5 subagent and Kiro's default model (claude-sonnet-4.5) are both from Anthropic. The subagent is a different tool and model from Kiro, but not a different vendor.

4. **Hand-written port pending**: The hand-written port slot is reserved for a person. The operator and Kiro are language models and do not write code in that slot.

## What the independence track proves

The same independent auditor (Coroner) gives the same kind of evidence for any Java port:

- A deterministic verdict (ALIVE or ZOMBIE)
- The exact divergence count
- A replayable certificate with all input hashes
- Branch-level exposure when applicable

The result does not depend on who wrote the port. The auditor is independent of the migration source.

Why the session 1 numbers equal the faulty demo port

The "Kiro agent, session 1" row has the same divergence count and exposure as the faulty T1 demo port in `samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java` (682 of 2000 cases, exposure sum 3995184.38). This is not because they are the same file:

- SHA-256 of session 1 port: 3f2b2d38...
- SHA-256 of demo faulty port: 8d9bb18a...
- Differing lines: 269 (diff output lines; the files have 193 and 182 lines)

The numbers are equal because both audits use the same 2,000 generated cases (seed 42, same `cases_file_sha256` in the certificates) and both ports make the same ASCII-order mistake (using `String.compareTo` instead of EBCDIC collating order), so the same input cases produce divergent outputs. The first divergent case for both is GEN-001525 (its minimal input is one transaction: branch 001, amount 6253.54; see minimal_case_input.csv in each run).

The session 1 port is distinct code from the demo faulty port. The identical divergence count demonstrates that Coroner detects the same mistake independently of how the mistake is expressed in the source code.

## Kiro-fresh isolation

The "Kiro agent, fresh isolated session" port was produced in a separate git worktree with stronger isolation to verify that the isolation rules can be enforced:

- Every tracked `.java` file was deleted from the worktree
- `docs/`, `README.md`, `.kiro/` (steering, skills, specs), all `trap.json` files and `runs/` were deleted
- The COBOL source, copybooks and schema were copied into a neutral folder `case1-input/` (no "ebcdic" in any path name)
- Three trap-hint comment lines were removed from the COBOL copy (see cobol-input.diff)
- The schema `description` field was replaced with a neutral business description

The COBOL code itself was unchanged, including `ALPHABET EBC IS EBCDIC`. The diffs `ports/kiro-fresh/cobol-input.diff` and `schema-input.diff` show exactly what differs from the original inputs.

The fresh session agent did not run any audit. The operator audited the port once against the original `MATCH-MERGE.cob`.

## Environment matters

The kiro-fresh port's verdict depends on the JVM default locale because it formats amounts with `String.format("%+010.2f")`, which prints a decimal comma under a French locale.

Measured verdicts (operator, 2000 cases, seed 42):

- In the project Docker image (Linux, `coroner-local:latest`, the environment of CI and the live demo): **ALIVE**, 0 of 2000 divergent cases.
- On the operator's Mac, whose JVM default locale is `fr_FR` even though the engine sets `LANG=C.UTF-8` (macOS Java ignores `LANG`): **ZOMBIE**, 2000 of 2000 divergent cases, exposure sum 5784.58 on 9 branches, grand total not matching.

The kiro (session 1) and claude ports give the same verdicts in the image as on the Mac: ZOMBIE 682 cases and ALIVE 0 cases, respectively. Their verdicts were the same in both measured environments.

The reference table in `TABLE.md` is produced by running all audits in the project image (`--image coroner-local:latest`), so every port is audited in the same environment.
