#!/usr/bin/env bash

# Smoke test runner for COBOL Coroner S0 toolchain validation.
# Runs on host (with .venv) and in Docker container.
# Exits 0 with 'Smoke test PASSED' if all checks succeed, exits 1 otherwise.

set -euo pipefail

# Change to repo root so script works from any directory
cd "$(dirname "$0")/.."

# Print FAILED on any error
trap 'echo "Smoke test FAILED"' ERR

# Detect Python interpreter: use .venv if present, else python3
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

# Create build directory if missing
mkdir -p build

echo "=== COBOL Smoke Test ==="

# Truncate trace file to ensure no stale data
: > build/toy_trace.txt

# Compile toy.cob with tracing
cobc -x -ftraceall smoke/toy.cob -o build/toy

# Run COBOL program with trace enabled
COB_SET_TRACE=Y COB_TRACE_FILE=build/toy_trace.txt ./build/toy

if [ ! -s "build/toy_trace.txt" ]; then
    echo "ERROR: Trace file is missing or empty"
    echo "Smoke test FAILED"
    exit 1
fi

echo "[COBOL] toy executed successfully"

# Parse trace and count line numbers
LINE_COUNT=$($PYTHON -c "
from coroner.parse.trace import parse_trace
lines = parse_trace('build/toy_trace.txt')
print(len(lines))
")

if [ "$LINE_COUNT" -eq 0 ]; then
    echo "ERROR: No line numbers found in trace"
    echo "Smoke test FAILED"
    exit 1
fi

echo "[COBOL] trace contains $LINE_COUNT line numbers"

echo "=== Java Smoke Test ==="

# Compile Java program
javac -d build/ smoke/Toy.java

# Run Java program and capture version
JAVA_VERSION=$(java -cp build/ Toy)

echo "[Java] $JAVA_VERSION"

# Verify Java version contains "17." prefix
if [[ "$JAVA_VERSION" != *' 17.'* ]]; then
    echo "ERROR: Java version does not contain ' 17.'"
    echo "Smoke test FAILED"
    exit 1
fi

echo ""
echo "Smoke test PASSED"
exit 0
