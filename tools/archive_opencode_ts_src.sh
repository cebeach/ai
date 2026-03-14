#!/bin/bash

# Generate an archive of the optencode .ts source files pointed at by opencode_pytest_harness/opencode_build

set -euo pipefail

# Directory containing this script
tools="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# Project root (parent of tools/)
root="$(cd "${tools}/.." && pwd -P)"

cd "$root"

timestamp=$(date +%Y%m%d_%H%M)

filename=opencode_ts_src_${timestamp}.tgz

find -L opencode_pytest_harness/opencode_build -name "*.ts" \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/dist/*" \
    -not -path "*/.turbo/*" \
    -not -path "*/build/*" \
    -not -path "*/__snapshots__/*" \
    | tar czf ${filename} -T -

if [ -f ${filename} ]; then
    echo "Wrote ${filename}"
else
    echo "tar failed"
    exit 1
fi


