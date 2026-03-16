# Project Instructions

| Field | Value |
|-------|-------|
| DocumentName | project_instructions |
| Category | design-spec |
| Revision | r17 |
| Fingerprint | 9b1084db4ea071b45e6adb64bf89d793c9427b7fa6fc588a5c11bbc1919ab97a |
| Status | active |
| Timestamp | 2026-03-15T21:36:59 |
| Authors | Chad Beach & ChatGPT-5 |

## Specification Authority

Authoritative specification:

    project_document_spec_r17.md

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

For governed Markdown, the `Timestamp` field MUST be generated in the local
system timezone of the environment performing the revision event.

Rules:

- generate the timestamp from the system's local wall-clock time at the actual revision event
- the timestamp text MUST remain in the canonical `YYYY-MM-DDTHH:MM:SS` format required by the specification
- timezone offsets or zone names MUST NOT be appended to the `Timestamp` field unless a future specification revision explicitly permits them
- if a tool inserts timestamps automatically, it MUST obtain the current local timezone safely from the host environment before formatting the timestamp text
- the recorded timestamp MUST correspond to the bytes of the working revision from which the fingerprint is computed

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

Before presenting a governed artifact, the model MUST execute the validator
defined by the specification.

The canonical validator is:

    validate_project_markdown.py

If the validator reports errors:

- the document MUST be corrected
- the validator MUST be executed again
- the process MUST repeat until no errors are reported

Artifacts MUST NOT be delivered until validation succeeds.

Before presenting an artifact:

1. verify compliance with the authoritative specification
2. verify the canonical header format
3. verify revision identifier and filename
4. verify the fingerprint rule

If violations exist, revise until compliant.

Artifacts MUST NOT be presented until compliant.

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

Prohibited:

    pip install <package> --break-system-packages
