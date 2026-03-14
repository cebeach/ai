#!/bin/bash

set -euo pipefail

# Directory containing this script
tools="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# Project root (parent of tools/)
root="$(cd "${tools}/.." && pwd -P)"

cd "$root"

timestamp=$(date +%Y%m%d_%H%M)

filename=opencode_pytest_harness_${timestamp}.tgz

tar czf "${filename}" \
    --exclude='opencode_pytest_harness/venv' \
    --exclude='opencode_pytest_harness/.git' \
    opencode_pytest_harness

if [ -f ${filename} ]; then
    echo "Wrote ${filename}"
else
    echo "tar failed"
    exit 1
fi

