#!/usr/bin/env python3
"""Download and verify the Java test jars: JUnit Platform Console Standalone and jqwik."""
import sys
import hashlib
import ssl
import time
from pathlib import Path
from http.client import HTTPException
from urllib.request import urlopen

MAVEN = "https://repo1.maven.org/maven2"
DEFAULT_URL = f"{MAVEN}/org/junit/platform/junit-platform-console-standalone/6.1.3/junit-platform-console-standalone-6.1.3.jar"
DEFAULT_SHA256 = "e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec"
DEFAULT_JAR_DIR = Path("build/junit")
JAR_NAME = "junit-platform-console-standalone-6.1.3.jar"
MAX_ATTEMPTS = 4
FIRST_WAIT_SECONDS = 2

# jqwik 1.10.2 (property-based testing on the Java side, EPL-2.0). Only the two jars it needs at
# run time: the console standalone jar already carries the JUnit Platform, opentest4j and
# apiguardian. jqwik-web and jqwik-time (in the aggregator POM) are not used.
# SHA-256 values equal the .jar.sha256 files published next to each jar on Maven Central.
JQWIK_JARS = (
    ("jqwik-api-1.10.2.jar",
     f"{MAVEN}/net/jqwik/jqwik-api/1.10.2/jqwik-api-1.10.2.jar",
     "7e3b95d4ff78410273921a55aeaaea4294e5ed8171f7284680e9c3a84bf7088e"),
    ("jqwik-engine-1.10.2.jar",
     f"{MAVEN}/net/jqwik/jqwik-engine/1.10.2/jqwik-engine-1.10.2.jar",
     "b4cc136a0efc1e2aa31514aae8d80b66fef53894c2d2777e2cc1143ca7511098"),
)


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


def ensure_jar(jar_name, url, expected_sha256, jar_dir=DEFAULT_JAR_DIR,
               attempts=MAX_ATTEMPTS, first_wait=FIRST_WAIT_SECONDS, sleep=time.sleep):
    """Make jar_dir/jar_name exist with the expected SHA-256. Return 0 on success, 1 on failure."""
    jar_dir = Path(jar_dir)
    jar_dir.mkdir(parents=True, exist_ok=True)
    jar_path = jar_dir / jar_name

    # Check if already downloaded and verified
    if jar_path.exists():
        actual_sha256 = hashlib.sha256(jar_path.read_bytes()).hexdigest()
        if actual_sha256 == expected_sha256:
            print(f"Jar already present and verified: {jar_path}")
            return 0
        print("Existing jar has wrong checksum, re-downloading...")
        jar_path.unlink()

    print(f"Downloading {jar_name}...")
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


def main(url=DEFAULT_URL, expected_sha256=DEFAULT_SHA256, jar_dir=DEFAULT_JAR_DIR,
         attempts=MAX_ATTEMPTS, first_wait=FIRST_WAIT_SECONDS, sleep=time.sleep):
    """Download the JUnit Platform Console Standalone jar only."""
    return ensure_jar(JAR_NAME, url, expected_sha256, jar_dir, attempts, first_wait, sleep)


def main_all(jar_dir=DEFAULT_JAR_DIR):
    """Download the JUnit jar and the jqwik jars. Return 1 if any download failed."""
    codes = [main(jar_dir=jar_dir)]
    codes += [ensure_jar(name, url, sha256, jar_dir) for name, url, sha256 in JQWIK_JARS]
    return 1 if any(codes) else 0


if __name__ == "__main__":
    sys.exit(main_all())
