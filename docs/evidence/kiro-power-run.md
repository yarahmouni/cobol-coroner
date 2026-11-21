# Kiro power "coroner-audit" in the Kiro IDE on Windows

Evidence of one real run, 2026-11-21. Every value below is quoted from the Kiro chat export of that session or read from the screenshots in `kiro-power-run/`.
User names, machine names and local Windows paths are redacted. Screenshots are cropped to the IDE panes; the list of other available powers, the status bar and the taskbar are masked or cut.

## Environment

| Item | Value | Source |
|---|---|---|
| Kiro IDE | 1.4.178 (user setup), VSCode Version 1.131.0, commit 5cce6a055314de3c7ceccf21ba521293b2c4dca9 | Help > About, `05-kiro-about.png` |
| Kiro Agent | 0.66.102-hotfix.1 | Help > About |
| OS | Windows_NT x64 10.0.19045 (Windows 10 Pro) | Help > About |
| Docker | Docker Desktop, engine 29.9.2, linux/amd64 | `docker version` on the same PC |
| Image | `ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8` | `powers/coroner-audit/mcp.json` |
| Chat session | "Get Started With Coroner-Audit Power", agent mode `vibe`, model `auto`, 17:16:25Z to 17:22:11Z | chat export `session.json` |

Nothing for Coroner was installed on the PC except Docker Desktop and the pulled image.

## 1. The power is installed and the server runs from the image

`01-powers-panel-and-power-details.png` shows the Powers panel with `coroner-audit` under INSTALLED, and the power page with "Try power", "Uninstall" and "Check for updates".

Asked to start with the power, Kiro reported:

> The `kiro_powers` tool isn't available in this session. I'll load the power's overview with `load_resource` instead.

It then called `load_resource` with `power::coroner-audit::overview` (3064 ms). The result listed the server and its 7 tools, as quoted from the export (bullet glyphs are broken in the export and shown here as "-"):

```
**Server: `coroner`**

- **run_differential_check** - Run differential verification on COBOL and Java programs
- **get_verdict** - Get verdict for a run
- **get_failure_report** - Get failure report for a ZOMBIE run
- **get_detection_matrix** - Get the trap catalog detection matrix
- **export_junit_test** - Export JUnit regression test for a ZOMBIE run
- **generate_certificate** - Generate or regenerate certificate for a run
- **verify_certificate** - Verify and replay a certificate offline

**Steering Files:** audit-workflow.md
```

Kiro also loaded `power::coroner-audit::steering::audit-workflow.md` (4346 ms).

In the IDE, each tool call is titled `@coroner-audit/coroner/<tool>`, and its id is `power::coroner-audit::tool::coroner::<tool>`. The power files therefore use the bare tool names, not `@coroner/`.

## 2. Case 1 audit through the power

User prompt (quoted):

> Yes, run it, but on Case 1 instead of credit-fees. The workspace is the same repository as /app in the image, so read the file names in samples/traps/T1-ebcdic-match-merge/ locally first (COBOL program, copybooks folder, schema.json and the faulty Java port), then call run_differential_check with those relative paths, seed 42 and 2000 cases. Then call get_verdict and get_failure_report on the returned run_id. Report only the measured values: run_id, status, cases_divergent, minimal case id, COBOL and Java outputs.

Kiro listed the folder with `Get-ChildItem -Recurse samples/traps/T1-ebcdic-match-merge` (exit code 0). The output gave absolute local paths, redacted here; relative to the workspace it listed `MATCH-MERGE.cob`, `schema.json`, `trap.json`, `copybooks/.gitkeep`, `fixtures/` (2 CSV files), `java/correct/MatchMerge.java` and `java/faulty/MatchMerge.java`.

### run_differential_check

Title `@coroner-audit/coroner/run_differential_check`, 37062 ms. Arguments:

```json
{
  "cobol": "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
  "copybooks": "samples/traps/T1-ebcdic-match-merge/copybooks",
  "java": "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java",
  "schema": "samples/traps/T1-ebcdic-match-merge/schema.json",
  "cases": 2000,
  "seed": 42
}
```

Result:

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

### get_verdict

Title `@coroner-audit/coroner/get_verdict`, arguments `{"run_id": "f584d5f35228"}`, 50670 ms. Result:

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

Title `@coroner-audit/coroner/get_failure_report`, arguments `{"run_id": "f584d5f35228"}`, 51981 ms. Result, with two long arrays shortened (marked `...`):

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
  "card": "Given the following input rows:\n  CASE-ID=GEN-001525, BRANCH=001, AMOUNT=6253.54\nWhen the COBOL reference and the Java port process this case\nThen COBOL writes row BRANCH=001 with SUBTOTAL=+0006253.54, Java does not\nThen Java writes row BRANCH=SUSP with SUBTOTAL=+0006253.54, COBOL does not\nCOBOL lines involved: ...MATCH-MERGE.cob:201 BALANCE-LINE. to ...MATCH-MERGE.cob:219 CONTINUE\n",
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

`input_row` is the first of the 17 original rows, not the minimal case. Kiro said so in its reply and used `minimal_case_rows`:

> The report's top-level `input_row` shows `BRANCH=D04, AMOUNT=5.88`. That is the first row of the generated case, and it doesn't match the `001` row that diverged. The `card` and `minimal_case_rows` use the `001` row, so I used that one.

`03-run-differential-check-result.png` shows Kiro's summary table: run_id `f584d5f35228`, ZOMBIE, 682 of 2000, coverage 6/8 and 22/30, minimal case `GEN-001525`, COBOL `BRANCH="001  "`, Java `BRANCH="SUSP "`, both `SUBTOTAL=+0006253.54`.

### verify_certificate

User prompt (quoted):

> Now call verify_certificate with path runs/f584d5f35228/certificate.json and report the measured result only.

Title `@coroner-audit/coroner/verify_certificate`, arguments `{"path": "runs/f584d5f35228/certificate.json"}`, 40133 ms. Result:

```json
{
  "valid": true,
  "reasons": [],
  "status": "ZOMBIE",
  "cases": 2000,
  "divergences": 682,
  "paragraph_coverage": "6/8",
  "branch_coverage": "22/30"
}
```

`04-verify-certificate-result.png` shows Kiro's report of this result.

## 3. Comparison with the expected figures

| Figure | Expected (measured on the Mac, same image and arguments) | Kiro IDE on Windows |
|---|---|---|
| run_id | `f584d5f35228` | `f584d5f35228` |
| status | ZOMBIE | ZOMBIE |
| cases_divergent of cases_total | 682 of 2000 | 682 of 2000 |
| coverage | 6/8, 22/30 | 6/8, 22/30 |
| minimal case | `GEN-001525`, one row: branch 001, 6253.54; COBOL `001  `, Java `SUSP ` | same |
| run_differential_check duration | 22.5 s | 37.1 s |

## 4. The power files Kiro adapted

Kiro edited the 4 files in `powers/coroner-audit/` in a separate chat ("Set Up Coroner Power", not part of the export). `02-kiro-file-changes.png` shows its summary. The changed files were checked against the original power by diff:

- `mcp.json` is byte for byte the Docker stdio configuration with the pinned image.
- Later change on the Mac (docs/reviews.md R-163): `mcp.json`, `POWER.md` and `README.md` now pin the image published on 2026-11-21 from commit c3358ed (sha256:0ca88a1f...501a4ad4). The run recorded in this file used the previous image (sha256:837503172e4d...b0ebe1e8), as quoted above.
- `POWER.md`: `kiro_version` removed from the front matter; Prerequisites now say Docker Desktop and the image; the `@coroner/` prefix replaced by bare tool names; `get_detection_matrix` states the error the image returns.
- `README.md`: install from the Powers panel; Prerequisites as in POWER.md; the `{REPOSITORY_ROOT}` Configuration section removed; the "Tested:" placeholder left unchanged.
- `steering/audit-workflow.md`: bare tool names.

## 5. Deviations and notes

- The `kiro_powers` tool named in the IDE's own "Try power" prompt was not available; Kiro used `load_resource`.
- The Case 1 prompt was not the exact prompt of the plan: it first asked Kiro to list the T1 folder locally. The tool call arguments are the planned ones.
- In the "Set Up" chat, the prompt said not to run any command. Kiro reported: "I did run one command before the edits, to read `kiro-prompt.txt`." Kiro read `kiro-prompt.txt`, the file holding the task, with that one command because the owner asked it to.
- In the same chat Kiro reported: "the pre-commit hook, which I turned on earlier". On the PC, the local git config has `core.hooksPath` set to `.githooks`. Nothing was committed on Windows.
- Each tool call needed explicit approval in the IDE (consent source `kiro-scope:untrusted-execution`, workspace not trusted). All 15 approvals in the export are "accept".
- The chat export breaks some non-ASCII characters (bullets show as a replacement glyph).
