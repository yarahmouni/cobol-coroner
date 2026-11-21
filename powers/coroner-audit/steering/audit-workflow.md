---
inclusion: always
---

# Coroner Audit Workflow

When auditing a Java port with Coroner tools:

1. **Run the audit first**: Call `run_differential_check` with the COBOL program, Java port, schema and copybooks. Use 200 cases for a fast check, 2000 for a full audit.

2. **Read the verdict**: Call `get_verdict` with the run_id. Check the status:
   - ALIVE: Business behavior preserved. Go to step 5.
   - ZOMBIE: Business behavior diverged. Continue to step 3.
   - ERROR: Reference did not run. Check the COBOL program.

3. **Get failure details (ZOMBIE only)**: Call `get_failure_report` to see the minimal case, divergent fields, and COBOL lines executed. Call `export_junit_test` to get the JUnit regression test.

4. **Fix the Java port**: Based on the failure report:
   - Identify the COBOL operation that produced the correct output
   - Check for wrong rounding mode, sign handling, or collating sequence
   - Fix the Java code
   - Return to step 1

5. **Generate certificate (ALIVE only)**: Call `generate_certificate` to produce a replayable record. Call `verify_certificate` to verify it offline.

## Rules

- **Never edit the COBOL reference program**. The COBOL output is the specification.
- **Never edit expected outputs**. They come only from running the COBOL program.
- **Report only measured values**. If a tool is not available or fails, say so and stop. Never write a verdict from memory or documentation.
- **Fix, do not patch**. You identify the issue and fix the Java code. Coroner never patches code for you.

## Claims

- ALIVE means "business behavior preserved on N cases", not "proven equivalent".
- ZOMBIE means "business behavior diverged on M cases".
- The certificate is a reproducible run record, not a guarantee.
- Results are "no behavioral difference across the tested scenarios", not a proof for all inputs.
