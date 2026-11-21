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
- /api/gate-check: 1 request per 10 seconds per IP, charged only to requests that start a replay (see "Gate Check" below)
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

### Gate Check (POST /api/gate-check)

The guided story asks the real gate whether a run may be committed. The endpoint takes one form field, `run_id`, and applies these checks in this order:

1. Global limit: 100 requests per minute.
2. Per-IP limit: 20 requests per minute.
3. `run_id` validation: exactly 12 lowercase hexadecimal characters, otherwise 404. The certificate is read only from the server-side run folder of that id; a missing certificate gives 404.
4. Certificate size limit: 1 MB, otherwise 413.
5. Cache lookup by the SHA-256 of the raw certificate file bytes (not a field inside the certificate), so an edited certificate never gets the cached answer of the original. Entries live 600 seconds. A cache hit is answered at once and does not consume the gate-check limit. It still counts toward the global and per-IP limits above.
6. Gate-check limit, only for a request that will start a replay: 1 request per 10 seconds per IP (window set by `CORONER_GATE_CHECK_RATE_WINDOW`, default 10).
7. Replay of the certificate in a child process group, off the event loop, with a timeout of 90 seconds (`CORONER_REPLAY_TIMEOUT`, default 90). On timeout the whole process group is killed, the answer is 503 and nothing is cached.

The decision comes from the same function as the command-line gate (`gate_decision`): the file hashes must match the certificate, the replay must be VALID, and the status must be ZOMBIE for the answer "This ZOMBIE migration cannot be committed". Any other failed case answers that the certificate is invalid or does not match the audited files.

Only answers from a replay that ran to a verdict are cached (VALID, or INVALID for a real mismatch such as a modified certificate or a changed file). A replay that timed out, was killed or failed to run is answered with 503, "Replay did not complete, try again" and a Retry-After header, and nothing is cached, so a failed replay never turns into ten minutes of "invalid".

### Schema Generator Scripts

A schema.json may name a Python `generator_script` that produces the test cases. It is the only place where the engine runs code that comes with a sample, so it is restricted. The path is read relative to the schema's folder, symlinks are resolved, and the script must be a regular file inside that folder. Otherwise the run stops with "ERROR: generator script outside schema directory", exit status 2, before the script is read or executed, and no run, verdict or certificate is written. The engine reads the script once, hashes those bytes and compiles and runs exactly those bytes; it does not import it. The hash recorded in the run is the hash of the executed bytes, and if the file on disk no longer has that hash when the inputs are recorded, the run stops with an error. The script's SHA-256 is part of the run id and of the certificate. Certificate replay refuses a certificate whose script changed ("generator script hash mismatch"), and so do the CI gate, the Git pre-commit hook and the gate check above, because the script is one of the files they compare. The public demo runs only the bundled samples and accepts no user schema or script.

### Cloudflare Protection

- Cloudflare Tunnel only (no published host port)
- Further Cloudflare settings are managed outside this repository
- No Cloudflare Access (judges must not log in)
- Only coroner.iqoba.com routed to the API
- Tunnel credentials file mounted read-only
- No tunnel token or credential in the repository
