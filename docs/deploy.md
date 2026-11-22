# Deployment guide

This guide deploys COBOL Coroner at https://coroner.iqoba.com on a Linux amd64 server behind a Cloudflare Tunnel. Follow it in order.

How outputs are labelled in this guide:

- "Measured on the operator's Mac, 2026-11-21": real output of the command on the operator's machine (Docker Desktop), copied verbatim. Container, volume and network names start with the name of the local project folder; on the server they start with the name of the folder you clone into.
- "Measured on the server, 2026-11-21": measured by the owner on the deployment server; "(owner's summary)" marks outputs given as a summary rather than terminal lines.

Image change on 2026-11-22 (second image): the image pinned in this guide is the one published by `publish-image.yml` run 45029885381 from commit 2c2a11b (901 tests passed in the image). It replaces the image of commit eb4b915 (sha256:3f57cae7...67511ba3, run 44976586677), which is the image the live site runs until the owner redeploys. It adds the verdict box for a reused Run audit result (R-174) and the amount difference figure for Cases 2 to 5, kept in a derived file that coroner-init adds for existing runs (R-175, R-177). Local upgrade check (operator, 2026-11-22): a stack on the previous image with a Case 3 run was switched to the new image on the same volumes; coroner-init wrote amount_difference.json for 6 runs ("written 6, already present 0, not applicable 7, no figure 0, errors 0"), the 141 existing run files were byte-identical, the Case 3 certificate replays VALID, the cached Case 3 result shows "44 amounts affected" and "Largest single difference: 19962848.06", and the deployment check passed all 10 checks.

Image change on 2026-11-22 (first image): the image of commit eb4b915 (805 tests passed in the image) replaced the image of commit c3358ed (sha256:0ca88a1f...501a4ad4, run 44943106518), which was never deployed, and added the reboot fix (restart policies and recovery of stale running jobs, R-170) and the gate message fix (R-172). The outputs labelled "Measured on the operator's Mac" below were recorded with the image of commit c3358ed. Where a block shows the image digest, the digest was replaced by the new one; the other lines, the times and the run ids are as recorded. Local check of the eb4b915 image (operator, 2026-11-22): the deployment check passed every check, with run ids f584d5f35228 and 29c15f04407b; with the engine stopped, three Run audit jobs stayed running and the API answered 429; after the engine restarted it logged "Recovered 3 stale running job(s)" and Run audit was accepted. Outputs labelled "Measured on the server" were measured on the previous image (sha256:837503172e4d...b0ebe1e8) and stay as recorded until the owner redeploys.

## What you get

Three Coroner services plus cloudflared. All three Coroner services run the same prebuilt image from GitHub Container Registry, pinned by digest:

```
ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
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

Measured on the server with the previous image (...b0ebe1e8). Not measured again on the server with the new image; the owner has not redeployed yet.

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

Measured on the operator's Mac, 2026-11-21 (`docker compose pull` with `docker-compose.yml` only, in a separate compose project with fresh volumes, after `docker logout ghcr.io`, with the previous image not present; so cloudflared is not part of it): the anonymous pull took 45 seconds. The layer lines of this pull were not recorded. The image layers are the same on the server.

On the server the same command also pulls cloudflared. Measured on the server, 2026-11-21 (owner's summary): both images were pulled, the Coroner image in 17.4 s and cloudflared in 0.8 s.

Read the digest back from the pulled image and compare it with the one in `docker-compose.yml`. They must match exactly:

```bash
docker image inspect --format '{{index .RepoDigests 0}}' ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
```

The output of this command was not recorded for the new image. What was measured on the operator's Mac, 2026-11-21, with the image of commit c3358ed, is `docker compose config --images` in the same separate compose project, which lists the digest for the three Coroner services (the digest shown is the new one, see "Image change on 2026-11-22" at the top):

```
ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
```

## 5. Check the merged configuration

Before starting, list the image lines of the merged configuration:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml config | grep -n "image:"
```

Measured on the operator's Mac, 2026-11-21 (with `TUNNEL_ID` and `TUNNEL_CREDENTIALS_FILE` set to dummy values; line numbers are positions in the merged output):

```
23:    image: cloudflare/cloudflared:2026.10.7@sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba
75:    image: ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
118:    image: ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
154:    image: ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
183:x-coroner-image: ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211
```

All three Coroner services must show the same digest, and none of them may have a `build` key. The API must not publish a port on the server. This command must print nothing:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml config | grep -n "published"
```

Measured on the operator's Mac, 2026-11-21 (same dummy values): the command printed nothing.

If it prints a line, the `ports: !reset []` override did not apply: your Compose is too old (see Troubleshooting).

Measured on the server, 2026-11-21 (owner's summary): the image check printed four image lines (the three Coroner services on the digest ending in b0ebe1e8, and cloudflared), and the `published` check printed nothing.

## 6. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

Measured on the server, 2026-11-21 (owner's summary): Compose created the network and the two volumes; `coroner-init` exited after 55.0 s; `coroner-engine`, `coroner-api` and `cloudflared` started. On the operator's Mac, the same command with `docker-compose.yml` only (no cloudflared), in a separate compose project with fresh volumes, took 47 seconds on 2026-11-21. The Compose output lines of this start were not recorded.

First start took 47 seconds there, because coroner-init generates the bundled demo runs before the API starts. A later restart or redeploy generates no run that already exists: coroner-init keeps every existing run folder and only rebuilds the two catalog files (see "Update to a new image").

List the running services:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}'
```

Measured on the server, 2026-11-21 (owner's summary): `cloudflared`, `coroner-api` and `coroner-engine` all have a status starting with `Up`. Look for `coroner-api`, `coroner-engine` and `cloudflared` with a status starting with `Up`. Without `-a`, `coroner-init` is not listed because it has exited. On the operator's Mac (no cloudflared), 2026-11-21, the command was run with `-a`, so the exited `coroner-init` is listed:

```
SERVICE          IMAGE                                                                                                      STATUS
coroner-api      ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211   Up 5 minutes
coroner-engine   ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211   Up 6 minutes
coroner-init     ghcr.io/yarahmouni/cobol-coroner@sha256:7bc88f3cd371903865c3303af2e9ca6285edc18b23b42874fe812f1d4efc7211   Exited (0) 5 minutes ago
```

Check the restart policy of each running container. The command lists the running containers of this compose project and prints the policy the Docker daemon applies to each:

```bash
docker inspect --format '{{.Name}} {{.HostConfig.RestartPolicy.Name}}' $(docker compose -f docker-compose.yml -f docker-compose.server.yml ps -q)
```

Expected output (not measured on the server; the container names start with the name of the folder you cloned into, here `cobol-coroner`): three lines, each ending in `unless-stopped`.

```
/cobol-coroner-cloudflared-1 unless-stopped
/cobol-coroner-coroner-api-1 unless-stopped
/cobol-coroner-coroner-engine-1 unless-stopped
```

`coroner-init` is not listed because it has exited, and it has no restart policy on purpose (see "After a host reboot").

Check that the demo runs were generated:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml logs coroner-init
```

Measured on the operator's Mac, 2026-11-21 (last 12 lines):

```
coroner-init-1  | No run found for T4 faulty, generating it
coroner-init-1  | Generated run e00ac9d50c76 for T4 faulty
coroner-init-1  | No run found for T4 correct, generating it
coroner-init-1  | Generated run 1c1b8639eb0c for T4 correct
coroner-init-1  | No run found for T5 faulty, generating it
coroner-init-1  | Generated run 5e61025dd742 for T5 faulty
coroner-init-1  | No run found for T5 correct, generating it
coroner-init-1  | Generated run 677bd44c5bf5 for T5 correct
coroner-init-1  | 
coroner-init-1  | Wrote /data/runs/trap_catalog.json
coroner-init-1  | Wrote /data/runs/trap_catalog.txt
coroner-init-1  | Bundled demo runs generated.
```

On the server the service name prefix differs. The last line must be `Bundled demo runs generated.` On the server, 2026-11-21, the logs end with `Bundled demo runs generated.`

The excerpt above is the end of a first start, on fresh volumes, where every run is generated. On a later start the script prints one more line before the catalog step, `Bundled runs kept: <run ids>; generated: <run ids>` (`none` when a list is empty), and the catalog step prints `Kept existing run <id> for <trap> <faulty or correct>` for each port that already has a run. The last line is unchanged.

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

What a redeploy does to the data volume: `coroner-init` runs again on every `up -d`. It never reruns an audit for an existing run id and never changes a file inside a run folder, so Verify keeps working on runs made before the redeploy, including visitor runs. It always rebuilds the two derived files `runs/trap_catalog.json` and `runs/trap_catalog.txt` from the runs on disk (`python -m coroner traps --from-runs`), so the new image's card and case names appear without regenerating anything. A bundled run is generated only if its folder is missing, in a scratch folder under `build/` and moved into `runs/` only when no folder with that run id exists. If the catalog finds a run folder that exists but whose `inputs.json` does not match a trap port, the rebuild stops with exit code 2 and writes nothing. This never keeps the site down: `coroner-init` prints the rebuild output, then one line, `WARNING: catalog rebuild failed (exit <rc>); the previous catalog files are kept and the site starts with them.` (or, when no `runs/trap_catalog.json` exists yet, `WARNING: catalog rebuild failed (exit <rc>); no catalog file exists yet, the Detection Matrix has no data until a rebuild succeeds.`), exits 0 and ends with `Bundled demo runs generated.`, so `coroner-api` starts and serves every existing run with the previous catalog files, which stay byte for byte unchanged. A failure while generating a bundled run still exits 2. After fixing the cause, rebuild the catalog by hand: `docker compose -f docker-compose.yml -f docker-compose.server.yml run --rm coroner-init`.

After the upgrade, `docker compose -f docker-compose.yml -f docker-compose.server.yml logs coroner-init | grep "Amount difference"` shows the derivation summary.

## After a host reboot

The stack comes back by itself. `coroner-api`, `coroner-engine` and `cloudflared` have `restart: unless-stopped` in `docker-compose.server.yml`, so the Docker daemon starts them again when the host boots, without running Compose. `coroner-init` has no restart policy: it stays `Exited (0)`, which is normal, and it is not run again. The API and the engine start from the existing volumes, which `coroner-init` already filled at the first start. This behaviour is not measured here by rebooting the host. A Run audit that was running when the host went down shows an error and must be run again; the engine marks it at start.

Check:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml ps -a --format 'table {{.Service}}\t{{.Status}}'
```

Look for `coroner-api`, `coroner-engine` and `cloudflared` with a status starting with `Up`, and `coroner-init` as `Exited (0)`.

A service stopped with `docker compose stop` stays stopped after a reboot (that is what `unless-stopped` means). `docker compose down` removes the containers, so nothing comes back until the next `up -d`.

## Troubleshooting

**Error 1033.** Cloudflare shows error 1033 when the tunnel is not connected: nobody is running cloudflared for coroner.iqoba.com, or it cannot reach Cloudflare. Check, in this order:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml ps
docker compose -f docker-compose.yml -f docker-compose.server.yml logs --tail 50 cloudflared
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

The first command shows whether `cloudflared` is `Up` (an `Exited` status means no tunnel). The second shows why it stopped or whether it registered its connections ("Registered tunnel connection" lines). The third starts every service that is not running and changes nothing for the ones that are.

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

Measured on the operator's Mac, 2026-11-21: the start time given in step 6 (47 seconds), and the compose state shown there with the UI answering on http://127.0.0.1:8000.

Open http://127.0.0.1:8000. The home page shows the Run audit form.

Run the deployment check against it (needs the project virtual environment, see the last section):

```bash
make deploy-check
```

Measured on the operator's Mac, 2026-11-21 (`make deploy-check URL=http://127.0.0.1:8000`, exit code 0, 242 seconds wall time; the first line is the command `make` runs with `PYTHON` pointing to the project environment). This run was made on the image of commit c3358ed. The image then changed for the reboot fix (R-170) and the gate message (R-172), and the local check of the new image passed on 2026-11-22 (every check PASS, run ids f584d5f35228 and 29c15f04407b; the output of that run was not recorded here):

```
.venv/bin/python scripts/deploy_check.py --url http://127.0.0.1:8000
Building image from clean git clone...
Current HEAD: c3358edb8845747c4c848b6aceccdb3bb34bce14
Cloning into <TMPDIR>/coroner-deploy-XXXX...
Building Docker image (this may take a few minutes)...
PASS: Image built successfully from clean checkout

Running checks against http://127.0.0.1:8000...
PASS: GET / returns 200 with Run audit form
T1 faulty: job submitted, job_id=8fde10b9e9af
PASS: T1 faulty: ZOMBIE verdict, run_id=f584d5f35228
T1 correct: job submitted, job_id=61a0679e6b82
PASS: T1 correct: ALIVE verdict, run_id=29c15f04407b
PASS: Tamper: INVALID with replay mismatch, run_id=f584d5f35228
PASS: Verify: certificate VALID, run_id=f584d5f35228
PASS: Cache-Control: /api/* responses include no-store
PASS: Body limit: 17 KB body rejected with 413
PASS: Story step 5: Cause of death, positioning sentence and a branch table row
PASS: Fool page: counter and three checkboxes

Deployment check PASSED: all checks succeeded
```

The whole command took 242 seconds, including the image build from a clean `git clone`.

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

The output below was measured against the live site while it ran the previous image (...b0ebe1e8); it is kept as recorded.

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
