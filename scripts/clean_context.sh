#!/usr/bin/env bash
# Export git-tracked and untracked-not-ignored files to a temp directory
set -euo pipefail

TEMP_DIR=$(mktemp -d)

# Copy files using NUL-separated names (handles spaces)
FILE_COUNT=0
while IFS= read -r -d '' file; do
    mkdir -p "$TEMP_DIR/$(dirname "$file")"
    cp "$file" "$TEMP_DIR/$file"
    FILE_COUNT=$((FILE_COUNT + 1))
done < <(git ls-files -co --exclude-standard -z)

# Fail if empty
if [[ $FILE_COUNT -eq 0 ]]; then
    echo "Error: no files to copy" >&2
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "clean build context: $FILE_COUNT files" >&2

echo "$TEMP_DIR"
