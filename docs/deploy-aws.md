# Running COBOL Coroner on one AWS EC2 instance

Nothing in this guide has been measured on AWS: every output below is labelled "Not measured on AWS", and the numbers that are quoted come from the compose files and from [`deploy.md`](deploy.md).

This guide is optional and is not how the live demo is hosted. It creates no AWS resource by itself, and it states no prices. It is for a reader who already has an AWS account and wants the same compose files on one EC2 instance. It only covers what differs from [`deploy.md`](deploy.md); everything else is linked, not copied.

## 1. The instance

### Architecture: x86_64

The instance must be x86_64. All three Coroner services and cloudflared pin the platform in the compose files:

```
platform: linux/amd64
```

This line is in `docker-compose.yml` (coroner-init, coroner-api, coroner-engine) and in `docker-compose.server.yml` (cloudflared). The Coroner image is pinned by digest and the cloudflared image is pinned by digest, both for linux/amd64. On an arm64 instance Docker would need emulation to start them, and this repository has not been tested that way. Instance families built on arm64 processors do not fit. Check the architecture shown in the EC2 console for the instance type you choose, then check it again on the instance (section 3).

### Memory

[`deploy.md`](deploy.md), section "What you get", gives the sum of the memory limits: 2688 MB in steady state (api 512 MB, engine 2048 MB, cloudflared 128 MB). While coroner-init runs at first start, its 2048 MB limit comes on top (4736 MB of limits in total).

The instance needs at least the steady-state sum plus what the operating system and Docker use. A first start needs more than that, up to the 4736 MB of limits. These are limits, not measured usage, and nothing was measured on AWS.

The compose files also set a CPU limit per service (engine 2, api 1, cloudflared 0.25). The engine stops an audit after 60 seconds (`CORONER_JOB_TIMEOUT=60` in `docker-compose.yml`) and a certificate replay after 90 seconds (`CORONER_REPLAY_TIMEOUT`, [SECURITY.md](../SECURITY.md)). The audit times in `deploy.md` were measured on a Mac. On a slower instance an audit could reach these timeouts. Run the deployment check (section 4) to find out.

### Disk

The size of the image on disk is not measured on AWS, so this guide gives no number. After the pull in `deploy.md` step 4, run:

```bash
docker system df
```

Not measured on AWS. The `Images` row shows the space used by the pulled images. Choose a volume size that leaves room for these images, the `coroner-data` and `coroner-exchange` volumes, and the operating system. If the disk fills up, `deploy.md` (Troubleshooting, "Out of disk") describes the failure.

## 2. Network

Two options. Only the first is described and tested in this repository.

### (a) Recommended: Cloudflare Tunnel, same as deploy.md

This is the setup of [`deploy.md`](deploy.md). `docker-compose.server.yml` removes the published port of the API and adds cloudflared, which opens an outbound connection to Cloudflare. Visitors reach the API through the tunnel only.

Security group:

- Inbound: no rule for the web. One rule for SSH, for the operator, restricted to your own IP address.
- Outbound: keep outbound traffic open. The instance must reach ghcr.io (the Coroner image), Docker Hub (the cloudflared image) and Cloudflare (the tunnel). If you restrict outbound traffic, allow these destinations.

The hostname in `cloudflared-config.yml` is `coroner.iqoba.com`, which belongs to the project owner's Cloudflare account. For your own instance you need a zone in your own Cloudflare account, and you replace that hostname in `cloudflared-config.yml` and in the `tunnel route dns` command of `deploy.md` step 2 with yours. The file routes one hostname to `coroner-api:8000` and answers 404 for everything else.

### (b) Without Cloudflare

This repository does not support this option. `docker-compose.server.yml` removes the published port of the API (`ports: !reset []`) and the only override that exists adds cloudflared. Publishing the API behind your own reverse proxy with TLS needs a different override, and this repository does not provide one. This guide does not invent one.

Facts you need if you build your own:

- `docker-compose.yml` alone publishes the API only on `127.0.0.1:8000`, which is reachable from the instance itself and not from the network.
- The TLS certificate and the proxy configuration are your responsibility.
- `CORONER_TRUSTED_PROXY` is set to the cloudflared container address (10.5.0.3) only in `docker-compose.server.yml`. [`SECURITY.md`](../SECURITY.md) states that `CF-Connecting-IP` is trusted only from that address and that `X-Forwarded-For` is never trusted. From this, the per-IP limits and the "one active audit per client IP" rule would apply to the address of your proxy and not to each visitor. This is an inference from SECURITY.md and was not tested.
- The security controls listed in SECURITY.md are documented and tested for option (a). Any control that depends on Cloudflare is managed outside this repository.

## 3. Install Docker Engine and the Compose plugin

Follow Docker's official installation pages for the distribution on your instance:

- Docker Engine: https://docs.docker.com/engine/install/
- Compose plugin on Linux: https://docs.docker.com/compose/install/linux/

Then run the version checks of [`deploy.md`](deploy.md), section "1. Prerequisites on the server":

```bash
uname -m
```

Not measured on AWS. The line must be `x86_64`.

```bash
docker version --format '{{.Server.Version}}'
```

Not measured on AWS. The line is the Docker Engine version.

```bash
docker compose version --short
```

Not measured on AWS. The line is the Compose version. Compose must support `!reset`, which `docker-compose.server.yml` uses to remove the published port. The compose files were tested with Compose 2.33.1, and older versions fail as described in `deploy.md`, Troubleshooting, "Compose too old for `!reset`".

```bash
git --version
```

Not measured on AWS. The line looks like `git version <x.y.z>`.

## 4. Deploy

Continue with [`deploy.md`](deploy.md) from [section 2, "Cloudflare tunnel"](deploy.md#2-cloudflare-tunnel), through the pull, the merged-configuration check, the start, and the check from anywhere. Use your own hostname where the guide says `coroner.iqoba.com` (section 2 above).

Two points for an instance:

- The cloudflared credentials file lives on the instance disk. Keep it outside the repository clone, as `deploy.md` says.
- `make deploy-check` first builds the Dockerfile from a clean `git clone`, which the server itself never does. To avoid building on the instance, run the check from your own computer, or on the instance with `--skip-build`, as described in the section "Check from anywhere" of `deploy.md`. Its output on AWS: Not measured on AWS. A healthy deployment prints the PASS lines listed there.

## 5. Costs and cleanup

This guide gives no prices. Check the pricing pages and the billing console of your own account.

When you are done:

- Stop the instance if you want to keep it for later, or terminate it. A stopped instance still has its volume. Terminating an instance deletes its root volume only if the "delete on termination" setting is on, so check it and delete any volume that remains.
- Delete anything else you created for this test: additional volumes, snapshots, images (AMIs) and any public IP address you allocated.
- Delete the Cloudflare tunnel and the DNS record for your hostname in your Cloudflare account. Deleting the instance's volume removes the credentials file from the instance, but the tunnel stays in your Cloudflare account until you delete it.
- To remove only Coroner and its data from a running instance, `docker compose -f docker-compose.yml -f docker-compose.server.yml down -v` stops the services and deletes the volumes, including the bundled demo runs (see `deploy.md`, "Day-to-day operations").
