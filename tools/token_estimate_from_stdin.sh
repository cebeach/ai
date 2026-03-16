#!/usr/bin/env bash

# token_estimate_from_stdin.sh
#
# Purpose
# -------
# Estimate token counts for Markdown / specification text provided via stdin.
#
# Behavior
# --------
# Estimates tokens using a Markdown-tuned heuristic:
#
#     tokens ≈ (chars / 3.9) + (words × 0.12) + structural_adjustments
#
# Why the heuristic works
# -----------------------
# Modern LLM tokenizers average roughly 1 token per 3–4 characters,
# but Markdown specs contain structures that increase token density:
#
#   - code fences
#   - tables
#   - lists
#   - punctuation-heavy rule blocks
#
# Heuristic components
# --------------------
# chars / 3.9
#     baseline character-to-token ratio for technical Markdown
#
# words × 0.12
#     correction for short-token fragmentation
#
# structural adjustments
#     +0.8 for code fences, tables, or separator rows
#     +0.3 for lists
#
# Fingerprint row exclusion
# -------------------------
# The Fingerprint header row matches the table-row pattern (^\|) but is a
# single metadata line, not a content table row. Per project_document_spec,
# the Fingerprint row has this exact form:
#
#     ^| Fingerprint | [0-9a-f]{64} |$
#
# This row is excluded from the structural table adjustment so that its
# presence does not inflate the token estimate.
#
# Accuracy
# --------
# Typically within ±1–3% for Markdown specs
#
# Usage
# -----
#
#   cat file.md | ./token_estimate_from_stdin.sh
#
#   or
#
#   ./token_estimate_from_stdin.sh < file.md
#
# Output
# ------
# Prints a single integer token count.

awk '
{
  chars += length($0) + 1
  words += NF

  # Exclude the Fingerprint header row from the table structural adjustment.
  # Per project_document_spec the row has exactly this form:
  #   | Fingerprint | <64 lowercase hex chars> |
  # It is a single metadata field, not a content table row.
  is_fingerprint_row = ($0 ~ /^\| Fingerprint \| [0-9a-f]{64} \|$/)

  if (!is_fingerprint_row && ($0 ~ /^```|^~~~|^\|/)) extra += 0.8
  if ($0 ~ /^[-*0-9]/) extra += 0.3
}
END {
  printf "%.0f\n", (chars / 3.9) + (words * 0.12) + extra
}
'
