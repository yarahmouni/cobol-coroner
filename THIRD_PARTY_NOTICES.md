# Third-Party Components

COBOL Coroner uses the following third-party components.

## Python Packages (Runtime)

### mcp 2.3.0
- License: MIT
- Used in: MCP server (coroner/mcp)
- Source: https://pypi.org/project/mcp/

### fastapi 0.163.1
- License: MIT
- Used in: Web API (coroner/ui/app.py)
- Source: https://pypi.org/project/fastapi/

### uvicorn 0.54.0
- License: BSD-3-Clause
- Used in: ASGI server for FastAPI
- Source: https://pypi.org/project/uvicorn/

### Jinja2 3.1.6
- License: BSD-3-Clause
- Used in: HTML templates (coroner/ui/templates/)
- Source: https://pypi.org/project/Jinja2/

### python-multipart 0.0.33
- License: Apache-2.0
- Used in: Form data parsing in FastAPI
- Source: https://pypi.org/project/python-multipart/

## Python Packages (Development)

### pytest 9.2.0
- License: MIT
- Used in: Test suite (tests/)
- Source: https://pypi.org/project/pytest/

### pyyaml 6.0.3
- License: MIT
- Used in: YAML parsing (workflow validation)
- Source: https://pypi.org/project/pyyaml/

### hypothesis 6.170.14
- License: MPL-2.0
- Used in: Property-based testing (tests/test_compare.py)
- Source: https://pypi.org/project/hypothesis/

## Python Packages (Test Only)

### httpx 0.28.1
- License: BSD-3-Clause
- Used in: HTTP client for API tests (tests/test_ui*.py)
- Source: https://pypi.org/project/httpx/

### pytest-xdist 3.8.0
- License: MIT
- Used in: Parallel test run (`make test`, `-n auto`); installed with the dev and test extras
- Source: https://pypi.org/project/pytest-xdist/
- Note: its dependency execnet 2.1.2 (MIT) is installed with it

## Python Packages (Screenshots Only)

### playwright 1.64.1
- License: Apache-2.0
- Used in: Browser automation for screenshots (scripts/make_screenshots.py)
- Source: https://pypi.org/project/playwright/
- Note: `python -m playwright install chromium` downloads a Chromium browser not part of this repository

### Pillow 13.0.0
- License: MIT-CMU
- Used in: Image optimization for screenshots (scripts/make_screenshots.py)
- Source: https://pypi.org/project/Pillow/

## Vendored JavaScript Libraries

### htmx 2.0.4
- License: 0BSD (BSD Zero Clause License)
- Location: coroner/ui/static/htmx.min.js
- SHA-256: e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447
- Source: https://htmx.org/

## Docker Base Image

### python:3.12-slim-bookworm
- License: see upstream
- Source: https://hub.docker.com/_/python
- Digest: sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
- Used in: Dockerfile (both builder and final stages)

## Debian Packages (from snapshot.debian.org/archive/debian/20261119T000000Z)

### build-essential 12.9
- License: see upstream
- Used in: Builder stage (Dockerfile)
- Source: Debian bookworm

### xz-utils 5.4.1-1+deb12u2
- License: see upstream
- Used in: Builder stage (extracting GnuCOBOL tarball)
- Source: Debian bookworm

### libgmp-dev 2:6.2.1+dfsg1-1.1
- License: see upstream
- Used in: Builder stage and runtime stage (GnuCOBOL dependency)
- Source: Debian bookworm

### libdb-dev 5.3.2
- License: see upstream
- Used in: Builder stage and runtime stage (GnuCOBOL dependency)
- Source: Debian bookworm

### libncurses-dev 6.4-4
- License: see upstream
- Used in: Builder stage and runtime stage (GnuCOBOL dependency)
- Source: Debian bookworm

### openjdk-17-jdk-headless 17.0.21+9-1~deb12u1
- License: see upstream
- Used in: Runtime stage (Java 17)
- Source: Debian bookworm

### libgmp10 2:6.2.1+dfsg1-1.1
- License: see upstream
- Used in: Runtime stage (GnuCOBOL runtime dependency)
- Source: Debian bookworm

### libdb5.3 5.3.28+dfsg2-1
- License: see upstream
- Used in: Runtime stage (GnuCOBOL runtime dependency)
- Source: Debian bookworm

### libncurses6 6.4-4
- License: see upstream
- Used in: Runtime stage (GnuCOBOL runtime dependency)
- Source: Debian bookworm

### gcc 4:12.2.0-3
- License: see upstream
- Used in: Runtime stage (cobc needs gcc at runtime)
- Source: Debian bookworm

### libc6-dev 2.36-9+deb12u14
- License: see upstream
- Used in: Runtime stage (cobc needs libc headers at runtime)
- Source: Debian bookworm

### git 1:2.39.5-0+deb12u3
- License: see upstream
- Used in: Runtime stage (repository checks in tests)
- Source: Debian bookworm

### make 4.3-4.1
- License: see upstream
- Used in: Runtime stage (Makefile targets)
- Source: Debian bookworm

## GnuCOBOL

### GnuCOBOL 3.2.0
- License: see upstream
- Source: https://ftp.gnu.org/gnu/gnucobol/gnucobol-3.2.tar.xz
- SHA-256: 3bb48af46ced4779facf41fdc2ee60e4ccb86eaa99d010b36685315df39c2ee2
- Built from source in Dockerfile

## JUnit

### junit-platform-console-standalone 6.1.3
- License: EPL-2.0 (Eclipse Public License 2.0)
- Location: build/junit/junit-platform-console-standalone-6.1.3.jar (downloaded by scripts/download_junit.py, not committed)
- SHA-256: e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec
- Used in: JUnit regression test execution (coroner/diag/junit.py)
- Source: https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/6.1.3/

### jqwik 1.10.2 (jqwik-api and jqwik-engine)
- License: Eclipse Public License v2.0 (EPL-2.0), as stated in the POM of each artifact
- Location: build/junit/jqwik-api-1.10.2.jar and build/junit/jqwik-engine-1.10.2.jar (downloaded by scripts/download_junit.py, not committed)
- SHA-256 jqwik-api-1.10.2.jar: 7e3b95d4ff78410273921a55aeaaea4294e5ed8171f7284680e9c3a84bf7088e
- SHA-256 jqwik-engine-1.10.2.jar: b4cc136a0efc1e2aa31514aae8d80b66fef53894c2d2777e2cc1143ca7511098
- Used in: property tests of the Case 1 Java ports (samples/traps/T1-ebcdic-match-merge/java/property/, `make pbt`)
- Source: https://repo1.maven.org/maven2/net/jqwik/
- Note: the other jqwik modules and the dependencies named in the POMs are not downloaded: the JUnit console standalone jar already carries the JUnit Platform, opentest4j and apiguardian classes.

## cloudflared

### cloudflare/cloudflared:2026.10.7
- License: see upstream
- Source: https://hub.docker.com/r/cloudflare/cloudflared
- Digest: sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba
- Used in: docker-compose.server.yml (Cloudflare Tunnel client)
