# Style Plugin Architecture

## Purpose

- Defines how interchangeable style modules integrate with rules in AGENTS.md.
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

- style_architecture.md > style_module > task_input
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
- validation behavior
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
  would violate rules in AGENTS.md or .agents/spec/document_specification.md.
- StyleBoundaryInvariant: Style rules modify presentation only and MUST NOT modify system behavior.
- StyleConflictInvariant: If a style rule conflicts with a specification or instruction rule the
  higher authority rule overrides the style rule.
- StyleAnchorInvariant: Immediately before generation the system MUST anchor the active style
  invariants, including at minimum StyleSelectionInvariant, StyleBoundaryInvariant, and
  LexicalExclusionInvariant, so that style constraints are applied throughout output generation.
- LexicalExclusionInvariant: Words listed in `BannedWords` MUST NOT appear in assistant-authored prose
  except in exempt contexts (quotations, code, filenames, identifiers, command tokens, required specification terms).

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

## Constraint Anchoring

The StyleAnchorInvariant formalizes the anchoring requirement. Immediately before generation the
system SHOULD anchor both foundational and style invariants.

Example

ConstraintAnchor

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
