---
inclusion: always
---

# Comparison rules

- No numeric tolerance is allowed in differential comparison.
- All monetary values are compared exactly after normalization to the scale defined in `schema.json`.
- Strings are compared exactly after trimming trailing spaces.
- Line endings are normalized to LF.
- Columns are matched by name, never by position.
- The first column is the case id. Row counts must be equal.
- Dates use YYYYMMDD.
- Return codes: the exact OS exit status (0 to 255) of the COBOL run and of the Java run are compared per run, and per case whenever a single case is re-run (minimal case, failure report). A mismatch is reported as "FAIL: return code differs (COBOL x, Java y)" (D-31).
- The reference COBOL binary is never instrumented. Coverage uses a separate instrumented build in `build/coverage/`.
