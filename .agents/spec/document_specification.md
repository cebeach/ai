# Document Specification

## Purpose

Machine-optimized normative rules for creating and managing versioned Markdown documents.

## Document Names and Filenames

A document name is one or more lowercase alphanumeric words joined by underscores. The filename is the document name with a `.md` extension.

## Header

The header consists of a title line, a blank line, the header table, and a blank line. Fields appear exactly once in this order: `DocumentName`, `Role`, `Revision`, `Fingerprint`, `Status`, `Timestamp`, `Authors`.

```
| Field | Value |
|-------|-------|
```

## Field Rules

| Field | Rule |
|-------|------|
| DocumentName | Must match the filename (without `.md`) |
| Role | One of: `specification`, `proposal`, `plan`, `status`, `guide`, `vision` |
| Revision | Format `rN` where N is a positive integer, starting at `r1`, incrementing monotonically |
| Fingerprint | SHA-256 of the UTF-8 document bytes with the Fingerprint row (including its trailing newline) removed |
| Status | One of: `draft`, `active`, `stable`, `superseded` |
| Timestamp | Output of `date -u +"%Y-%m-%dT%H:%M:%S UTC"` at the time of producing or updating the revision |
| Authors | One or more author names |

## Revision Model

Each revision is an immutable snapshot. Revisions increment monotonically from `r1`. When delivering a new revision, the response must include a change summary identifying added, modified, and removed content. This summary belongs in the response only — never embedded in the document.

## Content Preservation

A diff between rN and rN+1 must contain no deletions unless each deleted span is explicitly authorized for removal in the current revision event. Compression, summarization, and abbreviation count as deletions.

## Markdown Authoring

Author Markdown directly as UTF-8 text. Pandoc, pypandoc, conversion pipelines, and generating Markdown from host-language string literals are prohibited.

## Validation and Delivery

Before delivery, run `document_validate.py` against the exact artifact to be delivered. The delivery response must identify the validator used, the file validated, and the result. The delivered file must be byte-identical to the validated file. Any modification after a successful validator run requires re-validation. Validator success is necessary but not sufficient for correctness.

## AI Generation Contract

Generate draft → validate → fix violations → repeat until the validator passes.

## Formatting

Sections must be separated by blank lines. Horizontal rules are prohibited. Trailing backslash escapes are allowed only inside fenced code blocks, indented code blocks, and inline code. Angle-bracket placeholders are prohibited outside code blocks. Placeholders use the form `{identifier}`.

## Spelling and Grammar

Use American English. Documents must consist of grammatically correct and semantically complete sentences. Documents with grammatical errors, incomplete sentences, or unresolved placeholders must be rejected and revised until clean.
