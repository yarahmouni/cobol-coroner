#!/usr/bin/env bash
# Keep only the trap catalog files in <base dir>/runs and delete every run folder.
#
# Used by the final stage of the Dockerfile (after `python3 -m coroner traps`) and by the test that
# simulates that step. The catalog files are derived from the real runs made by `coroner traps`;
# the run folders are removed to keep the image small (about 113 MB each).
#
# Usage: keep_catalog_only.sh [BASE_DIR]   (default: $CORONER_BASE_DIR, or the current directory)
# Exit 2 when the runs folder or one of the two catalog files is missing; nothing is deleted then.

set -euo pipefail

BASE_DIR="${1:-${CORONER_BASE_DIR:-.}}"
RUNS_DIR="$BASE_DIR/runs"

if [ ! -d "$RUNS_DIR" ]; then
    echo "ERROR: $RUNS_DIR does not exist" >&2
    exit 2
fi
for catalog_file in trap_catalog.json trap_catalog.txt; do
    if [ ! -f "$RUNS_DIR/$catalog_file" ]; then
        echo "ERROR: $RUNS_DIR/$catalog_file is missing; nothing deleted" >&2
        exit 2
    fi
done

find "$RUNS_DIR" -mindepth 1 -maxdepth 1 \
    ! -name trap_catalog.json ! -name trap_catalog.txt \
    -exec rm -rf {} +

echo "Kept trap_catalog.json and trap_catalog.txt in $RUNS_DIR"
