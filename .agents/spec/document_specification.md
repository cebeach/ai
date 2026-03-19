# Document Specification

## Purpose

- Machine-optimized version of the project document specification.
- Preserves all normative rules while minimizing tokens.

## Interpretation

All rules below are normative unless explicitly labeled Allowed.

## Role Semantics

- specification: normative rules
- proposal: candidate design
- plan: execution steps
- status: progress report
- guide: instructional content
- vision: high-level direction

## Canonical Grammar

```
letter := lowercase ASCII letter
digit := ASCII digit
digit_nonzero := "1"–"9"

word_initial := letter | digit
word := word_initial { letter | digit }
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

- The `Timestamp` field records the local wall-clock time of the human author performing the revision event.
- The `Timestamp` value MUST reflect the author's real local wall-clock time and MUST NOT be invented or copied from an unrelated revision.
- The `Timestamp` value MUST NOT be later than the time the revision is produced.
- `Timestamp SHOULD be approximately equal to RevisionEventTime`

## Header

- The header consists of a title line, blank line, header table, and blank line.

```
| Field | Value |
|-------|-------|
```

- The header immediately follows the title.
- Fields appear in canonical order.
- Each field appears exactly once.
- The header ends after the `Authors` row.
- One blank line follows the table.

## Canonical Header Fields

Canonical order: `DocumentName`, `Role`, `Revision`, `Fingerprint`, `Status`, `Timestamp`, `Authors`.

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

- The fingerprint binds the timestamp and document content to the revision state.
- The `Timestamp` field is included in the fingerprint input.
- Any change to the `Timestamp` field MUST change the computed fingerprint.
- Any change to document content outside the `Fingerprint` row MUST change the computed fingerprint.
- Therefore the fingerprint identifies the complete working revision state.

## RevisionDelta

Each revision MUST include a summary of changes:
- added
- modified
- removed (explicitly listed)

### Revision Snapshot Model

- A finalized revision is an immutable snapshot of document state.
- The fingerprint is the content-derived identifier of that snapshot.
- The document MUST be interpreted as UTF-8 without BOM.
- Line endings MUST be preserved exactly as they appear in the document.
- Only the `Fingerprint` header row is removed.
- All other content remains unchanged.
- Whitespace outside the removed row MUST NOT be altered.

## Markdown Production

- Author Markdown directly as UTF-8 text.
- Source Markdown is the primary artifact.
- Pandoc, pypandoc, document conversion pipelines, tools that rewrite Markdown structure, and generating Markdown from host-language string literals are prohibited.


## ContentPreservationInvariant

- When producing revision `rN+1` from revision `rN`, all content from `rN` MUST be preserved unless the user explicitly authorizes its removal or replacement.
- Compression, summarization, abbreviation, or omission of prior content counts as removal unless explicitly authorized.

## AI Generation Contract

- generate draft → validate → fix violations → repeat until pass

## ValidationInvariant

- Before presentation or delivery, the system MUST execute `document_validate.py` against the exact artifact to be delivered.
- Any errors reported by the canonical validator MUST be treated as specification violations.
- Validator success is necessary but not sufficient for correctness.
- The delivery response MUST include validation evidence identifying the validator used, the target file validated, and the validation result.
- The artifact delivered MUST be byte-identical to the artifact validated; any modification after a successful validator run requires re-validation.
- A governed artifact MUST NOT be described as compliant, validated, complete, or ready for delivery unless `DeliverableRevision` is true.

## Correctness Invariant

A finalized revision is correct if and only if:

1. the document structure satisfies this specification
2. the filename and header metadata are consistent
3. the `Timestamp` represents a plausible revision event
4. the `Fingerprint` equals the SHA-256 digest of the document bytes with the
   `Fingerprint` header row removed
5. the revision is content-complete relative to the prior revision unless the
   user explicitly authorized removal or replacement
6. the canonical validator has been executed successfully against the exact
   artifact to be delivered
7. the artifact delivered is byte-identical to the artifact validated

ValidatedArtifact := artifact for which `document_validate.py` returned success
ByteIdentity := SHA256(delivered_bytes) = SHA256(validated_bytes)
ContentComplete := all prior-revision content is preserved unless explicitly removed or replaced by user instruction

```
CorrectRevision := valid_structure ∧ consistent_metadata ∧ plausible_timestamp ∧ fingerprint_matches_bytes ∧ ContentComplete ∧ ValidatedArtifact ∧ ByteIdentity
DeliverableRevision := CorrectRevision ∧ validation_succeeded ∧ delivery_provenance_present
```

- A document MUST NOT be described as correct, compliant, validated, or ready for delivery unless `DeliverableRevision` is true.


## Placeholders

- `{identifier}`
- Angle-bracket placeholders are prohibited outside fenced code blocks, indented code blocks, and inline code.

## Revision Model

- Documents are managed as versioned artifacts.
- Each revision corresponds to a distinct document file.
- Revisions start at `r1` and increase monotonically.
- The revision identifier appears in the header.

## Formatting

- Sections MUST be separated by blank lines.
- Horizontal rules are prohibited.
- Trailing backslash escapes (`\`) are allowed only in fenced code blocks, indented code blocks, and inline code.

## Spelling

- Use American English.

## Grammar Invariant

- Documents MUST consist of grammatically correct and semantically complete sentences.
- Documents containing grammatical errors, incomplete sentences, omitted required terms, or unresolved placeholders MUST be rejected and revised until no such issues remain.
