# Certificate Requirements

## 1. Overview

The Coroner Certificate is a reproducible run record that allows offline verification of a differential run. It records every input hash, tool version, seed, verdict and coverage metric so the run can be replayed and validated without network access.

The certificate is never a guarantee or formal proof. It states only what was observed: "business behavior preserved on N cases" or "business behavior diverged on M cases".

## 2. Functional Requirements

### 2.1 Certificate Generation

**Req 1.1**: After writing `verdict.json`, the run form of `coroner verify` writes `certificate.json` to `runs/<run_id>/` with UTF-8 encoding, LF line endings and sorted keys.

**Req 1.2**: The certificate contains:
- `certificate_format`: integer 1
- `title`: "Coroner Certificate"
- `statement`: "Reproducible run record: <sub_label>. Validated under GnuCOBOL 3.x. This is not a formal proof of equivalence."
- every field from `inputs.json`: `cobol_file_sha256`, `copybook_hashes`, `java_file_sha256`, `schema_file_sha256`, `cases_file_sha256`, `cases_file_encoding`, `cases_file_line_ending`, `case_count`, `random_seed`, `python_version`, `cobc_version`, `javac_version`, `java_version`, `coroner_version`, `comparison_engine_sha256`, `timestamp`
- the file paths: `cobol_file`, `copybook_dir`, `java_file`, `schema_file`, `cases_file` (relative to repository root when inside it, absolute otherwise)
- verdict fields: `status`, `sub_label`, `cases_total`, `cases_divergent`
- return codes: `run_return_codes` (COBOL and Java exit statuses)
- coverage: `paragraph_coverage_reached`, `paragraph_coverage_total`, `branch_coverage_reached`, `branch_coverage_total`
- when ZOMBIE: `minimal_case_id`, `divergent_fields`
- `certificate_sha256`: SHA-256 hex digest of the canonical JSON (sorted keys, compact separators `{"separators": (",", ":")}`) of every other field

**Req 1.3**: The sub_label in the statement follows D-20: "PASS: business behavior preserved on N cases" or "FAIL: business behavior diverged on M cases".

**Req 1.4**: The certificate is never worded as "certified equivalent", "proven", "guaranteed" or "formal proof" (no-formal-proof.md, D-24).

### 2.2 Certificate Replay

**Req 2.1**: When the CLI receives exactly one argument ending in `.json`, it treats it as a certificate replay (D-36). The run form options `--cobol`, `--java`, `--schema` are not used.

**Req 2.2**: Replay steps (offline):
1. Load the certificate JSON.
2. Recompute `certificate_sha256` from all other fields in canonical form. If it differs from the recorded hash, print "Certificate: INVALID: certificate content was modified" and exit 3.
3. Check the SHA-256 of the COBOL source file at the recorded path against `cobol_file_sha256`. Mismatch: "Certificate: INVALID: COBOL file hash mismatch" and exit 3.
4. Check the SHA-256 of each copybook in the recorded directory against `copybook_hashes`. Mismatch: "Certificate: INVALID: copybook hash mismatch for <file>" and exit 3.
5. Check the SHA-256 of the Java source file against `java_file_sha256`. Mismatch: "Certificate: INVALID: Java file hash mismatch" and exit 3.
6. Check the SHA-256 of the schema file against `schema_file_sha256`. Mismatch: "Certificate: INVALID: schema file hash mismatch" and exit 3.
7. Check the SHA-256 of the cases file against `cases_file_sha256`. Mismatch: "Certificate: INVALID: cases file hash mismatch" and exit 3.
8. Re-run the COBOL reference build, the coverage build and the Java program on the stored cases file from the certificate (never regenerate cases). Compare outputs with the engine.
9. Recompute the verdict, divergence count, return codes and coverage metrics.
10. If any replayed metric differs from the recorded value, print "Certificate: INVALID: replay mismatch (<field_name>)" and exit 3.
11. If tool versions differ (`python_version`, `cobc_version`, `javac_version`, `java_version`, `coroner_version`, `comparison_engine_sha256`), print a warning "Warning: <tool> version differs (recorded: X, current: Y)" to stderr but continue.
12. Print:
    - "Certificate: VALID" or "Certificate: INVALID: <reasons>"
    - The verdict line with sub-label
    - "Cases: N"
    - "Divergences: M"
    - "Paragraph coverage X/Y"
    - "Branch coverage (Coroner definition) X/Y"
    - "Replayed offline from <cases_file>"

**Req 2.3**: Exit codes for replay:
- 0: certificate valid, verdict ALIVE
- 1: certificate valid, verdict ZOMBIE
- 3: certificate invalid
- 2: error (file not found, JSON parse error, etc.)

**Req 2.4**: The CLI placeholder "not implemented yet" for certificate replay is removed.

## 3. Non-Functional Requirements

**Req 3.1**: A certificate with modified content (any field changed, hash not recomputed) is detected as INVALID.

**Req 3.2**: A certificate with a modified cases file (one byte changed) is detected as INVALID.

**Req 3.3**: A certificate whose recorded metrics were edited and its `certificate_sha256` recomputed is detected as INVALID when the replay metrics differ.

**Req 3.4**: Replay uses only the stored cases file. It never calls the generator.

**Req 3.5**: Replay is offline. No network requests.

## 4. Test Coverage

- Generate a certificate from a 200-case ALIVE run (correct Java), replay it: VALID, exit 0.
- Generate a certificate from a 200-case ZOMBIE run (legacy variant), replay it: VALID, exit 1.
- Edit one field of a certificate copy (e.g., change `case_count`), replay: INVALID content, exit 3.
- Copy a certificate, copy its cases file, change one byte of the cases file, replay the certificate: INVALID cases file hash, exit 3.
- Copy a certificate, edit `cases_divergent` and recompute `certificate_sha256`, replay: INVALID replay mismatch, exit 3.

## 5. Acceptance Criteria

- `make demo` writes `certificate.json` with all required fields and a valid `certificate_sha256`.
- `python -m coroner verify runs/<run_id>/certificate.json` replays the certificate and prints "Certificate: VALID" with the verdict, coverage and "Replayed offline from ...".
- All certificate tests pass with `pytest`.
- No wording uses "certified equivalent", "proven", "guaranteed" or claims a formal proof.
