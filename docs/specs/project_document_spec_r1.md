# Project Document Specification

| Field | Value |
|-------|-------|
| DocumentName | project_document_spec |
| Category | design-spec |
| Revision | r1 |
| Fingerprint | eb0830de481e9e5ded2cd7059784917a23b0e1deee0bcb3d884931dd96e4ad89 |
| Status | active |
| Timestamp | 2026-03-15T07:00:00-07:00 |
| Authors | Chad Beach & ChatGPT-5 |
| HeaderEnd | true |

## 0x00 Purpose

Defines the normative structure, grammar, formatting rules, and production requirements for governed Markdown documents.

## 0x01 Interpretation

This document is entirely normative.

Lists under the labels Required, Allowed, Disallowed, Prohibited, Preferred, and Avoid are normative.

Examples are informative unless explicitly stated otherwise.

## 0x02 Section Layout Independence

Except where explicitly defined by this specification (for example the header), document body section ordering, naming, and numbering are not constrained.

Project documents MAY organize sections in any order appropriate to the domain being described.

Validation tooling MUST enforce formatting and structural requirements defined by this specification but MUST NOT assume any canonical section order for the document body.

## 0x03 Canonical Grammar

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

FingerprintInput := DocumentName "|" Revision "|" Timestamp
Fingerprint := SHA256(FingerprintInput)

Timestamp := YYYY "-" MM "-" DD "T" hh ":" mm ":" ss Offset
Offset := "-07:00" | "-08:00"
```

## 0x04 Filename

Format:

```
{DocumentName}_{Revision}.md
```

Required:

- filename MUST follow the canonical grammar
- Revision MUST appear in both filename and header
- revisions start at r1 and increase monotonically

## 0x05 AI Generation Contract

Required:

1. governed Markdown documents MUST be written as raw UTF-8 text directly to `.md` files
2. generators MUST treat the Markdown source as the primary artifact
3. generators MUST treat the header as a fixed literal prefix when a canonical wire format is defined
4. generators MUST use `validate_project_markdown.py` during document generation as a feedback loop
5. a governed document MUST NOT be presented as compliant until validation succeeds

Generator feedback loop:

```
generate draft → run validator → fix violations → repeat until pass
```

If validation fails, the generator MUST revise the artifact and run validation again until the document passes or generation is abandoned.

## 0x06 Artifact Production Method

Production method is part of compliance.

Required:

- Markdown MUST be authored as Markdown text
- the exact bytes written to the `.md` file MUST be the authored Markdown text
- generators MUST write directly to the `.md` file or to a UTF-8 buffer that is persisted verbatim

Prohibited:

- generating Markdown via host-language string literals
- document conversion pipelines
- rendering, exporting, or transpiling Markdown from another format
- tools that rewrite Markdown structure

If a production method is not explicitly permitted by this specification, it is prohibited.

## 0x07 Header

Required:

- header table appears immediately after the title
- one blank line between title and header table
- header row: `| Field | Value |`
- separator row: `|-------|-------|`
- fields appear in canonical order
- each field appears exactly once
- exactly one blank line follows the table

## 0x08 Header Wire Format

The first twelve lines of a governed Markdown document constitute a fixed wire format.

Generators MUST reproduce the header prefix exactly.

Only field values may vary.

## 0x09 Canonical Header Prefix Constant

```
# Document Title

| Field | Value |
|-------|-------|
| DocumentName | value |
| Category | design-spec |
| Revision | rN |
| Fingerprint | value |
| Status | draft | active | stable | superseded |
| Timestamp | YYYY-MM-DDTHH:MM:SS-07:00 |
| Authors | text |
| HeaderEnd | true |

```

## 0x0A Placeholders

Angle-bracket placeholders are prohibited.

## 0x0B Revisions

Documents are append-only.

Existing revisions MUST NOT be modified. New revisions MUST increment the revision number.

## 0x0C Markdown Emission

Markdown MUST be written directly to `.md` files.

Prohibited:

- Pandoc
- pypandoc
- Markdown conversion pipelines

## 0x0D Formatting

Required:

- sections separated by blank lines

Prohibited:

- horizontal rules

Trailing backslash escapes (`\\`) are allowed only inside:

- fenced code blocks
- indented code blocks
- inline code spans

## 0x0E Spelling

Preferred:

- color
- behavior
- standardize
- optimize

Avoid:

- British spellings corresponding to the preferred American forms above

## 0x0F Python Policy

Required:

- PEP-8
- minimum Python 3.11
- formatter ruff
- line length 110
- dependency isolation via venv

Prohibited:

- `pip install <package> --break-system-packages`
