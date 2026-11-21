# Judge guide

This guide shows how to check the main claims of COBOL Coroner yourself. Each check gives the command, the line it should print, and the file in this repository where the measured result is recorded.

## 1. Positioning

AWS Transform, Kiro, an LLM or a human migrates COBOL to Java. Coroner independently verifies the result. Coroner never translates COBOL.

## 2. Five minutes, no install

Live demo: https://coroner.iqoba.com (deployment check passed on 2026-11-21, all 10 checks, see deploy.md)

The home page has a Run audit form. Pick sample T1 and port Faulty, then Run Audit. Then pick T1 and port Correct. Open each run page. The run page has Verify and Tamper links.

The deployment check that must pass before the site is announced is described in [`deploy.md`](deploy.md), section "Check from anywhere".

## 3. Fifteen minutes with Docker

You need Docker with Compose. You do not need COBOL or Java on your machine. Work from a clone or from the ZIP of the repository.

Start the services. The compose file pulls a prebuilt image pinned by digest. No login is needed.

```bash
docker compose up -d
```

First start takes about one minute, because `coroner-init` generates the bundled demo runs. `docs/deploy.md` ("Try it locally first" and step 6) records 1 minute 19 seconds on the operator's Mac. When it ends, the last lines of `docker compose logs coroner-init` are:

```
coroner-init-1  | Wrote /data/runs/trap_catalog.json
coroner-init-1  | Wrote /data/runs/trap_catalog.txt
coroner-init-1  | Bundled demo runs generated.
```

(The container name prefix depends on the folder name.)

Open http://127.0.0.1:8000. What to click:

1. Run Audit: sample `T1 (EBCDIC collation)`, port `Faulty`, then Run Audit. The form shows the verdict and a link to the run. `docs/reviews.md` R-106 records, for a Run audit of T1 faulty at 2000 cases in the browser, the form line "ZOMBIE, 682 of 2000 cases diverge".
2. Run Audit again with port `Correct`. The verdict is ALIVE.
3. On a run page, use Verify. A real replay of the certificate gives "Certificate: VALID".
4. On the same run page, use the Tamper link. Change Status to ALIVE and Cases Divergent to 0, then submit. The result is "Certificate: INVALID, replay mismatch (status: expected ALIVE, got ZOMBIE)" (R-104 in `docs/reviews.md`). The original certificate is not changed.
5. Open `/matrix` for the Detection Matrix (measured counts for T1 to T5, T6 not measured).

Stop with `docker compose down`.

### Automatic check: `make deploy-check`

This script runs the same steps against a URL and prints one line per check. It needs the project virtual environment:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
make deploy-check
```

`make deploy-check` first builds the image from a real `git clone` of the checkout. If you work from the ZIP, or want to skip the build, run only the checks:

```bash
.venv/bin/python scripts/deploy_check.py --url http://127.0.0.1:8000 --skip-build
```

Measured on the operator's Mac, 2026-11-21 (`docs/deploy.md`, "Try it locally first"; run ids are the ones that run printed):

```
PASS: GET / returns 200 with Run audit form
PASS: T1 faulty: ZOMBIE verdict, run_id=f584d5f35228
PASS: T1 correct: ALIVE verdict, run_id=29c15f04407b
PASS: Tamper: INVALID with replay mismatch, run_id=f584d5f35228
PASS: Verify: certificate VALID, run_id=f584d5f35228
PASS: Cache-Control: /api/* responses include no-store
PASS: Body limit: 17 KB body rejected with 413

Deployment check PASSED: all checks succeeded
```

Without `--skip-build`, the output also starts with "PASS: Image built successfully from clean checkout". Exit codes: 0 all checks passed, 1 at least one check failed, 2 the build failed.

## 4. Check the key claims yourself

The commands in this section that run the engine need the project image. Build it once from the clone or the ZIP:

```bash
docker build --platform linux/amd64 -t coroner-local:latest .
```

The image holds GnuCOBOL 3.2, JDK 17 and Python 3.12 at the versions pinned in the `Dockerfile`. The CLI is `python3 -m coroner` (`coroner/cli.py`); its subcommands are `verify`, `traps` and `gate`. In the image the working directory is `/app` and the commands below write runs to `/tmp/coroner-runs`.

### 4.1 T1 faulty is ZOMBIE, T1 correct is ALIVE

Claim: a Java port that sorts branch codes in ASCII order instead of the EBCDIC order of the COBOL program is rejected, although the grand total still matches. The correct port is accepted.

```bash
docker run --init --rm -e CORONER_BASE_DIR=/tmp/coroner-runs coroner-local:latest \
  python3 -m coroner verify \
  --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob \
  --copybooks samples/traps/T1-ebcdic-match-merge/copybooks \
  --java samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java \
  --schema samples/traps/T1-ebcdic-match-merge/schema.json \
  --cases 2000 --seed 42
```

Expected first line, last lines, and exit status 1:

```
ZOMBIE: FAIL: business behavior diverged on 682 cases
Unreconciled branch exposure: sum 3995184.38, max 2025606.03, 2 branches affected, suspense difference 3995184.38, grand total matches: yes
```

For the correct port, replace `faulty` with `correct` in the `--java` path. Expected first line, exit status 0:

```
ALIVE: PASS: business behavior preserved on 2000 cases
```

Recorded in: `README.md` (section "Demo", measured output), `docs/reviews.md` R-89 (run f584d5f35228 faulty, run 29c15f04407b correct), and `docs/deploy.md` (the PASS lines of the deployment check). The same run, with the card, the JUnit test and the replay, is `make demo-ebcdic` on a machine that has GnuCOBOL, JDK 17 and the project virtual environment.

The other four traps are measured by `python3 -m coroner traps` (`make traps` on a prepared machine). The counts are in the README table and in `runs/trap_catalog.json` after the run.

### 4.2 Certificate replay is VALID, tampering is INVALID

Claim: every run writes `certificate.json`. Replaying it offline reruns both programs on the stored cases and checks every recorded hash. An edited certificate is rejected.

Replay, in the same container as the audit (the runs are not kept after the container ends):

```bash
docker run --init --rm -e CORONER_BASE_DIR=/tmp/coroner-runs coroner-local:latest sh -c '
python3 -m coroner verify \
  --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob \
  --copybooks samples/traps/T1-ebcdic-match-merge/copybooks \
  --java samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java \
  --schema samples/traps/T1-ebcdic-match-merge/schema.json \
  --cases 2000 --seed 42
python3 -m coroner verify /tmp/coroner-runs/runs/f584d5f35228/certificate.json
'
```

The second command prints these lines (strings from `coroner/cli.py`; the run id is the one printed on the "Run:" line of the first command):

```
Certificate: VALID
ZOMBIE: FAIL: business behavior diverged on 682 cases
Cases: 2000
Divergences: 682
```

A certificate whose recorded content or replay result does not match prints `Certificate: INVALID: <reason>` and exits with status 3. The exit status of a valid replay is 0 for ALIVE and 1 for ZOMBIE.

The easiest tamper check is in the UI (section 3, step 4). It edits a copy on the server and recomputes the certificate hash, so the result shows the replay catching the change, not only the hash. Expected: "Certificate: INVALID, replay mismatch (status: expected ALIVE, got ZOMBIE)".

Recorded in: `docs/reviews.md` R-58 (three forgery cases and their messages), R-104 (Tamper), and `docs/screenshots/verify-invalid.png`.

### 4.3 The gate blocks a ZOMBIE commit

Claim: a Git commit that stages a ZOMBIE port is refused, and the corrected port is committed.

This check needs a machine with GnuCOBOL 3.2, JDK 17 and the project virtual environment (see the README Quick start), because the pre-commit hook runs on the host. Use a scratch clone, as the recorded evidence did.

```bash
git config core.hooksPath .githooks
python3 -m coroner.catalog.legacy_variant samples/credit-fees/java/CreditFees.java build/variants/CreditFees.java
cp build/variants/CreditFees.java samples/credit-fees/java/CreditFees.java
git add samples/credit-fees/java/CreditFees.java
git commit -m "Port with HALF_EVEN"
```

The hook checks the staged content on 500 cases, seed 42. Expected output and exit status 1, quoted from `docs/evidence/git-precommit-block-then-allow.md` (the run id and the count are from that record):

```
Commit blocked by Coroner: ZOMBIE: FAIL: business behavior diverged on 21 cases. See runs/aa7e43333e51/failure_report.json. Fix the Java port, then run run_differential_check again.
```

The same file records the allowed commit of the corrected port:

```
Coroner pre-commit: ALIVE: PASS: business behavior preserved on 500 cases (Duration: 3.3 s)
```

Other recorded evidence:

- `docs/evidence/kiro-gate-block-then-allow.md`: a Kiro agent is blocked by the delivery gate, fixes `HALF_EVEN` to `HALF_UP`, and the commit is then allowed.
- `docs/evidence/kiro-hooks-verification.md`: 13 real hook runs. The wording that follows from them: Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed.
- `docs/screenshots/commit-blocked.png`.

The CI gate does the same in a pipeline. `.github/workflows/coroner-gate.yml` runs `python3 -m coroner gate` in the image (exit 0 on ALIVE with a VALID certificate) and checks that the `HALF_EVEN` variant gives exit code 1. Exit codes of `coroner gate`: 0 ALIVE and VALID certificate, 1 ZOMBIE, missing or invalid certificate, 2 ERROR or a bad scope file (README, section "CI gate").

### 4.4 The independence table

Claim: Coroner gives a verdict for a port whoever wrote it. The same COBOL program (T1) was ported by a Kiro agent in two sessions and by Claude Opus 5.5 run as a Claude Code subagent. Each port was audited once, unchanged.

```bash
python3 samples/independence/run_table.py --image coroner-local:latest
```

The script runs every audit inside the image and rewrites `samples/independence/TABLE.md`. R-112 in `docs/reviews.md` records 35.9 s for this command. Expected rows (verbatim from `TABLE.md`, columns shortened here):

| Port | Verdict | Divergent cases | Run ID | Branch exposure |
|---|---|---|---|---|
| Claude Opus 5.5 | ALIVE | 0 of 2000 | 0d1e698359fb | sum 0.00 |
| Kiro agent, session 1 | ZOMBIE | 682 of 2000 | a4709d638df5 | sum 3995184.38, max 2025606.03, 2 branches |
| Kiro agent, fresh isolated session | ALIVE | 0 of 2000 | 7af943198226 | sum 0.00 |

The hand-written row says "pending". Only a person can write that port. The row is removed if it has not arrived by 2026-11-26 (Q3 in `docs/reviews.md`).

Read `samples/independence/README.md` for the limits: one program, one seed, 2,000 cases, and the verdicts are not a comparison of models. The same README explains why the session 1 port has the same count as the demo faulty port although it is a different file.

The audit uses the image on purpose. The fresh port formats amounts with `String.format("%+010.2f")`, which follows the JVM default locale. On the operator's Mac the same port gave ZOMBIE on 2000 of 2000 cases. The engine now runs Java with a fixed locale (R-118), and the certificate records `java_locale`.

### 4.5 The CardDemo audit of the Kiro-made port

Claim: a Kiro agent in an isolated session ported one bounded interest-calculation path of AWS's open-source CardDemo sample (CBACT04C) to Java. Coroner finds no behavioral difference on the tested cases.

Run it inside the project image. On a developer Mac, 200 cases do not fit in the 60 s run timeout of the engine (R-124 records 50.66 s for the reference run and more than 60 s for the coverage run), so the audit was produced in the image. The command is the one recorded in `docs/reviews.md` R-126:

```bash
docker run --init --rm -e CORONER_BASE_DIR=/tmp/coroner-runs coroner-local:latest \
  python3 -m coroner verify \
  --cobol samples/carddemo-cbact04c/adapted/HARNESS-CBACT04C.cob \
  --copybooks samples/carddemo-cbact04c/upstream/cpy \
  --java samples/carddemo-cbact04c/java/Cbact04c.java \
  --schema samples/carddemo-cbact04c/schema.json \
  --cases 200 --seed 42
```

Expected output, from `docs/evidence/carddemo-cbact04c-port/audit-200-seed42-image.txt` (exit status 0):

```
ALIVE: PASS: business behavior preserved on 200 cases
Paragraph coverage 34/34
Branch coverage (Coroner definition) 66/99
Validated under GnuCOBOL 3.x
Run: runs/a5edaf1924a5
Duration: 40.8 s
```

The coverage lines measure the harness program that the engine compiles, not CBACT04C alone (R-126). The duration depends on your machine.

Recorded in: `docs/evidence/carddemo-cbact04c-port/` (the exact prompt, the full transcript, the hashes of the inputs the agent could read, the list of files in its sandbox, the audit output). The port was committed as the agent wrote it (SHA-256 `e16d5d6ce285efb81eafb532a8803a9fda6c43214e1d1ecfc26178c39eda08ea`).

Required notice: Uses AWS's open-source CardDemo sample (Apache 2.0). Not affiliated with or endorsed by AWS. The upstream files are kept byte for byte in `samples/carddemo-cbact04c/upstream/`; the one change to the program is documented in `samples/carddemo-cbact04c/CHANGES.md`. VSAM is replaced by deterministic test files, so this does not emulate z/OS VSAM.

## 5. What the verdicts mean and do not mean

The wording comes from `.kiro/steering/no-formal-proof.md`.

- ALIVE means "PASS: business behavior preserved on N cases". It is a statement about the N generated cases, not about all inputs.
- ZOMBIE means "FAIL: business behavior diverged on M cases". The run shows the failing case, the COBOL output, the Java output, the divergent field and the COBOL lines executed.
- Coroner is not a formal proof of equivalence. It does not claim a port is proven equivalent or guaranteed.
- Results are "Validated under GnuCOBOL 3.x". Coroner does not emulate IBM z/OS. GnuCOBOL and IBM differ on some points, for example the sign nibble B (`docs/evidence/gnucobol-encodings.md`).
- The verdict is deterministic. No AI model decides it. The same inputs and seed give the same verdict.
- The Coroner Certificate is a reproducible run record: the verdict, N cases, the seed, tool versions and the SHA-256 of the input files. It is not a guarantee.
- Out of scope in V1: CICS, DB2, IMS, VSAM, JCL, EBCDIC-encoded data (the EBCDIC collating sequence is in scope), multi-program applications, targets other than Java 17.
- T6 of the trap catalog is a placeholder. It is "not measured".
- The detection rates depend on the generator settings of each trap. They are not real-world statistics, and there is no global detection rate.
- A return code is compared as an OS exit status (0 to 255).

## 6. Where to read further

- [`docs/KIRO_USAGE.md`](KIRO_USAGE.md): how Kiro was used (specs, steering, skills, hooks, MCP, agents), with links to the evidence files.
- [`docs/PREEXISTING_CODE.md`](PREEXISTING_CODE.md): which files are third-party or were not written for this project, with their licences.
- [`SECURITY.md`](../SECURITY.md): how to report a vulnerability and the security controls of the live demo.
- [`docs/reviews.md`](reviews.md): every Kiro call and how its result was verified, including the defects found and sent back.
- [`docs/decisions.md`](decisions.md): the decision log.
- [`docs/deploy.md`](deploy.md): deployment guide with measured outputs.
