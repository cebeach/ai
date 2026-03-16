# Project Document Specification

| Field | Value |
|-------|-------|
| DocumentName | project_document_spec |
| Category | design-spec |
| Revision | r17 |
| Fingerprint | 95fbbc9d384dfb1126b9847aa44223645f379bf89df5519385c1b3a1b042cb7a |
| Status | active |
| Timestamp | 2026-03-16T03:30:00 |
| Authors | Chad Beach & ChatGPT-5 |

## Purpose

Machine-optimized version of the project document specification.
Preserves all normative rules while minimizing tokens.

## Interpretation

All rules below are normative unless explicitly labeled Allowed.

## Filename

Format

```
{DocumentName}_{Revision}.md
```

Rules

- filename MUST follow canonical grammar
- Revision appears in filename and header
- revisions start at `r1` and increase monotonically

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
```

## Timestamp Semantics

The `Timestamp` field records the actual time at which the working document
revision was last materially updated prior to Output Gate completion.

Rules

- the `Timestamp` value MUST represent a real document authoring or revision event
- the `Timestamp` value MUST NOT be invented, guessed, rounded for convenience, or copied from an unrelated revision
- when a document revision is modified, the `Timestamp` field MUST be updated to the actual time of that modification
- the `Timestamp` field MUST reflect the time associated with the bytes of the working revision from which the fingerprint is computed
- a placeholder or mechanically convenient value such as `00:00:00` MUST NOT be used unless it is the true recorded time of the revision event

## Header

Structure

- title line
- blank line
- header table
- blank line

Table format

```
| Field | Value |
|-------|-------|
```

Rules

- header immediately follows title
- fields appear in canonical order
- each field appears exactly once
- the header ends after the `Authors` row
- one blank line follows table

## Canonical Header Fields

Canonical order

- `DocumentName`
- `Category`
- `Revision`
- `Fingerprint`
- `Status`
- `Timestamp`
- `Authors`

## Canonical Header Prefix

```
# Document Title

| Field | Value |
|-------|-------|
| DocumentName | value |
| Category | design-spec |
| Revision | rN |
| Fingerprint | 7bce4307940df41fbe4cf1ad9ff1441c202d039d1772db0532d8fb6b6f3f95b1 |
| Status | draft | active | stable | superseded |
| Timestamp | 2026-03-16T02:39:55 |
| Authors | text |

```

## Fingerprint Model

The fingerprint identifies a document revision by content.

Construction:

1. Start with the exact UTF-8 encoded bytes of the Markdown document.
2. Locate the header row whose field name is `Fingerprint`.
3. Remove the entire row, including its trailing newline character.
4. Preserve all remaining bytes exactly without normalization or reformatting.
5. Compute the SHA-256 hash of the resulting byte sequence.
6. Write the computed fingerprint value into the `Fingerprint` field of the working file for that revision.

```
Fingerprint := SHA256(FingerprintInput)
```

Determinism requirements:

- The document MUST be interpreted as UTF-8 without BOM.
- Line endings MUST be preserved exactly as they appear in the document.
- Only the `Fingerprint` header row is removed; all other content remains unchanged.
- Whitespace outside the removed row MUST NOT be altered.
- updating the `Fingerprint` field of a working document revision is permitted prior to Output Gate completion.

## Markdown Production

Required

- author Markdown directly as UTF-8 text
- source Markdown is the primary artifact

Prohibited

- Pandoc
- pypandoc
- document conversion pipelines
- tools that rewrite Markdown structure
- generating Markdown from host-language string literals

If not explicitly permitted, production methods are prohibited.

## AI Generation Contract

Workflow

generate draft → validate → fix violations → repeat until pass

A document MUST NOT be presented as compliant until validation succeeds.

Validator

```
validate_project_markdown.py
```

## Output Gate

Before a governed document may be presented, delivered, or declared compliant with this specification, it MUST pass the Output Gate.

The Output Gate enforces structural and rule compliance defined by this specification.

### Automated Validation

Automated validation MUST be performed using the validator program:

```
validate_project_markdown.py
```

The validator implements the compliance checks defined by this specification.

The validator MUST be executed against the generated document prior to artifact delivery.

### Canonical Validator

`validate_project_markdown.py` is the canonical automated validator for documents governed by this specification.

Automated validation MUST be performed using this validator.

Alternative validation tools, scripts, or implementations MUST NOT be substituted unless explicitly authorized by a future revision of this specification.

If additional validation tools are developed, they MUST produce results that are functionally equivalent to the canonical validator and their use MUST be explicitly permitted by the specification revision in effect.

The results of the canonical validator SHALL be considered authoritative for automated compliance determination.

### Violations

Any errors reported by `validate_project_markdown.py` MUST be treated as specification violations.

If violations are reported:

1. The document MUST be corrected.
2. The validator MUST be executed again.
3. This process MUST repeat until the validator reports no errors.

A document MUST NOT be presented, delivered, or declared compliant until the validator completes without reporting errors.

A revision becomes finalized when it passes the Output Gate and is presented, delivered, or otherwise declared compliant. After finalization, the revision MUST be treated as immutable.

### Additional Compliance Checks

In addition to automated validation, the Output Gate requires verification that:

- the canonical header format is correct
- the revision identifier and filename are correct
- the fingerprint rule is satisfied
- the timestamp corresponds to a real revision event

If any of these checks fail, the document MUST be corrected before delivery.

## Placeholders

Allowed

```
{identifier}
```

Prohibited

- angle-bracket placeholders

## Revision Model

Documents are managed as versioned artifacts.

Each revision represents a complete published snapshot of the document at the
time the revision was finalized.

Rules

- each revision corresponds to a distinct document file
- the revision identifier appears in both the header and filename
- revision numbers increase monotonically
- earlier published revisions remain unchanged
- substantive changes produce a new revision

During drafting, a working file for a new revision MAY be modified in place.

Allowed modifications during drafting include:

- authoring document content
- inserting or updating the `Fingerprint` field
- corrections required to pass automated validation

A revision becomes finalized when it passes the Output Gate and is presented,
delivered, or otherwise declared compliant.

After a revision is finalized:

- that revision MUST be treated as immutable
- the file representing that revision MUST NOT be modified in place
- any later change MUST be made as a new revision with a new revision identifier

Version control history (for example a Git repository) establishes the
publication history of document revisions.

## Formatting

Required

- sections separated by blank lines

Prohibited

- horizontal rules

Trailing backslash escapes (`\`) allowed only in:

- fenced code blocks
- indented code blocks
- inline code

## Spelling

Use American English.

Preferred

```
color
behavior
standardize
optimize
```

Avoid

```
colour
behaviour
standardise
optimise
```
