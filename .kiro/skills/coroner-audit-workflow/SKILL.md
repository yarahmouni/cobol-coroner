---
name: coroner-audit-workflow
description: End-to-end workflow for auditing a Java port with Coroner
---

# Coroner Audit Workflow

Complete workflow for auditing a Java 17 port of a COBOL program using Coroner MCP tools.

## Step 1: Initial verification

Call `@coroner/run_differential_check` with:
- `cobol`: Path to COBOL source file
- `copybooks`: Path to copybooks directory
- `java`: Path to Java source file
- `schema`: Path to schema.json
- `cases`: 200 for fast check, 2000 for full audit
- `seed`: 42 (or any fixed seed for reproducibility)

## Step 2: Read the verdict

Call `@coroner/get_verdict` with the `run_id` from step 1.

Check the `status` field:
- `ALIVE`: PASS, business behavior preserved on N cases. Go to step 6.
- `ZOMBIE`: FAIL, business behavior diverged on M cases. Continue to step 3.

**Rule**: Report a verdict, a count or a coverage value only when it comes from a Coroner tool result in this session. If a tool is not available or fails, say so and stop; never write a verdict from memory or from the documentation.

## Step 3: Get failure details (ZOMBIE only)

Call `@coroner/get_failure_report` with the `run_id`.

The report shows:
- Minimal failing case (smallest absolute values)
- Input row that triggered the divergence
- COBOL and Java outputs
- Divergent fields
- COBOL lines executed (with source file and line number)

## Step 4: Export regression test (ZOMBIE only)

Call `@coroner/export_junit_test` with the `run_id`.

This returns `ZombieRegressionTest.java`, a JUnit 5 source test that reproduces the divergence on the Java side.

## Step 5: Fix the Java port

Based on the failure report and executed COBOL lines:
- Identify the COBOL operation that produced the correct output.
- Check if the Java port applies the wrong rounding mode, wrong sign handling, or wrong collating sequence.
- Fix the Java code.
- Return to step 1.

## Step 6: Generate and verify certificate (ALIVE only)

Call `@coroner/generate_certificate` with the `run_id` to produce a replayable certificate.

Call `@coroner/verify_certificate` with the certificate path to verify it offline.

The certificate records:
- Verdict status and sub-label
- Number of cases and divergences
- Coverage metrics
- SHA-256 of every input file (COBOL, Java, schema, copybooks, cases)
- Tool versions and seed

## Tools used

- `@coroner/run_differential_check`: Run the verification pipeline
- `@coroner/get_verdict`: Read verdict.json
- `@coroner/get_failure_report`: Read failure_report.json (ZOMBIE only)
- `@coroner/export_junit_test`: Get ZombieRegressionTest.java (ZOMBIE only)
- `@coroner/generate_certificate`: Write certificate.json
- `@coroner/verify_certificate`: Offline certificate replay
