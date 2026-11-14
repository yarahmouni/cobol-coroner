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
- Return codes are compared for every case.
- The reference COBOL binary is never instrumented. Coverage uses a separate instrumented build in `build/coverage/`.
