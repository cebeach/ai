# Project Instructions

| Field | Value |
|-------|-------|
| DocumentName | project_instructions |
| Category | design-spec |
| Revision | r21 |
| Fingerprint | 59684e0c37587ccd2bbd700280ca8279a42b500b839011bb42880a58838c8fe3 |
| Status | active |
| Timestamp | 2026-03-15T22:42:22 |
| Authors | Chad Beach & ChatGPT-5 |

## Specification Authority

Authoritative specification:

    project_document_spec_r21.md

The specification is normative and complete.

Rules:

- the specification defines all document structure and validation rules
- rules not present in the specification MUST NOT be invented or inferred
- if uncertainty exists, the specification takes precedence

## Specification Lock

Before generating or modifying governed Markdown:

1. consult the authoritative specification
2. treat it as the sole rule source

## Constraint Re-Anchoring

Before generating a governed artifact, the model MUST reconfirm the
authoritative specification and treat it as the sole rule source.

## Constrained Generation

Generate artifacts strictly under the authoritative specification.

Anything not explicitly permitted by the specification is prohibited.

## Timestamp Generation

For governed Markdown, the `Timestamp` field MUST represent the local
wall-clock time of the human author performing the revision event.

Rules:

- automated systems and LLMs act on behalf of the author
- such systems MUST use the author's timezone when generating the `Timestamp`
- the `Timestamp` MUST correspond to the revision event represented by the document bytes
- the `Timestamp` MUST NOT be later than the time the revision is produced

## Interaction Processing

Tokenizer:

```
token_count_from_stdin.py
```

Reads text from `stdin` and prints the token count as an integer.

Per interaction:

- prompt → tokenizer → display integer
- response → tokenizer → display integer

Rules

- prompt and response text MUST be unchanged
- tokenizer input MUST use `stdin`
- tokenizer output MUST be displayed verbatim
- no additional text MUST be added

Example

```
echo "<text>" | python token_count_from_stdin.py
```

## Output Gate

Generated artifacts MUST pass the Output Gate before presentation.

## Automated Validation

Before presenting a governed artifact, the model MUST execute the validator:

    project_document_validate.py

If the validator reports errors:

- the document MUST be corrected
- the validator MUST be executed again
- repeat until no errors are reported

Artifacts MUST NOT be delivered until validation succeeds.

## Revision Policy

Documents follow a forward-only revision model.

When modifying a document:

- increment revision
- update filename
- maintain a valid header

Existing revisions MUST NOT be modified or overwritten.

## Artifact Delivery

Generated governed documents MUST be provided as downloadable files.

Do NOT display full document contents verbatim in chat unless explicitly requested.

## Python Environment

Use `venv`. Do not modify system Python.
