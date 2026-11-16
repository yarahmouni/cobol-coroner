# COBOL Coroner

**The independent regression auditor for COBOL-to-Java migrations.**

It checks whether a migration kept the business behavior on N generated cases, and shows exactly where it broke.

COBOL Coroner does not just compare outputs. It detects the banking migration traps that silently corrupt totals, control breaks and data ordering.

> AI accelerates. Coroner certifies.

COBOL Coroner does not convert code. It verifies a migration that already exists, whoever produced it (AWS Transform, Kiro, Claude or a human).

Give it:
- a batch COBOL program and its copybooks,
- its Java 17 version,
- a `schema.json` describing input and output columns.

Coroner runs both programs on the same generated test cases, compares the outputs field by field with no numeric tolerance, and returns a deterministic verdict:

- **ALIVE**: PASS: business behavior preserved on N cases (0 divergence found).
- **ZOMBIE**: FAIL: business behavior diverged on M cases, with the failing case, the COBOL output, the Java output, the divergent field and the COBOL lines executed.

## Quick start

Prerequisites: GnuCOBOL 3.2, JDK 17, Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
make test
make demo
make zombie
make acceptance
make junit-jars
```

CLI form:

```bash
python -m coroner verify --cobol COBOL_FILE --copybooks COPYBOOK_DIR --java JAVA_FILE --schema SCHEMA_JSON [--cases N] [--seed S] [--timings]
```

Exit codes: 0 = ALIVE, 1 = ZOMBIE, 2 = error.

## What a run writes

Every run stores artifacts in `runs/<run_id>/`:

- `inputs.json`: input hashes, seed, tool versions, case count
- `generated_cases.csv`: synthetic test cases
- `comparison_results.json`: COBOL and Java outputs aligned by case
- `coverage_report.json`: paragraph and branch coverage
- `verdict.json`: the final verdict with sub-label
- `failure_report.json`: (ZOMBIE only) minimal case details and executed lines
- `ZombieRegressionTest.java`: (ZOMBIE only) JUnit 5 test that reproduces the divergence

Example output from the dev machine with correct Java and 2,000 cases:

```
ALIVE: PASS: business behavior preserved on 2000 cases
Paragraph coverage 12/12
Branch coverage (Coroner definition) 42/70
Validated under GnuCOBOL 3.x
```

With the HALF_EVEN variant (a rounding bug):

```
ZOMBIE: FAIL: business behavior diverged on 86 cases
Paragraph coverage 12/12
Branch coverage (Coroner definition) 42/70
Validated under GnuCOBOL 3.x
```

Note: Branch coverage counts only the branches reached by generated valid inputs. Input-validation error paths are not generated.

## The full chain

> Kiro translates. Coroner certifies. Git and Jenkins enforce the verdict.

A Kiro agent ports the COBOL program, Coroner audits the port through MCP, a Kiro Stop hook and a Git pre-commit hook block a ZOMBIE verdict, a Jenkins or GitHub Actions gate enforces it, and the replayable certificate records the result (in progress).

Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed.

The stop hook re-prompts the agent up to 3 times (v2 engine) or once per turn (v3 engine); it does not prevent the agent from finishing.

The Git pre-commit hook runs a fast 500-case check on the demo sample staged content and blocks ZOMBIE commits. It audits exactly what will be committed, not the working tree. The `git commit --no-verify` bypass is available to the owner under their responsibility.

## Kiro skills

Three skills guide the coroner-auditor agent:
- `banking-trap-recognition`: Recognize the six banking migration traps in COBOL and Java (EBCDIC collation, rounding, COMP-3 sign, zoned overpunch, REDEFINES, reserved for owner trap).
- `cobol-semantics-safety`: COBOL semantic rules a Java port must preserve (rounding to HALF_UP, truncation to DOWN, BigDecimal with explicit scale, sign handling, EBCDIC collating sequence).
- `coroner-audit-workflow`: End-to-end workflow from run_differential_check to certificate verification.

## Trap catalog

The branch-code mix of T1 is a generator setting (schema.json domain_weights), not a real-world statistic.

## Status

Work in progress for Kiroween 2026 (category: Resurrection). See `docs/sprints.md`.

## What Coroner is not

- Not a converter.
- Not a formal proof of equivalence. An ALIVE verdict means "business behavior preserved on N cases", nothing more.
- Validated under GnuCOBOL 3.x only, not IBM Enterprise COBOL.
- Return codes are compared as OS exit statuses, which are limited to 0 to 255 (a COBOL RETURN-CODE outside that range is reduced by the operating system).

## Out of scope (V1)

CICS, DB2, IMS, VSAM, JCL, EBCDIC-encoded data (the EBCDIC collating sequence trap is in scope), multi-program applications, Pacbase, target languages other than Java 17.

## Limitations

- COMP-3 sign nibbles B, A, E and other non-preferred nibbles are excluded from certified cases (GnuCOBOL reads B as positive, IBM documentation treats B as negative). Coroner tests use only preferred sign nibbles C (positive), D (negative), and F (unsigned/positive).

## How Kiro was used

To be completed during the build: specs, steering, hooks and MCP server, see `/.kiro`.

## Data

All COBOL programs and data in this repository are synthetic. No code or data from any real bank is used.

## License

Apache-2.0. See LICENSE.
