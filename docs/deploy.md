# Deployment guide

This guide deploys COBOL Coroner at https://coroner.iqoba.com on a Linux amd64 server behind a Cloudflare Tunnel. Follow it in order.

How outputs are labelled in this guide:

- "Measured on the operator's Mac, 2026-11-21": real output of the command on the operator's machine (Docker Desktop), copied verbatim. Container, volume and network names start with the name of the local project folder; on the server they start with the name of the folder you clone into.
- "Measured on the server, 2026-11-21": measured by the owner on the deployment server; "(owner's summary)" marks outputs given as a summary rather than terminal lines.

## What you get

Three Coroner services plus cloudflared. All three Coroner services run the same prebuilt image from GitHub Container Registry, pinned by digest:

```
ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8
```

The package is public, so pulling needs no login. The image is published by `.github/workflows/publish-image.yml` and is the image the CI tests run. The server never builds anything.

- **coroner-init** (one-shot): generates the bundled demo runs at first start, then exits. Network none. Limits: 2 CPUs, 2 GB memory, 256 PIDs.
- **coroner-api**: FastAPI web application serving the UI and the endpoints. Limits: 1 CPU, 512 MB memory, 128 PIDs.
- **coroner-engine**: runs COBOL and Java for the audits. Network none. Limits: 2 CPUs, 2 GB memory, 256 PIDs.
- **cloudflared**: Cloudflare Tunnel client, `cloudflare/cloudflared:2026.10.7` pinned by digest. Limits: 0.25 CPU, 128 MB memory, 32 PIDs.

Sum of the memory limits: 2688 MB in steady state (api 512 MB, engine 2048 MB, cloudflared 128 MB). While coroner-init runs at first start, its 2048 MB limit comes on top (4736 MB of limits in total). Host memory used by other services is out of scope: Coroner stays within its own container limits.

No inbound port is opened on the server. The API is reachable only through the Cloudflare Tunnel at coroner.iqoba.com.

Developers who want to build the image from the Dockerfile instead use the override `docker-compose.build.yml` (see "Try it locally first"). The server does not use it.

## 1. Prerequisites on the server

The compose files set `platform: linux/amd64`, so the server must be amd64.

```bash
uname -m
```

Measured on the server, 2026-11-21:

```
x86_64
```

```bash
docker version --format '{{.Server.Version}}'
```

Measured on the operator's Mac, 2026-11-21:

```
28.0.1
```

Measured on the server, 2026-11-21:

```
29.10.0
```

```bash
docker compose version --short
```

Measured on the operator's Mac, 2026-11-21:

```
2.33.1-desktop.1
```

Measured on the server, 2026-11-21:

```
5.8.0
```

The compose files were tested with Compose 2.33.1. The server runs Compose 5.8.0, which is newer, and the `!reset` override works there: the `published` check of step 5 printed nothing on the server. Older Compose versions do not support `!reset` (see Troubleshooting).

```bash
git --version
```

Measured on the server, 2026-11-21:

```
git version 2.43.0
```

## 2. Cloudflare tunnel

Needs the server and your Cloudflare account.

### (a) Zone active in Cloudflare

Log in to https://dash.cloudflare.com/ and check that the zone that serves coroner.iqoba.com shows "Active" in the Websites list.

### (b) Create the tunnel and the route

Run cloudflared from the same pinned image as `docker-compose.server.yml`.

Create a host directory for the cloudflared configuration, owned by uid 65532 (the nonroot user of the cloudflared image):

```bash
mkdir -p <CLOUDFLARED_HOME>/.cloudflared
sudo chown -R 65532:65532 <CLOUDFLARED_HOME>/.cloudflared
sudo chmod 700 <CLOUDFLARED_HOME>/.cloudflared
```

Log in to Cloudflare. The command prints a URL, opens nothing by itself, and waits until you authorize it in a browser:

```bash
docker run --rm -v <CLOUDFLARED_HOME>/.cloudflared:/home/nonroot/.cloudflared cloudflare/cloudflared:2026.10.7@sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba tunnel login
```

Measured on the operator's Mac, 2026-11-21 (the query string is cut):

```
Please open the following URL and log in with your Cloudflare account:

https://dash.cloudflare.com/argotunnel?<long query string>

Leave cloudflared running to download the cert automatically.
```

Create the tunnel. It writes `<CLOUDFLARED_HOME>/.cloudflared/<TUNNEL_UUID>.json` on the host and prints the tunnel UUID:

```bash
docker run --rm -v <CLOUDFLARED_HOME>/.cloudflared:/home/nonroot/.cloudflared cloudflare/cloudflared:2026.10.7@sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba tunnel create coroner
```

Measured on the server, 2026-11-21 (excerpt; the credentials folder and the UUID are redacted):

```
Tunnel credentials written to <credentials folder>/<TUNNEL_UUID>.json ... Created tunnel coroner with id <TUNNEL_UUID>
```

Note the UUID for `.env`.

Route the hostname to the tunnel:

```bash
docker run --rm -v <CLOUDFLARED_HOME>/.cloudflared:/home/nonroot/.cloudflared cloudflare/cloudflared:2026.10.7@sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba tunnel route dns coroner coroner.iqoba.com
```

Measured on the server, 2026-11-21:

```
INF Added CNAME coroner.iqoba.com which will route to this tunnel tunnelID=<TUNNEL_UUID>
```

If the command reports an error instead, the route does not exist yet.

### (c) Credentials file permissions

The credentials file written by `tunnel create` must be readable by uid 65532 and must stay outside the repository clone:

```bash
sudo chmod 600 <CLOUDFLARED_HOME>/.cloudflared/<TUNNEL_UUID>.json
```

## 3. Get the code and configure

Clone the public repository. You need the clone for the compose files and `cloudflared-config.yml`; the image itself is pulled, not built.

```bash
git clone https://github.com/yarahmouni/cobol-coroner.git
cd cobol-coroner
git log -1 --oneline
```

Check that the clone pins the image digest of this guide (the command must print the lines `x-coroner-image:` with the digest above):

```bash
grep -n "x-coroner-image" docker-compose.yml
```

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

- `TUNNEL_ID`: the UUID printed by `tunnel create`.
- `TUNNEL_CREDENTIALS_FILE`: absolute path of the credentials JSON file (`<CLOUDFLARED_HOME>/.cloudflared/<TUNNEL_UUID>.json`).

`.env` is git-ignored and must never be committed. Check:

```bash
git check-ignore -v .env
```

Measured on the operator's Mac, 2026-11-21:

```
.gitignore:10:.env	.env
```

## 4. Pull the pinned images

No build happens on the server and no registry login is needed. Pull the three Coroner services (one image) and cloudflared:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml pull
```

Measured on the operator's Mac, 2026-11-21 (`docker compose pull` with `docker-compose.yml` only, so cloudflared is not in this output; the image layers are the same on the server):

```
 coroner-init Skipped - Image is already being pulled by coroner-engine 
 coroner-api Skipped - Image is already being pulled by coroner-engine 
 coroner-engine Pulling 
 8d79fc8bd5fd Pull complete 
 949d78adb05f Pull complete 
 bc777f1a7182 Pull complete 
 e818fb0ed7af Pull complete 
 c8b5dc0d7729 Pull complete 
 03081bab56a7 Pull complete 
 2185503755d0 Pull complete 
 8c88dceddb62 Pull complete 
 0e0cd2eaf9e9 Pull complete 
 f85e9761f760 Pull complete 
 e852391a6cbc Pull complete 
 e6e5137408a8 Pull complete 
 2e65c2200cda Pull complete 
 coroner-engine Pulled 
docker compose pull  0.19s user 0.16s system 0% cpu 48.869 total
```

The last line is the `time` output of the operator's shell: the pull took 48.9 seconds there. On the server the same command also pulls cloudflared. Measured on the server, 2026-11-21 (owner's summary): both images were pulled, the Coroner image in 17.4 s and cloudflared in 0.8 s.

Read the digest back from the pulled image and compare it with the one in `docker-compose.yml`. They must match exactly:

```bash
docker image inspect --format '{{index .RepoDigests 0}}' ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8
```

Measured on the operator's Mac, 2026-11-21:

```
ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8
```

## 5. Check the merged configuration

Before starting, list the image lines of the merged configuration:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml config | grep -n "image:"
```

Measured on the operator's Mac, 2026-11-21 (line numbers are positions in the merged output):

```
23:    image: cloudflare/cloudflared:2026.10.7@sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba
75:    image: ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8
118:    image: ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8
154:    image: ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8
183:x-coroner-image: ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8
```

All three Coroner services must show the same digest, and none of them may have a `build` key. The API must not publish a port on the server. This command must print nothing:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml config | grep -n "published"
```

If it prints a line, the `ports: !reset []` override did not apply: your Compose is too old (see Troubleshooting).

Measured on the server, 2026-11-21 (owner's summary): the image check printed four image lines (the three Coroner services on the digest ending in b0ebe1e8, and cloudflared), and the `published` check printed nothing.

## 6. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

Measured on the server, 2026-11-21 (owner's summary): Compose created the network and the two volumes; `coroner-init` exited after 55.0 s; `coroner-engine`, `coroner-api` and `cloudflared` started. On the operator's Mac, the same command with `docker-compose.yml` only (no cloudflared) gave, on 2026-11-21:

```
 Network cobol-lazarus_default  Creating
 Network cobol-lazarus_default  Created
 Volume "cobol-lazarus_coroner-data"  Creating
 Volume "cobol-lazarus_coroner-data"  Created
 Volume "cobol-lazarus_coroner-exchange"  Creating
 Volume "cobol-lazarus_coroner-exchange"  Created
 Container cobol-lazarus-coroner-init-1  Creating
 Container cobol-lazarus-coroner-init-1  Created
 Container cobol-lazarus-coroner-engine-1  Creating
 Container cobol-lazarus-coroner-engine-1  Created
 Container cobol-lazarus-coroner-api-1  Creating
 Container cobol-lazarus-coroner-api-1  Created
 Container cobol-lazarus-coroner-init-1  Starting
 Container cobol-lazarus-coroner-init-1  Started
 Container cobol-lazarus-coroner-engine-1  Starting
 Container cobol-lazarus-coroner-engine-1  Started
 Container cobol-lazarus-coroner-init-1  Waiting
 Container cobol-lazarus-coroner-init-1  Exited
 Container cobol-lazarus-coroner-api-1  Starting
 Container cobol-lazarus-coroner-api-1  Started
docker compose up -d  0.24s user 0.16s system 0% cpu 1:11.11 total
```

First start took 1 minute 11 seconds there, because coroner-init generates the bundled demo runs before the API starts. A later restart skips the generation.

List the running services:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'
```

Measured on the server, 2026-11-21 (owner's summary): `cloudflared`, `coroner-api` and `coroner-engine` all have a status starting with `Up`. Look for `coroner-api`, `coroner-engine` and `cloudflared` with a status starting with `Up`. `coroner-init` is not listed because it has exited. On the operator's Mac (no cloudflared), 2026-11-21:

```
SERVICE          IMAGE                                                                                                      STATUS
coroner-api      ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8   Up Less than a second
coroner-engine   ghcr.io/yarahmouni/cobol-coroner@sha256:837503172e4d54702edb6b87d48659e120cc1d3fda11bd6ebe2f5789b0ebe1e8   Up About a minute
```

Check that the demo runs were generated:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml logs coroner-init
```

Measured on the operator's Mac, 2026-11-21 (last lines):

```
coroner-init-1  | Running T5 faulty Java...
coroner-init-1  | Running T5 correct Java...
coroner-init-1  | 
coroner-init-1  | Wrote /data/runs/trap_catalog.json
coroner-init-1  | Wrote /data/runs/trap_catalog.txt
coroner-init-1  | Bundled demo runs generated.
```

On the server the service name prefix differs. The last line must be `Bundled demo runs generated.` On the server, 2026-11-21, the logs end with `Bundled demo runs generated.`

Check that cloudflared connected:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml logs cloudflared
```

Measured on the server, 2026-11-21 (owner's summary): four "Registered tunnel connection" lines, connIndex 0 to 3. The check that counts is the one in the last section of this guide.

## Day-to-day operations

Logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml logs -f
docker compose -f docker-compose.yml -f docker-compose.server.yml logs -f coroner-api
docker compose -f docker-compose.yml -f docker-compose.server.yml logs -f coroner-engine
docker compose -f docker-compose.yml -f docker-compose.server.yml logs -f cloudflared
```

Restart:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml restart
```

Stop:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml down
```

`down -v` also deletes the volumes, including the bundled demo runs. Use it only to start fresh.

Update to a new image: a new digest is published by the `publish-image.yml` workflow and written to its job summary. In `docker-compose.yml`, replace the digest on the line that starts with `x-coroner-image:` (the one line that all three services use), then:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml pull
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

## Troubleshooting

**Credentials file unreadable by uid 65532.** The cloudflared container cannot read the credentials file. Check ownership and mode:

```bash
ls -l <CLOUDFLARED_HOME>/.cloudflared/<TUNNEL_UUID>.json
```

It must be owned by uid 65532 with mode 600:

```bash
sudo chown 65532:65532 <CLOUDFLARED_HOME>/.cloudflared/<TUNNEL_UUID>.json
sudo chmod 600 <CLOUDFLARED_HOME>/.cloudflared/<TUNNEL_UUID>.json
docker compose -f docker-compose.yml -f docker-compose.server.yml restart cloudflared
```

**Tunnel id mismatch.** The cloudflared logs show "Unauthorized: Tunnel credentials file does not match the credentials required for this tunnel." The `TUNNEL_ID` in `.env` does not match the credentials file. Compare it with the UUID in the credentials file name, fix `.env`, and restart cloudflared as above.

**Compose too old for `!reset`.** The check in step 5 prints a `published` line. Upgrade the Docker Compose plugin (tested with 2.33.1).

**Port 8000 busy in tester mode.** Without `docker-compose.server.yml`, the API publishes 127.0.0.1:8000, and `up` fails with "port is already allocated" when another process holds it. Stop that process or change the port in `docker-compose.yml`.

**Out of disk.** The init service or an audit fails with "no space left on device". Check with `df -h`, free space, and start again.

**Docker cannot pull the image.** Check that the server can reach ghcr.io and that you did not log in with a wrong credential (`docker logout ghcr.io` removes it; the package is public).

## Try it locally first (tester mode)

Before the server, run the same pinned image on your own machine, without cloudflared. This is also what a tester does from the repository ZIP.

```bash
docker compose up -d
```

Measured on the operator's Mac, 2026-11-21: the output shown in step 6 (1 minute 11 seconds, UI answering on http://127.0.0.1:8000 afterwards).

Open http://127.0.0.1:8000. The home page shows the Run audit form.

Run the deployment check against it (needs the project virtual environment, see the last section):

```bash
make deploy-check
```

Measured on the operator's Mac, 2026-11-21 (`URL` defaults to http://127.0.0.1:8000; the first line is the command as `make` printed it with `PYTHON` pointing to the project environment):

```
.venv/bin/python scripts/deploy_check.py --url http://127.0.0.1:8000
Building image from clean git clone...
Current HEAD: 6b6b34858876a0dc500bdef0842f9dc214872045
Cloning into <temp dir>
Building Docker image (this may take a few minutes)...
PASS: Image built successfully from clean checkout

Running checks against http://127.0.0.1:8000...
PASS: GET / returns 200 with Run audit form
T1 faulty: job submitted, job_id=204621afa1da
PASS: T1 faulty: ZOMBIE verdict, run_id=f584d5f35228
T1 correct: job submitted, job_id=dc7283adb66d
PASS: T1 correct: ALIVE verdict, run_id=29c15f04407b
PASS: Tamper: INVALID with replay mismatch, run_id=f584d5f35228
PASS: Verify: certificate VALID, run_id=f584d5f35228
PASS: Cache-Control: /api/* responses include no-store
PASS: Body limit: 17 KB body rejected with 413
PASS: Story step 5: Cause of death, positioning sentence and a branch table row
PASS: Fool page: counter and three checkboxes

Deployment check PASSED: all checks succeeded
make deploy-check URL=http://127.0.0.1:8000 PYTHON=.venv/bin/python  1.28s user 2.26s system 1% cpu 3:22.92 total
```

The last line is the `time` output of the operator's shell: 3 minutes 22.9 seconds in total, including the image build from a clean `git clone`.

Stop:

```bash
docker compose down
```

Developers who changed the code and want to run their own build use the override. It builds the image from the Dockerfile as `coroner-local:latest` and never pulls:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build
```

## Rollback

The image digest is committed in `docker-compose.yml`, on the line that starts with `x-coroner-image:`. To go back to the previous image:

1. Find the previous digest in the job summary of the earlier `publish-image.yml` run, or in the earlier version of `docker-compose.yml` (`git log -p -- docker-compose.yml`).
2. Replace the digest on the `x-coroner-image:` line with the previous one.
3. Pull and restart:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml pull
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

4. Run the check below. Volumes are kept, so the bundled demo runs stay.

## Check from anywhere

From any computer with Docker, git and the project virtual environment:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
make deploy-check URL=https://coroner.iqoba.com
```

`make deploy-check` first builds the Dockerfile from a clean `git clone` of the checkout on your computer (this proves the repository builds from a clean tree; the server itself never builds), then runs the checks against the URL. The cold build time is not measured: the live check of 2026-11-21 reused the local Docker build cache. To run only the checks against the live site:

```bash
.venv/bin/python scripts/deploy_check.py --url https://coroner.iqoba.com --skip-build
```

Measured against https://coroner.iqoba.com from the operator's Mac, 2026-11-21 (exit code 0, 1 min 32 s in total, build from the Docker cache):

```
.venv/bin/python scripts/deploy_check.py --url https://coroner.iqoba.com
Building image from clean git clone...
Current HEAD: d39ddb184f335f29595156d3eb130503d0b8ff31
Cloning into <temporary folder>...
Building Docker image (this may take a few minutes)...
PASS: Image built successfully from clean checkout
Running checks against https://coroner.iqoba.com...
PASS: GET / returns 200 with Run audit form
T1 faulty: job submitted, job_id=09f8167874a7
PASS: T1 faulty: ZOMBIE verdict, run_id=f584d5f35228
T1 correct: job submitted, job_id=e452d99a59d9
PASS: T1 correct: ALIVE verdict, run_id=29c15f04407b
PASS: Tamper: INVALID with replay mismatch, run_id=f584d5f35228
PASS: Verify: certificate VALID, run_id=f584d5f35228
PASS: Cache-Control: /api/* responses include no-store
PASS: Body limit: 17 KB body rejected with 413
PASS: Story step 5: Cause of death, positioning sentence and a branch table row
PASS: Fool page: counter and three checkboxes
Deployment check PASSED: all checks succeeded
```

The run ids are the same as in the local measurements of this guide because a run id is derived from content, not from the machine or the time: it is the first 12 hex characters of a SHA-256 over the hashes of the COBOL source, the Java source, the schema and the copybooks, the seed, the case count, the cobc flags and the tool versions (cobc, javac, java, python, Coroner), plus the generator script hash when the schema has one; the timestamp is excluded (`compute_run_id` in `coroner/store.py`). The same image with the same seed and case count gives the same run id on any machine.

The script prints one line per check. A healthy deployment prints these nine PASS lines (quoted from `scripts/deploy_check.py`; the run ids are filled in by the script), then the final line, and exits with code 0:

```
PASS: GET / returns 200 with Run audit form
PASS: T1 faulty: ZOMBIE verdict, run_id=<run id>
PASS: T1 correct: ALIVE verdict, run_id=<run id>
PASS: Tamper: INVALID with replay mismatch, run_id=<run id>
PASS: Verify: certificate VALID, run_id=<run id>
PASS: Cache-Control: /api/* responses include no-store
PASS: Body limit: 17 KB body rejected with 413
PASS: Story step 5: Cause of death, positioning sentence and a branch table row
PASS: Fool page: counter and three checkboxes

Deployment check PASSED: all checks succeeded
```

Exit codes: 0 all checks passed, 1 at least one check failed (a `FAIL:` line says which), 2 the build failed (without `--skip-build`).

What each check means and what to do on a `FAIL:`:

- **GET /**: the home page loads and contains the Run audit form. On FAIL, check that coroner-api is running and that cloudflared connected (cloudflared logs).
- **T1 faulty and T1 correct**: a Run audit (2000 cases, seed 42) returns ZOMBIE for the faulty port and ALIVE for the correct port. On FAIL, read the coroner-engine logs for job errors.
- **Tamper**: an edited copy of the certificate replays as INVALID with a replay mismatch. **Verify**: the unmodified certificate replays as VALID. On FAIL, check that the run files exist under `/data/runs` and read the coroner-api logs.
- **Cache-Control**: every `/api/*` response carries `no-store`. **Body limit**: a 17 KB body is rejected with 413. A FAIL on either is a code issue, not a deployment issue.
- **Story step 5**: `/story/step/5` shows the "Cause of death" heading, the positioning sentence and at least one branch table row. **Fool page**: `/fool` shows the counter sentence and the three checkboxes case1, case2 and case4. Both read the bundled demo runs and start no audit. On FAIL, check that coroner-init ended with `Bundled demo runs generated.` (step 6).
