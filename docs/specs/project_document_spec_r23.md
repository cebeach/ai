# Project Document Specification

| Field | Value |
|-------|-------|
| DocumentName | project_document_spec |
| Category | design-spec |
| Revision | r23 |
| Fingerprint | 9382d64a72a3986dcab98ee535b564f8b5925229a8db61ba8203c5f683bf1764 |
| Status | active |
| Timestamp | 2026-03-16T02:26:44 |
| Authors | Chad Beach & ChatGPT-5 |

## Purpose

Machine-optimized version of the project document specification.
Preserves all normative rules while minimizing tokens.

## Interpretation

All rules below are normative unless explicitly labeled Allowed.

## Filename

```
{DocumentName}_{Revision}.md
```

The filename MUST follow canonical grammar.
Revision appears in filename and header.
Revisions start at `r1` and increase monotonically.

## Canonical Grammar

```
letter := lowercase ASCII letter
digit := ASCII digit
digit_nonzero := "1"–"9"

word := letter { letter | digit }
DocumentName := word { "_" word }

PositiveInteger := digit_nonzero { digit }
Revision := "r" PositiveInteger

Filename := DocumentName "_" Revision ".md"

Identifier := letter { letter | digit | "_" }
Placeholder := "{" Identifier "}"

FingerprintInput := UTF8(document bytes with the Fingerprint header row removed, including its trailing newline)
Fingerprint := SHA256(FingerprintInput)

Timestamp := YYYY "-" MM "-" DD "T" hh ":" mm ":" ss

RevisionEventTime := time at which the working revision bytes are finalized
ValidationTime := time at which the canonical validator evaluates the document
```

## Timestamp Semantics

The `Timestamp` field records the local wall-clock time of the human author
performing the revision event.

The `Timestamp` value MUST represent a real document authoring or revision event.
The `Timestamp` value MUST reflect the author's local wall-clock time.
The `Timestamp` value MUST NOT be invented or copied from an unrelated revision.
The `Timestamp` value MUST NOT be later than the time the revision is produced.
`Timestamp ≤ RevisionEventTime`
`Timestamp SHOULD be approximately equal to RevisionEventTime`
The `Timestamp` field MUST correspond to the document bytes used for fingerprint computation.

## Header

The header consists of a title line, blank line, header table, and blank line.

```
| Field | Value |
|-------|-------|
```

The header immediately follows the title.
Fields appear in canonical order.
Each field appears exactly once.
The header ends after the `Authors` row.
One blank line follows the table.

## Canonical Header Fields

Canonical order: `DocumentName`, `Category`, `Revision`, `Fingerprint`, `Status`, `Timestamp`, `Authors`.

## Fingerprint Model

The fingerprint identifies a document revision by content.

1. Start with the exact UTF-8 encoded bytes of the Markdown document.
2. Locate the header row whose field name is `Fingerprint`.
3. Remove the entire row, including its trailing newline character.
4. Preserve all remaining bytes exactly without normalization or reformatting.
5. Compute the SHA-256 hash of the resulting byte sequence.
6. Write the computed fingerprint value into the `Fingerprint` field of the working file for that revision.

```
Fingerprint := SHA256(FingerprintInput)
```

### Revision Binding

The fingerprint binds the timestamp and document content to the revision state.

The `Timestamp` field is included in the fingerprint input.
Any change to the `Timestamp` field MUST change the computed fingerprint.
Any change to document content outside the `Fingerprint` row MUST change the computed fingerprint.
Therefore the fingerprint identifies the complete working revision state.

### Revision Snapshot Model

A finalized revision is an immutable snapshot of document state.

The fingerprint is the content-derived identifier of that snapshot.

The document MUST be interpreted as UTF-8 without BOM.
Line endings MUST be preserved exactly as they appear in the document.
Only the `Fingerprint` header row is removed.
All other content remains unchanged.
Whitespace outside the removed row MUST NOT be altered.

## Markdown Production

Author Markdown directly as UTF-8 text. Source Markdown is the primary artifact.

Pandoc, pypandoc, document conversion pipelines, tools that rewrite Markdown
structure, and generating Markdown from host-language string literals are prohibited.

## AI Generation Contract

generate draft → validate → fix violations → repeat until pass

A document MUST NOT be presented as compliant until validation succeeds.

```
project_document_validate.py
```

## Output Gate

Before a governed document may be presented or delivered it MUST pass the Output Gate.

Automated validation MUST be performed using:

```
project_document_validate.py
```

Any errors reported by the canonical validator MUST be treated as specification violations.

## Correctness Invariant

A finalized revision is correct if and only if:

1. the document structure satisfies this specification
2. the filename and header metadata are consistent
3. the `Timestamp` represents a plausible revision event
4. the `Fingerprint` equals the SHA-256 digest of the document bytes with the `Fingerprint` header row removed

```
CorrectRevision := valid_structure ∧ consistent_metadata ∧ plausible_timestamp ∧ fingerprint_matches_bytes
```

## Placeholders

```
{identifier}
```

Angle-bracket placeholders are prohibited.

## Revision Model

Documents are managed as versioned artifacts.

Each revision corresponds to a distinct document file.
The revision identifier appears in both the header and filename.
Revision numbers increase monotonically.
Earlier published revisions remain unchanged.

## Formatting

Sections MUST be separated by blank lines. Horizontal rules are prohibited.
Trailing backslash escapes (`\`) are allowed only in fenced code blocks,
indented code blocks, and inline code.

## Spelling

Use American English.
