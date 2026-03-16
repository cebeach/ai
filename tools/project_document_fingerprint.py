#!/usr/bin/env python3
"""Work with the governed Markdown fingerprint defined by project_document_spec_r17.

This implementation is intentionally r17-only.
It recognizes only the canonical r17 header at the top of the document and
fails fast on non-conformant inputs rather than attempting compatibility with
older revisions or alternate layouts.

Modes:
- default: update Timestamp and Fingerprint in place, then print the new
  fingerprint to stdout
- --compute-only: compute the fingerprint from the file as it currently exists,
  leave the file unchanged, and print the computed fingerprint to stdout
- --check: verify that the embedded Fingerprint field matches the computed
  fingerprint for the file as it currently exists, leave the file unchanged,
  print the computed fingerprint to stdout, and exit non-zero on mismatch

Rules implemented from r17:
- read the document as exact bytes
- require UTF-8 without BOM
- require the canonical r17 header structure at the top of the document
- require the canonical r17 field order ending after Authors
- preserve all existing bytes and line endings exactly outside the updated rows
- allow mixed line endings
- when updating, replace Timestamp first and compute the digest from the bytes
  containing the updated Timestamp row with only the Fingerprint row removed,
  including its trailing newline
- when computing or checking without updating, compute the digest from the file
  exactly as it exists with only the Fingerprint header row removed
- print only the computed fingerprint to stdout on success
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class FingerprintError(Exception):
    """Raised when input cannot be processed under the r17 fingerprint rules."""


TIMESTAMP_TEXT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
FINGERPRINT_TEXT_RE = re.compile(r"^[0-9a-f]{64}$")
HEADER_ROW_RE = re.compile(
    rb"^\| (?P<field>[A-Za-z][A-Za-z0-9]*) \| (?P<value>.*) \|(?:\r\n|\n)$"
)
CANONICAL_FIELDS = [
    "DocumentName",
    "Category",
    "Revision",
    "Fingerprint",
    "Status",
    "Timestamp",
    "Authors",
]


@dataclass(frozen=True)
class HeaderRow:
    field_name: str
    value: bytes
    start: int
    end: int
    newline: bytes


@dataclass(frozen=True)
class ParsedHeader:
    rows: list[HeaderRow]
    header_end: int



def read_utf8_without_bom(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise FingerprintError("document must be UTF-8 without BOM")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FingerprintError(f"document is not valid UTF-8: {exc}") from exc
    return raw



def splitlines_keepends_with_offsets(raw: bytes) -> list[tuple[int, int, bytes]]:
    parts = raw.splitlines(keepends=True)
    lines: list[tuple[int, int, bytes]] = []
    pos = 0
    for part in parts:
        end = pos + len(part)
        lines.append((pos, end, part))
        pos = end
    if pos < len(raw):
        lines.append((pos, len(raw), raw[pos:]))
    return lines



def _require_exact_line(line: bytes, allowed: tuple[bytes, ...], message: str) -> None:
    if line not in allowed:
        raise FingerprintError(message)



def parse_r17_header(raw: bytes) -> ParsedHeader:
    lines = splitlines_keepends_with_offsets(raw)
    if len(lines) < 12:
        raise FingerprintError("document is too short to contain the canonical r17 header")

    if not lines[0][2].startswith(b"# "):
        raise FingerprintError("line 1 must be a title line beginning with '# '")
    _require_exact_line(lines[1][2], (b"\n", b"\r\n"), "line 2 must be blank")
    _require_exact_line(
        lines[2][2],
        (b"| Field | Value |\n", b"| Field | Value |\r\n"),
        "line 3 must be '| Field | Value |'",
    )
    _require_exact_line(
        lines[3][2],
        (b"|-------|-------|\n", b"|-------|-------|\r\n"),
        "line 4 must be '|-------|-------|'",
    )

    rows: list[HeaderRow] = []
    for index, field_name in enumerate(CANONICAL_FIELDS, start=4):
        start, end, line = lines[index]
        match = HEADER_ROW_RE.match(line)
        if not match:
            raise FingerprintError(f"line {index + 1} must be a canonical header row")
        actual_field = match.group("field").decode("ascii")
        if actual_field != field_name:
            raise FingerprintError(
                f"line {index + 1} must contain the {field_name} field in canonical order"
            )
        newline = b"\r\n" if line.endswith(b"\r\n") else b"\n"
        rows.append(
            HeaderRow(
                field_name=actual_field,
                value=match.group("value"),
                start=start,
                end=end,
                newline=newline,
            )
        )

    blank_index = 4 + len(CANONICAL_FIELDS)
    if blank_index >= len(lines):
        raise FingerprintError("header must be followed by one blank line")
    _require_exact_line(lines[blank_index][2], (b"\n", b"\r\n"), "header must be followed by one blank line")

    header_end = lines[blank_index][1]
    return ParsedHeader(rows=rows, header_end=header_end)



def find_header_row(raw: bytes, field_name: str) -> HeaderRow:
    parsed = parse_r17_header(raw)
    for row in parsed.rows:
        if row.field_name == field_name:
            return row
    raise FingerprintError(f"could not locate the {field_name} header row")



def find_fingerprint_row(raw: bytes) -> HeaderRow:
    return find_header_row(raw, "Fingerprint")



def find_timestamp_row(raw: bytes) -> HeaderRow:
    return find_header_row(raw, "Timestamp")



def validate_timestamp_text(timestamp: str) -> str:
    if not TIMESTAMP_TEXT_RE.fullmatch(timestamp):
        raise FingerprintError("timestamp must match YYYY-MM-DDTHH:MM:SS")
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise FingerprintError(f"timestamp is not a valid calendar time: {exc}") from exc
    return timestamp



def current_timestamp_text() -> str:
    return datetime.now().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")



def replace_header_row(raw: bytes, row: HeaderRow, field_name: str, value: bytes) -> bytes:
    replacement = b"| " + field_name.encode("ascii") + b" | " + value + b" |" + row.newline
    return raw[: row.start] + replacement + raw[row.end :]



def replace_timestamp_row(raw: bytes, timestamp_text: str) -> bytes:
    row = find_timestamp_row(raw)
    return replace_header_row(raw, row, "Timestamp", timestamp_text.encode("ascii"))



def replace_fingerprint_row(raw: bytes, digest: str) -> bytes:
    row = find_fingerprint_row(raw)
    return replace_header_row(raw, row, "Fingerprint", digest.encode("ascii"))



def fingerprint_input_bytes(raw: bytes) -> bytes:
    row = find_fingerprint_row(raw)
    return raw[: row.start] + raw[row.end :]



def compute_fingerprint_from_bytes(raw: bytes) -> str:
    return hashlib.sha256(fingerprint_input_bytes(raw)).hexdigest()



def embedded_fingerprint(raw: bytes) -> str:
    row = find_fingerprint_row(raw)
    try:
        value = row.value.decode("ascii")
    except UnicodeDecodeError as exc:
        raise FingerprintError("Fingerprint field is not ASCII") from exc
    if not FINGERPRINT_TEXT_RE.fullmatch(value):
        raise FingerprintError("Fingerprint field must be 64 lowercase hexadecimal characters")
    return value



def compute_fingerprint(path: Path) -> str:
    raw = read_utf8_without_bom(path)
    parse_r17_header(raw)
    return compute_fingerprint_from_bytes(raw)



def update_timestamp_and_fingerprint_in_place(path: Path, timestamp_override: str | None = None) -> str:
    raw = read_utf8_without_bom(path)
    parse_r17_header(raw)
    timestamp_text = validate_timestamp_text(timestamp_override) if timestamp_override is not None else current_timestamp_text()
    with_updated_timestamp = replace_timestamp_row(raw, timestamp_text)
    digest = compute_fingerprint_from_bytes(with_updated_timestamp)
    final_bytes = replace_fingerprint_row(with_updated_timestamp, digest)
    path.write_bytes(final_bytes)
    return digest



def check_fingerprint(path: Path) -> tuple[str, bool]:
    raw = read_utf8_without_bom(path)
    parse_r17_header(raw)
    actual = embedded_fingerprint(raw)
    expected = compute_fingerprint_from_bytes(raw)
    return expected, actual == expected



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Update or verify the governed Markdown Timestamp and Fingerprint "
            "for project_document_spec_r17-conformant documents. "
            "On success, prints only the computed fingerprint to stdout."
        )
    )
    parser.add_argument("path", type=Path, help="Path to the Markdown document")
    parser.add_argument(
        "--timestamp",
        dest="timestamp",
        help="Exact revision-event timestamp in YYYY-MM-DDTHH:MM:SS format",
    )
    parser.add_argument(
        "--compute-only",
        action="store_true",
        help="Compute the fingerprint from the file as it exists and leave the file unchanged",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether the embedded Fingerprint matches the computed fingerprint and leave the file unchanged",
    )
    return parser



def validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.compute_only and args.check:
        parser.error("--compute-only and --check cannot be used together")
    if args.timestamp is not None and (args.compute_only or args.check):
        parser.error("--timestamp can only be used when updating the file")



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_cli_args(parser, args)

    try:
        if args.compute_only:
            print(compute_fingerprint(args.path))
            return 0
        if args.check:
            digest, ok = check_fingerprint(args.path)
            print(digest)
            return 0 if ok else 1
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
