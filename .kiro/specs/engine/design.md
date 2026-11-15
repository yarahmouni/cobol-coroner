# Design: Coroner engine (S1)

## Overview

The Coroner engine is the core verification system that generates test cases, runs both COBOL and Java programs, compares outputs field by field with no numeric tolerance, and returns a deterministic ALIVE or ZOMBIE verdict.

The engine takes as inputs: a COBOL source file with copybooks, a Java 17 source file, and a schema.json describing input and output columns. It compiles both programs, generates N test cases from a fixed seed, executes both programs in batch mode (one COBOL run, one JVM), normalizes and compares outputs per comparison-rules.md, captures coverage from an instrumented COBOL build, and stores all results in `runs/<run_id>/`.

The verdict is ALIVE when 0 divergences are found, ZOMBIE when at least 1 divergence is found. For ZOMBIE verdicts, the engine generates a failure report with the minimal failing case and a JUnit 5 source test (ZombieRegressionTest.java) that reproduces the divergence.

Success criteria from sprints.md: 2,000 cases give ALIVE with correct Java and ZOMBIE with the HALF_EVEN legacy variant; wall-clock time under 60 seconds including compilation; 0 false ZOMBIE on 10 runs of correct Java; 0 false ALIVE on 10 runs of bugged Java.

## Architecture

### High-level flow

```
CLI: python -m coroner verify --cobol PATH --copybooks PATH --java PATH --schema PATH [--cases N] [--seed S]
    |
    v
Load and validate inputs (size limits, file existence)
Parse schema.json (input/output columns, types, scales)
Compute run_id = SHA-256(input hashes, seed, case count, tool versions)[:12]
    |
    v
Generate cases (coroner/gen)
  - Targeted: limits, boundaries, branches, rounding ties
  - Random: Hypothesis with fixed seed (or random.Random(seed) if Hypothesis cannot run deterministically outside tests)
  - Write runs/<run_id>/generated_cases.csv
    |
    v
Compile and run (coroner/run)
  - COBOL reference: cobc -x -Wall -I <copybooks> -o build/<name> <source>
  - COBOL instrumented: same + -ftraceall -o build/coverage/<name>
  - Java: javac -Xlint:all -d build/java/<run_id> <source>
  - Run reference COBOL once (all cases)
  - Run Java once (one JVM, all cases)
  - Run instrumented COBOL once (coverage trace)
    |
    v
Compare outputs (coroner/compare)
  - Parse COBOL and Java CSVs
  - Normalize per schema (decimal scale, string trim, LF)
  - Compare field by field, no numeric tolerance
  - Return codes per run (owner validation pending)
  - Write runs/<run_id>/comparison_results.json
    |
    v
Generate verdict (coroner/verdict)
  - ALIVE: 0 divergences
  - ZOMBIE: M divergences
  - Sub-labels per no-formal-proof.md
  - Write runs/<run_id>/verdict.json
    |
    v
Generate reports (coroner/diag)
  - Coverage: paragraph and branch per D-07
  - If ZOMBIE: failure report, minimal case, ZombieRegressionTest.java
  - Write runs/<run_id>/coverage_report.json, failure_report.json, ZombieRegressionTest.java
    |
    v
CLI output: verdict, coverage, run_id
Exit code: 0 (ALIVE), 1 (ZOMBIE), 2 (error)
```

### Key design decisions

1. **Package layout:** All modules inside coroner/ package, no new top-level or scripts/ files. Modules: parse/ (schema.py, copybook.py, trace.py), gen/, run/, compare/, diag/ (report.py, minimal_case.py, junit.py, coverage.py), verdict.py, store.py, cli.py, __main__.py, catalog/legacy_variant.py.

2. **Separate builds:** Reference COBOL binary never instrumented. Instrumented build in build/coverage/ used only for traces. Reference build used for all output comparison.

3. **Batch execution:** One COBOL run processes all cases. One JVM run processes all cases. Single-case re-runs only for minimal case and failure report details.

4. **Deterministic generation:** Fixed seed for everything. Same seed gives same CSV bytes. Hypothesis integration for random cases if it supports deterministic generation outside tests; otherwise use random.Random(seed).

5. **Run storage:** run_id = SHA-256(input hashes, seed, case count, tool versions)[:12]. All artifacts in runs/<run_id>/. Atomic write of verdict.json last.

6. **Minimal case:** Deterministic rule: among divergent cases, smallest absolute value of numeric inputs in schema order, then case id. Reusable by fault catalog (no duplicated logic).

7. **JUnit test:** ZombieRegressionTest.java runs Java as subprocess (main calls System.exit), asserts divergent field equals COBOL value. JUnit jars pinned with SHA-256, downloaded by make target, never committed.

8. **Performance budget:** 60 seconds for 2,000 cases including compilation. Expected breakdown: COBOL compile 2s, Java compile 1s, case generation 2s, COBOL run 15s, Java run 10s, instrumented COBOL run 20s, comparison 5s, reports 2s, margin 3s.

## Components and Interfaces

### Component 1: Schema parsing (coroner/parse/schema.py)

**Purpose:** Load and validate schema.json. Extract input field domains (sign, digits, scale), output field properties, numeric constants for boundary generation.

**Signature:**
```python
@dataclass
class SchemaColumn:
    name: str
    type: str  # "string", "decimal", "integer"
    pic: str
    description: str
    scale: int | None = None
    signed: bool = False
    comp3: bool = False

@dataclass
class Schema:
    program_name: str
    description: str
    input_file: str
    input_columns: list[SchemaColumn]
    output_file: str
    output_columns: list[SchemaColumn]
    internal_precision: dict[str, dict] | None = None

def load_schema(path: str) -> Schema:
    """Load and validate schema.json. Raise ValueError on invalid schema."""
```

**Behavior:**
- Read JSON, validate required fields per Requirement 1.7.
- Parse PIC clauses to extract sign (leading S), digit count, scale (V or decimal point).
- Check internal_precision for COMP-3 fields.
- Raise ValueError with clear message on missing fields or invalid structure.

### Component 2: Copybook and source parsing (coroner/parse/copybook.py)

**Purpose:** Parse COBOL source and copybooks to extract numeric constants (for boundaries), paragraph names, and branch first-statement line numbers.

**Note:** Parser is written for constructs used by the demo sample and the veteran's catalog programs: IF/ELSE/END-IF, EVALUATE/WHEN, PERFORM, paragraphs, VALUE clauses, literals in conditions, SORT. Unsupported constructs cause the coverage report to state "not measured" for that program rather than guessing.

**Signature:**
```python
@dataclass
class BranchInfo:
    paragraph: str
    line_number: int
    branch_type: str  # "IF_TRUE", "IF_ELSE", "EVALUATE_WHEN", "EVALUATE_OTHER"

def parse_cobol_structure(source_path: str, copybook_dir: str) -> dict:
    """
    Returns:
      {
        "constants": [Decimal("10.00"), ...],
        "paragraphs": {"MAIN-PARA": 42, ...},  # name -> line number
        "branches": [BranchInfo(...), ...]
      }
    """
```

**Behavior:**
- Regex-based parsing: extract VALUE clauses and numeric literals from IF conditions.
- Identify paragraph names and their starting line numbers.
- Branches (operator verification on GnuCOBOL 3.2.0 with -ftraceall): CONTINUE is traced as a statement (so ELSE CONTINUE branches are measurable); WHEN lines are traced when their condition is TESTED, even when not taken, so a WHEN line is never a branch marker. Branches are: IF true arm (first statement after IF), IF ELSE arm (first statement after ELSE), each EVALUATE WHEN arm (first statement inside WHEN), and WHEN OTHER (first statement inside WHEN OTHER). The branch marker is the line of the FIRST STATEMENT inside the arm. Nested IFs count each level.
- Simple parser: does not handle all COBOL syntax, focuses on credit-fees patterns. Extensible for future programs.

### Component 3: Trace parsing (coroner/parse/trace.py)

**Purpose:** Parse GnuCOBOL -ftraceall trace files, key executed lines by (source_file, line_number).

**Signature:**
```python
TraceKey = tuple[str, int]  # (source_file, line_number)

def parse_trace(trace_path: str) -> dict[TraceKey, int]:
    """
    Returns: {("CREDIT-FEES.cob", 42): 1, ("CREDIT-FEES.cob", 43): 1000, ...}
    Execution count per line (usually 1 per branch, N for loops).
    """
```

**Behavior:**
- Read trace line by line.
- Extract "Source: <file>" to track current source file.
- Extract "Line: N" to track executed line.
- Key by (source_file, line_number).
- Increment count for each appearance (loops execute the same line multiple times).
- Extension of S0 parser (review R-09).

### Component 4: Case generation (coroner/gen/__init__.py)

**Purpose:** Generate N test cases from schema, COBOL structure, and fixed seed. Write generated_cases.csv.

**Signature:**
```python
def generate_cases(
    schema: Schema,
    cobol_structure: dict,
    seed: int,
    num_cases: int,
    tie_share: float = 0.05
) -> str:
    """
    Returns: path to generated_cases.csv
    Deterministic: same seed gives same CSV bytes.
    """
```

**Behavior:**

1. **Targeted cases:**
   - Limits: minimum and maximum for each PIC (e.g., S9(9)V99 gives -999999999.99 and 999999999.99).
   - Boundaries: for each constant C in cobol_structure["constants"], generate C - 0.01, C, C + 0.01 (adjusted for scale).
   - Branches: values that force each IF true and false (heuristic: threshold +/- small delta).
   - Rounding ties: constructed from PRODUCTS of decimal input columns, not from single values. For a pair of decimal input columns (a with scale sa, b with scale sb) whose product is computed at a higher scale than the output scale (2), choose b as a power of ten within its domain (for example 0.01000 with scale 5) and a whose digits put an exact 5 at the third decimal of the product. Example: 1234.50 x 0.01000 = 12.3450000 (preceding digit 4, even). Only ties with an EVEN preceding digit diverge under HALF_EVEN (D-06). For tie_share=0.05 and num_cases=2000, generate about 100 tie cases: about 50 with even preceding digits (25 positive, 25 negative) that stay visible in the output (absolute value at least the largest positive threshold found among constants, for credit-fees 10.00, or negative), plus about 50 with odd preceding digits as controls. Calibration target (acceptance test): the HALF_EVEN variant diverges on 80 to 120 of 2,000 cases with default seed 42. This is a calibration target for the generator, not a guarantee.

2. **Random cases:**
   - Owner decision needed: check if Hypothesis can generate deterministically outside @given (st.register_random with seed).
   - If yes: use Hypothesis strategies for each column, generate random cases.
   - If no: use random.Random(seed) for uniform random values in PIC ranges.

3. **Case ID:** "GEN-00001", "GEN-00002", ..., zero-padded to fit schema PIC.

4. **Canonical format:** decimal as "-123.45" (optional sign, digits, optional decimal point and decimals), no leading '+', no exponent, no spaces. Strings without quotes.

5. **Write CSV:** header row from schema.input_columns, then all case rows. LF line endings.

**Owner decision needed:**

> **Hypothesis deterministic generation outside tests**
>
> Hypothesis provides `st.register_random(Random(seed))` to make strategies deterministic. However, this is designed for use within `@given`, and the documentation does not guarantee reproducibility across Hypothesis versions when used outside test functions.
>
> **Option A:** Use Hypothesis with `st.register_random` for random cases. Risk: case generation might change across Hypothesis versions, breaking determinism.
>
> **Option B:** Use `random.Random(seed)` for random cases at runtime. Reserve Hypothesis for property-based tests in coroner/compare (normalization properties). Trade-off: simpler, guaranteed deterministic, but loses Hypothesis shrinking and advanced strategies.
>
> **Recommendation:** Option B for runtime generation, Hypothesis only for tests. This aligns with quality.md (shortest readable code, no abstraction without a second use).
>
> The design supports both: `generate_cases` will use a pluggable random source, controlled by a flag or config.

### Component 5: Compilation and execution (coroner/run/__init__.py)

**Purpose:** Compile COBOL (reference and instrumented) and Java. Run both programs. Capture outputs and return codes.

**Signature:**
```python
@dataclass
class RunResult:
    output_path: str
    return_code: int
    stderr: str
    wall_time: float

def compile_cobol(source: str, copybooks: str, output: str, flags: list[str]) -> None:
    """Run cobc with timeout. Raise RuntimeError on failure."""

def compile_java(source: str, output_dir: str) -> None:
    """Run javac with timeout. Raise RuntimeError on failure."""

def run_cobol(binary: str, input_csv: str, output_csv: str, timeout: float = 60.0) -> RunResult:
    """Run COBOL binary with INPUT_FILE and OUTPUT_FILE env vars."""

def run_java(class_name: str, classpath: str, input_csv: str, output_csv: str, timeout: float = 60.0) -> RunResult:
    """Run Java main with INPUT_FILE and OUTPUT_FILE env vars."""

def run_cobol_instrumented(binary: str, input_csv: str, output_csv: str, trace_file: str, timeout: float = 60.0) -> RunResult:
    """Run instrumented COBOL with COB_SET_TRACE=Y and COB_TRACE_FILE."""
```

**Behavior:**
- subprocess.run with timeout, capture stdout/stderr.
- Environment: minimal (PATH, INPUT_FILE, OUTPUT_FILE, COB_SET_TRACE, COB_TRACE_FILE). No network.
- Raise RuntimeError on timeout or non-zero compile exit code.
- Return RunResult with output path, return code, stderr, wall time.

**Build order:**
1. Compile reference COBOL: `cobc -x -Wall -I <copybooks> -o build/<name> <source>`
2. Compile instrumented COBOL: same + `-ftraceall -o build/coverage/<name>`
3. Compile Java: `javac -Xlint:all -d build/java/<run_id> <source>`
4. Run reference COBOL on generated_cases.csv
5. Run Java on generated_cases.csv
6. Run instrumented COBOL on generated_cases.csv (trace to runs/<run_id>/coverage_trace.txt)

### Component 6: Output comparison (coroner/compare/__init__.py)

**Purpose:** Parse, normalize, compare COBOL and Java outputs. Return comparison results.

**Signature:**
```python
@dataclass
class CaseResult:
    case_id: str
    divergent: bool
    divergent_fields: list[tuple[str, str, str]]  # (field_name, cobol_value, java_value)

@dataclass
class ComparisonResult:
    cases: list[CaseResult]
    run_return_codes: tuple[int, int]  # (cobol, java)
    row_count_match: bool
    total_divergent: int

def compare_outputs(
    cobol_csv: str,
    java_csv: str,
    schema: Schema,
    cobol_return_code: int,
    java_return_code: int
) -> ComparisonResult:
    """Compare outputs field by field with normalization."""
```

**Behavior:**

1. **Parse CSVs:** csv.DictReader, columns by name.
2. **Normalize:**
   - Decimal: parse with `Decimal(value)`. If the value has non-zero digits beyond the schema scale, the field is divergent (report the raw text). Otherwise, pad to the scale with `quantize(Decimal(10) ** -scale, rounding=ROUND_UNNECESSARY)` to verify no rounding is needed. A text that is not a valid decimal is divergent with its raw value. Rule (D-09, no tolerance): normalization never rounds. If Java prints "12.355" where COBOL prints "12.36", the third decimal differs, so they are divergent.
   - String: `value.rstrip()` (trim trailing spaces only).
   - Line endings: already LF (files opened in text mode).
3. **Compare:**
   - First column is case_id.
   - Row counts must match (if not, row_count_match=False, all cases marked divergent).
   - For each case, compare all output columns by name.
   - If column missing in one output: divergent, value "missing".
   - If normalized values differ: divergent.
4. **Return codes:** Per Requirement 5.3, mark run-level return-code mismatch as divergent. NOTE: comparison-rules.md says "for every case"; in batch mode this is per run; owner validation pending.
5. **Property-based tests:** Hypothesis tests for normalization properties: normalization never changes the numeric value (parse before and after must be equal when both valid); any value with extra non-zero decimals beyond schema scale is reported divergent; idempotent for strings.

### Component 7: Verdict (coroner/verdict.py)

**Purpose:** Determine ALIVE or ZOMBIE verdict from comparison results. Move Verdict type here from coroner/mcp/server.py.

**Signature:**
```python
@dataclass
class Verdict:
    status: str  # "ALIVE" or "ZOMBIE"
    sub_label: str
    cases_total: int
    cases_divergent: int
    run_return_codes: tuple[int, int]  # (cobol, java)
    validation_notice: str = "Validated under GnuCOBOL 3.x"

def compute_verdict(comparison: ComparisonResult) -> Verdict:
    """Return ALIVE if 0 divergences and return codes match, else ZOMBIE."""
```

**Behavior:**
- ALIVE: `cases_divergent == 0` and `run_return_codes[0] == run_return_codes[1]`, sub_label = "PASS: business behavior preserved on {cases_total} cases"
- ZOMBIE with case divergences: `cases_divergent > 0`, sub_label = "FAIL: business behavior diverged on {cases_divergent} cases"
- ZOMBIE with only return code mismatch: `cases_divergent == 0` and return codes differ, sub_label = "FAIL: business behavior diverged on 0 cases; return code COBOL {cobol_rc}, Java {java_rc}"
- ZOMBIE with both: sub_label = "FAIL: business behavior diverged on {cases_divergent} cases; return code COBOL {cobol_rc}, Java {java_rc}"
- NOTE: owner validation pending on Requirement 5.3 interpretation (run-level vs per-case return codes).
- MCP server imports Verdict from here, no logic in MCP handler.

### Component 8: Run storage (coroner/store.py)

**Purpose:** Compute run_id, write all artifacts to runs/<run_id>/, atomic verdict.json write.

**Signature:**
```python
def compute_run_id(
    cobol_hash: str,
    java_hash: str,
    schema_hash: str,
    copybook_hashes: list[tuple[str, str]],
    seed: int,
    case_count: int,
    tool_versions: dict
) -> str:
    """First 12 hex chars of SHA-256."""

def store_inputs(run_dir: str, inputs_data: dict) -> None:
    """Write inputs.json with hashes, seed, versions, timestamp."""

def store_verdict(run_dir: str, verdict: Verdict) -> None:
    """Atomic write of verdict.json."""

def store_comparison(run_dir: str, comparison: ComparisonResult) -> None:
    """Write comparison_results.json."""
```

**Behavior:**
- run_id = SHA-256(concatenate all input hashes, seed, case_count, tool versions)[:12]
- Create runs/<run_id>/ if missing.
- Write inputs.json, generated_cases.csv (copy), comparison_results.json, coverage_report.json.
- If ZOMBIE: write failure_report.json, ZombieRegressionTest.java.
- Write verdict.json last (atomic: write to temp file, rename).
- Tool versions: `subprocess.run(["cobc", "--version"], ...)` etc.

### Component 9: Coverage report (coroner/diag/coverage.py)

**Purpose:** Compute paragraph and branch coverage from trace.

**Signature:**
```python
@dataclass
class CoverageReport:
    paragraph_coverage: tuple[int, int]  # (covered, total)
    branch_coverage: tuple[int, int]  # (covered, total)
    paragraph_details: dict[str, bool]  # name -> covered
    branch_details: list[dict]  # [{line, paragraph, covered}, ...]

def compute_coverage(trace: dict[TraceKey, int], cobol_structure: dict) -> CoverageReport:
    """Match trace keys against paragraphs and branch first statements."""
```

**Behavior:**
- Paragraph covered: paragraph "Paragraph:" trace record or any statement line inside it appears in trace.
- Branch covered: first statement line of branch appears in trace (D-07).
- Fallback (if branch coverage unreliable by 2026-11-23): statement coverage instead of branch coverage.

### Component 10: Failure report (coroner/diag/report.py)

**Purpose:** Generate failure report for ZOMBIE verdicts.

**Signature:**
```python
@dataclass
class FailureReport:
    minimal_case: CaseResult
    input_row: dict[str, str]
    cobol_output: dict[str, str]
    java_output: dict[str, str]
    executed_lines: list[tuple[str, int]]  # (source_file, line_number)

def generate_failure_report(
    comparison: ComparisonResult,
    schema: Schema,
    generated_cases_csv: str,
    cobol_binary: str,
    java_classpath: str,
    java_class: str,
    instrumented_binary: str,
    run_dir: str
) -> FailureReport:
    """Select minimal case, re-run instrumented COBOL, extract details."""
```

**Behavior:**
- Select minimal case from comparison.cases (see Component 11).
- Read input row for that case from generated_cases.csv.
- Re-run instrumented COBOL on one-row input (header + case).
- Re-run Java on one-row input.
- Parse trace, extract executed lines.
- Return FailureReport with all details.

### Component 11: Minimal case selection (coroner/diag/minimal_case.py)

**Purpose:** Deterministic minimal failing case selection. Reusable by fault catalog.

**Signature:**
```python
def select_minimal_case(
    divergent_cases: list[CaseResult],
    schema: Schema,
    input_rows: dict[str, dict]  # case_id -> input row
) -> CaseResult:
    """
    Deterministic rule: among divergent cases, smallest absolute value of
    numeric input columns in schema order, then lexicographic case_id.
    Numeric inputs parsed with Decimal; non-numeric values sort last.
    """
```

**Behavior:**
- Filter comparison.cases to divergent only.
- For each case, read input row from generated_cases.csv.
- Parse numeric inputs with Decimal for ordering. The generator only emits valid canonical inputs, but a non-numeric value sorts last.
- Sort by: (abs(numeric_col_1), abs(numeric_col_2), ..., case_id).
- Return first.

### Component 12: JUnit test generation (coroner/diag/junit.py)

**Purpose:** Generate ZombieRegressionTest.java for minimal case.

**Signature:**
```python
def generate_junit_test(
    minimal_case: CaseResult,
    input_row: dict[str, str],
    expected_output: dict[str, str],
    java_class: str,
    schema: Schema,
    output_path: str
) -> None:
    """Write ZombieRegressionTest.java that runs Java as subprocess."""
```

**Behavior:**
- Template: JUnit 5 test class with one @Test method.
- Write input CSV (header + row) to temp file.
- Run Java as subprocess: `ProcessBuilder`, args = ["java", "-cp", classpath, java_class], environment INPUT_FILE and OUTPUT_FILE, timeout 10s.
- Read output row, parse divergent field.
- Assert: `assertEquals(expectedCobolValue, actualJavaValue, "Field X diverged")`.
- Assert return code if it diverged.
- Write to output_path.

**JUnit jars:**
- junit-jupiter-api and junit-platform-console-standalone at pinned versions (TODO: versions and SHA-256 in task).
- Downloaded by `make junit-jars` into build/junit/, never committed.
- Tests skip if jars missing.

### Component 13: CLI (coroner/cli.py and coroner/__main__.py)

**Purpose:** Command-line interface for verify command.

**Signature:**
```python
def verify_command(
    cobol: str,
    copybooks: str,
    java: str,
    schema: str,
    cases: int = 2000,
    seed: int = 42,  # default seed documented here
) -> int:
    """
    Run full verification pipeline.
    Returns: 0 (ALIVE), 1 (ZOMBIE), 2 (error).
    """
```

**Behavior:**
- Validate inputs (file existence, size limits per Requirement 1).
- Call all components in order.
- Print verdict and coverage to stdout.
- Print run_id for reference.
- Return exit code.

**__main__.py:**
```python
if __name__ == "__main__":
    # argparse for --cobol, --copybooks, --java, --schema, --cases, --seed
    exit_code = verify_command(...)
    sys.exit(exit_code)
```

### Component 14: Legacy variant catalog (coroner/catalog/legacy_variant.py)

**Purpose:** Generate HALF_EVEN variant from correct Java source for demo.

**Signature:**
```python
def generate_half_even_variant(source_path: str, output_path: str) -> None:
    """
    Rewrite RoundingMode.HALF_UP to RoundingMode.HALF_EVEN.
    Documented rewrite for the legacy demo variant (D-29).
    """
```

**Behavior:**
- Read Java source.
- Replace all occurrences of "RoundingMode.HALF_UP" with "RoundingMode.HALF_EVEN".
- Write to output_path.
- Used by fault catalog (separate spec), called by make zombie.

## Data Models

### Schema data structures
```python
@dataclass
class SchemaColumn:
    name: str
    type: str  # "string", "decimal", "integer"
    pic: str
    description: str
    scale: int | None = None
    signed: bool = False
    comp3: bool = False

@dataclass
class Schema:
    program_name: str
    description: str
    input_file: str
    input_columns: list[SchemaColumn]
    output_file: str
    output_columns: list[SchemaColumn]
```

### Comparison data structures
```python
@dataclass
class CaseResult:
    case_id: str
    divergent: bool
    divergent_fields: list[tuple[str, str, str]]  # (field, cobol, java)

@dataclass
class ComparisonResult:
    cases: list[CaseResult]
    run_return_codes: tuple[int, int]
    row_count_match: bool
    total_divergent: int
```

### Verdict
```python
@dataclass
class Verdict:
    status: str  # "ALIVE" or "ZOMBIE"
    sub_label: str
    cases_total: int
    cases_divergent: int
    run_return_codes: tuple[int, int]  # (cobol, java)
    validation_notice: str = "Validated under GnuCOBOL 3.x"
```

### Coverage
```python
@dataclass
class CoverageReport:
    paragraph_coverage: tuple[int, int]
    branch_coverage: tuple[int, int]
    paragraph_details: dict[str, bool]
    branch_details: list[dict]
```

### Failure report
```python
@dataclass
class FailureReport:
    minimal_case: CaseResult
    input_row: dict[str, str]
    cobol_output: dict[str, str]
    java_output: dict[str, str]
    executed_lines: list[tuple[str, int]]
```

### Run storage files

**runs/<run_id>/inputs.json:**
```json
{
  "cobol_source_sha256": "abc...",
  "java_source_sha256": "def...",
  "schema_sha256": "ghi...",
  "copybook_hashes": [{"name": "TYPES.cpy", "sha256": "jkl..."}],
  "seed": 42,
  "case_count": 2000,
  "cobc_version": "GnuCOBOL 3.2.0",
  "javac_version": "17.0.21",
  "python_version": "3.12.16",
  "timestamp": "2026-11-15T12:34:56Z"
}
```

**runs/<run_id>/verdict.json:**
```json
{
  "status": "ZOMBIE",
  "sub_label": "FAIL: business behavior diverged on 103 cases",
  "cases_total": 2000,
  "cases_divergent": 103,
  "run_return_codes": [0, 0],
  "validation_notice": "Validated under GnuCOBOL 3.x"
}
```

**runs/<run_id>/comparison_results.json:**
```json
{
  "cases": [
    {
      "case_id": "GEN-00042",
      "divergent": true,
      "divergent_fields": [["FEE-AMOUNT", "+0000012.35", "+0000012.34"]]
    }
  ],
  "run_return_codes": [0, 0],
  "row_count_match": true,
  "total_divergent": 103
}
```

**runs/<run_id>/coverage_report.json:**
```json
{
  "paragraph_coverage": [15, 15],
  "branch_coverage": [28, 28],
  "paragraph_details": {"MAIN-PROCESS": true, ...},
  "branch_details": [
    {"line": 42, "paragraph": "COMPUTE-FEE", "branch": "IF-positive", "covered": true}
  ]
}
```

## Error Handling

### Input validation errors (exit 2)
- File not found: "ERROR: File not found: {path}"
- File too large: "ERROR: File exceeds size limit: {path}"
- Invalid schema: "ERROR: Invalid schema: {message}"
- Missing required fields in schema: "ERROR: Missing required field in schema: {field}"

### Compilation errors (exit 2)
- COBOL compile failure: "ERROR: COBOL compilation failed\n{stderr}"
- Java compile failure: "ERROR: Java compilation failed\n{stderr}"

### Execution errors (exit 2)
- Timeout: "ERROR: {program} execution timed out after {timeout}s"
- Crash: "ERROR: {program} crashed with return code {code}\n{stderr}"

### Comparison errors (exit 2)
- CSV parse failure: "ERROR: Cannot parse {program} output CSV: {message}"
- Row count mismatch: Reported in comparison_results.json, verdict is ZOMBIE, not error.

### No error for ZOMBIE verdict
- ZOMBIE is not an error, it is a valid result. Exit code 1, not 2.

## Testing Strategy

### Unit tests (pytest)

**tests/test_schema.py:**
- load_schema: valid schema, invalid schema, missing fields.

**tests/test_copybook.py:**
- parse_cobol_structure: extract constants, paragraphs, branches.

**tests/test_trace.py:**
- parse_trace: simple trace, trace with copybooks, empty trace.

**tests/test_gen.py:**
- generate_cases: deterministic (same seed twice), correct case count, rounding ties count.

**tests/test_compare.py:**
- Normalization: decimal scale, string trim, idempotent (Hypothesis property).
- Comparison: equal outputs, divergent field, row count mismatch.

**tests/test_verdict.py:**
- compute_verdict: 0 divergences and matching return codes gives ALIVE, 1+ case divergences gives ZOMBIE, return code mismatch only gives ZOMBIE with 0 cases, both gives ZOMBIE with cases count plus return code note, sub-labels correct.

**tests/test_minimal_case.py:**
- select_minimal_case: smallest absolute numeric inputs, then case_id.

**tests/test_junit.py:**
- generate_junit_test: template correctness, can compile (skip if javac missing).

### Property-based tests (Hypothesis)

**tests/test_compare.py:**
```python
@given(st.decimals(allow_nan=False, allow_infinity=False))
def test_normalize_decimal_never_changes_value(value):
    """Normalization never changes the numeric value when both valid."""
    scale = 2
    try:
        normalized = normalize_decimal(value, scale)
        # If normalization succeeded, the value must be equal
        assert Decimal(value) == Decimal(normalized)
    except ValueError:
        # Value has extra non-zero decimals, divergent as expected
        pass

@given(st.decimals(allow_nan=False, allow_infinity=False, places=5))
def test_extra_decimals_divergent(value):
    """Values with non-zero digits beyond schema scale are divergent."""
    scale = 2
    value_str = str(value)
    # If value has non-zero digit at position 3+ after decimal
    if '.' in value_str:
        decimals = value_str.split('.')[1]
        if len(decimals) > scale and any(d != '0' for d in decimals[scale:]):
            # Must be reported as divergent
            with pytest.raises(ValueError):
                normalize_decimal(value_str, scale)

@given(st.text())
def test_normalize_string_idempotent(value):
    normalized = normalize_string(value)
    normalized_again = normalize_string(normalized)
    assert normalized == normalized_again
```

### End-to-end tests

**tests/test_e2e.py:**

```python
@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not found")
@pytest.mark.skipif(not shutil.which("javac"), reason="javac not found")
def test_e2e_alive():
    """Run engine on correct Java, assert ALIVE."""
    exit_code = verify_command(
        cobol="samples/credit-fees/CREDIT-FEES.cob",
        copybooks="samples/credit-fees/copybooks",
        java="samples/credit-fees/java/CreditFees.java",
        schema="samples/credit-fees/schema.json",
        cases=200,  # faster test
        seed=42
    )
    assert exit_code == 0
    
    # Check verdict.json
    verdict = json.load(open("runs/.../verdict.json"))
    assert verdict["status"] == "ALIVE"
    assert verdict["cases_divergent"] == 0

@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not found")
@pytest.mark.skipif(not shutil.which("javac"), reason="javac not found")
def test_e2e_zombie():
    """Run engine on HALF_EVEN variant, assert ZOMBIE."""
    # Generate variant first
    generate_half_even_variant(
        "samples/credit-fees/java/CreditFees.java",
        "build/test_temp/CreditFees_F01.java"
    )
    
    exit_code = verify_command(
        cobol="samples/credit-fees/CREDIT-FEES.cob",
        copybooks="samples/credit-fees/copybooks",
        java="build/test_temp/CreditFees_F01.java",
        schema="samples/credit-fees/schema.json",
        cases=200,
        seed=42
    )
    assert exit_code == 1
    
    verdict = json.load(open("runs/.../verdict.json"))
    assert verdict["status"] == "ZOMBIE"
    assert verdict["cases_divergent"] > 0
    
    # Check failure report exists
    assert os.path.exists("runs/.../failure_report.json")
    assert os.path.exists("runs/.../ZombieRegressionTest.java")
```

### Acceptance tests (slow, excluded from make test)

**tests/test_acceptance.py:**

```python
@pytest.mark.slow
@pytest.mark.parametrize("seed", [42, 123, 456, 789, 1011, 1213, 1415, 1617, 1819, 2021])
def test_acceptance_no_false_zombie(seed):
    """10 runs of correct Java must give ALIVE."""
    exit_code = verify_command(
        cobol="samples/credit-fees/CREDIT-FEES.cob",
        copybooks="samples/credit-fees/copybooks",
        java="samples/credit-fees/java/CreditFees.java",
        schema="samples/credit-fees/schema.json",
        cases=2000,
        seed=seed
    )
    assert exit_code == 0

@pytest.mark.slow
@pytest.mark.parametrize("seed", [42, 123, 456, 789, 1011, 1213, 1415, 1617, 1819, 2021])
def test_acceptance_no_false_alive(seed):
    """10 runs of HALF_EVEN variant must give ZOMBIE."""
    generate_half_even_variant(
        "samples/credit-fees/java/CreditFees.java",
        "build/test_temp/CreditFees_F01.java"
    )
    
    exit_code = verify_command(
        cobol="samples/credit-fees/CREDIT-FEES.cob",
        copybooks="samples/credit-fees/copybooks",
        java="build/test_temp/CreditFees_F01.java",
        schema="samples/credit-fees/schema.json",
        cases=2000,
        seed=seed
    )
    assert exit_code == 1

@pytest.mark.slow
def test_acceptance_half_even_calibration():
    """HALF_EVEN variant diverges on 80 to 120 of 2,000 cases with default seed 42.
    
    This is a calibration target for the tie generator, not a guarantee."""
    generate_half_even_variant(
        "samples/credit-fees/java/CreditFees.java",
        "build/test_temp/CreditFees_F01.java"
    )
    
    exit_code = verify_command(
        cobol="samples/credit-fees/CREDIT-FEES.cob",
        copybooks="samples/credit-fees/copybooks",
        java="build/test_temp/CreditFees_F01.java",
        schema="samples/credit-fees/schema.json",
        cases=2000,
        seed=42
    )
    assert exit_code == 1
    
    verdict = json.load(open("runs/.../verdict.json"))
    assert 80 <= verdict["cases_divergent"] <= 120, \
        f"Expected 80-120 divergences for calibration, got {verdict['cases_divergent']}"
```

**pytest.ini:**
```ini
[pytest]
markers =
    slow: marks tests as slow (excluded by default)
```

**Makefile:**
```makefile
test:
	pytest -v -m "not slow"

acceptance:
	pytest -v -m slow
```

### Test skips

All tests that require cobc, javac, or JUnit jars skip with clear reason:
```python
@pytest.mark.skipif(not shutil.which("cobc"), reason="cobc not found")
```

### Test timeouts

All subprocess calls in tests use timeout parameter:
```python
subprocess.run([...], timeout=10)
```

## Performance Budget

Target: 2,000 cases under 60 seconds wall-clock including compilation.

Estimated breakdown (dev machine: macOS, 8 cores, 16 GB RAM):

| Step | Time (s) | Notes |
|------|----------|-------|
| Input validation | 0.1 | File I/O |
| Schema parsing | 0.1 | JSON load |
| COBOL structure parsing | 0.5 | Regex on 390 lines |
| Case generation | 2.0 | 2000 rows with boundaries and ties |
| COBOL reference compile | 2.0 | cobc on 390 lines + 3 copybooks |
| COBOL instrumented compile | 2.5 | cobc with -ftraceall |
| Java compile | 1.0 | javac on 500 lines |
| COBOL reference run | 15.0 | 2000 records, file I/O |
| Java run | 10.0 | 2000 records, one JVM |
| COBOL instrumented run | 20.0 | Trace overhead, 2000 records |
| Trace parsing | 1.0 | 2000 records * avg 15 lines each |
| CSV comparison | 3.0 | 2000 rows * 4 output columns |
| Coverage computation | 0.5 | Match 30k trace lines to 28 branches |
| Failure report (if ZOMBIE) | 2.0 | Re-run 1 case, generate JUnit test |
| Store results | 0.5 | Write JSON files |
| Margin | 0.8 | |
| **Total** | **61.0** | **Slightly over, acceptable** |

COBOL and Java runs are the main costs. Optimization opportunities:
- Parallel COBOL and Java runs (save 10s).
- Parallel instrumented run with comparison (save 15s).
- With parallelization: under 40 seconds.

Decision: implement sequential first (simpler), parallelize if acceptance test fails timing.

**Trace size:** The instrumented run trace for 2,000 records is large (about 100 trace lines per record = 200,000 lines). The trace parser streams the file and keeps only (source, line) counts in memory, not the full trace. Measure in the acceptance test and print each step's time with `--timings` flag.

## CLI and Makefile Integration

### CLI command
```bash
python -m coroner verify \
  --cobol samples/credit-fees/CREDIT-FEES.cob \
  --copybooks samples/credit-fees/copybooks \
  --java samples/credit-fees/java/CreditFees.java \
  --schema samples/credit-fees/schema.json \
  --cases 2000 \
  --seed 42
```

**Output:**
```
ALIVE: PASS: business behavior preserved on 2000 cases
Paragraph coverage: 15/15
Branch coverage: 28/28
Run ID: a3f5d2c8e1b4
Results: runs/a3f5d2c8e1b4/
```

**Exit code:** 0 (ALIVE), 1 (ZOMBIE), 2 (error)

### Makefile targets

**make demo:** Run correct Java, expect ALIVE.
```makefile
demo:
	python -m coroner verify \
	  --cobol samples/credit-fees/CREDIT-FEES.cob \
	  --copybooks samples/credit-fees/copybooks \
	  --java samples/credit-fees/java/CreditFees.java \
	  --schema samples/credit-fees/schema.json \
	  --cases 2000
```

**make zombie:** Generate HALF_EVEN variant, run, expect ZOMBIE.
```makefile
zombie:
	mkdir -p samples/credit-fees/java/variants
	python -c "from coroner.catalog.legacy_variant import generate_half_even_variant; \
	           generate_half_even_variant('samples/credit-fees/java/CreditFees.java', \
	                                       'samples/credit-fees/java/variants/CreditFees_F01.java')"
	python -m coroner verify \
	  --cobol samples/credit-fees/CREDIT-FEES.cob \
	  --copybooks samples/credit-fees/copybooks \
	  --java samples/credit-fees/java/variants/CreditFees_F01.java \
	  --schema samples/credit-fees/schema.json \
	  --cases 2000
```

**make junit-jars:** Download JUnit jars with SHA-256 verification.
```makefile
junit-jars:
	mkdir -p build/junit
	# TODO: versions and checksums in task that implements this
	# Example:
	# curl -L -o build/junit/junit-jupiter-api-5.10.1.jar https://...
	# echo "SHA256 ..." | shasum -a 256 -c
```

These targets replace the S0 placeholders ("not available yet" exit 2).

## Open Questions for Owner

1. **Hypothesis deterministic generation:** Use Hypothesis with `st.register_random` (risk: version changes) or `random.Random(seed)` (guaranteed deterministic)? Recommendation: random.Random for runtime, Hypothesis for tests only.

2. **Return code comparison:** Requirement 5.3 says run-level return codes are compared. The design compares run-level return codes (one per program in batch mode) and flags a mismatch as divergent. For single-case re-runs (minimal case, failure report), case-specific return codes are compared. Is this interpretation correct?
