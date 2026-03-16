# Project Document Specification

| Field | Value |
|-------|-------|
| DocumentName | project_document_spec |
| Category | design-spec |
| Revision | r21 |
| Fingerprint | 211c736ca1a781613e2dddbcbb070acd84e77122993209159026eb7f545cf06d |
| Status | active |
| Timestamp | 2026-03-15T22:42:22 |
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

RevisionEventTime := time at which the working revision bytes are finalized
ValidationTime := time at which the canonical validator evaluates the document
```

## Timestamp Semantics

The `Timestamp` field records the local wall-clock time of the human author
performing the revision event.

Rules

- the `Timestamp` value MUST represent a real document authoring or revision event
- the `Timestamp` value MUST reflect the author's local wall-clock time
- the `Timestamp` value MUST NOT be invented or copied from an unrelated revision
- the `Timestamp` value MUST NOT be later than the time the revision is produced
- `Timestamp ≤ RevisionEventTime`
- `Timestamp SHOULD be approximately equal to RevisionEventTime`
- the `Timestamp` field MUST correspond to the document bytes used for fingerprint computation

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

### Revision Binding

The fingerprint binds the timestamp and document content to the revision state.

Rules

- the `Timestamp` field is included in the fingerprint input
- any change to the `Timestamp` field MUST change the computed fingerprint
- any change to document content outside the `Fingerprint` row MUST change the computed fingerprint
- therefore the fingerprint identifies the complete working revision state

### Revision Snapshot Model

A finalized revision is an immutable snapshot of document state.

The fingerprint is the content-derived identifier of that snapshot.

Determinism requirements:

- the document MUST be interpreted as UTF-8 without BOM
- line endings MUST be preserved exactly as they appear in the document
- only the `Fingerprint` header row is removed
- all other content remains unchanged
- whitespace outside the removed row MUST NOT be altered

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

## AI Generation Contract

Workflow

generate draft → validate → fix violations → repeat until pass

A document MUST NOT be presented as compliant until validation succeeds.

Validator

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

Formal expression

```
CorrectRevision := valid_structure ∧ consistent_metadata ∧ plausible_timestamp ∧ fingerprint_matches_bytes
```

## Placeholders

Allowed

```
{identifier}
```

Prohibited

- angle-bracket placeholders

## Revision Model

Documents are managed as versioned artifacts.

Rules

- each revision corresponds to a distinct document file
- the revision identifier appears in both the header and filename
- revision numbers increase monotonically
- earlier published revisions remain unchanged

## Formatting

Required

- sections separated by blank lines

Prohibited

- horizontal rules

## Spelling

Use American English.
