# OpenCode Tool Definition Override Proposal

| Field | Value |
|-------|-------|
| DocumentName | opencode_tool_definition_override_proposal |
| Category | design-spec |
| Revision | r1 |
| Fingerprint | ea26e4bdf4356163cbd134a585b33cb52d509bab9bf54d05a336b7cabee46b69 |
| Status | draft |
| Timestamp | 2026-03-20T03:22:49 UTC |
| Authors | Chad Beach, ChatGPT-5 |

## Purpose

Propose an upstream-friendly mechanism for controlling the model-facing text of
OpenCode tool definitions without patching core tool implementations.

## Problem

OpenCode tool definitions appear to contain substantial redundant prompt text.
Experimental compression work demonstrated large token savings, but the current
research approach modifies internal source files directly.

That patch shape is effective for local experimentation but may be too invasive
for upstream acceptance because it changes core prompt assembly behavior and
built-in tool metadata.

## Design Goal

Provide a supported configuration layer for model-facing tool schema control.

The mechanism should allow users to:

- narrow the tool surface presented to a given agent
- override tool descriptions
- override parameter descriptions
- preserve tool execution semantics
- avoid editing built-in tool source files

## Non-Goals

This proposal does not attempt to:

- change tool execution behavior
- introduce arbitrary prompt rewriting hooks
- redesign the full agent configuration system
- solve model-specific prompting beyond tool definition presentation

## Design Summary

The preferred design is a configuration-driven override layer in `opencode.json`.

The key idea is to separate:

- tool implementation
- tool execution permissions
- model-facing schema text

Tool behavior remains defined by built-in code. The override layer affects only
what the model sees in the tool schema.

## Preferred Design

### Per-Agent Tool Presentation Overrides

Each agent may define a tool map keyed by tool identifier.

Each tool entry may control:

- whether the tool is exposed to the agent
- the model-facing tool description
- model-facing parameter descriptions

Illustrative configuration:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "build": {
      "tools": {
        "read": {
          "enabled": true,
          "description": "Read a file or directory.",
          "parameters": {
            "filePath": "Path.",
            "offset": "Start line.",
            "limit": "Max lines."
          }
        },
        "glob": {
          "enabled": true,
          "description": "Find files by glob pattern.",
          "parameters": {
            "pattern": "Glob pattern.",
            "path": "Search dir."
          }
        },
        "bash": {
          "enabled": false
        }
      }
    }
  }
}
```

### Semantics

If a tool entry is omitted, OpenCode uses the built-in definition.

If a tool entry is present:

- `enabled = false` hides the tool from that agent
- `description` overrides the built-in tool description for model display
- `parameters` overrides only the named parameter descriptions
- unspecified parameters fall back to built-in descriptions

### Merge Rule

Resolution should be shallow and deterministic.

For a given agent and tool:

1. start with the built-in tool definition
2. apply `enabled` override if present
3. apply tool description override if present
4. apply per-parameter description overrides if present

This keeps execution semantics unchanged while making the schema text
configuration-driven.

## Alternate Design

### External Override Files

An alternate design is to support project-local override files for tool prose.

Example shape:

```text
.opencode/tools/read/description.txt
.opencode/tools/read/parameters.json
```

Benefits:

- easy editing of longer text
- project-local customization
- no rebuild required

Costs:

- introduces a second configuration surface
- parameter metadata still requires structured files
- merge and precedence rules become more complex

This design is viable, but weaker than a single `opencode.json` surface.

## Rejected Direction

### Prompt-Time Transformation Hook

A generic hook that rewrites tool schemas during prompt assembly is not the
preferred upstream design.

Reasons:

- less transparent
- harder to debug
- easier to misuse
- obscures the source of model-visible behavior

Such a hook may be useful for experimentation, but it should not be the first
upstream proposal.

## Minimal Upstreamable Scope

The smallest useful feature slice is:

1. per-agent tool enable or disable control
2. optional per-tool description override
3. optional per-parameter description override

This scope is intentionally narrow.

It captures most of the token-efficiency benefit without introducing a large
customization framework.

## Why This Proposal Is Useful Beyond Token Efficiency

Although motivated by prompt compression, this feature also supports:

- narrow-scope agents
- safer agent profiles
- model-specific tuning
- experimentation without source patches
- future localization of model-facing tool text

This broader framing improves the case for upstream acceptance.

## Implementation Sketch

A minimal implementation likely requires changes in only three conceptual areas.

### Configuration Schema

Extend the agent configuration schema to allow structured per-tool overrides.

### Tool Resolution

When resolving the model-visible tool set for an agent:

- filter disabled tools
- substitute configured description text
- substitute configured parameter descriptions

### Diagnostics

Expose an inspection path showing the final resolved tool schema for an agent.

For example, a debug command or diagnostic log should allow a user to verify:

- which tools are exposed
- which descriptions came from built-ins
- which descriptions came from overrides

Debuggability is important because model behavior depends directly on this
resolved schema.

## Compatibility

This proposal is backward compatible.

Existing configurations continue to work unchanged. Users who do not specify
overrides receive the current built-in behavior.

## Risks

Main risks:

- configuration surface grows unnecessarily
- users create inconsistent or misleading descriptions
- maintainers object to per-model prompting controls in core config

These risks are reduced by keeping the feature narrowly scoped and declarative.

## Recommendation

Prioritize an `opencode.json`-based override layer as the primary upstream
proposal.

Treat external text-file overrides as a secondary alternative only if maintainers
prefer content files over schema extension.

Do not lead with a generic prompt transformation hook.

## Decision Summary

Recommended order:

1. finish the tool-definition optimization research
2. separate empirical results from the current patch mechanism
3. propose a minimal configuration-based override feature upstream
4. continue broader agent work after the tool schema control path is clarified
