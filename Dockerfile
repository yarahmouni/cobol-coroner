# Multi-stage Dockerfile for COBOL Coroner smoke test
# Base: python:3.12-slim-bookworm pinned by digest
# Contains: GnuCOBOL 3.2.0 (built from source), OpenJDK 17, Python 3.12

# Builder stage: compile GnuCOBOL 3.2.0 from official GNU tarball
FROM python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS builder

# Install build dependencies with pinned versions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    xz-utils=5.4.1-1+deb12u2 \
    libgmp-dev=2:6.2.1+dfsg1-1.1 \
    libdb-dev=5.3.2 \
    libncurses-dev=6.4-4 \
    && apt-get clean

# Download GnuCOBOL 3.2.0 tarball using Python
# sha256 computed from the downloaded release tarball on 2026-11-15
RUN python3 -c "import urllib.request; urllib.request.urlretrieve('https://ftp.gnu.org/gnu/gnucobol/gnucobol-3.2.tar.xz', '/tmp/gnucobol-3.2.tar.xz')" && \
    echo "3bb48af46ced4779facf41fdc2ee60e4ccb86eaa99d010b36685315df39c2ee2  /tmp/gnucobol-3.2.tar.xz" | sha256sum -c -

# Extract and build GnuCOBOL 3.2.0
RUN cd /tmp && \
    tar -xf gnucobol-3.2.tar.xz && \
    cd gnucobol-3.2 && \
    ./configure --prefix=/opt/gnucobol && \
    make -j$(nproc) && \
    make install

# Download and verify JUnit jar
COPY scripts/download_junit.py /tmp/download_junit.py
RUN python3 /tmp/download_junit.py

# Final stage: runtime image
FROM python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# Install runtime dependencies with pinned versions
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless=17.0.21+9-1~deb12u1 \
    libgmp10=2:6.2.1+dfsg1-1.1 \
    libgmp-dev=2:6.2.1+dfsg1-1.1 \
    libdb5.3=5.3.28+dfsg2-1 \
    libdb-dev=5.3.2 \
    libncurses6=6.4-4 \
    libncurses-dev=6.4-4 \
    gcc=4:12.2.0-3 \
    libc6-dev=2.36-9+deb12u14 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy GnuCOBOL installation from builder stage
COPY --from=builder /opt/gnucobol /opt/gnucobol

# Add GnuCOBOL to PATH
ENV PATH="/opt/gnucobol/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/gnucobol/lib" \
    COB_LIBRARY_PATH="/opt/gnucobol/lib/gnucobol"

# Create non-root user coroner with UID 1000
RUN groupadd -g 1000 coroner && \
    useradd -u 1000 -g coroner -m -s /bin/bash coroner

# Set up working directory
WORKDIR /app

# Copy application files
COPY --chown=coroner:coroner coroner/ coroner/
COPY --chown=coroner:coroner smoke/ smoke/
COPY --chown=coroner:coroner samples/ samples/
COPY --chown=coroner:coroner tests/ tests/
COPY --chown=coroner:coroner scripts/ scripts/
COPY --chown=coroner:coroner pyproject.toml pyproject.toml
COPY --chown=coroner:coroner .kiro/coroner-scope.json .kiro/coroner-scope.json

# Create build directory and copy JUnit jar from builder stage
RUN mkdir -p build/junit && chown -R coroner:coroner build
COPY --from=builder --chown=coroner:coroner /build/junit/ build/junit/

# Install Python dependencies (runtime, dev and test groups) as root
RUN python3 -m pip install --no-cache-dir -e ".[dev,test]"

# Switch to non-root user
USER coroner

# Default command runs the smoke test
CMD ["bash", "smoke/run_smoke.sh"]
