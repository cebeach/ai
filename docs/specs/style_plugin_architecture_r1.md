# style_plugin_architecture

| Field | Value |
|-------|-------|
| DocumentName | style_plugin_architecture |
| Category | design-spec |
| Revision | r1 |
| Fingerprint | 7ba57504665bab3ffb9213b3e99d5904b0424c4735c1425236fe351914a7ecc8 |
| Status | draft |
| Timestamp | 2026-03-17T11:37:11 |
| Authors | ChatGPT |

## Purpose

Defines how interchangeable style modules integrate with the project
instruction layer. Style modules modify response presentation while
leaving system behavior and specification authority unchanged.

## Interpretation

All rules are normative unless labeled Allowed.

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

project_document_spec
> project_instructions
> style_module
> task_input

Higher layers override lower layers when conflicts occur.

## Style Module Scope

Style modules MAY control

- tone
- verbosity
- explanation structure
- terminology conventions
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

ActiveStyle := style_module_identifier

Example

ActiveStyle := style_technical_r1

System prompt assembly

project_document_spec
project_instructions
ActiveStyle

## Style Invariants

StyleSelectionInvariant

When a style module is active responses MUST follow it unless doing so
would violate project_document_spec or project_instructions.

StyleBoundaryInvariant

Style rules modify presentation only and MUST NOT modify system behavior.

StyleConflictInvariant

If a style rule conflicts with a specification or instruction rule the
higher authority rule overrides the style rule.

## Style Module Contract

A style module SHOULD include

Purpose
RuleIndex
PreferenceOrder
Invariants
ForbiddenPatterns
FallbackRule

## Constraint Anchoring

Immediately before generation the system SHOULD anchor both foundational
and style invariants.

Example

ConstraintAnchor

SpecAuthorityInvariant
ValidationInvariant
CommandProtocolInvariant
StyleSelectionInvariant
StyleBoundaryInvariant

## Naming Convention

Recommended filename format

style_name_rN.md

Examples

style_technical_r1.md
style_tutorial_r1.md
style_teacher_r1.md
style_debugging_assistant_r1.md

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
