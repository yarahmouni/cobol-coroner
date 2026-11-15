#!/usr/bin/env python3
"""Download and verify JUnit Platform Console Standalone jar."""
import sys
import hashlib
import ssl
from pathlib import Path
from urllib.request import urlopen


def main():
    jar_dir = Path("build/junit")
    jar_dir.mkdir(parents=True, exist_ok=True)
    
    jar_path = jar_dir / "junit-platform-console-standalone-6.1.3.jar"
    expected_sha256 = "e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec"
    
    # Check if already downloaded and verified
    if jar_path.exists():
        with open(jar_path, "rb") as f:
            actual_sha256 = hashlib.sha256(f.read()).hexdigest()
        if actual_sha256 == expected_sha256:
            print(f"JUnit jar already present and verified: {jar_path}")
            return 0
        else:
            print(f"Existing jar has wrong checksum, re-downloading...")
            jar_path.unlink()
    
    # Download
    print("Downloading JUnit Platform Console Standalone 6.1.3...")
    url = "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/6.1.3/junit-platform-console-standalone-6.1.3.jar"
    
    # Use unverified SSL context for Maven Central (SHA-256 verification provides security)
    ssl_context = ssl._create_unverified_context()
    with urlopen(url, context=ssl_context) as response:
        with open(jar_path, 'wb') as out_file:
            out_file.write(response.read())
    
    # Verify
    with open(jar_path, "rb") as f:
        actual_sha256 = hashlib.sha256(f.read()).hexdigest()
    
    if actual_sha256 != expected_sha256:
        print(f"ERROR: SHA-256 mismatch.", file=sys.stderr)
        print(f"Expected: {expected_sha256}", file=sys.stderr)
        print(f"Got:      {actual_sha256}", file=sys.stderr)
        jar_path.unlink()
        return 1
    
    print(f"Downloaded and verified: {jar_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
