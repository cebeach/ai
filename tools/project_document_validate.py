#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

FIELD_ORDER = [
    "DocumentName",
    "Category",
    "Revision",
    "Fingerprint",
    "Status",
    "Timestamp",
    "Authors",
]
STATUS_VALUES = {"draft", "active", "stable", "superseded"}
DOCUMENT_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*$")
REVISION_RE = re.compile(r"^r([1-9][0-9]*)$")
FILENAME_RE = re.compile(r"^([a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*)_(r[1-9][0-9]*)\.md$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
ANGLE_PLACEHOLDER_RE = re.compile(r"<[A-Za-z_][A-Za-z0-9_]*>")
AVOID_SPELLINGS = {
    "colour": "color",
    "behaviour": "behavior",
    "standardise": "standardize",
    "optimise": "optimize",
}
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
HORIZONTAL_RULE_RE = re.compile(r"^\s{0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})\s*$")
HEADER_ROW_RE = re.compile(r"^\| (?P<field>[A-Za-z][A-Za-z0-9]*) \| (?P<value>.*) \|$")
FINGERPRINT_ROW_RE = re.compile(rb"^\| Fingerprint \| .*? \|(?:\r\n|\n)", re.MULTILINE)


@dataclass
class ValidationResult:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ParsedDocument:
    path: Path
    raw_bytes: bytes
    lines: list[str]
    header_values: dict[str, str]
    header_end_line_index: int
    body_start_line_index: int


class ValidationError(Exception):
    pass


def read_utf8_without_bom(path: Path) -> tuple[bytes, str]:
    raw_bytes = path.read_bytes()
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raise ValidationError("document must be UTF-8 without BOM")
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"document is not valid UTF-8: {exc}") from exc
    return raw_bytes, text



def parse_document(path: Path) -> ParsedDocument:
    raw_bytes, text = read_utf8_without_bom(path)
    lines = text.splitlines()

    minimum_lines = 4 + len(FIELD_ORDER) + 1
    if len(lines) < minimum_lines:
        raise ValidationError("document is too short to contain the canonical header")

    if not lines[0].startswith("# "):
        raise ValidationError("line 1 must be a title line beginning with '# '")
    if lines[1] != "":
        raise ValidationError("line 2 must be blank")
    if lines[2] != "| Field | Value |":
        raise ValidationError("line 3 must be '| Field | Value |'")
    if lines[3] != "|-------|-------|":
        raise ValidationError("line 4 must be '|-------|-------|'")

    header_values: dict[str, str] = {}
    for offset, field in enumerate(FIELD_ORDER, start=4):
        line_number = offset + 1
        line = lines[offset]
        match = HEADER_ROW_RE.match(line)
        if not match:
            raise ValidationError(f"line {line_number} is not a valid header row")
        actual_field = match.group("field")
        value = match.group("value")
        if actual_field != field:
            raise ValidationError(
                f"line {line_number} must contain the '{field}' header field, found '{actual_field}'"
            )
        header_values[field] = value

    blank_line_index = 4 + len(FIELD_ORDER)
    if lines[blank_line_index] != "":
        raise ValidationError(f"line {blank_line_index + 1} must be blank")

    header_end_line_index = blank_line_index - 1
    body_start_line_index = blank_line_index + 1

    return ParsedDocument(
        path=path,
        raw_bytes=raw_bytes,
        lines=lines,
        header_values=header_values,
        header_end_line_index=header_end_line_index,
        body_start_line_index=body_start_line_index,
    )



def validate_filename(doc: ParsedDocument, result: ValidationResult) -> None:
    match = FILENAME_RE.fullmatch(doc.path.name)
    if not match:
        result.errors.append(
            "filename must match '{DocumentName}_{Revision}.md' using canonical grammar"
        )
        return

    filename_document_name, filename_revision = match.groups()
    if filename_document_name != doc.header_values["DocumentName"]:
        result.errors.append(
            "DocumentName in filename does not match the DocumentName header value"
        )
    if filename_revision != doc.header_values["Revision"]:
        result.errors.append("Revision in filename does not match the Revision header value")



def validate_header_values(doc: ParsedDocument, result: ValidationResult) -> None:
    document_name = doc.header_values["DocumentName"]
    revision = doc.header_values["Revision"]
    fingerprint = doc.header_values["Fingerprint"]
    category = doc.header_values["Category"]
    status = doc.header_values["Status"]
    timestamp = doc.header_values["Timestamp"]

    if not DOCUMENT_NAME_RE.fullmatch(document_name):
        result.errors.append("DocumentName is invalid under the canonical grammar")
    if category != "design-spec":
        result.errors.append("Category must be 'design-spec'")
    if not REVISION_RE.fullmatch(revision):
        result.errors.append("Revision must match 'r' followed by a positive integer")
    if not HEX64_RE.fullmatch(fingerprint):
        result.errors.append("Fingerprint must be a 64-character lowercase hexadecimal SHA-256 digest")
    if status not in STATUS_VALUES:
        result.errors.append("Status must be one of: draft, active, stable, superseded")
    if not TIMESTAMP_RE.fullmatch(timestamp):
        result.errors.append("Timestamp must match YYYY-MM-DDTHH:MM:SS")



def compute_expected_fingerprint(doc: ParsedDocument) -> str:
    match = FINGERPRINT_ROW_RE.search(doc.raw_bytes)
    if not match:
        raise ValidationError("could not locate the Fingerprint header row in the raw bytes")
    fingerprint_input = doc.raw_bytes[: match.start()] + doc.raw_bytes[match.end() :]
    return hashlib.sha256(fingerprint_input).hexdigest()



def validate_fingerprint(doc: ParsedDocument, result: ValidationResult) -> None:
    try:
        expected = compute_expected_fingerprint(doc)
    except ValidationError as exc:
        result.errors.append(str(exc))
        return

    actual = doc.header_values["Fingerprint"]
    if actual != expected:
        result.errors.append(
            f"Fingerprint mismatch: header has {actual}, expected {expected}"
        )



def validate_placeholders(doc: ParsedDocument, result: ValidationResult) -> None:
    in_fenced_code = False
    fence_delimiter = ""

    for line_number, line in enumerate(doc.lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            delimiter = "```" if stripped.startswith("```") else "~~~"
            if not in_fenced_code:
                in_fenced_code = True
                fence_delimiter = delimiter
            elif delimiter == fence_delimiter:
                in_fenced_code = False
                fence_delimiter = ""
            continue

        if in_fenced_code or line.startswith("    "):
            continue

        visible = strip_inline_code(line)
        match = ANGLE_PLACEHOLDER_RE.search(visible)
        if match:
            result.errors.append(
                f"line {line_number}: angle-bracket placeholder is prohibited: {match.group(0)}"
            )



def strip_inline_code(line: str) -> str:
    return INLINE_CODE_RE.sub("", line)



def validate_formatting(doc: ParsedDocument, result: ValidationResult) -> None:
    in_fenced_code = False
    fence_delimiter = ""

    for idx, line in enumerate(doc.lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            delimiter = "```" if stripped.startswith("```") else "~~~"
            if not in_fenced_code:
                in_fenced_code = True
                fence_delimiter = delimiter
            elif delimiter == fence_delimiter:
                in_fenced_code = False
                fence_delimiter = ""
            continue

        if in_fenced_code:
            continue

        if HORIZONTAL_RULE_RE.fullmatch(line):
            if idx != 4:
                result.errors.append(f"line {idx}: horizontal rules are prohibited")

        if idx >= doc.body_start_line_index + 1 and line.startswith("#"):
            previous = doc.lines[idx - 2]
            if previous != "":
                result.errors.append(f"line {idx}: section headings must be separated by a blank line")

        if line.endswith("\\") and not line.startswith("    "):
            without_inline_code = strip_inline_code(line)
            if without_inline_code.rstrip().endswith("\\"):
                result.errors.append(
                    f"line {idx}: trailing backslash escapes are allowed only in code"
                )



def validate_spelling(doc: ParsedDocument, result: ValidationResult) -> None:
    in_fenced_code = False
    fence_delimiter = ""

    for idx, line in enumerate(doc.lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            delimiter = "```" if stripped.startswith("```") else "~~~"
            if not in_fenced_code:
                in_fenced_code = True
                fence_delimiter = delimiter
            elif delimiter == fence_delimiter:
                in_fenced_code = False
                fence_delimiter = ""
            continue

        if in_fenced_code or line.startswith("    "):
            continue

        visible = strip_inline_code(line)
        for avoid, prefer in AVOID_SPELLINGS.items():
            if re.search(rf"\b{re.escape(avoid)}\b", visible, flags=re.IGNORECASE):
                result.errors.append(
                    f"line {idx}: use American English spelling '{prefer}' instead of '{avoid}'"
                )



def validate_revision_sequence(doc: ParsedDocument, result: ValidationResult) -> None:
    revision_match = REVISION_RE.fullmatch(doc.header_values["Revision"])
    if not revision_match:
        return

    current_revision = int(revision_match.group(1))
    if current_revision < 1:
        result.errors.append("Revision numbers must start at r1")
        return

    siblings = list(doc.path.parent.glob(f"{doc.header_values['DocumentName']}_r*.md"))
    revision_numbers: set[int] = set()
    for sibling in siblings:
        match = FILENAME_RE.fullmatch(sibling.name)
        if not match:
            continue
        sibling_document_name, sibling_revision = match.groups()
        if sibling_document_name != doc.header_values["DocumentName"]:
            continue
        revision_match = REVISION_RE.fullmatch(sibling_revision)
        if revision_match:
            revision_numbers.add(int(revision_match.group(1)))

    if current_revision not in revision_numbers:
        revision_numbers.add(current_revision)

    missing_lower_revisions = [n for n in range(1, current_revision) if n not in revision_numbers]
    if missing_lower_revisions:
        result.warnings.append(
            "could not verify monotonic revision history completely; missing sibling files for "
            + ", ".join(f"r{n}" for n in missing_lower_revisions)
        )



def validate_file(path: Path) -> ValidationResult:
    result = ValidationResult(path=path)
    if not path.exists():
        result.errors.append("file does not exist")
        return result
    if not path.is_file():
        result.errors.append("path is not a file")
        return result

    try:
        doc = parse_document(path)
    except ValidationError as exc:
        result.errors.append(str(exc))
        return result

    validate_filename(doc, result)
    validate_header_values(doc, result)
    validate_fingerprint(doc, result)
    validate_placeholders(doc, result)
    validate_formatting(doc, result)
    validate_spelling(doc, result)
    validate_revision_sequence(doc, result)
    return result



def iter_targets(paths: Iterable[Path], recursive: bool) -> list[Path]:
    collected: list[Path] = []
    for path in paths:
        if path.is_dir():
            pattern = "**/*.md" if recursive else "*.md"
            collected.extend(sorted(path.glob(pattern)))
        else:
            collected.append(path)
    return collected



def print_result(result: ValidationResult) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(f"[{status}] {result.path}")
    for error in result.errors:
        print(f"  ERROR: {error}")
    for warning in result.warnings:
        print(f"  WARN: {warning}")



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate governed Markdown documents against project_document_spec_r18.md"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Markdown files or directories to validate",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="recurse into directories",
    )
    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    targets = iter_targets(args.paths, recursive=args.recursive)
    if not targets:
        print("No Markdown files found.", file=sys.stderr)
        return 2

    results = [validate_file(path) for path in targets]
    for result in results:
        print_result(result)

    failed = sum(not result.ok for result in results)
    print()
    print(f"Validated {len(results)} file(s); {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
