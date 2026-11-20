# Security Policy

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

To report a security vulnerability, use GitHub's private vulnerability reporting:

1. Report directly at https://github.com/yarahmouni/cobol-coroner/security/advisories/new
2. Go to the Security tab of this repository and click "Report a vulnerability"
3. Provide details of the vulnerability

## Supported Versions

The main branch and the live demo at https://coroner.iqoba.com are supported.

## Live Demo Security Controls

The live demo at https://coroner.iqoba.com implements the following security controls:

### Container Isolation

- **Engine container**: network mode none (no network access), user 1000:1000 (non-root), read-only root filesystem, cap_drop ALL (no capabilities), no-new-privileges, 2 CPUs, 2 GB memory, 256 PIDs limit
- **API container**: user 1000:1000 (non-root), read-only root filesystem, no-new-privileges, 1 CPU, 512 MB memory, 128 PIDs limit
- **Init container**: network mode none, user 1000:1000, read-only root filesystem, cap_drop ALL, no-new-privileges, 2 CPUs, 2 GB memory, 256 PIDs limit
- **Cloudflared container**: user 65532:65532 (nonroot), read-only root filesystem, cap_drop ALL, no-new-privileges, 0.25 CPU, 128 MB memory, 32 PIDs limit

### Per-Audit Sandbox

- Fixed server-side samples only (credit-fees, T1 to T5)
- Fixed server-side ports only (correct, faulty)
- Seed: 0 to 1000000
- Cases: 10 to 2000
- Job timeout: 60 seconds (kills process group)
- One active audit per client IP
- Queue size: 3
- Visitor-run quota: 100 (oldest removed first; bundled demo runs are never counted toward quota or deleted)

### Request Validation

- Unknown fields rejected (Pydantic extra = "forbid")
- Body size limit: 16 KB on /api/* endpoints
- Certificate size limit: 1 MB

### Rate Limits (per API process)

- Global: 100 requests per minute
- Per IP: 20 requests per minute
- /api/run: 5 requests per minute per IP
- /api/verify: 1 request per 10 seconds per IP
- /api/tamper: 1 request per 10 seconds per IP
- All rate-limited responses include Retry-After header

### Network and Headers

- CF-Connecting-IP trusted only from CORONER_TRUSTED_PROXY (10.5.0.3, the cloudflared container address)
- X-Forwarded-For never trusted
- Cache-Control: no-store, no-cache, must-revalidate on all /api/* responses
- Cache-Control: public, max-age=86400 on /static/*

### Certificate Operations

- Verify and Tamper read only server-side certificates by validated run_id (12 lowercase hex characters)
- Tamper works server-side on a logged copy (deleted after replay)
- Replay timeout: 90 seconds (kills process group)
- Replay recomputes every recorded file hash before running

### Cloudflare Protection

- Cloudflare Tunnel only (no published host port)
- Further Cloudflare settings are managed outside this repository
- No Cloudflare Access (judges must not log in)
- Only coroner.iqoba.com routed to the API
- Tunnel credentials file mounted read-only
- No tunnel token or credential in the repository
