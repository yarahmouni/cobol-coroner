---
name: coroner-audit
version: 1.0.0
description: Independent behavioral audit of COBOL-to-Java migrations
---

# Coroner Audit Power

Enables any Kiro agent to audit a Java 17 port of a COBOL program using the COBOL Coroner differential verification engine.

## What it does

The coroner-audit power provides MCP tools that run both the COBOL program and its Java port on the same generated test cases, compare outputs field by field with no numeric tolerance, and return a deterministic verdict:

- **ALIVE**: Business behavior preserved on N cases (0 divergence found).
- **ZOMBIE**: Business behavior diverged on M cases, with the minimal failing case and COBOL lines involved.
- **ERROR**: Reference COBOL program did not run (file error, libcob error, timeout).

**Important**: Coroner never translates COBOL. It only verifies a migration that already exists.

## When to use it

Use this power when:
- Auditing a Java 17 port of a batch COBOL program
- You need deterministic proof that business behavior is preserved across test cases
- You want to identify exactly where and why a migration diverged
- You need a replayable certificate of the audit result

Do not use this power for:
- Translating COBOL to Java (Coroner only audits existing migrations)
- Programs with CICS, DB2, IMS, VSAM dependencies
- Programs that require z/OS-specific behavior

## Prerequisites

Docker Desktop is the only prerequisite on the host. No GnuCOBOL, no JDK and no Python venv are needed on the host.

The MCP server starts from the published image over stdio:

```
docker run --rm -i --init ghcr.io/yarahmouni/cobol-coroner@sha256:0ca88a1f3cf795b08c2c8b9169efd1d05e276e593f22aaeafd7be082501a4ad4 python -m coroner.mcp
```

- The image is linux/amd64, so it needs an x86-64 machine.
- The image holds the repository at `/app`, and tool paths are relative to it, for example `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`. No volume is needed.
- Runs live inside the container for one chat session (`--rm`). A `run_id` from an earlier session is not found in a new one.

## Available tools

The server exposes 7 tools, called by their bare names: `run_differential_check`, `get_verdict`, `get_failure_report`, `get_detection_matrix`, `export_junit_test`, `generate_certificate`, `verify_certificate`.

### run_differential_check

Run the full verification pipeline.

**Arguments:**
- `cobol` (string, required): Path to COBOL source file (e.g., `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`)
- `copybooks` (string, required): Path to copybooks directory (e.g., `samples/traps/T1-ebcdic-match-merge/copybooks`)
- `java` (string, required): Path to Java source file (e.g., `samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java`)
- `schema` (string, required): Path to schema.json (e.g., `samples/traps/T1-ebcdic-match-merge/schema.json`)
- `cases` (integer, optional): Number of test cases to generate (default: 2000, range: 1-10000)
- `seed` (integer, optional): Random seed for reproducibility (default: 42)

**Returns:** measured on 2026-11-21 with the four paths above, `cases` 2000 and `seed` 42, on the faulty port:

```json
{
  "run_id": "f584d5f35228",
  "status": "ZOMBIE",
  "sub_label": "FAIL: business behavior diverged on 682 cases",
  "cases_total": 2000,
  "cases_divergent": 682,
  "paragraph_coverage": "6/8",
  "branch_coverage": "22/30",
  "certificate_path": "runs/f584d5f35228/certificate.json"
}
```

**Exit codes (when run completes):**
- Status ALIVE: Verdict indicates behavior preserved
- Status ZOMBIE: Verdict indicates divergence
- Status ERROR: Reference did not run (see "How to read the verdict")

### get_verdict

Read the verdict of a completed run.

**Arguments:**
- `run_id` (string, required): 12-character lowercase hex run identifier

**Returns:** measured for run `f584d5f35228`:

```json
{
  "affected_branches": 2,
  "cases_divergent": 682,
  "cases_total": 2000,
  "exposure_max": "2025606.03",
  "exposure_sum": "3995184.38",
  "grand_total_matches": true,
  "run_return_codes": [
    0,
    0
  ],
  "status": "ZOMBIE",
  "sub_label": "FAIL: business behavior diverged on 682 cases",
  "suspense_difference": "3995184.38",
  "validation_notice": "Validated under GnuCOBOL 3.x"
}
```

### get_failure_report

Get details of the minimal failing case (ZOMBIE runs only).

**Arguments:**
- `run_id` (string, required): 12-character lowercase hex run identifier

**Returns:** the shape measured for run `f584d5f35228`. `executed_lines` and `original_case_rows` are shortened, and the card is cut after its first lines; every other field and value is as measured.

```json
{
  "case_id": "GEN-001525",
  "input_row": {
    "CASE-ID": "GEN-001525",
    "BRANCH": "D04",
    "AMOUNT": "5.88"
  },
  "cobol_output": {
    "CASE-ID": "GEN-001525",
    "BRANCH": "001  ",
    "SUBTOTAL": "+0006253.54"
  },
  "java_output": {
    "CASE-ID": "GEN-001525",
    "BRANCH": "SUSP ",
    "SUBTOTAL": "+0006253.54"
  },
  "divergent_fields": [
    {
      "kind": "missing_in_java",
      "output_key": {"CASE-ID": "GEN-001525", "BRANCH": "001"},
      "cobol_values": {"CASE-ID": "GEN-001525", "BRANCH": "001  ", "SUBTOTAL": "+0006253.54"},
      "java_values": {}
    },
    {
      "kind": "missing_in_cobol",
      "output_key": {"CASE-ID": "GEN-001525", "BRANCH": "SUSP"},
      "cobol_values": {},
      "java_values": {"CASE-ID": "GEN-001525", "BRANCH": "SUSP ", "SUBTOTAL": "+0006253.54"}
    }
  ],
  "cobol_return_code": 0,
  "java_return_code": 0,
  "executed_lines": [["/app/samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob", 63], "... 96 entries in total, lines 63 to 249"],
  "card": "Given the following input rows:\n  CASE-ID=GEN-001525, BRANCH=001, AMOUNT=6253.54\nWhen the COBOL reference and the Java port process this case\nThen COBOL writes row BRANCH=001 with SUBTOTAL=+0006253.54, Java does not\n...",
  "original_case_rows": ["... 17 rows, the first is BRANCH D04, AMOUNT 5.88"],
  "minimal_case_rows": [
    {
      "CASE-ID": "GEN-001525",
      "BRANCH": "001",
      "AMOUNT": "6253.54"
    }
  ]
}
```

`input_row` is the first row of the original case (the first of its 17 rows). It is not the minimal case. The minimal case is `minimal_case_rows`, here one row: branch 001, amount 6253.54.

For an ALIVE run the tool returns an error. Measured for run `29c15f04407b`:

```
Error executing tool get_failure_report: No failure report: the run was ALIVE
```

### export_junit_test

Export a JUnit 5 source test that reproduces the divergence (ZOMBIE runs only).

**Arguments:**
- `run_id` (string, required): 12-character lowercase hex run identifier

**Returns:** measured for run `f584d5f35228`, with the content cut after its first lines:

```json
{
  "path": "runs/f584d5f35228/ZombieRegressionTest.java",
  "content": "/**\n * Given/When/Then card:\n *\n * Given the following input rows:\n *   CASE-ID=GEN-001525, BRANCH=001, AMOUNT=6253.54\n * When the COBOL reference and the Java port process this case\n * Then COBOL writes row BRANCH=001 with SUBTOTAL=+0006253.54, Java does not\n..."
}
```

The returned test:
- Runs the Java port with the minimal case input
- Asserts the output equals the COBOL reference output
- Fails on the faulty port, passes on the corrected port

For an ALIVE run the tool returns an error. Measured for run `29c15f04407b`:

```
Error executing tool export_junit_test: No JUnit test: the run was ALIVE or the test was not generated
```

### generate_certificate

Generate or regenerate the Coroner Certificate for a run.

**Arguments:**
- `run_id` (string, required): 12-character lowercase hex run identifier

**Returns:** measured for run `29c15f04407b`:

```json
{
  "path": "runs/29c15f04407b/certificate.json",
  "certificate_sha256": "7a499f19ad2d561e5250dc0816bcedcaedcd980cd3fd821ce792bd0b1ebadd37"
}
```

(The hash differs on every generation, because the certificate records its timestamp.)

The certificate records (the keys written by `generate_certificate` in `coroner/certificate.py`):
- The statement ("Reproducible run record: <sub label>. Validated under GnuCOBOL 3.x. This is not a formal proof of equivalence."), the verdict status and sub-label
- Number of cases and divergences, and the exit status of the COBOL and the Java run
- Paragraph and branch coverage (reached and total)
- SHA-256 of the COBOL file, each copybook, the Java file, the schema and the generated cases file, with the file paths
- The random seed, the case count, the generator version and the tie share, so that replay can regenerate the cases
- Tool versions (Python, cobc, javac, java, coroner) and the hash of the comparison engine
- The Java locale and the cobc flags, and the timestamp
- `certificate_sha256`, the SHA-256 of all other fields in canonical JSON
- For a ZOMBIE run: the minimal case id and the divergent fields

### verify_certificate

Verify a certificate by replaying it offline.

**Arguments:**
- `path` (string, required): Path to certificate.json

**Returns:** measured for run `29c15f04407b`, with `path` set to `runs/29c15f04407b/certificate.json`:

```json
{
  "valid": true,
  "reasons": [],
  "status": "ALIVE",
  "cases": 2000,
  "divergences": 0,
  "paragraph_coverage": "6/8",
  "branch_coverage": "22/30"
}
```

When invalid, measured for `runs/tampered/certificate.json`. That file is a copy of `runs/29c15f04407b/certificate.json` made in the container, with its first `"cases_divergent": 0` replaced by `1` and the hash not recomputed:

```json
{
  "valid": false,
  "reasons": [
    "certificate content was modified"
  ],
  "status": null,
  "cases": null,
  "divergences": null,
  "paragraph_coverage": null,
  "branch_coverage": null
}
```

Replay first checks every recorded hash and the certificate content hash. It then regenerates the cases from the recorded seed when the generator version matches, recompiles and reruns both programs, and compares the status, the counts, the return codes and the coverage with the recorded values.

### get_detection_matrix

Get the trap catalog detection matrix.

**Arguments:**
- `trap_id` (string, optional): Return only one trap (e.g., "T1", "T2"). Without it the tool returns all traps under the key `traps`.

**Returns:** the trap catalog that was built into the image (`python -m coroner traps`, run during the image build). It works in a fresh container with no volume. Without `trap_id` it returns all traps under the key `traps`.

The catalog lists the run ids of the image build (for example `faulty_run_id` and `correct_run_id`). Their run folders are not in the image. To get a run folder, run the same audit again with `run_differential_check`: run ids are derived from content, so the same audit gives the same run id.

Measured for `trap_id` "T1", in a fresh container of the image pinned above, shortened to the fields listed here:

```json
{
  "id": "T1",
  "case_number": 1,
  "case_name": "The Missing Branch",
  "title": "EBCDIC vs ASCII collating order in sequential match-merge",
  "cases_detected": 682,
  "cases_generated": 2000,
  "detection_rate": "0.3410",
  "correct_verdict": "ALIVE",
  "faulty_run_id": "f584d5f35228",
  "correct_run_id": "29c15f04407b"
}
```

`detection_rate` is a string. The rate is measured for the generator settings of that trap, not a real-world statistic.

## How to read the verdict

The blocks below are the lines printed by `python -m coroner verify`, measured on 2026-11-21 in the image on Case 1 with 2000 cases and seed 42. They stop at "Validated under GnuCOBOL 3.x"; the `Run:` and `Duration:` lines that follow are left out.

### ALIVE verdict

```
ALIVE: PASS: business behavior preserved on 2000 cases
Paragraph coverage 6/8
Branch coverage (Coroner definition) 22/30
Unreconciled branch exposure: sum 0.00, max 0.00, 0 branches affected, suspense difference 0.00, grand total matches: yes
Validated under GnuCOBOL 3.x
```

Meaning: The Java port produced the same output as COBOL on all 2,000 test cases. No behavioral difference was detected across the tested scenarios. This is not a proof of equivalence for all possible inputs.

### ZOMBIE verdict

```
ZOMBIE: FAIL: business behavior diverged on 682 cases
Paragraph coverage 6/8
Branch coverage (Coroner definition) 22/30
Unreconciled branch exposure: sum 3995184.38, max 2025606.03, 2 branches affected, suspense difference 3995184.38, grand total matches: yes
Validated under GnuCOBOL 3.x
```

Meaning: The Java port produced different output than COBOL on 682 of 2,000 test cases. The failure report shows the minimal case that triggers the divergence and the COBOL lines involved.

### ERROR verdict

Measured with the COBOL program of `tests/test_broken_reference.py`, the credit-fees Java port and 20 cases: libcob stopped the program with a file error on its input file (status 35). The CLI prints these lines on stderr and exits with status 2:

```
ERROR: reference did not run
Reason: libcob error in stderr
```

The MCP tool returns this error for the same run (measured):

```
Error executing tool run_differential_check: ERROR: reference did not run. Check COBOL program for file errors, libcob errors, or timeouts.
```

Meaning: The COBOL reference program did not run successfully. Possible causes: missing file, libcob error, timeout. The Java port is never blamed for a broken reference.

## Certificate and replay

Every run produces a certificate at `runs/<run_id>/certificate.json`. The certificate:
- Is a reproducible JSON run record
- Records SHA-256 hashes of all input files
- Can be verified offline with `verify_certificate`
- Is not a formal proof or guarantee of equivalence

A valid certificate proves:
- The audit ran with the recorded inputs
- The recorded verdict matches what replay produces
- No file was modified since the audit

A certificate does not prove:
- Behavior on inputs outside the test cases
- Equivalence on z/OS or IBM Enterprise COBOL
- Absence of all possible bugs

## Limits

- Coroner audits one program at a time (no multi-program applications)
- Results are "no behavioral difference across the tested scenarios", not a proof
- GnuCOBOL 3.2 is the reference, not IBM Enterprise COBOL
- Return codes are compared as OS exit statuses (0-255 range)
- Validated under GnuCOBOL 3.x only

## Example workflow

```
1. Call run_differential_check with cobol, java, schema, copybooks
2. Check the status: ALIVE, ZOMBIE, or ERROR
3. If ZOMBIE:
   a. Call get_failure_report to see the minimal case
   b. Call export_junit_test to get the regression test
   c. Fix the Java port based on the COBOL lines shown
   d. Return to step 1
4. If ALIVE:
   a. Call generate_certificate to produce a replayable record
   b. Call verify_certificate to verify it
5. Commit the ALIVE certificate with the Java port
```

## What Coroner never does

- Never translates COBOL to Java
- Never edits the COBOL reference program
- Never edits expected outputs
- Never patches the Java port (you apply fixes based on the report)
- Never claims formal equivalence or guarantees
