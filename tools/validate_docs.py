#!/usr/bin/env python3
"""Validate Markdown documents against project_markdown_document_spec r8."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

HEADER_FIELDS = [
    "DocumentName",
    "Category",
    "Revision",
    "Fingerprint",
    "Status",
    "Timestamp",
    "Authors",
    "HeaderEnd",
]

CATEGORY_VALUES = {"design-spec", "architecture", "investigation", "memory"}
STATUS_VALUES = {"draft", "active", "stable", "superseded"}

DOCUMENT_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*$")
REVISION_RE = re.compile(r"^r[1-9][0-9]*$")
FILENAME_RE = re.compile(
    r"^(?P<name>[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*)_(?P<rev>r[1-9][0-9]*)\.md$"
)
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:-07:00|-08:00)$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
HORIZONTAL_RULE_RE = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
SECTION_RE = re.compile(r"^(#{2,6})\s+((\d+)(?:\.(\d+))*)\.\s+.+$")
TRAILING_BACKSLASH_RE = re.compile(r"(?<!\\)\\\s*$")
FENCED_CODE_RE = re.compile(r"^\s*(```+|~~~+)")
INDENTED_CODE_RE = re.compile(r"^(?:\t| {4,})")
TABLE_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|$")


@dataclass
class ValidationError:
    path: Path
    line: int | None
    message: str


@dataclass
class Header:
    title: str
    fields: dict[str, str]
    end_line_index: int


def iter_markdown_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(p for p in path.rglob("*.md") if p.is_file()))
        else:
            raise FileNotFoundError(path)
    return sorted(set(files))


def parse_table_row(line: str) -> tuple[str, str] | None:
    match = TABLE_ROW_RE.fullmatch(line)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def parse_header(path: Path, lines: list[str]) -> tuple[Header | None, list[ValidationError]]:
    errors: list[ValidationError] = []

    if not lines:
        return None, [ValidationError(path, None, "file is empty")]

    if not lines[0].startswith("# "):
        return None, [ValidationError(path, 1, "line 1 must be a level-1 title heading")]

    title = lines[0][2:].strip()
    if not title:
        errors.append(ValidationError(path, 1, "document title must not be empty"))

    idx = 1
    if idx >= len(lines) or lines[idx].strip() != "":
        errors.append(ValidationError(path, 2, "exactly one blank line must follow the title"))
        return None, errors
    idx += 1

    if idx >= len(lines) or lines[idx].strip() != "| Field | Value |":
        errors.append(ValidationError(path, idx + 1, "table header row must be exactly '| Field | Value |'"))
        return None, errors
    idx += 1

    if idx >= len(lines) or lines[idx].strip() != "|------|------|":
        errors.append(ValidationError(path, idx + 1, "table separator row must be exactly '|------|------|'"))
        return None, errors
    idx += 1

    fields: dict[str, str] = {}
    for expected in HEADER_FIELDS:
        if idx >= len(lines):
            errors.append(ValidationError(path, idx + 1, "header ended before all required rows"))
            return None, errors
        parsed = parse_table_row(lines[idx])
        if parsed is None:
            errors.append(ValidationError(path, idx + 1, f"invalid header row syntax: {lines[idx]!r}"))
            return None, errors
        key, value = parsed
        if key != expected:
            errors.append(ValidationError(path, idx + 1, f"expected header row '{expected}', found '{key}'"))
        fields[key] = value
        idx += 1

    if fields.get("HeaderEnd") != "true":
        errors.append(ValidationError(path, idx, "HeaderEnd row must be exactly '| HeaderEnd | true |'"))

    if idx >= len(lines) or lines[idx].strip() != "":
        errors.append(ValidationError(path, idx + 1, "exactly one blank line must follow the HeaderEnd row"))
        return None, errors

    if idx + 1 < len(lines) and lines[idx + 1].strip():
        # fine, body begins after the single blank line
        pass

    return Header(title=title, fields=fields, end_line_index=idx + 1), errors


def validate_filename(path: Path, header: Header) -> list[ValidationError]:
    errors: list[ValidationError] = []
    match = FILENAME_RE.fullmatch(path.name)
    if not match:
        errors.append(
            ValidationError(
                path,
                None,
                "filename must match {DocumentName}_{Revision}.md using lowercase letters, digits, "
                "and underscores",
            )
        )
        return errors

    filename_name = match.group("name")
    filename_rev = match.group("rev")

    if header.fields.get("DocumentName") != filename_name:
        errors.append(
            ValidationError(
                path,
                None,
                f"filename DocumentName '{filename_name}' does not match header "
                f"'{header.fields.get('DocumentName', '')}'",
            )
        )

    if header.fields.get("Revision") != filename_rev:
        errors.append(
            ValidationError(
                path,
                None,
                f"filename Revision '{filename_rev}' does not match header "
                f"'{header.fields.get('Revision', '')}'",
            )
        )

    return errors


def validate_header_values(path: Path, header: Header) -> list[ValidationError]:
    errors: list[ValidationError] = []
    fields = header.fields

    name = fields.get("DocumentName", "")
    category = fields.get("Category", "")
    revision = fields.get("Revision", "")
    fingerprint = fields.get("Fingerprint", "")
    status = fields.get("Status", "")
    timestamp = fields.get("Timestamp", "")

    if not DOCUMENT_NAME_RE.fullmatch(name):
        errors.append(ValidationError(path, None, f"invalid DocumentName: {name!r}"))

    if category not in CATEGORY_VALUES:
        errors.append(ValidationError(path, None, f"invalid Category: {category!r}"))

    if not REVISION_RE.fullmatch(revision):
        errors.append(ValidationError(path, None, f"invalid Revision: {revision!r}"))

    if status not in STATUS_VALUES:
        errors.append(ValidationError(path, None, f"invalid Status: {status!r}"))

    if not TIMESTAMP_RE.fullmatch(timestamp):
        errors.append(ValidationError(path, None, f"invalid Timestamp: {timestamp!r}"))

    if "|" in "".join(fields.values()):
        errors.append(ValidationError(path, None, "header values must not contain the pipe character '|'"))

    if not FINGERPRINT_RE.fullmatch(fingerprint):
        errors.append(ValidationError(path, None, "Fingerprint must be 64 lowercase hex characters"))

    if (
        DOCUMENT_NAME_RE.fullmatch(name)
        and REVISION_RE.fullmatch(revision)
        and TIMESTAMP_RE.fullmatch(timestamp)
        and FINGERPRINT_RE.fullmatch(fingerprint)
    ):
        expected = hashlib.sha256(f"{name}|{revision}|{timestamp}".encode("utf-8")).hexdigest()
        if fingerprint != expected:
            errors.append(
                ValidationError(
                    path,
                    None,
                    f"fingerprint mismatch: expected {expected}, found {fingerprint}",
                )
            )

    return errors


def strip_inline_code_spans(line: str) -> str:
    result: list[str] = []
    i = 0
    in_code = False
    fence_len = 0

    while i < len(line):
        if line[i] == "`":
            j = i
            while j < len(line) and line[j] == "`":
                j += 1
            ticks = j - i
            if not in_code:
                in_code = True
                fence_len = ticks
                result.append(" " * ticks)
                i = j
                continue
            if ticks == fence_len:
                in_code = False
                fence_len = 0
                result.append(" " * ticks)
                i = j
                continue

        result.append(" " if in_code else line[i])
        i += 1

    return "".join(result)


def validate_body_rules(path: Path, lines: list[str], start_index: int) -> list[ValidationError]:
    errors: list[ValidationError] = []
    section_numbers: list[tuple[int, ...]] = []

    in_fenced_code = False
    fenced_delim = ""
    in_indented_code = False

    for index, raw_line in enumerate(lines[start_index:], start=start_index + 1):
        fence_match = FENCED_CODE_RE.match(raw_line)
        if fence_match:
            delim = fence_match.group(1)[0]
            count = len(fence_match.group(1))
            if not in_fenced_code:
                in_fenced_code = True
                fenced_delim = delim * count
            elif raw_line.lstrip().startswith(fenced_delim):
                in_fenced_code = False
                fenced_delim = ""
            continue

        if in_fenced_code:
            continue

        if raw_line.strip() == "":
            in_indented_code = False
        elif INDENTED_CODE_RE.match(raw_line):
            in_indented_code = True
        elif in_indented_code and not raw_line.startswith((" ", "\t")):
            in_indented_code = False

        if in_indented_code:
            continue

        if HORIZONTAL_RULE_RE.fullmatch(raw_line):
            errors.append(ValidationError(path, index, "horizontal rules are prohibited"))

        de_coded = strip_inline_code_spans(raw_line)
        if TRAILING_BACKSLASH_RE.search(de_coded):
            errors.append(
                ValidationError(path, index, "trailing backslash outside code regions is prohibited")
            )

        section_match = SECTION_RE.match(raw_line)
        if section_match:
            heading_level = len(section_match.group(1))
            numeric_parts = tuple(int(part) for part in section_match.group(2).split("."))
            expected_parts = heading_level - 1
            if len(numeric_parts) != expected_parts:
                errors.append(
                    ValidationError(path, index, "section numbering depth does not match heading level")
                )
            section_numbers.append(numeric_parts)

    for previous, current in zip(section_numbers, section_numbers[1:]):
        if current <= previous:
            errors.append(
                ValidationError(
                    path,
                    None,
                    f"section numbering must be strictly increasing: {previous} followed by {current}",
                )
            )
            break

    return errors


def validate_file(path: Path) -> list[ValidationError]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header, errors = parse_header(path, lines)
    if header is None:
        return errors
    errors.extend(validate_filename(path, header))
    errors.extend(validate_header_values(path, header))
    errors.extend(validate_body_rules(path, lines, header.end_line_index))
    return errors


def format_error(error: ValidationError) -> str:
    if error.line is None:
        return f"ERROR  {error.path}  {error.message}"
    return f"ERROR  {error.path}:{error.line}  {error.message}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate Markdown documents against spec r8.")
    parser.add_argument("paths", nargs="+", help="Markdown files or directories to validate")
    args = parser.parse_args(argv)

    try:
        files = iter_markdown_files(Path(item) for item in args.paths)
    except FileNotFoundError as exc:
        print(f"ERROR  missing path: {exc}", file=sys.stderr)
        return 2

    if not files:
        print("ERROR  no markdown files found", file=sys.stderr)
        return 2

    all_errors: list[ValidationError] = []
    for path in files:
        all_errors.extend(validate_file(path))

    if all_errors:
        for error in all_errors:
            print(format_error(error))
        print(f"\nValidation failed: {len(all_errors)} error(s) across {len(files)} file(s).")
        return 1

    for path in files:
        print(f"OK     {path}")
    print(f"All documents valid. ({len(files)} file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
