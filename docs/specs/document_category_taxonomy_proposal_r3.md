# Document Category Taxonomy Proposal

| Field | Value |
|-------|-------|
| DocumentName | document_category_taxonomy_proposal |
| Category | proposal |
| Revision | r3 |
| Fingerprint | 26a5ff383ef3cfdc986623d65d0aa18f2acbd0413a91bcf075361eb9e63c7c89 |
| Status | draft |
| Timestamp | 2026-03-17T20:25:19 |
| Authors | Chad Beach & ChatGPT-5 |

## Purpose
This document proposes an extension to project_document_spec and project_instructions to introduce a controlled taxonomy for the `Role` field. The goal is to explicitly encode document purpose and authority, replacing the current informal and inconsistent use of the `Category` field.

## Problem Statement
The current specification defines a `Category` header field but does not constrain its values or define its semantics. In practice, documents with very different purposes—such as status reports, proposals, plans, and normative specifications—are labeled inconsistently, often as "design-spec".

This creates three issues:
1. Document intent is unclear
2. Validation cannot enforce role-specific rules
3. Non-normative documents may be mistaken for authoritative specifications

## Goals
- Explicitly encode document purpose and authority
- Distinguish normative documents from non-normative ones
- Enable future validator enforcement based on role
- Preserve compatibility with the existing document model

## Proposed Role Set
The following controlled vocabulary is proposed:

- specification
- proposal
- plan
- status
- guide
- vision

## Role Definitions
- specification: a normative document that defines rules, structure, or constraints that other artifacts must conform to
- proposal: a candidate design or approach that has not yet been adopted
- plan: a forward-looking document describing intended execution steps
- status: a time-bound report of current state, progress, blockers, and observations
- guide: instructional or procedural content intended for human use
- vision: a high-level articulation of direction, goals, or value proposition

## Specification Changes
project_document_spec SHALL be updated to:
1. Replace the `Category` header field with `Role`
2. Constrain `Role` to the defined enumeration
3. Introduce a "Role Semantics" section defining each role
4. Optionally define lightweight structural expectations per role

## Instruction Changes
project_instructions SHALL be updated to include a RoleSelectionInvariant:

- The system MUST determine the correct Role before generating or revising a document
- The system MUST preserve an existing Role unless explicitly changed by the user
- For new documents, the system SHOULD select Role based on intent:
  - specification for normative system definitions
  - proposal for conceptual or exploratory documents
  - plan for execution-oriented documents
  - status for progress summaries

## Authority Model
Only documents with `Role | specification |` MAY define or modify normative rules that affect validation or generation behavior.

All other roles are non-normative and MUST NOT introduce binding constraints.

## Non-Goals
- No changes to revision model
- No changes to filename grammar
- No changes to timestamp or fingerprint rules
- No changes to validation loop mechanics

## Rationale
This proposal improves clarity by making document purpose explicit. It aligns terminology with the existing authority model and enables future validation enhancements without increasing structural complexity.

## Future Work
- Extend validator to enforce Role enumeration
- Add role-specific linting rules
- Gradually migrate existing documents to correct roles
