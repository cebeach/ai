# Project Markdown Document Specification

DocumentName: project_markdown_document_spec

Category: design-spec

Revision: r1

Fingerprint: f5a86c440faf67cbca7f9a52526a6e1de09c29af52552278d1165d54639f3c20

Status: active

Timestamp: 2026-03-14T20:19:29-07:00

Authors: Chad Beach & ChatGPT-5

HeaderEnd: true


## 1. Purpose

This specification defines conventions for Markdown documents used as durable
project memory and engineering artifacts. These documents preserve design
specifications, architectural decisions, investigations, and debugging work so
AI-assisted engineering sessions can be resumed without losing context.

Sections 2–9 are **normative** unless stated otherwise.
Appendices are **informative**.


## 2. Normative Requirements


### 2.1 File Format

Allowed:

.md

Disallowed:

.docx
.pdf
.rtf


### 2.2 Canonical Grammar

```
letter := "a" | "b" | ... | "z"
digit := "0" | "1" | ... | "9"
digit_nonzero := "1" | "2" | ... | "9"

word := letter { letter | digit }
DocumentName := word { "_" word }

PositiveInteger := digit_nonzero { digit }
Revision := "r" PositiveInteger

Filename := DocumentName "_" Revision ".md"

Identifier := letter { letter | digit | "_" }
Placeholder := "{" Identifier "}"

FingerprintInput := DocumentName "|" Revision "|" Timestamp
Fingerprint := SHA256(FingerprintInput)

AI_Assistant_Name := Provider "-" Model
Offset := "-07:00" | "-08:00"
Timestamp := YYYY "-" MM "-" DD "T" hh ":" mm ":" ss Offset
```

Constraints:

• `DocumentName` must begin with a lowercase letter  
• digits are allowed after the first character  
• words are separated using underscores  
• `DocumentName` must always be a valid POSIX filename component  
• `/`, NUL, spaces, and punctuation other than `_` are prohibited  
• placeholder syntax uses `{}` braces only  


### 2.3 Filename Convention

Format:

```
{DocumentName}_{Revision}.md
```

Rules:

• filename must match `Filename`  
• revision must appear in both filename and header  
• revisions start at `r1` and increase monotonically  
• any modification requires a new revision  
• existing revisions must never be overwritten  


### 2.4 Document Header Standard

Header template:

```
# Document Title

DocumentName: document_identifier
Category: design-spec | architecture | investigation | memory
Revision: rN
Fingerprint: SHA256({DocumentName} "|" {Revision} "|" {Timestamp})
Status: draft | active | stable | superseded
Timestamp: YYYY-MM-DDTHH:MM:SS-07:00
Authors: Chad Beach & {AI_Assistant_Name}
HeaderEnd: true
```

Canonical header order:

```
DocumentName
Category
Revision
Fingerprint
Status
Timestamp
Authors
HeaderEnd
```

Rules:

• each field appears exactly once  
• fields must follow canonical order  
• no additional header fields may appear between them  

`HeaderEnd: true` marks the end of the header block.


### 2.5 Placeholder Syntax Standard

Format:

```
{PlaceholderName}
```

Rules:

• placeholders must use `{}` braces  
• angle-bracket placeholders are prohibited  
• placeholders represent replaceable specification tokens  


### 2.6 Section Formatting

Rules:

• monotonic section numbering across revisions  
• sections separated by blank lines  
• horizontal rules are prohibited  


### 2.7 American English Spelling Standard

Preferred:

```
color
behavior
standardize
optimize
```

Avoid:

```
colour
behaviour
standardise
optimise
```

Applies to:

• Markdown documents  
• AI-generated explanatory text  
• code comments  


### 2.8 Python Policy

All generated Python must follow **PEP-8**.

Rules:

• minimum supported version: **Python 3.11**  
• code blocks must declare supported version  
• formatting: **ruff**, line-length = 110  
• dependencies installed using **venv**  
• never recommend:

```bash
pip install <package> --break-system-packages
```


## Appendix A — Rationale (Informative)

Brace placeholders are required because angle brackets are frequently
interpreted as HTML by Markdown renderers and documentation tools. This can
cause placeholder text such as `<DocumentName>` to be rewritten or stripped.

Using `{Placeholder}` syntax avoids HTML parsing, improves deterministic
rendering, and produces more stable tokenization for AI systems.

The grammar restricts `DocumentName` so it always forms a valid POSIX filename
component. This ensures generated documents can be safely written on standard
filesystems without escaping or quoting.


## Appendix B — Examples (Informative)

Example filenames:

```
destilar_design_spec_r9.md
project_markdown_document_spec_r1.md
model2_training_notes_r4.md
token_efficient_local_agent_runtime_r3.md
```

Example placeholder usage:

```
{DocumentName}_{Revision}.md
SHA256({DocumentName} "|" {Revision} "|" {Timestamp})
```


## Revision History

```
r1 – baseline specification after revision reset
```
