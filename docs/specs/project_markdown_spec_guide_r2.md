# Project Markdown Specification Guide

| Field | Value |
|-------|-------|
| DocumentName | project_markdown_spec_guide |
| Category | design-spec |
| Revision | r2 |
| Fingerprint | ec594cde82184a33a097396fe1415a6bdc9fa9d60a2bd0ad5443404dc45815c0 |
| Status | active |
| Timestamp | 2026-03-15T08:00:00-07:00 |
| Authors | Chad Beach & ChatGPT-5 |
| HeaderEnd | true |

## 0x00 Overview

This document explains the rationale and practical usage patterns for the
Project Markdown Specification.

The specification defines the normative rules for governed Markdown
documents. This guide explains why those rules exist and how to apply them
during authoring.

## 0x01 Purpose of the Header

The header provides machine‑readable metadata used by validators and
AI agents.

Key properties ensured by the header:

- deterministic document identity
- stable revision tracking
- machine‑readable metadata
- reliable parsing for automation

Because the header structure is deterministic, tools can safely extract
document metadata without interpreting the body of the document.

## 0x02 Why Revisions Are Append‑Only

Append‑only revisions preserve the historical record of design decisions.

Benefits:

- stable references across project history
- reproducible documentation state
- clear audit trail for architectural changes

Instead of modifying a document in place, authors create a new revision
with an incremented revision identifier.

## 0x03 Why Markdown Must Be Written Directly

Markdown converters may rewrite syntax in ways that break structural
validation.

Examples of problematic behavior:

- table reformatting
- whitespace normalization
- escaping changes
- automatic line wrapping

Writing Markdown directly ensures that schema‑significant elements remain
intact and validator‑compatible.

## 0x04 Common Mistakes

Typical specification violations include:

- missing header rows
- incorrect fingerprint values
- additional blank lines around the header
- use of Markdown conversion tools
- horizontal rules in the document body

These errors are normally detected by the project validator.

## 0x05 Authoring Workflow

Typical workflow for producing a governed Markdown document:

1. create a new revision file
2. update revision identifier
3. compute the fingerprint
4. run the validator
5. fix any reported violations
6. commit the validated document

The validator is intended to be used as a feedback loop during document
generation.

## 0x06 Relationship to the Normative Specification

The normative rules are defined in the Project Markdown Specification.

Example reference:

```
project_markdown_spec_r11.md
```

This guide is explanatory. It does not override or modify the normative
rules defined in the specification.
