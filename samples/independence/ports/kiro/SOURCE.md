# Source: Kiro Agent Port

## Metadata

- **Producer**: Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5)
- **Date**: 2026-11-20
- **COBOL source**: samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob
- **Run**: Independence track, operator worktree

## Allowed inputs

The Kiro agent was allowed to read ONLY these files:

1. `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob` (COBOL source)
2. `samples/traps/T1-ebcdic-match-merge/copybooks/` (copybooks directory)
3. `samples/traps/T1-ebcdic-match-merge/schema.json` (input/output record layout)
4. `samples/traps/T1-ebcdic-match-merge/fixtures/` (example inputs and expected outputs)
5. `coroner/run/__init__.py` (to understand how Java programs are invoked)

## Forbidden inputs

The agent was explicitly forbidden from reading:

- `samples/traps/T1-ebcdic-match-merge/java/` (existing Java ports)
- `trap.json` (trap metadata)
- `docs/` (documentation)
- `runs/` (run artifacts)
- Any other Java files in the repository

**Statement**: The existing Java ports were NOT read. This port was written solely from the COBOL source, schema, and fixtures.

## Compilation

The Java file compiled cleanly with no errors:

```
javac -Xlint:all -d build/independence samples/independence/ports/kiro/MatchMerge.java
```

No compile fixes were needed.

## Audit results

Command:
```
.venv/bin/python -m coroner verify --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob --copybooks samples/traps/T1-ebcdic-match-merge/copybooks --java samples/independence/ports/kiro/MatchMerge.java --schema samples/traps/T1-ebcdic-match-merge/schema.json --cases 2000 --seed 42
```

Output:
```
ZOMBIE: FAIL: business behavior diverged on 682 cases
Paragraph coverage 6/8
Branch coverage (Coroner definition) 22/30
Unreconciled branch exposure: sum 3995184.38, max 2025606.03, 2 branches affected, suspense difference 3995184.38, grand total matches: yes
Validated under GnuCOBOL 3.x
Run: runs/a4709d638df5
Duration: 16.8 s
```

**Verdict**: ZOMBIE (682 divergences out of 2000 cases)

**Run ID**: runs/a4709d638df5

## Notes

This port was written as a faithful migration engineer would write it, using standard Java practices:
- BigDecimal for decimal arithmetic
- ASCII string comparison for branch ordering
- Sequential match logic against the branch table
- Standard Java file I/O and CSV parsing

The ZOMBIE verdict indicates that the ASCII collating sequence differs from the EBCDIC collating sequence used by the COBOL program, causing branch mismatches in 682 out of 2000 test cases.
