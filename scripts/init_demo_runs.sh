#!/usr/bin/env bash
# Prepare the bundled demo runs for Docker Compose start.
#
# Owner rule: a redeploy rebuilds only derived files. Every bundled run is generated only if its
# run folder does not exist, an existing run folder is never touched, and runs/trap_catalog.json
# and runs/trap_catalog.txt are always rebuilt from the runs on disk (python -m coroner traps
# --from-runs). Each verify must return its expected exit code (0 ALIVE, 1 ZOMBIE).
#
# Environment: CORONER_BASE_DIR (default /data), PYTHON (default python3),
# CORONER_VARIANT_JAVA (default build/variants/CreditFees.java, the HALF_EVEN variant).

set -euo pipefail

PY="${PYTHON:-python3}"
BASE_DIR="${CORONER_BASE_DIR:-/data}"
VARIANT_JAVA="${CORONER_VARIANT_JAVA:-build/variants/CreditFees.java}"
export CORONER_BASE_DIR="$BASE_DIR"

mkdir -p "$BASE_DIR/runs" "$BASE_DIR/build"

# New runs are made in a scratch folder and moved into runs/ only when their run id is not there
SCRATCH="$(mktemp -d "$BASE_DIR/build/.init-XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

KEPT=""
GENERATED=""

# Helper: run a verify command and check its exit code (0 ALIVE, 1 ZOMBIE)
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

# bundled_run <expected run id> <name> <expected exit> <verify arguments...>
# The run is generated only if runs/<expected run id> does not exist. The run id printed by the
# engine is checked again before the move, so an existing folder is never overwritten.
bundled_run() {
    expected_id=$1
    name=$2
    expected_rc=$3
    shift 3
    if [ -d "$BASE_DIR/runs/$expected_id" ]; then
        KEPT="$KEPT $expected_id"
        return 0
    fi
    work="$SCRATCH/$name"
    mkdir -p "$work"
    run_expect "$expected_rc" "$name" env CORONER_BASE_DIR="$work" "$PY" -m coroner verify "$@"
    actual_id="$(grep -m1 '^Run: runs/' "/tmp/$name.log" | sed 's|^Run: runs/||')"
    if [ -z "$actual_id" ] || [ ! -d "$work/runs/$actual_id" ]; then
        echo "ERROR: $name produced no run folder"
        exit 2
    fi
    if [ -e "$BASE_DIR/runs/$actual_id" ]; then
        # Same content as an existing run: keep the existing folder, discard the new one
        KEPT="$KEPT $actual_id"
        return 0
    fi
    mv "$work/runs/$actual_id" "$BASE_DIR/runs/$actual_id"
    GENERATED="$GENERATED $actual_id"
}

echo "Preparing bundled demo runs..."

# T1 faulty (ZOMBIE, exit 1)
bundled_run f584d5f35228 t1_faulty 1 \
    --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob \
    --copybooks samples/traps/T1-ebcdic-match-merge/copybooks \
    --java samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java \
    --schema samples/traps/T1-ebcdic-match-merge/schema.json \
    --cases 2000 --seed 42

# T1 correct (ALIVE, exit 0)
bundled_run 29c15f04407b t1_correct 0 \
    --cobol samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob \
    --copybooks samples/traps/T1-ebcdic-match-merge/copybooks \
    --java samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java \
    --schema samples/traps/T1-ebcdic-match-merge/schema.json \
    --cases 2000 --seed 42

# credit-fees correct (ALIVE, exit 0)
bundled_run df4d7929ce44 cf_correct 0 \
    --cobol samples/credit-fees/CREDIT-FEES.cob \
    --copybooks samples/credit-fees/copybooks \
    --java samples/credit-fees/java/CreditFees.java \
    --schema samples/credit-fees/schema.json \
    --cases 2000 --seed 42

# credit-fees HALF_EVEN variant (ZOMBIE, exit 1)
# Use the pre-generated variant (generated at image build time)
bundled_run 08d14a07bcdb cf_half_even 1 \
    --cobol samples/credit-fees/CREDIT-FEES.cob \
    --copybooks samples/credit-fees/copybooks \
    --java "$VARIANT_JAVA" \
    --schema samples/credit-fees/schema.json \
    --cases 2000 --seed 42

echo "Bundled runs kept:${KEPT:- none}; generated:${GENERATED:- none}"

# Detection matrix: always rebuilt from the runs on disk. A trap port with no run is generated
# once (never over an existing folder); existing run folders are not touched.
set +e
"$PY" -m coroner traps --from-runs > /tmp/trap_catalog.log 2>&1
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
