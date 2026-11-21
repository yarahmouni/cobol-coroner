# Changelog

All notable changes to COBOL Coroner. The format follows Keep a Changelog. Items are grouped from the commit history and from the review log ([`docs/reviews.md`](docs/reviews.md)). The short hashes in parentheses are commits. The project has no version numbers yet, so entries are grouped by date.

## Unreleased

State at 2026-11-21, from the review log (R-xxx) and the judge guide:

- The live site https://coroner.iqoba.com is online. The deployment check passed all 10 checks against it on 2026-11-21 (R-148, fd81f52); the judge guide links to it, and the deployment guide records the server outputs (R-152).
- Trap T6 is a placeholder; the owner's field trap has not been received (Q1).
- The independence table has one pending row for a port written by hand by the author. The row is removed if it has not arrived by 2026-11-26 (Q3).
- The Kiro power `coroner-audit` is not in the repository and is not claimed (Q6).
- The CardDemo audit run is not bundled yet and the main README has no CardDemo line (R-126).
- The guided story ("Try the bank failure") has a spec (c65a8ba) and its gate-check endpoint (909b2c2); the story pages are not described as built in the review log.
- The default test suite target of 60 s is not reached (R-78).

## 2026-11-21

### Added
- Video plan with a timed script, subtitles generated from the script table, and a recording script with a disk-space guard (3a311ab).
- Community files: `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `THIRD_PARTY_NOTICES.md` (296dfed). `SECURITY.md` later gained the gate-check endpoint controls and the generator-script confinement (f003574).
- `POST /api/gate-check`: replays a certificate off the event loop and decides with the same `gate_decision` as the CLI gate (909b2c2).
- Independence table: a fresh isolated Kiro port (ALIVE), an explanation of the session 1 port, audits run in the project image, a generated same-file column and one pending hand-written row (62344e7, a7a1e48).
- CardDemo CBACT04C sample (D-62), in four steps: upstream sources byte for byte with Apache notices, one documented COBOL change, a GnuCOBOL driver and three probe datasets (4911928); an audit harness that runs one process per case, compiled with the EBCDIC sign convention (57a60f2); the audit end to end in `coroner verify` with a generator script confined to the schema folder (fc61f81); a Java port written by an isolated Kiro session, committed verbatim with its prompt, transcript and input hashes, ALIVE on 200 generated cases in the project image (6188e97).
- Deployment guide `docs/deploy.md` for coroner.iqoba.com, with measured outputs and markers for what can only be measured on the server (bda61df).
- `docs/KIRO_USAGE.md` (2ff5198), `docs/PREEXISTING_CODE.md` (159afcf) and `docs/judge-guide.md` (ef6c196).

### Changed
- Compose files are pinned to the published image by digest, pulled when missing, with no build; `docker-compose.build.yml` keeps the local build (5154415).
- Java runs with a fixed `en_US` locale and UTF-8 encoding, recorded in certificates, so the same port gets the same verdict on a machine with another default locale (bd208dc).
- The independence same-file column walks `samples/` instead of using the Git file list, so it works in the image (a7a1e48).

### Fixed
- Killed replays and audits left zombie processes: every container and every `docker run` of the image now has an init process (41eb9e4).
- Gate check: a cached answer is served before the gate-check rate bucket, so going back to a story step does not get 429 (995bb1d). A replay that did not finish is never cached and answers 503 (188e2ae).
- The independence test makes its own 50-case audit instead of reading a local run, so CI with `CORONER_NO_SKIP` passes (c818c21).
- Gate-check tests make their own T1 runs once per session and no longer read the local `runs/` folder (b292905).
- The CardDemo driver `RUN-CBACT04C` carried a copy of the AWS copyright notice; its header now states it was written for this project (891d616).
- `THIRD_PARTY_NOTICES.md` named a wrong JUnit path (159afcf).

### Security
- Schema generator scripts are hashed from the exact bytes that run; replay and the gate refuse a changed script (fc61f81, 188e2ae).

## 2026-11-20

### Added
- Engine worker and exchange directory: audits run as a child process group with a real timeout (2c132f4).
- Run audit endpoint and form with queue, per-client and body limits, run reuse and a visitor-run quota (ac02072).
- Tamper page and endpoint: edits a copy of a real certificate on the server and replays it, with one shared certificate hash function (896a701).
- Docker Compose for testers and for the live server, a cloudflared tunnel override, and demo runs generated at first start (49183a0).
- Manual workflow that tests the image and publishes it to GitHub Container Registry, never tagged `latest` (b67badf).
- `make deploy-check`: builds from a clean clone, then checks a URL (8f604e9).
- Guided-story spec for "Try the bank failure" (c65a8ba).
- Independence proof: Case 1 ported by a Kiro agent and by a Claude subagent from the COBOL alone, audited by the same engine, with the table generated from real runs (f28c73e).
- Decisions D-60 to D-64 (857f269, 2e9ab67).

### Changed
- CI unit tests run inside the image built from the checkout; a skipped test fails in CI (1f5ef1f).
- `apt` reads a fixed Debian snapshot (20261119T000000Z) so pinned package versions stay available through judging (d432979).
- The web-ui spec no longer states a host capacity figure, and `prompts/` is ignored (826eee6).

### Fixed
- Certificates of engine-run audits could never replay, and Verify and Tamper blocked the site while a replay ran. Certificates now record a relative cases file path and replays run in a child process with a timeout (8f604e9).
- Job timeout did not stop the audit processes; the worker now kills the whole process group (2c132f4).
- Unit tests depended on local runs, the virtual environment and build files (1f5ef1f).

### Security
- Per-client address from `CF-Connecting-IP` is trusted only from the configured proxy (ac02072).
- Rate limits with `Retry-After` on every audit endpoint, Tamper limited like Verify, `Cache-Control` on every API response (d577fe0).
- Compose services run with limits on CPU, memory and processes; the engine and init services have no network (49183a0).

## 2026-11-18

### Added
- README screenshots and a demo GIF generated from real runs by `make screenshots` (44cfc01).
- Decision D-59, static fallback on Cloudflare Pages if the GitHub billing lock lasts (df4b022).

### Changed
- `make smoke-ui` builds from a clean export of the working tree (e3e512b).

### Fixed
- The image could not be built from a clean checkout because it copied an ignored folder; the JUnit jar is now downloaded and hash-checked in the build (e3e512b).
- The Verify button never worked in a browser: it posts form data and the endpoint only accepted JSON (44cfc01).
- `coroner traps` ignored `CORONER_BASE_DIR` and wrote into the repository `runs/` (44cfc01).

## 2026-11-17

### Added
- Web UI (FastAPI, Jinja2, htmx): run pages for ZOMBIE, ALIVE and ERROR, Verify, Detection Matrix (f0bc3eb), with a spec (39b814a).
- Branch reconciliation and timing files written for the UI, using the same sums as the exposure (ad6b6db).
- `coroner gate`, a GitHub Actions workflow and an example Jenkinsfile (89ff74b).
- Web UI deployment and test book spec (f12d30c).
- GitHub language statistics now count `samples/` and label COBOL sources (ad38093).
- Decisions D-55 to D-58 (e6599b0, e8fc7ec).

### Changed
- The Docker image runs the engine and the UI tests, and the CLI honours `CORONER_BASE_DIR` (a8baf5e).
- Trap T4 realism: the faulty port forgets only the zero overpunch characters (f51bf4a).
- Trap T1 realism: banking-day amounts, reversals and batch sizes (3ce6c5b).

### Fixed
- Unreconciled branch exposure was computed from the last case only; it now sums branches over all cases and reports suspense separately (883256f).
- The runtime image could not compile COBOL (missing GMP headers) (a8baf5e).
- Tests that ran the CLI wrote into the repository `runs/` (a8baf5e).
- The gate printed "ALIVE on 0 cases" because it read wrong certificate keys (89ff74b).

## 2026-11-16

### Added
- Traps T3 (COMP-3 sign nibble), T4 (EBCDIC zoned overpunch, certificate records `cobc_flags`), T5 (REDEFINES and invalid numeric data) and T6 (placeholder) (9100524, e800284, 6ff9b98, b169bf1).
- Given/When/Then card from the minimal case (cebbef4), made row-level for multi-row cases (971f70c).
- Trap catalog runner and Detection Matrix, `make traps` (bf0bd23), MCP `get_detection_matrix` on the measured catalog (d8acfb9), README matrix with measured numbers (763e99f), catalog acceptance test (e15e1e2).
- Generator version guard for the golden hashes (743b0b0).
- EBCDIC demo spec and multi-row minimal case verified by re-running both programs (5084950), JUnit export for multi-row cases (d8ac5da), `make demo-ebcdic` and the README Demo section (f330fd5).
- Decisions D-52 to D-54 (3a29dbb).

### Changed
- Faster default test suite: build cache, slow markers, grouped MCP sessions (754 s to 109 s) (3b3823a).

### Fixed
- The shared generator changed after the T2 commit, so `make zombie` gave a different count; the generator output is restored and the comparator matches padded COBOL headers (a2555c4).
- A JUnit run that found no test was reported as passed; it is now an error (d8ac5da).
- Catalog and MCP tests no longer write to or delete the real `runs/` (a9ab91f, d8acfb9).

## 2026-11-15

### Added
- Toolchain: toy COBOL and Java programs, a GnuCOBOL `-ftraceall` trace fixture and parser, a smoke runner, a stub MCP server and Kiro MCP configuration (901e4e4, c3fee4a, 6a9ac43, 65c8b0e, e703f81, 24ebb99, beb9a1d, 17de61f, 8f3a922, 85fd1ad). CI workflow with tests and a secret scan (ef2d685). Runtime C compiler and Makefile targets `smoke`, `demo`, `zombie`, `serve` (e97f4c6).
- `CREDIT-FEES` COBOL program with copybooks, schema and rounding-tie fixtures (2b4d628), and its Java 17 port, byte-identical to COBOL on all fixtures including parity cases (b1e79fd).
- Differential engine: schema and PIC parsing, trace parsing keyed by source file and line, COBOL structure parser, deterministic case generator, runners, exact comparator with no numeric tolerance, verdict wording, run storage with deterministic run id, coverage, minimal case and failure report (cb06d7f, a14a3b4, 7e4695d, 0717515, fd996b6, e2ced77, 03ab7c1, ddf9bbd, 0d57685, 3714048).
- JUnit 5 regression test export (b0a31fe), HALF_EVEN variant generator (a76a818), `coroner verify` CLI with `make demo` and `make zombie` (cd7318b), 10-seed acceptance test with `make acceptance` (ff75b8b), README quick start (2c2d483).
- Replayable Coroner Certificate and offline `coroner verify certificate.json` (7b3082d).
- Pre-commit fast mode with a 500-case check (a340ed3), then on the staged content (924288e).
- MCP server with 7 tools, the `coroner-auditor` agent and three Kiro skills (d400bc1). Kiro delivery gate and capped stop hook, with real block-then-allow evidence (4aa0d00).
- Trap catalog: engine extension for batch cases, composite keys, branch exposure and per-program compiler flags (9c8cd26), T1 EBCDIC match-merge (fcbc229), T2 truncation and rounding (a5f8e0a), spec and verified encodings (b6c3865).
- Pre-commit guard for home paths and unlisted root or `scripts/` files (281e43c).
- Specs for `cobol-sample`, `java-credit-fees` and the engine, and decisions D-17 to D-51 (b83d298, 582e239, 452f66b, 50b5ab9, 4c6fda8, c464036, 779201d, c77e40c, 64bc238, 74a08a9, b23b339, 8159594).

### Changed
- Renamed to COBOL Coroner (D-19) with ALIVE and ZOMBIE labels (D-20) (e780837, e94a795).
- Fault catalog replaced by the catalog of banking migration traps (D-29) (ba3112e); random cases use `random.Random(seed).random()` only and return codes are compared as exit status (D-30, D-31) (e51ce91).

### Fixed
- The deliberate CRLF row of the parity fixture is kept byte-exact in Git (e539ce5).
- A reference COBOL run that did not run gives ERROR, exit 2 and no certificate, never ZOMBIE (D-51) (b5f10da).
- The MCP stub used its own verdict type; it now uses the engine type (ddf9bbd).

### Security
- The pre-commit guard refuses staged files that contain a home path (281e43c).
- The engine runs COBOL and Java with a minimal pass-through environment (e2ced77).
