# Coroner Audit Power

Independent behavioral audit of COBOL-to-Java migrations for any Kiro agent.

## Installation

Install it from the Kiro IDE Powers panel by adding this local folder.

## Prerequisites

Docker Desktop is the only prerequisite on the host. No GnuCOBOL, no JDK and no Python venv are needed on the host.

The MCP server starts from the published image over stdio:

```
docker run --rm -i --init ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211 python -m coroner.mcp
```

- The image is linux/amd64, so it needs an x86-64 machine.
- The image holds the repository at `/app`, and tool paths are relative to it, for example `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`. No volume is needed.
- Runs live inside the container for one chat session (`--rm`). A `run_id` from an earlier session is not found in a new one.

## Usage

In any Kiro chat or agent:

```
Call run_differential_check with:
- cobol: samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob
- copybooks: samples/traps/T1-ebcdic-match-merge/copybooks
- java: samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java
- schema: samples/traps/T1-ebcdic-match-merge/schema.json
- cases: 2000
- seed: 42
```

See `POWER.md` for complete documentation of all 7 tools.

## What it does

Runs the COBOL program and its Java port on the same test cases, compares outputs field by field, and returns:
- **ALIVE**: Business behavior preserved on N cases
- **ZOMBIE**: Diverged on M cases, with the minimal failing case and fix guidance
- **ERROR**: Reference did not run

## What it never does

- Never translates COBOL (it only audits existing Java ports)
- Never edits code
- Never claims formal equivalence

## Testing

Tested 2026-11-21 in the Kiro IDE 1.4.178 on Windows 10 x64 with Docker 29.9.2. Through the installed power, Kiro called run_differential_check (run f584d5f35228, ZOMBIE, 682 of 2000), get_verdict, get_failure_report (GEN-001525) and verify_certificate (valid true). Evidence: docs/evidence/kiro-power-run.md. The Windows run used the previous image (sha256:837503172e4d...b0ebe1e8). The power now pins the image published on 2026-11-22 from commit 2c2a11b (publish-image.yml run 45029885381). The statements that the same Case 1 audit gives the same run id (f584d5f35228) and that get_detection_matrix works with no volume were measured on the image of commit c3358ed (R-163). For the new image only the operator's local check (2026-11-22) was made: the deployment check gave the run ids f584d5f35228 and 29c15f04407b. No power run is claimed on the new image.

## License

Same as COBOL Coroner: Apache-2.0
