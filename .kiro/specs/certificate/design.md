# Certificate Design

## 1. Architecture

Certificate generation and replay are implemented in `coroner/certificate.py`. The CLI (`coroner/cli.py`) detects a single `.json` argument and routes to replay mode instead of run mode.

```
Run mode:
  verify() --> generate_certificate() --> runs/<run_id>/certificate.json

Replay mode:
  verify(certificate.json) --> replay_certificate() --> re-run engine --> validate
```

## 2. Data Structures

### 2.1 Certificate Schema

```python
{
    "certificate_format": 1,
    "title": "Coroner Certificate",
    "statement": "Reproducible run record: <sub_label>. Validated under GnuCOBOL 3.x. This is not a formal proof of equivalence.",
    
    # From inputs.json
    "cobol_file_sha256": str,
    "copybook_hashes": {filename: sha256_hex, ...},
    "java_file_sha256": str,
    "schema_file_sha256": str,
    "cases_file_sha256": str,
    "cases_file_encoding": str,
    "cases_file_line_ending": str,
    "case_count": int,
    "random_seed": int,
    "python_version": str,
    "cobc_version": str,
    "javac_version": str,
    "java_version": str,
    "coroner_version": str,
    "comparison_engine_sha256": str,
    "timestamp": str,
    
    # File paths
    "cobol_file": str,
    "copybook_dir": str,
    "java_file": str,
    "schema_file": str,
    "cases_file": str,
    
    # Verdict
    "status": "ALIVE" | "ZOMBIE",
    "sub_label": str,
    "cases_total": int,
    "cases_divergent": int,
    "run_return_codes": {"cobol": int, "java": int},
    
    # Coverage
    "paragraph_coverage_reached": int,
    "paragraph_coverage_total": int,
    "branch_coverage_reached": int,
    "branch_coverage_total": int,
    
    # ZOMBIE only
    "minimal_case_id": str | null,
    "divergent_fields": [str] | null,
    
    # Self-verification
    "certificate_sha256": str
}
```

### 2.2 Canonical JSON Form

For `certificate_sha256` computation:
- Sort all keys alphabetically
- Compact separators: `separators=(",", ":")`
- No trailing whitespace or newlines
- UTF-8 encoding

The hash excludes the `certificate_sha256` field itself.

## 3. Components

### 3.1 Certificate Generation (`generate_certificate`)

**Input**:
- `run_id`: str
- `inputs`: dict (from `inputs.json`)
- `verdict`: Verdict
- `coverage`: dict (from `coverage_report.json`)
- `failure_report`: dict or None (from `failure_report.json` when ZOMBIE)
- File paths: `cobol_file`, `copybook_dir`, `java_file`, `schema_file`

**Logic**:
1. Load `inputs.json`, `verdict.json`, `coverage_report.json` from `runs/<run_id>/`.
2. If ZOMBIE, load `failure_report.json` for `minimal_case_id` and `divergent_fields`.
3. Construct the statement: `f"Reproducible run record: {verdict.sub_label}. Validated under GnuCOBOL 3.x. This is not a formal proof of equivalence."`
4. Build the certificate dict with all required fields except `certificate_sha256`.
5. Make file paths relative to repository root when inside it (use `os.path.relpath` if `os.path.commonpath` succeeds).
6. Compute the canonical JSON: `json.dumps(cert, sort_keys=True, separators=(",", ":"))`
7. Compute `certificate_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()`
8. Add `certificate_sha256` to the certificate dict.
9. Write to `runs/<run_id>/certificate.json` with `json.dump(cert, f, indent=2, sort_keys=True)` and LF.

**Output**: `certificate.json` file

### 3.2 Certificate Replay (`replay_certificate`)

**Input**: `certificate_path`: Path to `certificate.json`

**Logic**:

**Step 1: Load and verify content hash**
- Load the certificate JSON.
- Extract `certificate_sha256_recorded`.
- Remove `certificate_sha256` from the dict.
- Compute canonical JSON and its SHA-256.
- If mismatch: return `ReplayResult(valid=False, reason="certificate content was modified", ...)`

**Step 2: Verify file hashes**
- Load each file from the recorded path.
- Compute SHA-256 and compare:
  - `cobol_file` against `cobol_file_sha256`
  - Each copybook against `copybook_hashes[filename]`
  - `java_file` against `java_file_sha256`
  - `schema_file` against `schema_file_sha256`
  - `cases_file` against `cases_file_sha256`
- If any mismatch: return `ReplayResult(valid=False, reason="<file> hash mismatch", ...)`

**Step 3: Re-run the engine**
- Call the engine pipeline with:
  - `cobol_file`, `copybook_dir`, `java_file`, `schema_file` from the certificate
  - `cases_file` from the certificate (never regenerate)
  - No seed (cases already exist)
- Collect: verdict, cases_total, cases_divergent, return codes, coverage, minimal_case_id, divergent_fields

**Step 4: Compare metrics**
- Compare replayed values against recorded certificate values:
  - `status`, `cases_total`, `cases_divergent`
  - `run_return_codes.cobol`, `run_return_codes.java`
  - `paragraph_coverage_reached`, `paragraph_coverage_total`
  - `branch_coverage_reached`, `branch_coverage_total`
  - `minimal_case_id`, `divergent_fields` (when ZOMBIE)
- If any differ: return `ReplayResult(valid=False, reason="replay mismatch (<field>)", ...)`

**Step 5: Check tool versions**
- Compare current tool versions against recorded versions.
- If any differ: add to `warnings` list (not invalid).

**Step 6: Return result**
- Return `ReplayResult(valid=True, verdict=..., coverage=..., cases_file=..., warnings=...)`

**Output**: `ReplayResult` with validation status, verdict, coverage, warnings

### 3.3 ReplayResult Data Structure

```python
@dataclass
class ReplayResult:
    valid: bool
    reason: str  # empty if valid, error message if invalid
    verdict: Optional[Verdict]
    cases_total: int
    cases_divergent: int
    paragraph_coverage_reached: int
    paragraph_coverage_total: int
    branch_coverage_reached: int
    branch_coverage_total: int
    cases_file: str
    warnings: list[str]
```

### 3.4 CLI Integration

**Detection**: In `verify()` command:
```python
if len(sys.argv) == 3 and sys.argv[2].endswith('.json'):
    # Replay mode
    result = replay_certificate(sys.argv[2])
    print_replay_result(result)
    sys.exit(0 if result.valid and result.verdict.status == "ALIVE" else 
             1 if result.valid and result.verdict.status == "ZOMBIE" else 3)
else:
    # Run mode
    ...
```

**Print function**: `print_replay_result(result: ReplayResult)`
- If invalid: print `f"Certificate: INVALID: {result.reason}"`, exit 3
- Print warnings to stderr
- Print:
  ```
  Certificate: VALID
  <verdict.status>: <verdict.sub_label>
  Cases: <cases_total>
  Divergences: <cases_divergent>
  Paragraph coverage <paragraph_reached>/<paragraph_total>
  Branch coverage (Coroner definition) <branch_reached>/<branch_total>
  Replayed offline from <cases_file>
  ```

## 4. Error Handling

- Certificate file not found: exit 2 with "Error: certificate file not found"
- Certificate JSON invalid: exit 2 with "Error: invalid certificate JSON"
- Missing field in certificate: exit 2 with "Error: missing field <field>"
- File from certificate not found: exit 3 with "Certificate: INVALID: <file> not found"
- File hash mismatch: exit 3 with "Certificate: INVALID: <file> hash mismatch"
- Content hash mismatch: exit 3 with "Certificate: INVALID: certificate content was modified"
- Replay metric mismatch: exit 3 with "Certificate: INVALID: replay mismatch (<field>)"

## 5. Path Handling

When generating a certificate:
- If a file is inside the repository (determined by `git rev-parse --show-toplevel` or by checking if paths share a common prefix with the current directory), store relative paths.
- Otherwise, store absolute paths.

When replaying:
- Resolve relative paths from the current directory.
- Absolute paths are used as-is.

## 6. Testing Strategy

**Unit tests** (`tests/test_certificate.py`):
- `test_generate_certificate_alive`: 200-case run, check all fields present, verify `certificate_sha256`.
- `test_generate_certificate_zombie`: 200-case run with legacy variant, check minimal_case_id and divergent_fields.
- `test_replay_valid_alive`: Replay a generated ALIVE certificate, verify exit 0.
- `test_replay_valid_zombie`: Replay a generated ZOMBIE certificate, verify exit 1.
- `test_replay_invalid_content`: Edit one field, verify exit 3 with "certificate content was modified".
- `test_replay_invalid_cases_file`: Change one byte of cases file, verify exit 3 with "cases file hash mismatch".
- `test_replay_invalid_metrics`: Edit divergence count, recompute hash, verify exit 3 with "replay mismatch".

**Integration test**:
- `make demo`, then replay its certificate with `python -m coroner verify runs/<run_id>/certificate.json`.

## 7. Dependencies

No new dependencies. Uses:
- `json` (standard library)
- `hashlib` (standard library)
- Existing engine modules: `run`, `compare`, `diag`, `verdict`, `store`

## 8. Acceptance

- Certificate generated after every run with all required fields.
- Certificate replay validates hashes, re-runs engine, detects tampering.
- Exit codes correct: 0 (VALID+ALIVE), 1 (VALID+ZOMBIE), 3 (INVALID), 2 (ERROR).
- All tests pass.
- No forbidden wording in statement field.
