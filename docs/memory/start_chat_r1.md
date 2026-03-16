# AI Conversation Start Template

Document: start_chat
Category: memory
Revision: r1
Fingerprint: 4e6c8d1
Status: active
Timestamp: 2026-03-14T19:03:15-07:00
Author: ChatGPT + Chad


## 1. Purpose

This document provides a standardized template for starting a new AI conversation
when working on this project.

Because conversations are periodically restarted to obtain a fresh context window,
the new session must be provided with sufficient structured information to reconstruct
the project state.

This template ensures that new sessions begin with the correct context and instructions.


## 2. Standard Procedure

When starting a new conversation:

1. Attach the bootstrap document:

   docs/memory/project_bootstrap_rN.md

2. Attach the relevant design specifications.

3. Attach any investigation documents relevant to the current task.

4. Copy the prompt template below into the new conversation.


## 3. Conversation Start Prompt Template

Use the following prompt when opening a new chat session.

Please read the attached documents carefully before responding.

These documents represent the current project state and serve as persistent
project memory.

Important instructions:

1. Treat the attached Markdown documents as authoritative sources of truth.
2. Do not invent missing context.
3. Maintain consistency with the document specifications.
4. If a design decision appears unclear, ask for clarification rather than guessing.

After reading the documents, confirm that you understand the current
project state and summarize the relevant context before proceeding.

The task for this conversation is:

<INSERT TASK DESCRIPTION HERE>


Example:

The task for this conversation is:

Continue work on the destilar design specification and produce revision r10.


## 4. Recommended Documents to Attach

Typically include:

Bootstrap

docs/memory/project_bootstrap_rN.md

Relevant specifications

docs/specs/destilar_design_spec_rN.md
docs/specs/project_markdown_document_spec_rN.md

Architecture documents

docs/runtime/token_efficient_local_agent_runtime_rN.md

Investigations

docs/investigations/<relevant_document>.md


## 5. Expected Assistant Behavior

The assistant should:

1. Read all attached documents.
2. Treat them as authoritative context.
3. Maintain consistency with existing design decisions.
4. Produce new revisions of documents when requested.
5. Follow the Markdown document specification defined in:

docs/specs/project_markdown_document_spec_rN.md


## 6. Design Philosophy

This workflow treats Markdown documents as durable engineering artifacts
rather than temporary conversation output.

These artifacts serve as the persistent memory of the project and allow
complex design work to continue across multiple AI conversations without
losing architectural context.


## 7. Future Improvements

Potential improvements to the workflow include:

- automated document indexing
- design artifact validation scripts
- metadata extraction for project documentation
- tooling for navigating the design archive
