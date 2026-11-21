#!/usr/bin/env python3
"""Download and verify JUnit Platform Console Standalone jar."""
import sys
import hashlib
import ssl
import time
from pathlib import Path
from http.client import HTTPException
from urllib.request import urlopen

DEFAULT_URL = "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/6.1.3/junit-platform-console-standalone-6.1.3.jar"
DEFAULT_SHA256 = "e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec"
DEFAULT_JAR_DIR = Path("build/junit")
JAR_NAME = "junit-platform-console-standalone-6.1.3.jar"
MAX_ATTEMPTS = 4
FIRST_WAIT_SECONDS = 2


def fetch(url, attempts=MAX_ATTEMPTS, first_wait=FIRST_WAIT_SECONDS, sleep=time.sleep):
    """Return the bytes at url, retrying on HTTP and network errors (wait doubles each time)."""
    # Unverified SSL context for Maven Central: the SHA-256 check provides the security.
    ssl_context = ssl._create_unverified_context()
    wait = first_wait
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(url, context=ssl_context, timeout=60) as response:
                return response.read()
        except (OSError, HTTPException) as error:
            print(f"Download attempt {attempt} of {attempts} failed: {error}", file=sys.stderr)
            if attempt == attempts:
                raise
            sleep(wait)
            wait *= 2


def main(url=DEFAULT_URL, expected_sha256=DEFAULT_SHA256, jar_dir=DEFAULT_JAR_DIR,
         attempts=MAX_ATTEMPTS, first_wait=FIRST_WAIT_SECONDS, sleep=time.sleep):
    jar_dir = Path(jar_dir)
    jar_dir.mkdir(parents=True, exist_ok=True)
    jar_path = jar_dir / JAR_NAME

    # Check if already downloaded and verified
    if jar_path.exists():
        actual_sha256 = hashlib.sha256(jar_path.read_bytes()).hexdigest()
        if actual_sha256 == expected_sha256:
            print(f"JUnit jar already present and verified: {jar_path}")
            return 0
        print("Existing jar has wrong checksum, re-downloading...")
        jar_path.unlink()

    print("Downloading JUnit Platform Console Standalone 6.1.3...")
    try:
        data = fetch(url, attempts, first_wait, sleep)
    except (OSError, HTTPException) as error:
        print(f"ERROR: download failed after {attempts} attempts: {error}", file=sys.stderr)
        return 1
    jar_path.write_bytes(data)

    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != expected_sha256:
        print("ERROR: SHA-256 mismatch.", file=sys.stderr)
        print(f"Expected: {expected_sha256}", file=sys.stderr)
        print(f"Got:      {actual_sha256}", file=sys.stderr)
        jar_path.unlink()
        return 1

    print(f"Downloaded and verified: {jar_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
