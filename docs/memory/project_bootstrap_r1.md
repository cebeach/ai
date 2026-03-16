# Project Bootstrap

Document: project_bootstrap
Category: memory
Revision: r1
Fingerprint: 9e2ac71
Status: active
Timestamp: 2026-03-14T19:04:14-07:00
Author: ChatGPT + Chad


## 1. Purpose

This document provides the minimal context required to resume work
on the project in a fresh AI conversation.

It should be attached to new chat sessions to reconstruct
the project state.


## 2. Project Overview

This project focuses on:

1. Designing a token-efficient local AI agent runtime.
2. Improving tool schema efficiency in OpenCode.
3. Developing `destilar`, a repository distillation tool
   for AI-assisted code analysis.
4. Creating reproducible Markdown design artifacts that
   serve as long-term project memory.


## 3. Authoritative Documents

The following documents define the current design state.

### Specifications

docs/specs/destilar_design_spec_rN.md
docs/specs/project_markdown_document_spec_r1.md

### Architecture

docs/runtime/token_efficient_local_agent_runtime_rN.md

### Investigations

docs/investigations/opencode_startup_directory_investigation_rN.md


## 4. Design Principles

The project prioritizes:

- token efficiency
- deterministic system behavior
- reproducible design artifacts
- AI-assisted engineering workflows


## 5. Document Conventions

Project documents follow the specification defined in:

docs/specs/project_markdown_document_spec_r1.md


## 6. How to Resume Work

When starting a new chat session:

1. Attach this document.
2. Attach the relevant design documents.
3. Provide a short prompt describing the new task.
4. Use the template defined in:

docs/memory/start_chat_r1.md


## 7. Current Work Focus

The current focus of development is:

`destilar` — a repository distillation tool that produces
question-shaped source corpora for LLM analysis.

The tool extracts a curated subset of repository files
plus structural metadata to support efficient architectural
analysis by LLM systems.


## 8. Context for Future Readers

This project explores methods for improving AI-assisted
software engineering workflows.

Key ideas include:

- token-efficient runtime architectures
- curated source corpora for LLM reasoning
- reproducible design documentation
- structured Markdown artifacts used as persistent project memory
