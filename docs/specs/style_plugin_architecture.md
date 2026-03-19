# Style Plugin Architecture

| Field | Value |
|-------|-------|
| DocumentName | style_plugin_architecture |
| Role | specification |
| Revision | r1 |
| Fingerprint | 1876bbd4bb36e60fbd4419ab39e515214422fec253770b2c99c70b2fc77ff27f |
| Status | draft |
| Timestamp | 2026-03-18T01:30:09 |
| Authors | ChatGPT |

## Purpose

- Defines how interchangeable style modules integrate with the project instruction layer.
- Style modules modify response presentation while leaving system behavior and specification authority unchanged.

## Interpretation

- All rules are normative unless labeled Allowed.

## Layer Model

Specification
↓
ProjectInstructions
↓
StylePluginArchitecture
↓
StyleModule
↓
TaskInput
↓
Generation

## Authority Order

- document_specification > project_instructions > style_module > task_input
- Higher layers override lower layers when conflicts occur.

## Style Module Scope

Style modules MAY control

- tone
- verbosity
- explanation structure
- terminology conventions
- banned words
- example usage
- rhetorical conventions

Style modules MUST NOT control

- specification authority
- validation rules
- command grammar
- revision semantics
- tool permissions
- output gate behavior

## Style Selection

`active_style := style_module_identifier`

Example: `active_style := style_technical`

System prompt assembly

1. document_specification
2. project_instructions
3. active_style

## Style Invariants

- StyleSelectionInvariant: When a style module is active responses MUST follow it unless doing so
  would violate document_specification or project_instructions.
- StyleBoundaryInvariant: Style rules modify presentation only and MUST NOT modify system behavior.
- StyleConflictInvariant: If a style rule conflicts with a specification or instruction rule the
  higher authority rule overrides the style rule.
- LexicalExclusionInvariant: Words listed in `BannedWords` MUST NOT appear in assistant-authored prose
  except in exempt contexts defined by this architecture.

## Style Module Contract

A style module SHOULD include

- Purpose
- RuleIndex
- PreferenceOrder
- Invariants
- ForbiddenPatterns
- BannedWords
- FallbackRule

## BannedWords

- A style module MAY define `BannedWords`.
- `BannedWords` is a list of prohibited words for assistant-authored prose.

### Scope

The rule applies only to assistant-authored prose.

The rule does NOT apply to

- quotations
- code
- filenames
- identifiers
- command tokens
- required specification terms

### Enforcement Procedure

Before finalizing output, the system MUST

1. detect words from `BannedWords` in drafted prose
2. rewrite offending spans while preserving semantics
3. validate absence before output

### Conflict Rule

- If avoiding a banned word would reduce correctness, distort quoted material, or violate required
  specification terminology, correctness and fidelity take precedence.
- In such cases the word MAY appear only in the minimal required context.

### Boundary Rule

- `BannedWords` is a presentation constraint only and MUST NOT modify specification authority,
  command grammar, validation behavior, or revision semantics.

## Constraint Anchoring

Immediately before generation the system SHOULD anchor both foundational and style invariants.

Example

ConstraintAnchor

- SpecAuthorityInvariant
- ValidationInvariant
- CommandProtocolInvariant
- StyleSelectionInvariant
- StyleBoundaryInvariant
- LexicalExclusionInvariant

## Naming Convention

Recommended filename format

style_name.md

Examples

- style_technical.md
- style_tutorial.md
- style_teacher.md
- style_debugging_assistant.md

## Extension

Additional behavioral presets MAY be introduced as a separate layer.

Example

Specification
→ ProjectInstructions
→ PersonalityProfile
→ StyleModule
→ TaskInput
→ Generation

This preserves separation between reasoning policy and linguistic style.
