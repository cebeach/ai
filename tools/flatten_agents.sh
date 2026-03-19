#!/usr/bin/env bash

# flatten_agents.sh
# This is a helper script to faciliate upload a flattened version of our agents definitions to either claude.ai or ChatGPT.
# - Create a new directory (agents_flat)
# - Copy AGENTS.md into it
# - Flatten all files under .agents/ into the new directory
# - Remove any reference to ".agents/style" and ".agents/spec"

set -euo pipefail

# Configuration
TARGET_DIR="/tmp/agents_flat"
SRC_DIR=".agents"

# 1. Create target directory
mkdir -p "$TARGET_DIR"

# 2. Copy AGENTS.md
cp AGENTS.md "$TARGET_DIR/"

# 3. Flatten all files from .agents/ into the target directory
#    (ignore the original subdirectory structure)
find "$SRC_DIR" -type f -exec cp {} "$TARGET_DIR/" \;

# 4. Strip any occurrence of ".agents/style" and ".agents/spec" from the copied files
#    e.g., ".agents/style/style_architecture.md" → "style_architecture.md"
find "$TARGET_DIR" -type f -exec \
  sed -i -e 's/\.agents\/style\///g' \
        -e 's/\.agents\/spec\///g' \
        {} \;

echo "Done. All files are in '$TARGET_DIR'."
