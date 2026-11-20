#!/usr/bin/env bash
# Generate bundled demo runs for Docker Compose first start
# Each verify must return its expected exit code (0 ALIVE, 1 ZOMBIE)

set -euo pipefail

PY="${PYTHON:-python3}"
BASE_DIR="${CORONER_BASE_DIR:-/data}"

# Check if all expected runs already exist
if [ -d "$BASE_DIR/runs/f584d5f35228" ] && \
   [ -d "$BASE_DIR/runs/29c15f04407b" ] && \
   [ -d "$BASE_DIR/runs/df4d7929ce44" ] && \
   [ -d "$BASE_DIR/runs/08d14a07bcdb" ] && \
   [ -f "$BASE_DIR/runs/trap_catalog.json" ]; then
    echo "Bundled demo runs already exist, skipping generation."
    exit 0
fi

echo "Generating bundled demo runs..."

# Helper: run a command and check its exit code for verify commands
run_expect() {
    expected=$1
    name=$2
    shift 2
    set +e
    "$@" > "/tmp/$name.log" 2>&1
    rc=$?
    set -e
    cat "/tmp/$name.log"
    if [ "$rc" -ne "$expected" ]; then
        echo "ERROR: $name expected exit $expected, got $rc"
        exit 2
    fi
    grep "^Run: " "/tmp/$name.log" || {
        echo "ERROR: $name printed no Run line"
        exit 2
    }
}

# T1 faulty (ZOMBIE, exit 1)
run_expect 1 t1_faulty "$PY" -m coroner verify \
    --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob \
    --copybooks samples/traps/T1-ebcdic-match-merge/copybooks \
    --java samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java \
    --schema samples/traps/T1-ebcdic-match-merge/schema.json \
    --cases 2000 --seed 42

# T1 correct (ALIVE, exit 0)
run_expect 0 t1_correct "$PY" -m coroner verify \
    --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob \
    --copybooks samples/traps/T1-ebcdic-match-merge/copybooks \
    --java samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java \
    --schema samples/traps/T1-ebcdic-match-merge/schema.json \
    --cases 2000 --seed 42

# credit-fees correct (ALIVE, exit 0)
run_expect 0 cf_correct "$PY" -m coroner verify \
    --cobol samples/credit-fees/CREDIT-FEES.cob \
    --copybooks samples/credit-fees/copybooks \
    --java samples/credit-fees/java/CreditFees.java \
    --schema samples/credit-fees/schema.json \
    --cases 2000 --seed 42

# credit-fees HALF_EVEN variant (ZOMBIE, exit 1)
# Use pre-generated variant from build/variants/ (generated at image build time)
run_expect 1 cf_half_even "$PY" -m coroner verify \
    --cobol samples/credit-fees/CREDIT-FEES.cob \
    --copybooks samples/credit-fees/copybooks \
    --java build/variants/CreditFees.java \
    --schema samples/credit-fees/schema.json \
    --cases 2000 --seed 42

# Detection matrix (exit 0, writes catalog files)
set +e
"$PY" -m coroner traps > /tmp/trap_catalog.log 2>&1
rc=$?
set -e
cat /tmp/trap_catalog.log
if [ "$rc" -ne 0 ]; then
    echo "ERROR: trap_catalog expected exit 0, got $rc"
    exit 2
fi
if [ ! -f "$BASE_DIR/runs/trap_catalog.json" ]; then
    echo "ERROR: trap_catalog.json not found"
    exit 2
fi
if [ ! -f "$BASE_DIR/runs/trap_catalog.txt" ]; then
    echo "ERROR: trap_catalog.txt not found"
    exit 2
fi

echo "Bundled demo runs generated."
