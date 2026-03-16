#!/usr/bin/env python3
"""Compute and write the project fingerprint defined by project_document_spec.

Rules implemented:
- read the document as exact bytes
- require UTF-8 without BOM
- preserve all existing bytes and line endings exactly
- remove only the Fingerprint header row, including its trailing newline,
  when computing the digest
- allow mixed line endings
- write the computed fingerprint back to the same file in place
- print the computed fingerprint to stdout
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path


class FingerprintError(Exception):
    """Raised when input cannot be processed under the fingerprint rules."""


# Matches the Fingerprint header row and its trailing newline, preserving the
# exact bytes of the row terminator for later reuse. Supports LF or CRLF and
# permits mixed line endings elsewhere in the document.
FINGERPRINT_ROW_RE = re.compile(
    rb"^\| Fingerprint \| (?P<value>.*?) \|(?P<newline>\r\n|\n)",
    re.MULTILINE,
)


def read_utf8_without_bom(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise FingerprintError("document must be UTF-8 without BOM")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FingerprintError(f"document is not valid UTF-8: {exc}") from exc
    return raw


def find_fingerprint_row(raw: bytes) -> re.Match[bytes]:
    match = FINGERPRINT_ROW_RE.search(raw)
    if not match:
        raise FingerprintError("could not locate the Fingerprint header row")
    return match


def fingerprint_input_bytes(raw: bytes) -> bytes:
    match = find_fingerprint_row(raw)
    return raw[: match.start()] + raw[match.end() :]


def compute_fingerprint_from_bytes(raw: bytes) -> str:
    payload = fingerprint_input_bytes(raw)
    return hashlib.sha256(payload).hexdigest()


def compute_fingerprint(path: Path) -> str:
    raw = read_utf8_without_bom(path)
    return compute_fingerprint_from_bytes(raw)


def write_fingerprint_in_place(path: Path) -> str:
    raw = read_utf8_without_bom(path)
    match = find_fingerprint_row(raw)
    digest = compute_fingerprint_from_bytes(raw)

    newline = match.group("newline")
    replacement = b"| Fingerprint | " + digest.encode("ascii") + b" |" + newline
    updated = raw[: match.start()] + replacement + raw[match.end() :]
    path.write_bytes(updated)
    return digest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute the project fingerprint for a governed Markdown document, "
            "write it back to the document in place, and print it to stdout."
        )
    )
    parser.add_argument("path", type=Path, help="Path to the Markdown document")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        print(write_fingerprint_in_place(args.path))
    except FingerprintError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("ERROR: file does not exist", file=sys.stderr)
        return 1
    except IsADirectoryError:
        print("ERROR: path is a directory", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
