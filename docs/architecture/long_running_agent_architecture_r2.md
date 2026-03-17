# Long-Running Agent Architecture

| Field | Value |
|-------|-------|
| DocumentName | long_running_agent_architecture |
| Category | design-spec |
| Revision | r2 |
| Fingerprint | cc5e6de9bd148ac057ccaba7df1d483c0d7dded2cc4d16f6b8522ba25ffa2b58 |
| Status | draft |
| Timestamp | 2026-03-16T20:24:32 |
| Authors | Chad Beach & Claude Sonnet 4.6 |

## 1. Objective

This document proposes an architecture for autonomous, indefinitely-running AI coding agents
on consumer-grade GPU hardware. The target platform is a single NVIDIA RTX 4090 running
llama.cpp llama-server with OpenCode as the agent frontend, as documented in
`local_ai_agent_design_r109.md`.

The central problem is the long-running agent problem: LLM context windows are finite,
but complex software engineering tasks are not. The proposed solution is a three-layer
architecture consisting of a Supervisor Proxy, a file-based hot memory tier, and a
vector database cold memory tier, decoupled from the agent frontend by sitting at the
llama-server API boundary.

## 2. Background

### 2.1 The Long-Running Agent Problem

An LLM agent works within a single context window. When that window fills, the agent
loses access to earlier reasoning, decisions, and intermediate results. For tasks spanning
hours or days — large refactors, multi-feature development, extended research — this
boundary is hit repeatedly and its management determines whether the agent makes useful
progress or degrades.

Anthropic's published harness approach addresses this with two specialized agents: an
Initializer agent that establishes environment scaffolding on the first session, and a
Coding agent that makes incremental progress in each subsequent session while leaving
structured artifacts for the next. The key artifacts are a progress log, a feature
checklist, an `init.sh` script, and a git history. This approach is effective but reactive:
it relies on the agent recognizing session boundaries and writing clean handoffs without
external coordination.

The Anthropic memory tool (beta, `context-management-2025-06-27`) adds a complementary
mechanism: when context editing is enabled and the context approaches a configured
threshold, the model receives a warning and is prompted to preserve critical information
into memory files before old tool results are cleared. This is still reactive — the
model acts under pressure near the limit.

### 2.2 Limitations of Existing Approaches

Compaction summarizes earlier context automatically but does not guarantee that structured
state (task status, architectural decisions, debugging history) is preserved with fidelity.
The reactive warning mechanism gives the agent fewer tokens to produce a quality checkpoint
than a proactive interrupt would. Neither mechanism provides cross-session semantic search
over past agent history.

### 2.3 Design Principle

A proactive context supervisor, operating outside the agent frontend at the API boundary,
can monitor token consumption continuously and trigger structured checkpoints before
pressure builds. This decouples context lifecycle management from both the agent model
and the agent frontend, making the solution model-agnostic and frontend-agnostic.

## 3. Architecture Overview

The architecture has four components:

1. Supervisor Proxy — an HTTP reverse proxy between OpenCode and llama-server that
   monitors token consumption and injects checkpoint instructions.
2. Hot Memory — a `/memories` file directory providing structured, deterministic
   retrieval of current task state.
3. Cold Memory — a PostgreSQL + pgvector database providing semantic similarity search
   over historical session summaries.
4. Memory MCP Server — an MCP server exposing both memory tiers to agents as first-class
   tools.

```
OpenCode (or any OpenAI-compatible frontend)
    |
    | HTTP (OpenAI-compatible API)
    v
Supervisor Proxy  <-----> Memory MCP Server
    |                           |
    | HTTP (pass-through)        |
    v                           v
llama-server              PostgreSQL + pgvector
    |
    +-- Slot 0: Initializer agent
    +-- Slot 1: Coding agent
    +-- Slot 2: Supervisor model calls
    +-- Slot 3: Reserved
```

All components run locally. No cloud dependency is introduced.

## 4. Component Design

### 4.1 Supervisor Proxy

The Supervisor Proxy is a lightweight HTTP proxy implemented in Python using `fastapi`
and `httpx`. It intercepts every request from the agent frontend to llama-server and
inspects every response.

**Token accounting.** llama-server returns `usage.prompt_tokens` and
`usage.completion_tokens` in every `/v1/chat/completions` response. The proxy
accumulates these per session slot, maintaining a running token count.

**Threshold policy.** Two thresholds are defined per session:

- Yellow threshold (default 70% of context budget): the proxy appends a checkpoint
  instruction to the next user turn, directing the agent to finish its current atomic
  unit of work, commit progress to git, and write a structured checkpoint to its memory
  files. The agent completes its current work naturally before the checkpoint fires.
- Red threshold (default 90%): the proxy injects a `clear_tool_uses` context edit
  into the next API request, forcing immediate context reduction. The agent reads back
  from memory files and continues within the same session.

**Interrupt safety.** The proxy inspects response content to detect whether a tool call
is in progress. Checkpoint instructions are only injected when the response represents
a completed turn (no pending tool calls), avoiding torn state from mid-tool-call
interruption.

**Pass-through transparency.** When no threshold is crossed, the proxy forwards
requests and responses unmodified with negligible latency overhead.

### 4.2 Hot Memory

Hot memory uses the Anthropic memory tool file-system interface: a `/memories` directory
of plain text or structured files readable and writable by the agent via the six memory
tool commands (`view`, `create`, `str_replace`, `insert`, `delete`, `rename`).

Canonical hot memory files for a coding session:

| File | Content |
|------|---------|
| `progress.md` | Completed features, current feature, blockers, last git commit |
| `features.json` | Full feature checklist with pass/fail status per feature |
| `decisions.md` | Architectural decisions and their rationale |
| `init.md` | How to start the development server and run baseline tests |
| `context_budget.md` | Current token count, thresholds, checkpoint history |

The Initializer agent is responsible for creating and populating these files at session
start. Each Coding agent checkpoint updates them. The Supervisor Proxy verifies that
a checkpoint write has occurred before clearing context at the red threshold.

### 4.3 Cold Memory

Cold memory is a PostgreSQL database with the pgvector extension, providing approximate
nearest-neighbor search over session summary embeddings.

**Schema.** Each checkpoint produces one or more summary chunks stored with:

- `session_id` — unique identifier for the agent session
- `timestamp` — wall-clock time of the checkpoint
- `chunk_text` — the summary text
- `embedding` — vector embedding of `chunk_text`
- `metadata` — JSON blob (task name, feature, git commit hash, token count at checkpoint)

**Embedding model.** Embeddings are generated locally using a CPU-side embedding model
served via llama-server (e.g., `nomic-embed-text`). No cloud embedding API is required.
The embedding model consumes no GPU VRAM as it runs on CPU.

**Retrieval pattern.** At the start of a new session, the Initializer agent queries
cold memory for the top-k most semantically similar past sessions to the current task
description. Retrieved summaries are injected into the initial context as background
knowledge, compressing weeks of past work into a few hundred tokens.

**Pruning policy.** Sessions older than a configurable retention window, or below a
minimum relevance score, are pruned periodically to keep the database compact.

### 4.4 Memory MCP Server

The Memory MCP Server exposes both memory tiers to all agents as MCP tools. This
provides a uniform interface regardless of which tier is being accessed, and allows
future changes to storage backends without modifying agent prompts.

Exposed tools:

| Tool | Tier | Description |
|------|------|-------------|
| `memory_read(path)` | Hot | Read a memory file or directory listing |
| `memory_write(path, content)` | Hot | Create or overwrite a memory file |
| `memory_patch(path, old, new)` | Hot | Replace text in a memory file |
| `memory_search(query, k)` | Cold | Semantic search over historical summaries |
| `memory_store(text, metadata)` | Cold | Embed and store a summary chunk |
| `memory_prune(session_id)` | Cold | Delete all chunks for a session |

The MCP server runs as a local stdio or HTTP process and is registered in the OpenCode
MCP configuration alongside existing servers (SearXNG, trilium-bolt, etc.).

## 5. Agent Roles

### 5.1 Initializer Agent

Runs once per project. Responsibilities:

- Creates the hot memory file structure.
- Writes `features.json` from the task specification.
- Writes `init.md` with server startup and baseline test procedures.
- Queries cold memory for semantically related past sessions and injects findings
  into `decisions.md` as prior art.
- Makes an initial git commit establishing the baseline state.

### 5.2 Coding Agent

Runs in every subsequent session. Responsibilities:

- Reads all hot memory files at session start.
- Runs `init.md` startup sequence and verifies baseline functionality.
- Selects the highest-priority incomplete feature from `features.json`.
- Implements the feature incrementally, committing to git at each stable point.
- Responds to yellow-threshold checkpoint instructions by finishing the current
  atomic unit, committing, and writing updated hot memory files.
- Marks features passing only after end-to-end verification.

### 5.3 Supervisor Proxy (operational role)

The Supervisor Proxy has no LLM model of its own for primary operation; it is a
deterministic process. Its model calls (Slot 2) are used only for one optional
function: evaluating checkpoint summary quality before committing to cold memory,
using a short rubric prompt. This call is cheap (a few hundred tokens) and infrequent
(once per checkpoint).

## 6. Checkpoint Protocol

A checkpoint is the atomic unit of context lifecycle management. The protocol is:

1. Supervisor detects yellow threshold crossed.
2. Supervisor appends checkpoint instruction to next agent turn.
3. Agent completes current atomic work unit (file edit, test run, or similar).
4. Agent writes updated `progress.md`, `features.md`, and `decisions.md`.
5. Agent commits to git with a descriptive message.
6. Agent signals checkpoint complete (a defined string in its response).
7. Supervisor reads updated memory files, embeds the progress summary, and writes
   to cold memory via the MCP server.
8. Supervisor resets the session token counter.
9. Agent continues with the next feature.

If the red threshold is crossed before step 6 completes, the Supervisor injects
a `clear_tool_uses` edit. The agent re-reads hot memory and resumes from the last
committed git state.

## 7. Failure Modes and Mitigations

| Failure | Mitigation |
|---------|-----------|
| Agent produces low-quality checkpoint summary | Supervisor evaluates summary against rubric; rejects and re-prompts once before accepting |
| Agent interrupted mid-tool-call | Proxy detects pending tool call; defers checkpoint instruction to next completed turn |
| Hot memory files corrupted or missing | Supervisor detects missing required files; triggers Initializer agent for that file only |
| Cold memory unavailable | Agents degrade gracefully to hot memory only; cold memory is advisory, not required |
| llama-server slot exhausted | Supervisor queues checkpoint requests; does not initiate new sessions until a slot is free |
| pgvector query slow | Embedding index (IVFFlat or HNSW) maintained automatically; query budget capped at 200ms |

## 8. Hardware Fit

The proposed architecture adds no GPU load. The Supervisor Proxy, Memory MCP Server,
and PostgreSQL with pgvector all run on CPU. The optional CPU-side embedding model
(`nomic-embed-text`) is small and imposes negligible system load relative to the
inference workload.

llama-server's four-slot configuration from `local_ai_agent_design_r109.md` maps
directly to the agent roles: Slot 0 for the Initializer agent, Slot 1 for the primary
Coding agent, Slot 2 reserved for Supervisor quality-evaluation calls, and Slot 3
available for a second concurrent Coding agent or experimentation.

The gpt-oss-20b MXFP4 model's full 131,072-token context fits with approximately 6GB
VRAM headroom at Q8_0 KV cache quantization. With the proactive checkpoint architecture,
the Coding agent should rarely approach the 131K ceiling; the yellow threshold at 70%
fires at approximately 91K tokens, well before the limit.

## 9. Implementation Sequence

Phases are ordered to deliver value incrementally with each phase independently useful.

**Phase 1: Supervisor Proxy (core).** Implement the HTTP proxy with token accounting
and yellow/red threshold injection. Validate against a live OpenCode session.
Deliverable: working proxy with no memory integration; checkpoint instructions injected
as plain text.

**Phase 2: Hot Memory Integration.** Implement the Memory MCP Server's hot-memory
tools. Update Initializer and Coding agent prompts to use structured memory files.
Validate checkpoint round-trip: agent writes memory, context clears, agent recovers
from memory.

**Phase 3: Cold Memory Integration.** Deploy PostgreSQL + pgvector. Add the embedding
model. Implement cold-memory tools in the MCP server. Validate semantic retrieval at
Initializer session start.

**Phase 4: Supervisor Quality Evaluation.** Add the optional rubric-based checkpoint
quality check using Slot 2. Tune rubric against real checkpoints. This phase is
optional and can be deferred indefinitely.

## 10. Open Questions

- What is the optimal yellow threshold for the gpt-oss-20b MXFP4 model on real
  Superpowers sessions? The §18 context consumption study in `local_ai_agent_design_r109.md`
  is the right vehicle for this measurement.
- Can the Coding agent reliably recognize and respond to checkpoint instructions injected
  mid-conversation, or does the instruction need to appear as a system-level message?
  This requires empirical testing in Phase 1.
- What embedding dimensionality and index type (IVFFlat vs HNSW) gives the best
  retrieval quality for session summaries at this scale?
- Should the Supervisor Proxy support multiple concurrent Coding agents on Slots 1 and 3,
  with independent token budgets and checkpoint queues?

## 11. References

- `local_ai_agent_design_r109.md` — hardware baseline and software stack
- Anthropic: [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (November 2025)
- Anthropic: [Memory Tool Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) (`context-management-2025-06-27` beta)
- Thomas Wiegold: [Claude API Memory Tool: Build Agents That Learn](https://thomas-wiegold.com/blog/claude-api-memory-tool-guide/)
- pgvector: https://github.com/pgvector/pgvector
- llama.cpp llama-server: https://github.com/ggml-org/llama.cpp
- OpenCode: https://github.com/anomalyco/opencode
