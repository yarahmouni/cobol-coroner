# Source of this port

- Source: Claude Opus 5.5 (Anthropic), run as a Claude Code subagent; not a Kiro agent.
- Date: 2026-11-20.
- Port: `MatchMerge.java`, a Java port of `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`, written from the COBOL alone.

## Files read

- `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`
- `samples/traps/T1-ebcdic-match-merge/copybooks/` (listed; the directory is empty, so no copybook was read)
- `samples/traps/T1-ebcdic-match-merge/schema.json`
- `samples/traps/T1-ebcdic-match-merge/fixtures/branch-ordering.csv`
- `samples/traps/T1-ebcdic-match-merge/fixtures/branch-ordering-expected.csv`
- `coroner/run/__init__.py` (read only for the calling convention: `java -cp <dir> MatchMerge`, input and output paths in the `INPUT_FILE` and `OUTPUT_FILE` environment variables)

No other Java port was read. No file under `samples/traps/*/java/`, `samples/independence/ports/kiro/`, `docs/`, `runs/`, `.kiro/`, no `trap.json` and no README was opened, listed or searched. No web search was used.

## Checks before the audit

Before the single audit run, the port was checked against the fixture (`branch-ordering-expected.csv`, identical byte for byte) and against the COBOL program compiled locally with `cobc` on one hand-made edge-case input (CRLF line ends, an empty line, a short record, a blank CASE-ID, a lower-case branch). The outputs were identical, so the port was not changed.

## Compile fixes

None. The first `javac` run compiled without errors.

## Audit

Command, run once from the working directory:

```
.venv/bin/python -m coroner verify --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob --copybooks samples/traps/T1-ebcdic-match-merge/copybooks --java samples/independence/ports/claude/MatchMerge.java --schema samples/traps/T1-ebcdic-match-merge/schema.json --cases 2000 --seed 42
```

Output:

```
ALIVE: PASS: business behavior preserved on 2000 cases
Paragraph coverage 6/8
Branch coverage (Coroner definition) 22/30
Unreconciled branch exposure: sum 0.00, max 0.00, 0 branches affected, suspense difference 0.00, grand total matches: yes
Validated under GnuCOBOL 3.x
Run: runs/0d1e698359fb
Duration: 14.3 s
```

Verdict: ALIVE (PASS). Divergent cases: 0 of 2000. The output has no separate divergent count line; the count of 0 follows from the PASS line on all 2000 cases. Run id: `runs/0d1e698359fb`.

The port was not changed after the audit.
