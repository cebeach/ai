#!/usr/bin/env python3
"""Update a governed Markdown document's Timestamp and Fingerprint in place.

Rules implemented from project_document_spec_r21 and project_instructions_r34:
- read the document as exact bytes
- require UTF-8 without BOM
- preserve all existing bytes and line endings exactly outside the updated rows
- require exactly one Timestamp header row and exactly one Fingerprint header row
- the Timestamp defaults to the current US/Pacific wall-clock time, equivalent to:
      TZ='America/Los_Angeles' date +"%Y-%m-%dT%H:%M:%S"
  and may be overridden by the caller via --timestamp
- compute the digest from the bytes containing the updated Timestamp row, with
  only the Fingerprint header row removed, including its trailing newline
- allow mixed line endings
- write the updated Timestamp and Fingerprint back to the same file in place
- print the computed fingerprint to stdout
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_LA_TZ = ZoneInfo("America/Los_Angeles")


class FingerprintError(Exception):
    """Raised when input cannot be processed under the fingerprint rules."""


FINGERPRINT_ROW_RE = re.compile(
    rb"^\| Fingerprint \| (?P<value>.*?) \|(?P<newline>\r\n|\n)",
    re.MULTILINE,
)
TIMESTAMP_ROW_RE = re.compile(
    rb"^\| Timestamp \| (?P<value>.*?) \|(?P<newline>\r\n|\n)",
    re.MULTILINE,
)
TIMESTAMP_TEXT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def read_utf8_without_bom(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise FingerprintError("document must be UTF-8 without BOM")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FingerprintError(f"document is not valid UTF-8: {exc}") from exc
    return raw


def find_exactly_one_row(raw: bytes, pattern: re.Pattern[bytes], field_name: str) -> re.Match[bytes]:
    matches = list(pattern.finditer(raw))
    if not matches:
        raise FingerprintError(f"could not locate the {field_name} header row")
    if len(matches) > 1:
        raise FingerprintError(f"found multiple {field_name} header rows")
    return matches[0]


def find_fingerprint_row(raw: bytes) -> re.Match[bytes]:
    return find_exactly_one_row(raw, FINGERPRINT_ROW_RE, "Fingerprint")


def find_timestamp_row(raw: bytes) -> re.Match[bytes]:
    return find_exactly_one_row(raw, TIMESTAMP_ROW_RE, "Timestamp")


def current_timestamp_text() -> str:
    """Return the current US/Pacific wall-clock time as YYYY-MM-DDTHH:MM:SS.

    Equivalent to: TZ='America/Los_Angeles' date +"%Y-%m-%dT%H:%M:%S"
    """
    return datetime.now(_LA_TZ).strftime("%Y-%m-%dT%H:%M:%S")


def validate_timestamp_text(timestamp: str) -> str:
    if not TIMESTAMP_TEXT_RE.fullmatch(timestamp):
        raise FingerprintError("timestamp must match YYYY-MM-DDTHH:MM:SS")
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise FingerprintError(f"timestamp is not a valid calendar time: {exc}") from exc
    return timestamp


def replace_matched_row(raw: bytes, match: re.Match[bytes], field_name: bytes, value: bytes) -> bytes:
    newline = match.group("newline")
    replacement = b"| " + field_name + b" | " + value + b" |" + newline
    return raw[: match.start()] + replacement + raw[match.end() :]


def replace_timestamp_row(raw: bytes, timestamp_text: str) -> bytes:
    match = find_timestamp_row(raw)
    return replace_matched_row(raw, match, b"Timestamp", timestamp_text.encode("ascii"))


def fingerprint_input_bytes(raw: bytes) -> bytes:
    match = find_fingerprint_row(raw)
    return raw[: match.start()] + raw[match.end() :]


def compute_fingerprint_from_bytes(raw: bytes) -> str:
    payload = fingerprint_input_bytes(raw)
    return hashlib.sha256(payload).hexdigest()


def replace_fingerprint_row(raw: bytes, digest: str) -> bytes:
    match = find_fingerprint_row(raw)
    return replace_matched_row(raw, match, b"Fingerprint", digest.encode("ascii"))


def update_timestamp_and_fingerprint_in_place(path: Path, timestamp: str | None = None) -> str:
    raw = read_utf8_without_bom(path)
    timestamp_text = validate_timestamp_text(timestamp) if timestamp is not None else current_timestamp_text()
    with_updated_timestamp = replace_timestamp_row(raw, timestamp_text)
    digest = compute_fingerprint_from_bytes(with_updated_timestamp)
    final_bytes = replace_fingerprint_row(with_updated_timestamp, digest)
    path.write_bytes(final_bytes)
    return digest


def compute_fingerprint(path: Path) -> str:
    raw = read_utf8_without_bom(path)
    return compute_fingerprint_from_bytes(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Update the Timestamp and Fingerprint for a governed Markdown document in place, "
            "then print the computed fingerprint to stdout. "
            "By default the Timestamp is set to the current US/Pacific wall-clock time, "
            "equivalent to: TZ='America/Los_Angeles' date +\"%Y-%m-%dT%H:%M:%S\". "
            "Use --timestamp to supply an explicit value instead."
        )
    )
    parser.add_argument("path", type=Path, help="Path to the Markdown document")
    parser.add_argument(
        "--timestamp",
        dest="timestamp",
        default=None,
        help=(
            "Override the Timestamp with an explicit value in YYYY-MM-DDTHH:MM:SS format. "
            "When omitted, defaults to the current US/Pacific wall-clock time."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        print(update_timestamp_and_fingerprint_in_place(args.path, args.timestamp))
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
