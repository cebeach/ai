#!/usr/bin/env python3
"""
Validate Markdown documents against the Project Markdown Document Specification.

Supported Python version: 3.11+

Validated rules

• filename matches {DocumentName}_{Revision}.md
• required header fields exist and appear in canonical order
• HeaderEnd is exactly "true"
• Revision syntax is r{PositiveInteger}
• Fingerprint == SHA256(DocumentName "|" Revision "|" Timestamp)
• Timestamp is ISO-8601 Pacific time (-07:00 or -08:00)
• DocumentName satisfies project grammar and POSIX filename safety
• Category and Status values are valid
"""

import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REQUIRED_HEADER_ORDER = (
    "DocumentName",
    "Category",
    "Revision",
    "Fingerprint",
    "Status",
    "Timestamp",
    "Authors",
    "HeaderEnd",
)

ALLOWED_CATEGORIES = {"design-spec", "architecture", "investigation", "memory"}

ALLOWED_STATUSES = {"draft", "active", "stable", "superseded"}

DOCUMENT_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*$")

REVISION_RE = re.compile(r"^r[1-9]\d*$")

FILENAME_RE = re.compile(
    r"^(?P<document_name>[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*)_(?P<revision>r[1-9]\d*)\.md$"
)

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:-07:00|-08:00)$")


@dataclass
class ValidationError:
    path: Path
    message: str


@dataclass
class Header:
    fields: dict
    order: list


def compute_fingerprint(document_name: str, revision: str, timestamp: str) -> str:
    value = f"{document_name}|{revision}|{timestamp}"
    return hashlib.sha256(value.encode()).hexdigest()


def parse_header(text: str, path: Path) -> tuple[Header | None, list[ValidationError]]:
    errors: list[ValidationError] = []
    fields: dict[str, str] = {}
    order: list[str] = []

    for line in text.splitlines()[1:]:
        line = line.strip()

        if not line:
            continue

        if ":" not in line:
            continue

        key, value = [x.strip() for x in line.split(":", 1)]

        if key in REQUIRED_HEADER_ORDER:
            fields[key] = value
            order.append(key)

        if key == "HeaderEnd":
            break

    for field in REQUIRED_HEADER_ORDER:
        if field not in fields:
            errors.append(ValidationError(path, f'missing header field "{field}"'))

    if fields.get("HeaderEnd") != "true":
        errors.append(ValidationError(path, 'HeaderEnd must equal "true"'))

    if errors:
        return None, errors

    return Header(fields, order), []


def validate_header_order(path: Path, header: Header) -> list[ValidationError]:
    if tuple(header.order) == REQUIRED_HEADER_ORDER:
        return []

    return [
        ValidationError(
            path,
            f"header fields must appear in canonical order {REQUIRED_HEADER_ORDER}",
        )
    ]


def validate_filename(path: Path, header: Header) -> list[ValidationError]:
    errors: list[ValidationError] = []

    match = FILENAME_RE.match(path.name)

    if not match:
        return [
            ValidationError(path, 'filename must match "{DocumentName}_{Revision}.md"'),
        ]

    name = match.group("document_name")
    rev = match.group("revision")

    if name != header.fields["DocumentName"]:
        errors.append(ValidationError(path, "DocumentName mismatch between filename and header"))

    if rev != header.fields["Revision"]:
        errors.append(ValidationError(path, "Revision mismatch between filename and header"))

    return errors


def validate_document_name(path: Path, header: Header) -> list[ValidationError]:
    name = header.fields["DocumentName"]

    if DOCUMENT_NAME_RE.fullmatch(name):
        return []

    return [ValidationError(path, f'invalid DocumentName "{name}"')]


def validate_revision(path: Path, header: Header) -> list[ValidationError]:
    revision = header.fields["Revision"]

    if REVISION_RE.fullmatch(revision):
        return []

    return [ValidationError(path, f'invalid Revision "{revision}"')]


def validate_category_status(path: Path, header: Header) -> list[ValidationError]:
    errors: list[ValidationError] = []

    category = header.fields["Category"]
    status = header.fields["Status"]

    if category not in ALLOWED_CATEGORIES:
        errors.append(ValidationError(path, f'invalid Category "{category}"'))

    if status not in ALLOWED_STATUSES:
        errors.append(ValidationError(path, f'invalid Status "{status}"'))

    return errors


def validate_timestamp(path: Path, header: Header) -> list[ValidationError]:
    ts = header.fields["Timestamp"]

    if not TIMESTAMP_RE.fullmatch(ts):
        return [ValidationError(path, f'invalid Timestamp "{ts}"')]

    try:
        datetime.fromisoformat(ts)
    except ValueError as exc:
        return [ValidationError(path, str(exc))]

    return []


def validate_fingerprint(path: Path, header: Header) -> list[ValidationError]:
    name = header.fields["DocumentName"]
    rev = header.fields["Revision"]
    ts = header.fields["Timestamp"]

    expected = compute_fingerprint(name, rev, ts)
    actual = header.fields["Fingerprint"]

    if expected == actual:
        return []

    return [ValidationError(path, "Fingerprint mismatch")]


def validate_file(path: Path) -> list[ValidationError]:
    text = path.read_text(encoding="utf-8")

    header, errors = parse_header(text, path)

    if errors:
        return errors

    checks = (
        validate_header_order,
        validate_filename,
        validate_document_name,
        validate_revision,
        validate_category_status,
        validate_timestamp,
        validate_fingerprint,
    )

    results: list[ValidationError] = []

    for check in checks:
        results.extend(check(path, header))

    return results


def gather_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []

    for raw in paths:
        p = Path(raw)

        if p.is_file() and p.suffix == ".md":
            files.append(p)

        elif p.is_dir():
            files.extend(sorted(p.rglob("*.md")))

    return files


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: validate_docs.py <file-or-directory> ...")
        return 2

    files = gather_files(argv[1:])

    if not files:
        print("no markdown files found")
        return 1

    total_errors = 0

    for path in files:
        errors = validate_file(path)

        if errors:
            print(f"FAIL  {path}")
            for err in errors:
                print(f"  - {err.message}")
            total_errors += len(errors)

        else:
            print(f"OK    {path}")

    if total_errors:
        print(f"\n{total_errors} validation error(s)")
        return 1

    print("\nAll documents valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
