# token-efficient_local_agent_runtime_r2.md
Revision: r2
Date: 2026-03-12

## 1. Purpose

This document summarizes the architecture for a token-efficient local agent runtime designed for OpenAI's open-weights model gpt-oss-20b running on consumer-grade GPUs.

The architecture is optimized for:

- minimal context window overhead
- compatibility with OpenCode’s existing tool-calling mechanism
- simplicity for the model interface
- extensibility through plugins
- clear separation between runtime infrastructure and domain logic

The system is designed so that internal complexity remains hidden behind a simple and reliable interface for the model.

## 2. Target Model Constraints

The runtime is designed specifically for the open-weights model **gpt-oss-20b**.

Model characteristics:

- Mixture-of-Experts architecture
- ~20.9B total parameters
- ~3.6B active parameters per token
- 24 transformer layers
- hybrid attention (global + sliding window)
- context window up to 128K tokens

Because this model runs on consumer GPUs with limited VRAM, **prompt token efficiency is a primary design constraint**.

Architectural choices must therefore:

- minimize tool schema overhead
- avoid complex or deeply abstract interfaces
- keep tool invocation predictable for the model

## 3. Core Design Principles

### 3.1 Domain-Agnostic Runtime

The runtime must not implement domain semantics.

Its responsibility is limited to infrastructure:

- message transport
- plugin discovery
- routing
- state management

All domain logic is implemented by plugins.

### 3.2 Plugin-Based Extensibility

Capabilities are implemented as **plugins representing bounded contexts**.

Example contexts:

- web
- repo
- memory
- research (future)
- vector (future)

Plugins register their capabilities with the runtime during initialization.

### 3.3 Model-Facing Simplicity

The interface presented to the model must remain concrete and predictable.

The model should interact with a small number of stable capability surfaces.

Example operations:

- web.search
- web.fetch
- repo.find
- repo.grep
- repo.read_chunk
- memory.lookup
- memory.store

The model should never need to understand plugin systems, routing logic, or internal runtime architecture.

### 3.4 Runtime Minimalism

The runtime acts as a **capability microkernel**.

It must remain small and stable.

Core runtime responsibilities:

- message transport
- plugin registry
- router
- state store

## 4. Architectural Components

### 4.1 Message Transport

Responsible for moving structured messages between OpenCode and the runtime.

Recommended transport:

- persistent Python subprocess
- stdio communication
- newline-delimited JSON or length-prefixed framing

This avoids networking overhead while maintaining a structured protocol.

### 4.2 Plugin Registry

At runtime startup, plugins are discovered and registered.

Example directory structure:

plugins/
  web/
  repo/
  memory/

Each plugin exposes:

- context name
- supported actions
- handler functions

Example plugin registration:

```python
def register(runtime):
    runtime.register_context(
        name="web",
        actions={
            "search": web_search,
            "fetch": web_fetch
        }
    )
```

### 4.3 Router

The router dispatches incoming messages to the appropriate plugin.

Responsibilities:

- parse message envelope
- resolve context and action
- invoke plugin handler
- return result

The runtime must **not interpret domain meaning**.

### 4.4 State Store

The runtime maintains shared state across requests.

State categories:

Durable state

- persisted notes
- saved artifacts

Session state

- active handles
- plugin session data

Soft state (cached)

- search results
- fetched pages
- parsed documents

Soft state entries may expire automatically using TTL policies.

## 5. Runtime Message Protocol

The runtime uses a minimal message envelope inspired by networking protocols and kernel IPC.

Message fields:

- id — request identifier
- type — context.action
- payload — arguments

Example request:

```json
{
  "id": 42,
  "type": "repo.grep",
  "payload": {
    "pattern": "TODO",
    "path": "."
  }
}
```

Example success response:

```json
{
  "id": 42,
  "result": {
    "matches": []
  }
}
```

Example error response:

```json
{
  "id": 42,
  "error": "invalid_arguments"
}
```

The protocol intentionally remains minimal to ensure long-term stability.

## 6. Plugin Interface Contract

Each plugin must implement a registration function.

Required structure:

```python
def register(runtime):
    runtime.register_context(
        name="<context_name>",
        actions={
            "<action_name>": handler_function
        }
    )
```

Handler function signature:

```python
def handler_function(payload, state):
    ...
```

Where:

- payload contains request arguments
- state provides access to runtime session data

Plugins are responsible for:

- argument validation
- domain logic
- generating structured responses

## 7. Runtime Session Model

The runtime maintains session-level state to avoid reinjecting large artifacts into the model context.

Artifacts are referenced through **opaque handles**.

Example handles:

search:12

page:9

grep:44

Handles allow the model to reference previously generated artifacts without increasing prompt size.

## 8. Artifact Handle Lifecycle

The highest-value next refinement is to specify the lifecycle and contract for artifact handles.

Opaque handles are already central to the architecture's token-efficiency strategy, but revision r3 does not yet define:

- how handles are created
- which plugin owns them
- whether they are durable or session-scoped
- how they expire
- how other plugins may reference them
- what metadata is available without re-materializing the artifact

Without this contract, the runtime can route calls, but plugins cannot safely cooperate around cached search results, fetched pages, parsed documents, grep results, or generated artifacts.

### 8.1 Why This Refinement Comes First

Handle semantics sit at the boundary between:

- protocol design
- state store design
- plugin interoperability
- token-efficiency strategy

This makes handle lifecycle more foundational than a detailed `web` plugin spec or `repo` plugin spec. Those plugin designs depend on knowing how results are named, retained, discovered, and reused.

### 8.2 Artifact Categories

Artifacts referenced by handles fall into three categories.

**Ephemeral artifacts**

Created during a session and eligible for automatic eviction.
Examples:

- search result sets
- fetched pages
- grep result sets
- parsed intermediate structures

**Session artifacts**

Persist for the lifetime of the current runtime session unless explicitly released.
Examples:

- active work buffers
- staged result collections
- plugin-owned session objects

**Durable artifacts**

Persist across runtime restarts.
Examples:

- saved notes
- exported documents
- named research summaries

### 8.3 Canonical Handle Shape

A handle must be opaque to the model but structured enough for the runtime to validate and route safely.

Recommended canonical external form:

```text
<kind>:<id>
```

Examples:

```text
search:12
page:9
grep:44
artifact:3
```

The model may pass the handle back verbatim, but must not be expected to infer internal storage layout from it.

### 8.4 Handle Record in State Store

Each handle should map to a runtime-owned record in the state store.

Recommended fields:

```json
{
  "handle": "page:9",
  "kind": "page",
  "owner_context": "web",
  "scope": "ephemeral",
  "created_at": "2026-03-12T12:00:00Z",
  "expires_at": "2026-03-12T12:30:00Z",
  "mime": "text/html",
  "summary": "Fetched page for llama.cpp KV cache discussion",
  "size": 18422,
  "data_ref": "state://soft/page/9",
  "metadata": {
    "url": "https://example.com"
  }
}
```

Required conceptual fields:

- `handle`
- `kind`
- `owner_context`
- `scope`
- `data_ref`

Optional but recommended fields:

- `created_at`
- `expires_at`
- `summary`
- `mime`
- `size`
- `metadata`

### 8.5 Ownership Rule

Every handle has exactly one owning plugin context.

Examples:

- `web.search` owns `search:*` handles
- `web.fetch` owns `page:*` handles
- `repo.grep` owns `grep:*` handles
- `memory.store` may create `note:*` or `artifact:*` handles

The owning plugin is responsible for:

- creating the handle record
- validating artifact-specific metadata
- materializing artifact contents when later referenced
- defining artifact-specific expiration defaults

The runtime remains responsible only for generic storage and routing.

### 8.6 Resolution Rule

When a request payload contains a handle, the runtime should resolve it in two stages:

1. validate that the handle exists
2. route access through the owning plugin when artifact semantics are required

This preserves the domain-agnostic runtime rule. The runtime may know that a handle exists and who owns it, but it must not interpret the artifact's domain meaning.

### 8.7 Cross-Plugin Reference Rule

Plugins may consume handles produced by other plugins only through explicit action contracts.

Example acceptable flows:

- `web.fetch` consumes a `search:*` handle plus item index
- `memory.store` consumes a `page:*` handle to persist a fetched page summary
- `research.summarize` may later consume `page:*` or `grep:*` handles

Example unacceptable flow:

- direct plugin access to another plugin's private in-memory structures

Cross-plugin interoperability must happen through routed actions and opaque handles, not shared internals.

### 8.8 Expiration and Eviction

Each handle must have one of these retention modes:

- `ttl` — expires automatically after a default or explicit TTL
- `session` — retained until session end
- `durable` — retained until explicitly deleted or replaced

Recommended defaults for version 1:

- search results: `ttl`
- fetched pages: `ttl`
- grep results: `ttl`
- work buffers: `session`
- saved notes and exported artifacts: `durable`

Eviction of ephemeral handles must remove materialized data and handle metadata together, or leave behind a clear tombstone that returns `not_found` or `expired`.

### 8.9 Handle Introspection

To keep the model interface simple, version 1 should expose at most one generic introspection action:

- `runtime.describe_handle`

This action would return lightweight metadata only, such as:

- handle kind
- owner context
- summary
- size
- creation time
- expiration time

This helps the model decide whether to reuse an artifact without reinjecting full contents.

### 8.10 Error Semantics for Handles

Recommended handle-related errors:

- `not_found` — handle does not exist
- `expired` — handle existed but is no longer valid
- `denied` — caller may not use this handle in the requested way
- `invalid_arguments` — handle type is syntactically valid but not acceptable for the action

### 8.11 Version 1 Design Rule

Version 1 should optimize for operational simplicity:

- opaque string handles
- runtime-owned handle table
- plugin-owned artifact semantics
- TTL eviction for soft state
- no distributed reference counting
- no complex capability delegation model

This keeps the system cognitively simple for both the model and the implementation.

## 9. Networking-Inspired Concepts

Several networking concepts influence the runtime design.

Message envelopes

Structured request and response packets.

Session state

Shared runtime session context.

Soft state

Cached artifacts that expire automatically.

Opaque handles

Stable references to runtime artifacts.

Request identifiers

Used to correlate requests and responses.

## 10. Microkernel Analogy

The runtime behaves similarly to a **microkernel operating system**.

Runtime responsibilities:

- routing
- plugin loading
- state management

Plugins behave like user-space services.

This architecture allows the core runtime to remain stable while capabilities evolve independently.

## 11. Tool Call Sequence Diagram

Example execution flow:

User request
  ↓
OpenCode sends tool call
  ↓
Runtime receives message
  ↓
Router resolves context + action
  ↓
Plugin handler executes
  ↓
Result returned to runtime
  ↓
Response returned to OpenCode
  ↓
Model receives result

## 12. Token-Efficiency Considerations

Token usage must remain minimal when interacting with the model.

Design strategies:

Small number of exposed tools

Avoid large MCP tool catalogs.

Opaque handles

Avoid re-injecting large artifacts.

Stable tool interface

Prevent repeated schema injection.

Structured outputs

Keep results predictable for the model.

## 13. Formal Runtime Protocol Specification

This section defines the minimal protocol between OpenCode and the runtime.

### 13.1 Transport Assumptions

Version 1 assumes:

- one persistent runtime process
- one bidirectional local transport
- request/response messaging over stdio
- UTF-8 encoded JSON

### 13.2 Request Structure

Every request must contain:

- `id`
- `type`
- `payload`

Canonical form:

```json
{
  "id": 1,
  "type": "web.search",
  "payload": {
    "query": "llama.cpp kv cache"
  }
}
```

Field semantics:

- `id`: caller-assigned request identifier
- `type`: namespaced operation in `context.action` form
- `payload`: action-specific arguments

### 13.3 Response Structure

A response must contain:

- `id`
- exactly one of `result` or `error`

Success:

```json
{
  "id": 1,
  "result": {
    "items": []
  }
}
```

Error:

```json
{
  "id": 1,
  "error": {
    "code": "invalid_arguments",
    "message": "pattern is required"
  }
}
```

### 13.4 Error Codes

Initial recommended error codes:

- `invalid_request`
- `invalid_type`
- `invalid_arguments`
- `not_found`
- `timeout`
- `denied`
- `plugin_error`
- `internal_error`

### 13.5 Framing

Two framing options are acceptable:

- newline-delimited JSON for simplicity
- length-prefixed JSON for stricter framing

Version 1 should prefer newline-delimited JSON unless multiline payload size or streaming requirements make length-prefixing necessary.

### 13.6 Protocol Stability Rule

The message envelope is part of the stable runtime ABI.

Future evolution should prefer:

- additive fields
- backward-compatible semantics
- explicit version negotiation only when necessary

## 14. Plugin Lifecycle Model

Plugins should follow a consistent lifecycle.

### 14.1 Discovery

At startup the runtime scans the plugin search path and imports candidate modules.

### 14.2 Registration

Each plugin calls `register(runtime)` to declare:

- context name
- supported actions
- handlers
- optional initialization hooks

### 14.3 Initialization

A plugin may allocate internal resources during startup, such as:

- caches
- indexes
- file handles
- external library clients

Initialization should fail fast and clearly if dependencies are unavailable.

### 14.4 Active Operation

During normal operation the plugin receives routed requests and returns structured results.

### 14.5 Shutdown

Plugins should support graceful shutdown so they can:

- flush persistent state
- release resources
- close handles
- emit final logs if needed

Recommended optional interface:

```python
def shutdown(state):
    ...
```

### 14.6 Failure Isolation

A plugin failure should not corrupt runtime state. The runtime should catch plugin exceptions and convert them into structured protocol errors.

## 15. Security Model for Plugin Isolation

The runtime is local-first, but plugins should still be treated as capability boundaries.

### 15.1 Core Principle

Each plugin should receive only the authority it needs.

### 15.2 Isolation Goals

The runtime should aim to prevent:

- unnecessary filesystem access
- unrestricted network access
- hidden cross-plugin coupling
- mutation through read-only contexts

### 15.3 Capability Separation

Examples:

- `repo` may have repository read access
- `web` may have controlled outbound retrieval access
- `memory` may have durable storage access

The runtime itself should not inherit domain-specific privileges.

### 15.4 Mutating vs Non-Mutating Operations

Read-oriented actions and mutating actions should remain clearly separated.

Example:

- `repo.grep` is read-only
- `memory.store` mutates durable state

This separation matters for validation, auditing, and possible retry behavior.

### 15.5 Defensive Defaults

Recommended defaults:

- deny by default for undeclared capabilities
- structured error on denied action
- explicit plugin registration for all actions
- no implicit access to other plugin internals

## 16. Reference Implementation Sketch

A minimal reference implementation should be achievable in roughly 150 lines of Python.

Key pieces:

- runtime object
- context registry
- message loop
- request parser
- response serializer
- plugin loader

Illustrative sketch:

```python
import json
from importlib import import_module


class Runtime:
    def __init__(self):
        self.contexts = {}
        self.state = {}

    def register_context(self, name, actions):
        self.contexts[name] = actions

    def dispatch(self, msg):
        req_id = msg["id"]
        msg_type = msg["type"]
        payload = msg.get("payload", {})

        if "." not in msg_type:
            return {"id": req_id, "error": {"code": "invalid_type", "message": msg_type}}

        context, action = msg_type.split(".", 1)
        actions = self.contexts.get(context)
        if not actions or action not in actions:
            return {"id": req_id, "error": {"code": "not_found", "message": msg_type}}

        try:
            result = actions[action](payload, self.state)
            return {"id": req_id, "result": result}
        except Exception as e:
            return {"id": req_id, "error": {"code": "plugin_error", "message": str(e)}}


def load_plugin(runtime, module_name):
    module = import_module(module_name)
    module.register(runtime)


def main():
    runtime = Runtime()
    # load_plugin(runtime, "plugins.web.plugin")
    # load_plugin(runtime, "plugins.repo.plugin")

    for line in __import__("sys").stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        response = runtime.dispatch(msg)
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
```

This is illustrative only, but it demonstrates how small the stable core can remain.

## 17. OpenCode Proof-of-Concept Interface Contract

The next implementation milestone should be a proof of concept that integrates the runtime with OpenCode while exposing the smallest possible tool surface to the model.

This section defines the recommended interface contract for that proof of concept.

### 17.1 Goal

The proof of concept should validate five things:

- OpenCode can call the runtime reliably through one stable transport
- the runtime can route requests to plugins without understanding domain semantics
- opaque handles reduce prompt growth across multi-step interactions
- results remain structured enough for gpt-oss-20b to use predictably
- the interface is small enough to avoid excessive schema overhead

The goal is not to build the final platform.

The goal is to validate the smallest viable end-to-end architecture.

### 17.2 Model-Facing Tool Surface

For the proof of concept, OpenCode should expose a very small set of tool operations.

Recommended initial surface:

- `runtime.call`
- `runtime.handle`

This is intentionally smaller than exposing every plugin action as a separate OpenCode tool.

`runtime.call` is the general request path.

`runtime.handle` is a lightweight inspection path for previously created handles.

This keeps the model-facing schema small while preserving extensibility behind the runtime boundary.

### 17.3 Why a Two-Tool Surface Is Preferred for the Proof of Concept

A separate OpenCode tool per capability action would create larger schemas and more repeated prompt overhead.

For example, directly exposing all of the following at the OpenCode layer would grow quickly:

- `web.search`
- `web.fetch`
- `repo.find`
- `repo.grep`
- `repo.read_chunk`
- `memory.lookup`
- `memory.store`

That style is conceptually simple, but it spends context on tool catalog size before the architecture is validated.

For the proof of concept, a smaller bridge is preferable:

- OpenCode sees one general runtime request tool
- the runtime still preserves `context.action` internally
- plugins remain independently evolvable

This preserves the architectural principle of model-facing simplicity while reducing schema injection cost.

### 17.4 Canonical OpenCode Request Shape

The primary OpenCode tool should accept a payload shaped like this:

```json
{
  "type": "repo.grep",
  "payload": {
    "pattern": "TODO",
    "path": "."
  }
}
```

The OpenCode bridge should convert this into the runtime protocol by attaching a request identifier.

Example runtime message:

```json
{
  "id": 42,
  "type": "repo.grep",
  "payload": {
    "pattern": "TODO",
    "path": "."
  }
}
```

This keeps the model-visible shape close to the internal protocol and avoids unnecessary translation layers.

### 17.5 Canonical OpenCode Response Shape

The bridge should return runtime responses with minimal transformation.

Success form:

```json
{
  "ok": true,
  "result": {
    "handle": "grep:44",
    "matches": [
      {
        "path": "src/main.py",
        "line": 18,
        "text": "# TODO: refactor"
      }
    ]
  }
}
```

Error form:

```json
{
  "ok": false,
  "error": {
    "code": "invalid_arguments",
    "message": "pattern is required"
  }
}
```

The bridge should not wrap results in verbose explanatory text.

The model should receive compact structured data.

### 17.6 Initial Proof-of-Concept Plugin Scope

The proof of concept should start with exactly two functional plugins:

- `repo`
- `web`

Optional later addition:

- `memory`

This ordering is recommended because `repo` and `web` cover the most common retrieval workflows while keeping mutation risk low.

Recommended initial actions:

`repo`

- `repo.find`
- `repo.grep`
- `repo.read_chunk`

`web`

- `web.search`
- `web.fetch`

These actions are already aligned with the architecture's intended model-facing concepts. fileciteturn1file0

### 17.7 Handle Behavior in the Proof of Concept

The proof of concept should aggressively use handles for any result that might otherwise be re-injected.

Recommended behavior:

- `web.search` returns a search handle plus a short top-results summary
- `web.fetch` returns a page handle plus extracted text preview
- `repo.grep` returns a grep handle plus first matches
- `repo.read_chunk` may return either inline content alone or inline content plus a chunk handle

This allows the model to say things like:

- inspect `search:12`
- fetch result 2 from `search:12`
- read more from `page:9`
- continue from `grep:44`

This handle-first pattern is a central token-efficiency mechanism in the architecture. fileciteturn1file4

### 17.8 OpenCode Bridge Responsibilities

The OpenCode-specific bridge should remain extremely thin.

Its responsibilities should be limited to:

- receiving tool calls from OpenCode
- validating the top-level request shape
- assigning request IDs
- forwarding JSON messages over stdio to the runtime
- returning runtime responses to OpenCode

It should not:

- implement plugin logic
- reinterpret domain semantics
- expand results into verbose prose
- maintain a second parallel state model beyond what is needed for transport bookkeeping

This preserves the domain-agnostic runtime principle. fileciteturn1file1

### 17.9 Recommended OpenCode Tool Definitions

For the proof of concept, the OpenCode tool contract should be conceptually equivalent to the following.

`runtime.call`

```json
{
  "type": "object",
  "properties": {
    "type": {
      "type": "string",
      "description": "Requested runtime action in context.action form"
    },
    "payload": {
      "type": "object",
      "description": "Arguments for the requested action"
    }
  },
  "required": ["type", "payload"],
  "additionalProperties": false
}
```

`runtime.handle`

```json
{
  "type": "object",
  "properties": {
    "handle": {
      "type": "string",
      "description": "Opaque runtime handle"
    },
    "view": {
      "type": "string",
      "enum": ["summary", "meta", "preview"],
      "description": "Requested lightweight handle view"
    }
  },
  "required": ["handle"],
  "additionalProperties": false
}
```

The bridge implementation may choose different public names, but the conceptual surface should remain this small.

### 17.10 Proof-of-Concept Success Criteria

The proof of concept should be considered successful if all of the following are true:

- OpenCode can execute repeated multi-step retrieval tasks through the runtime
- the model reuses handles rather than repeatedly requesting full content
- plugin addition does not require changing the runtime core
- the runtime core remains small and readable
- the bridge layer stays thin and mechanical

A stronger success signal would be a transcript showing a realistic coding or research task completed using only the minimal OpenCode bridge plus `repo` and `web`.

### 17.11 Recommended Build Order

The recommended implementation order is:

1. runtime core over stdio
2. OpenCode bridge exposing `runtime.call` and `runtime.handle`
3. `repo` plugin with `find`, `grep`, and `read_chunk`
4. `web` plugin with `search` and `fetch`
5. handle state persistence for session scope
6. small transcript-driven evaluation set

This order validates transport, routing, capability execution, and token efficiency as early as possible.

### 17.12 Design Decision

For the proof of concept, the architecture should prefer:

- a minimal OpenCode bridge with one general request tool and one handle tool

rather than:

- exposing every plugin action as an independent OpenCode tool at the outset

This decision may be revisited later.

At the current stage, it offers the best balance of token efficiency, cognitive simplicity, and implementation speed for gpt-oss-20b.


## 18. Future Extensions

The architecture supports new capability domains through plugins.

Potential future domains:

research
vector
docs
system
calendar
database

Plugins can be added without modifying the runtime core.

## 19. Summary

The architecture consists of a minimal capability runtime acting as a microkernel for agent capabilities.

Core runtime components:

- message transport
- plugin registry
- router
- state store

Domain functionality is implemented through plugins.

The model interacts with a small, stable capability surface while the runtime provides extensibility and efficiency behind the scenes.

The next implementation milestone should be a working OpenCode proof of concept using a thin bridge, the runtime core, and two simple plugins: `repo` and `web`.
