# EBCDIC/control-break demo requirements

Priority 9 (D-33, D-34, D-45).

## Context

The owner's demo showcases trap T1 (EBCDIC vs ASCII sort order breaks control-break subtotals) with measured numbers only: ZOMBIE verdict, Unreconciled branch exposure, minimal case with COBOL lines, JUnit export, certificate replay, then correct port ALIVE.

Operator findings on run 92a9f12d2aaa (faulty port, 2000 cases, seed 42) expose five engine bugs and one delivery requirement that this spec must fix.

## Requirements (EARS)

### Req 1: Multi-row minimal case reduction
**When** a schema declares case_rows (one case is several input rows) and a case diverges, **the system shall** find the smallest subset of that case's input rows that still diverges, using delta reduction with deterministic ordering, and **shall** assert that the final subset diverges by re-running both programs on it.

**When** the reduction yields a subset that does not diverge, **the system shall** raise an error and **shall not** write the failure report or JUnit test.

**The system shall** keep both the full original case rows and the minimal subset in failure_report.json.

### Req 2: Row-level divergence description
**When** comparing multi-row outputs, **the system shall** describe divergences by the output key value (for example "BRANCH=001 present in COBOL output position 1, Java position 3" or "SUBTOTAL for BRANCH=Z99 COBOL +123.45 Java +100.00"), not as field "row" with "present"/"missing".

**The system shall** count divergences consistently with the existing engine (262 for run 92a9f12d2aaa). Only the description changes.

### Req 3: Multi-row Given/When/Then card
**When** generating the card for a multi-row case, **the Given** clause **shall** list the case's input rows (or the minimal subset if reduced).

**The Then** clause **shall** name each divergent branch and show COBOL vs Java values.

**For** T1 traps, **the system shall** include the comparison and ordering statements of the match-merge in the COBOL lines involved, not only ADD statements.

### Req 4: JUnit test verification
**The system shall** generate ZombieRegressionTest.java such that it compiles with `javac` and runs with JUnit 6.1.3, fails when executed against the faulty port, and passes when executed against the correct port.

**The demo script shall** verify the generated test by compiling and running it against both ports as part of the demo workflow.

**Note**: Automated JUnit verification within the engine (coroner/diag/junit.py) is deferred to hardening (Nov 25-27) and not part of priority 9.

### Req 5: Integrated demo command
**The system shall** provide a command `make demo-ebcdic` that runs, from real executions only:

1. faulty T1 verify (2000 cases, seed 42) printing the verdict block
2. the Given/When/Then card
3. the JUnit test run against the faulty port (must fail)
4. the JUnit test run against the correct port (must pass)
5. `coroner verify <certificate>` replay (must be VALID)
6. correct T1 verify (must be ALIVE)

**The system shall** exit 0 only if every step behaved as expected (ZOMBIE for faulty, VALID replay, ALIVE for correct, JUnit fail then pass). Otherwise **the system shall** exit 1 with the failing step named.

No number is written in the Makefile, script or docs except as measured output captured from real runs.

### Req 6: Test coverage
**The system shall** provide fast tests for the multi-row shrinker on real T1 cases (test 1-minimality and determinism by actually running the T1 programs), the row-level divergence description, and the multi-row card generation on a small real T1 run.

**The system shall** provide a slow test for `make demo-ebcdic` end-to-end that records its measured duration.

### Req 7: README demo section
**The system shall** add a "Demo" section to README.md with the `make demo-ebcdic` command and a placeholder sentence that the operator fills with measured output.

No number is typed by hand in the spec, README or Makefile.

## Acceptance criteria

1. Multi-row minimal case for T1 diverges when re-run (both programs).
2. Divergence descriptions name the output key and branch value.
3. Card lists input rows and divergent branch values.
4. ZombieRegressionTest.java compiles, fails on faulty port, passes on correct port.
5. `make demo-ebcdic` exits 0 on the dev machine.
6. Fast and slow tests pass.
7. README has the demo command with a measured-output placeholder.
