# Document Specification

## Purpose

- Machine-optimized version of the project document specification.
- Preserves all normative rules while minimizing tokens.

## Interpretation

All rules below are normative unless explicitly labeled Allowed.

## Canonical Grammar

```
letter          := lowercase ASCII letter
digit           := ASCII digit
digit_nonzero   := "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"

word_initial    := letter | digit
word            := word_initial { letter | digit }
DocumentName    := word { "_" word }

PositiveInteger := digit_nonzero { digit }
Revision        := "r" PositiveInteger

Filename        := DocumentName ".md"

Identifier      := letter { letter | digit | "_" }
Placeholder     := "{" Identifier "}"

RoleValues      := specification | proposal | plan | status | guide | vision
StatusValues    := draft | active | stable | superseded
```

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

## Role Semantics

- specification: normative rules
- proposal: candidate design
- plan: execution steps
- status: progress report
- guide: instructional content
- vision: high-level direction

## Header Field Invariants

```
FingerprintInvariant := Fingerprint MUST be set to SHA256(UTF-8 bytes of the document with the Fingerprint header row removed, including its trailing newline) after producing or updating a revision
TimestampInvariant   := Timestamp MUST be set to the output of date -u +"%Y-%m-%dT%H:%M:%S UTC" when producing or updating a revision
```

## RevisionDelta

When producing a new revision, the system MUST report a summary of changes to the
user in the delivery response. The summary MUST identify:

- added content
- modified content
- removed content (explicitly listed)

The summary is a response-turn artifact. It MUST NOT be embedded as a section
in the governed document.

### Revision Snapshot Model

- A finalized revision is an immutable snapshot of document state.
- The fingerprint is the content-derived identifier of that snapshot.

## Markdown Production

- Author Markdown directly as UTF-8 text.
- Source Markdown is the primary artifact.
- Pandoc, pypandoc, document conversion pipelines, tools that rewrite Markdown structure, and generating Markdown from host-language string literals are prohibited.

## ContentPreservationInvariant

- `diff(rN, rN+1)` MUST contain no deletions unless each deleted span is explicitly authorized for removal in the current revision event.
- Compression, summarization, and abbreviation are deletions under this rule.

## AI Generation Contract

- generate draft → validate → fix violations → repeat until pass

## ValidationInvariant

- Before presentation or delivery, the system MUST execute `document_validate.py` against the exact artifact to be delivered.
- Any errors reported by the canonical validator MUST be treated as specification violations.
- Validator success is necessary but not sufficient for correctness.
- The delivery response MUST include validation evidence identifying the validator used, the target file validated, and the validation result.
- The artifact delivered MUST be byte-identical to the artifact validated; any modification after a successful validator run requires re-validation.

## Correctness Invariant

```
ValidStructure := header fields present in canonical order, each exactly once, with correct surrounding blank lines, title line, no forbidden formatting, no angle-bracket placeholders, grammar and spelling rules satisfied, Markdown authored directly as UTF-8
ConsistentMetadata := DocumentName matches filename ∧ Role ∈ RoleValues ∧ Revision matches grammar ∧ Status ∈ StatusValues ∧ FingerprintInvariant ∧ TimestampInvariant ∧ Authors present
DeliveryProvenancePresent := delivery response identifies validator, target file, and validation result
ValidatedArtifact := artifact for which `document_validate.py` returned success
ByteIdentity := SHA256(delivered_bytes) = SHA256(validated_bytes)
ContentComplete := diff(rN, rN+1) contains no unauthorized deletions
CorrectRevision := ValidStructure ∧ ConsistentMetadata ∧ ContentComplete ∧ ValidatedArtifact ∧ ByteIdentity
DeliverableRevision := CorrectRevision ∧ DeliveryProvenancePresent
```

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
