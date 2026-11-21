# Pre-existing and third-party code

This file tells the judges which parts of the repository were not written for this project, so that new work can be told from reused work. Each statement names the file it comes from. Decision D-63 in [`docs/decisions.md`](decisions.md) requires this file and says it states "what existed before 2026-10-30 (nothing of COBOL Coroner itself; third-party samples such as CardDemo if used, with their licenses)".

## 1. Project code and the exceptions

### Start of the work

- The history of this repository was rewritten early in the project (`docs/reviews.md`, R-06 and R-19), so the published history starts from the rewritten first commit.
- A judge can read the dates of the first published commits with `git log --reverse --format="%ad %s" --date=short | head -3`. Real output:

```
2026-11-15 Initial commit: COBOL Lazarus project kit
2026-11-15 S0 task 3: toy COBOL program with IF/ELSE
2026-11-15 S0 task 4: capture real GnuCOBOL trace fixture (line numbers present)
```

- D-63 gives 2026-10-30 as the hackathon start date. The dates above are after it.

### What was written during the hackathon

The following were written after the first commit. Nothing in these folders was copied from an earlier project, apart from the exceptions listed below.

- `coroner/` (engine, CLI, MCP server, UI, gate, hooks)
- `tests/`
- `scripts/`
- `.kiro/` (specs, steering, skills, agents, settings)
- `docs/`
- `samples/credit-fees/`
- `samples/traps/` (T1 to T5 COBOL programs, faulty and correct Java ports, fixtures; T6 is a placeholder)
- `samples/independence/`
- `samples/carddemo-cbact04c/` except the files listed in section 2
- `smoke/`, `Dockerfile`, `Makefile`, `docker-compose*.yml`, `Jenkinsfile`, `.github/workflows/`, `pyproject.toml`

### Exceptions inside the folders above

These files contain code that was not written during the hackathon. They are described in section 2.

| File | What it is |
|---|---|
| `samples/carddemo-cbact04c/upstream/` (11 files) | AWS CardDemo files, kept byte for byte |
| `samples/carddemo-cbact04c/adapted/CBACT04C.cob` | AWS CardDemo program with one 8-line block replaced |
| `coroner/ui/static/htmx.min.js` | htmx 2.0.4, vendored |
| `LICENSE`, `samples/carddemo-cbact04c/LICENSE` | Apache License 2.0 text |

## 2. Third-party code and data included in the repository

### AWS CardDemo (CBACT04C)

Source: https://github.com/aws-samples/aws-mainframe-modernization-carddemo, commit `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e` (2025-10-16), as stated in [`samples/carddemo-cbact04c/NOTICE`](../samples/carddemo-cbact04c/NOTICE) and [`samples/carddemo-cbact04c/README.md`](../samples/carddemo-cbact04c/README.md). Licence: Apache License 2.0 ([`samples/carddemo-cbact04c/LICENSE`](../samples/carddemo-cbact04c/LICENSE)). Copyright line in NOTICE: "Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved."

Required statement (D-62, `docs/decisions.md`): Uses AWS's open-source CardDemo sample (Apache 2.0). Not affiliated with or endorsed by AWS.

Scope (D-62): only the interest calculation of CBACT04C. The sample README words it as "one bounded interest-calculation path".

**Verbatim files.** `samples/carddemo-cbact04c/upstream/` holds:

- `cbl/CBACT04C.cbl`
- `cpy/CVACT01Y.cpy`, `cpy/CVACT03Y.cpy`, `cpy/CVTRA01Y.cpy`, `cpy/CVTRA02Y.cpy`, `cpy/CVTRA05Y.cpy`
- `data/acctdata.txt`, `data/cardxref.txt`, `data/discgrp.txt`, `data/tcatbal.txt`

`docs/reviews.md` R-119 records that these files were compared with the files downloaded at that commit and are identical. `.gitattributes` has the rule `samples/carddemo-cbact04c/upstream/** -text`, because `tcatbal.txt` mixes CRLF and LF line endings and Git must store it unchanged (R-119).

**Changed file.** `samples/carddemo-cbact04c/adapted/CBACT04C.cob` is the upstream program with one change. A `diff` of `upstream/cbl/CBACT04C.cbl` against it, run for this document, reports a single block, lines 614 to 621 of the upstream file. The eight lines `MOVE FUNCTION CURRENT-DATE TO COBOL-TS` and the seven `MOVE COB-... TO DB2-...` lines that follow are replaced by seven lines that take the date from `PARM-DATE` and use a fixed time of 12:00:00 (`MOVE '12' TO DB2-HH`, and so on). The `diff` reports no other difference, so the AWS copyright header and `AUTHOR. AWS.` are unchanged. The change is documented in [`samples/carddemo-cbact04c/CHANGES.md`](../samples/carddemo-cbact04c/CHANGES.md) ("Only change to the upstream program"). The change notice is in CHANGES.md and not inside the COBOL file.

**Build option, not a source change.** Every program of the sample is compiled with `cobc -fsign=EBCDIC` (CHANGES.md, "Build options"; `samples/carddemo-cbact04c/schema.json`, key `cobc_flags`).

**Added files** (CHANGES.md, "Additions (new files)"): `adapted/RUN-CBACT04C.cob`, `adapted/CEE3ABD.cob`, `adapted/LOAD-FILES.cob`, `adapted/DUMP-ACCT.cob`, `adapted/HARNESS-CBACT04C.cob`, `tools/dataset_to_row.py`, `harness-check/`, `probe/sign-convention/SIGN-PROBE.cob`, `schema.json`, `generator.py`, `Makefile`, `datasets/`. These files were written for this project and carry no AWS header. The header of `RUN-CBACT04C.cob` says it is a driver added for the COBOL Coroner audit, under Apache-2.0 like the repository. `datasets/` files and `probe/` outputs are produced from the CardDemo data formats and from runs of the adapted programs.

**Not a faithful z/OS emulation.** The sample README says: "This preserves the business logic under audit; it does not emulate z/OS VSAM."

**The Java port.** `samples/carddemo-cbact04c/java/Cbact04c.java` is not AWS code. A Kiro agent wrote it from the adapted COBOL (section 4).

### htmx

`coroner/ui/static/htmx.min.js`: htmx 2.0.4, licence 0BSD, SHA-256 `e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447` ([`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md), "Vendored JavaScript Libraries"). `tests/test_ui_vendor.py` checks the same hash.

### Licence texts

`LICENSE` is the Apache License 2.0, the licence of this project (`pyproject.toml`: `license = {text = "Apache-2.0"}`). `samples/carddemo-cbact04c/LICENSE` is the Apache License 2.0 kept for the CardDemo files.

### Files generated by tools, not written by hand

`tests/fixtures/sample_trace.txt` and `tests/fixtures/trace2/sample_trace.txt` are traces written by GnuCOBOL 3.2.0 (`-ftraceall`) when it ran the project's own test programs (`docs/reviews.md`, R-08 and R-41). The GnuCOBOL tool is described in section 3.

### Nothing else found

A case-insensitive search of the repository for the word "copyright" finds, outside this file and `docs/reviews.md` (which only quote the word), only the Apache licence texts and the CardDemo files named above: `LICENSE`, `samples/carddemo-cbact04c/LICENSE`, `samples/carddemo-cbact04c/NOTICE`, `samples/carddemo-cbact04c/README.md`, `samples/carddemo-cbact04c/adapted/CBACT04C.cob` and `samples/carddemo-cbact04c/upstream/cbl/CBACT04C.cbl`. A missing copyright line does not prove that a file is original, so this search is a check, not a guarantee.

## 3. Third-party software used but not included

None of the items below is committed. They are installed or downloaded when the Docker image is built or when the project is set up. Licences and versions are listed in [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md); the values below are read from the files named in each row.

| Software | Version or pin | Where it is fixed |
|---|---|---|
| Base image `python:3.12-slim-bookworm` | digest `sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df` | `Dockerfile` (both stages) |
| Debian packages | fixed Debian snapshot `20261119T000000Z` (`ARG DEBIAN_SNAPSHOT`), each package pinned to an exact version | `Dockerfile` |
| OpenJDK 17 | `openjdk-17-jdk-headless=17.0.21+9-1~deb12u1` | `Dockerfile`, runtime stage |
| GnuCOBOL | 3.2 (built from `https://ftp.gnu.org/gnu/gnucobol/gnucobol-3.2.tar.xz`), SHA-256 `3bb48af46ced4779facf41fdc2ee60e4ccb86eaa99d010b36685315df39c2ee2`, checked with `sha256sum -c` | `Dockerfile`, builder stage |
| Other Debian packages | build-essential 12.9, xz-utils 5.4.1-1+deb12u2, libgmp-dev 2:6.2.1+dfsg1-1.1, libdb-dev 5.3.2, libncurses-dev 6.4-4, libgmp10 2:6.2.1+dfsg1-1.1, libdb5.3 5.3.28+dfsg2-1, libncurses6 6.4-4, gcc 4:12.2.0-3, libc6-dev 2.36-9+deb12u14, git 1:2.39.5-0+deb12u3, make 4.3-4.1 | `Dockerfile` |
| JUnit Platform Console Standalone | 6.1.3 (EPL-2.0), SHA-256 `e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec` | `scripts/download_junit.py` |
| cloudflared | `cloudflare/cloudflared:2026.10.7`, digest `sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba`, live server only | `docker-compose.server.yml`, `docs/deploy.md` |
| GitHub Actions | `actions/checkout` v7.0.1, `actions/setup-python` v7.1.0, `gitleaks/gitleaks-action` v3.0.0, each pinned by commit SHA | `.github/workflows/` |

JUnit download: `scripts/download_junit.py` downloads the jar from `https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/6.1.3/` into `build/junit/`, which is ignored by Git, and removes the file unless its SHA-256 equals the value above. The script opens the connection with an unverified SSL context and relies on the SHA-256 check (comment in the script). The Dockerfile runs the script in the builder stage and copies the jar into the runtime stage. The jar is used by `coroner/diag/junit.py`.

Python packages, exact pins in [`pyproject.toml`](../pyproject.toml):

| Group | Packages |
|---|---|
| Runtime | mcp 2.3.0, fastapi 0.163.1, uvicorn 0.54.0, jinja2 3.1.6, python-multipart 0.0.33 |
| `dev` | pytest 9.2.0, pyyaml 6.0.3, hypothesis 6.170.14 |
| `test` | httpx 0.28.1 |
| `screenshots` | playwright 1.64.1, pillow 13.0.0 |
| Build | setuptools 75.6.0 |

Only these direct dependencies are pinned. Their own dependencies are resolved by `pip` at install time. `playwright` downloads a Chromium browser when `python -m playwright install chromium` is run; that browser is not part of the repository (THIRD_PARTY_NOTICES.md).

## 4. AI-generated code

- [`docs/KIRO_USAGE.md`](KIRO_USAGE.md): a Kiro agent wrote the code, specs, designs, tasks and tests, driven with `kiro-cli chat --no-interactive --agent coroner-builder`. An operator wrote the prompts, ran every result and kept the log ([`docs/reviews.md`](reviews.md)). The review log states: "Kiro writes all code, specs, designs and tasks; fixes are sent back to Kiro until clean." The exceptions where the operator edited files directly are R-06 and R-23 in the log, and KIRO_USAGE.md section 1 lists them.
- [`samples/independence/`](../samples/independence/README.md): Java ports of `samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob`, each labelled with its source in [`TABLE.md`](../samples/independence/TABLE.md):
  - `ports/kiro/`: Kiro agent, session 1 (kiro-cli, agent `coroner-builder`, model claude-sonnet-4.5).
  - `ports/kiro-fresh/`: Kiro agent, fresh isolated session.
  - `ports/claude/`: Claude Opus 5.5 (Anthropic), run as a Claude Code subagent, not a Kiro agent.
  - `ports/hand-written/`: no port. Only [`README.md`](../samples/independence/ports/hand-written/README.md) exists; the row stays "pending" until a person writes the port.

  Each port folder has `prompt.txt` and `SOURCE.md`; the Kiro folders also have `transcript.txt`.
- [`samples/carddemo-cbact04c/java/Cbact04c.java`](../samples/carddemo-cbact04c/java/Cbact04c.java): written by a Kiro agent (kiro-cli 3.5.0, agent `coroner-builder`, model claude-sonnet-5.5) in one isolated session and committed as written. Prompt, transcript, input hashes and the audit output are in [`docs/evidence/carddemo-cbact04c-port/`](evidence/carddemo-cbact04c-port/README.md).
- The faulty and correct Java ports in `samples/traps/` and `samples/credit-fees/java/` were written by Kiro agent calls and reviewed by the operator, as the entries R-31, R-64, R-67, R-69, R-71 of `docs/reviews.md` record. `.kiro/specs/` and `.kiro/steering/` were also produced in Kiro calls under review (R-01 to R-03, R-28 to R-38).
