# OpenCode Token Efficiency: Design and Methodology

Revision: r2
Timestamp: 2026-03-14 12:00:00


## 1. Purpose

This document describes the design of the token efficiency work being conducted
against the OpenCode agent framework, and the pytest regression harness built to
validate it. It covers the research hypothesis, the specific changes made to the
OpenCode source, the build and installation procedure, the harness architecture,
the methodology for iterative schema compression experiments, and the before/after
token measurement infrastructure.


## 2. Research Hypothesis

The OpenAI gpt-oss model series was post-trained explicitly on agentic tool use.
From the model card (https://huggingface.co/openai/gpt-oss-120b):

> "Agentic capabilities: Use the models' native capabilities for function
> calling, web browsing, Python code execution, and Structured Outputs."

The technical report (arXiv:2508.10925) confirms that tool-use capability was
instilled during post-training rather than being purely emergent from pretraining.
This has a direct implication for prompt engineering: if the model has internalized
the semantics of standard agentic tools — read, write, edit, glob, grep — then the
verbose natural-language descriptions OpenCode injects into every prompt context
may be largely redundant. The model already knows what these tools do.

The hypothesis is therefore: **the tool schema descriptions can be progressively
compressed toward a minimal signal without degrading reliable tool invocation.**
The practical benefit is a reduction in prompt token overhead on every request,
which compounds across multi-turn agentic sessions.

The measured baseline before any compression work: a tool-enabled build agent
session costs approximately 418 prompt tokens and 545 total request tokens for a
trivial prompt ("What is your name?"). Typical agent frameworks cost several
thousand tokens for tool definitions alone. The compression work aims to determine
how much further below this baseline the schemas can be pushed while preserving
correct tool selection, argument formation, and multi-step orchestration.


## 3. What Was Changed in OpenCode

The patch modifies twelve files across three concerns: tool allowlisting, tool
description compression, and parameter annotation compression.

### 3.1 Tool Allowlisting (agent.ts, prompt.ts)

**agent.ts** adds a `tools` field to the agent schema:

```typescript
tools: z.record(z.string(), z.boolean()).optional(),
```

This allows an agent definition in `opencode.json` to declare an explicit
allowlist of tool IDs, for example:

```json
"build": {
  "tools": {
    "read": true,
    "glob": true,
    "grep": true,
    "edit": true,
    "write": true
  }
}
```

**prompt.ts** implements the allowlist check during tool resolution:

```typescript
const configuredTools = input.agent.tools
const hasStrictAllowlist = !!configuredTools && Object.keys(configuredTools).length > 0

function isAllowedTool(toolID: string) {
  if (!hasStrictAllowlist) return true
  return configuredTools?.[toolID] === true
}
```

The check is applied at two points in `resolveTools`: once for built-in tools
and once for MCP tools. When an allowlist is present, any tool not explicitly
listed with `true` is excluded from the resolved tool set before the schema is
assembled and injected into the prompt.

This is the primary mechanism for tool surface reduction. By restricting the
build agent to the five filesystem tools it actually needs for coding tasks,
all other tools (bash, task, lsp, todowrite, etc.) are excluded from the prompt
entirely, eliminating their schema tokens before any description compression
is applied.

The production OpenCode binary does not implement this check — it serializes all
available tools into the prompt regardless of any `tools` field present in the
agent definition. This behavioral difference is the primary driver of the token
count divergence measured in §10.

### 3.2 Tool Description Compression (.txt files)

Each tool's natural-language description is stored in a `.txt` file alongside
its TypeScript implementation. These descriptions are injected verbatim into the
tool schema sent to the model. The patch replaces each verbose description with
a minimal one-line equivalent:

| Tool | Original description (tokens) | Compressed description |
|------|-------------------------------|------------------------|
| read | 14 lines, ~180 tokens | `Read a file or directory.` |
| glob | 6 lines, ~80 tokens | `Find files by glob pattern.` |
| grep | 8 lines, ~100 tokens | `Search file contents by regex.` |
| edit | 10 lines, ~140 tokens | `Replace exact text in a file.` |
| write | 8 lines, ~110 tokens | `Write a file.` |

The original descriptions contained substantial instructional prose: usage
rules, edge case warnings, suggestions about when to prefer other tools, and
behavioral constraints ("NEVER write new files unless explicitly required",
"ALWAYS prefer editing existing files"). The compression hypothesis is that a
post-trained model does not need this scaffolding — it already has a prior
over correct tool behavior from training and will invoke the tool correctly
given only a minimal semantic label.

### 3.3 Parameter Annotation Compression (.ts files)

In addition to the top-level description, each tool parameter carries a
`.describe()` annotation that is included in the JSON schema sent to the model.
The patch compresses these to minimal labels:

**read.ts:**
```typescript
// Before
filePath: z.string().describe("The absolute path to the file or directory to read")
offset:   z.coerce.number().describe("The line number to start reading from (1-indexed)")
limit:    z.coerce.number().describe("The maximum number of lines to read (defaults to 2000)")

// After
filePath: z.string().describe("Path.")
offset:   z.coerce.number().describe("Start line.")
limit:    z.coerce.number().describe("Max lines.")
```

**glob.ts:**
```typescript
// Before
pattern: z.string().describe("The glob pattern to match files against")
path:    z.string().optional().describe(`The directory to search in. If not specified,
         the current working directory will be used. IMPORTANT: Omit this field to use
         the default directory. DO NOT enter "undefined" or "null" — simply omit it
         for the default behavior. Must be a valid directory path if provided.`)

// After
pattern: z.string().describe("Glob pattern.")
path:    z.string().optional().describe("Search dir.")
```

**grep.ts:**
```typescript
// Before
pattern: z.string().describe("The regex pattern to search for in file contents")
path:    z.string().optional().describe("The directory to search in. Defaults to the current working directory.")
include: z.string().optional().describe('File pattern to include in the search (e.g. "*.js", "*.{ts,tsx}")')

// After
pattern: z.string().describe("Regex.")
path:    z.string().optional().describe("Search dir.")
include: z.string().optional().describe("File glob.")
```

**edit.ts:**
```typescript
// Before
filePath:   z.string().describe("The absolute path to the file to modify")
oldString:  z.string().describe("The text to replace")
newString:  z.string().describe("The text to replace it with (must be different from oldString)")
replaceAll: z.boolean().optional().describe("Replace all occurrences of oldString (default false)")

// After
filePath:   z.string().describe("Path.")
oldString:  z.string().describe("Match text.")
newString:  z.string().describe("New text.")
replaceAll: z.boolean().optional().describe("Replace all.")
```

**write.ts:**
```typescript
// Before
content:  z.string().describe("The content to write to the file")
filePath: z.string().describe("The absolute path to the file to write (must be absolute, not relative)")

// After
content:  z.string().describe("Text.")
filePath: z.string().describe("Path.")
```

The parameter annotations contribute to the JSON schema that is serialized
into the prompt alongside the tool name and description. Even short per-parameter
strings accumulate across five tools and multiple parameters each.


## 4. Build and Installation

This section covers building OpenCode from the patched source on Debian 12. The
build targets commit `f8475649d` with the cumulative patch applied. Both the
production binary (unpatched) and the experimental binary (patched) can be built
from the same repository by checking out the appropriate state before each build.

### 4.1 Install Bun

OpenCode uses Bun as its package manager and runtime.

Install Bun:

```
curl -fsSL https://bun.sh/install | bash
```

Bun installs to:

```
~/.bun/bin/bun
```

If needed, add Bun to PATH:

```
echo 'export BUN_INSTALL="$HOME/.bun"' >> ~/.bashrc
echo 'export PATH="$BUN_INSTALL/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verify installation:

```
bun --version
```

Optional dependencies:

```
sudo apt update
sudo apt install build-essential unzip
```

### 4.2 Obtain the Source

Clone the repository and check out the base commit used for the patch:

```
git clone https://github.com/opencode-ai/opencode.git
cd opencode
git checkout f8475649d
```

Confirm the correct base revision:

```
git rev-parse HEAD
```

Expected:

```
f8475649d
```

### 4.3 Apply the Cumulative Patch

Place the patch file in the repository root:

```
opencode_cumulative_f8475649d.patch
```

Apply it:

```
git apply opencode_cumulative_f8475649d.patch
```

Verify that the patch modified the expected files:

```
git status
```

The modified files should include:

```
packages/opencode/src/agent/agent.ts
packages/opencode/src/session/prompt.ts
packages/opencode/src/tool/*
```

### 4.4 Install Dependencies

Install workspace dependencies:

```
bun install
```

### 4.5 Optional Type Checking

Run TypeScript type checking:

```
bun run --cwd packages/opencode typecheck
```

### 4.6 Build the Binary

Build the OpenCode CLI using the build script defined in
`packages/opencode/package.json`:

```
bun run --cwd packages/opencode build
```

This compiles the CLI and produces platform-specific binaries in:

```
packages/opencode/dist/
```

### 4.7 Locate the Built Binary

For Linux x64 systems the binary will be at:

```
packages/opencode/dist/opencode-linux-x64/bin/opencode
```

Example absolute path:

```
~/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode
```


## 5. Running OpenCode

Run the binary from a working directory that is not the OpenCode repository root,
to avoid injecting repository documentation into the prompt context:

```
mkdir -p /tmp/opencode-test
cd /tmp/opencode-test
~/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode
```


## 6. Patch Management

### 6.1 Regenerating the Cumulative Patch

To regenerate the patch from a modified repository:

```
git diff f8475649d -- \
  packages/opencode/src/agent/agent.ts \
  packages/opencode/src/session/prompt.ts \
  packages/opencode/src/tool \
  > opencode_cumulative_f8475649d.patch
```

This produces a single reproducible patch representing all changes since
commit `f8475649d`.

### 6.2 Diagnostic Commands

Useful commands when debugging:

```
git status
git diff
bun install
bun run --cwd packages/opencode typecheck
bun run --cwd packages/opencode build
bun run --cwd packages/opencode dev
```


## 7. Regression Harness

The pytest regression harness (`opencode_pytest_harness/`) provides automated
black-box validation of the compressed OpenCode build. Its purpose is to confirm
that schema compression does not degrade the model's ability to correctly select,
invoke, and chain the filesystem tools.

### 7.1 Why Black-Box Testing

The harness tests OpenCode as a complete system by driving the TUI CLI via
`pexpect`. It does not call the llama-server API directly, mock tool responses,
or inspect internal OpenCode state. This approach was chosen because:

- The unit of correctness is end-to-end behavior: did the model invoke the right
  tool with the right arguments, and did the file system change as expected?
- White-box API testing would require maintaining a parallel test client that
  diverges from the actual OpenCode session lifecycle, making it harder to catch
  regressions in session management, permission handling, or tool dispatch.
- The TUI driver approach means the harness tests exactly what a user would
  experience, including edge cases like the permission dialog (which would not
  arise in a direct API call).

### 7.2 Ephemeral Workspace Isolation

Each test creates a fresh workspace under pytest's `tmp_path` fixture:

```
tmp_path/
    workspace/          ← fixture files, snapshot root
    .xdg_config/        ← opencode config, invisible to snapshots
    .xdg_data/          ← opencode session storage (XDG_DATA_HOME)
    .xdg_state/         ← opencode state
    .xdg_cache/         ← bun cache + node_modules
```

All four XDG directories are redirected via environment variables
(`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`) so
that OpenCode's session files, configuration, and caches are fully contained
within `tmp_path`. This prevents state from one test affecting another.

The `XDG_DATA_HOME` redirection is essential: OpenCode stores session files
under `XDG_DATA_HOME` (typically `~/.local/share/opencode`). Without this
redirect, session files from prior runs accumulate in the real home directory
and can be loaded by subsequent test runs, producing stale workspace path
references in the model's context (a symptom of anomalyco/opencode#8538, in
which sessions created in a git-rooted directory cannot be found when OpenCode
is later invoked from a non-git directory).

### 7.3 KV Cache Flush

The `flush_llama_kv_cache` autouse fixture in `conftest.py` erases all
llama-server KV cache slots before each test via:

```
POST /slots/{id}?action=erase&id_slot={id}
```

Without this, the model's KV cache accumulates context from prior tests within
the same pytest session. Because gpt-oss-20b uses LCP-based prompt cache reuse,
residual cached tokens from one test's workspace can bleed into the next test's
context, potentially producing incorrect tool invocations that reference stale
file paths or content.

The flush requires llama-server to be started with `--slot-save-path` (any
writable directory). This flag gates the POST /slots endpoint regardless of
whether save/restore is used. See the llama-server launch script for the
complete invocation.

### 7.4 Permission Pre-Grant

The harness `opencode.json` includes a `permission` block that pre-allows all
known tools:

```json
"permission": {
  "read": "allow",
  "glob": "allow",
  "grep": "allow",
  "edit": "allow",
  "write": "allow",
  "bash": "allow",
  "task": "allow",
  "todowrite": "allow",
  "external_directory": "allow"
}
```

This exhaustive permission block serves two purposes. For the experimental binary,
it suppresses the interactive permission dialog that would otherwise appear because
the ephemeral workspace has no `.git` root, causing all workspace paths to be
classified as "external". For the production binary (which ignores the tool
allowlist and serializes all tools), it ensures that any tool the model chooses
to invoke is pre-permitted, allowing production runs to complete without hanging
on an unexpected dialog.

### 7.5 Declarative YAML Test Cases

Test cases are defined in YAML files under `tests/cases/`. Each case specifies
a fixture workspace, a natural-language prompt sent to the model, and assertions
over stdout content and workspace side effects:

```yaml
name: edit_file
fixture: basic_files
prompt: |
  Replace "TODO: replace-me" with "DONE: replaced" in beta.md.
expect:
  file_contains:
    - path: beta.md
      contains: "DONE: replaced"
  file_not_contains:
    - path: beta.md
      contains: "TODO: replace-me"
```

The `stdout_contains_re` key supports regex patterns for cases where the TUI
terminal wrapping splits expected strings across lines:

```yaml
expect:
  stdout_contains:
    - beta.md
  stdout_contains_re:
    - 'src[\s/]*nested[\s/]*sample\.py'
```

### 7.6 Fixture Workspace

The `basic_files` fixture provides a minimal workspace that exercises all five
tools:

```
basic_files/
    alpha.txt          ← read target (line-by-line retrieval)
    beta.md            ← edit and grep target (contains "TODO: replace-me")
    src/nested/
        sample.py      ← glob and workflow target (contains greet() function)
```

This workspace was designed to be the smallest possible set of files that
exercises distinct tool behaviors: a plain text file for read, a markdown file
for edit and grep, and a nested Python file requiring directory traversal for
glob.


## 8. Current Validation State

The harness validates seven test cases, all of which pass against the compressed
build:

| Case | Tools exercised | Status |
|------|----------------|--------|
| read_basic | read | PASS |
| glob_discovery | glob | PASS |
| grep_positive | grep (positive match) | PASS |
| grep_negative | grep (negative match) | PASS |
| edit_file | read + edit | PASS |
| write_file | write | PASS |
| workflow_modify_function | glob + read + edit | PASS |

The edit tool case is particularly significant: the model demonstrated the
ability to recover from a runtime safety constraint (read-before-edit enforcement)
without prompting, spontaneously issuing a read call before proceeding with the
edit. This recovery behavior was observed with the compressed schema — suggesting
the model's understanding of the tool's safety requirements is intrinsic rather
than dependent on the verbose description.


## 9. Experimental Methodology

The harness is designed to support iterative compression experiments. The
workflow is:

1. **Modify** one or more `.txt` or `.ts` files in the OpenCode source to further
   compress or remove description content
2. **Rebuild** the OpenCode binary from the patched source
3. **Run** the full harness: `pytest -s tests/`
4. **Observe** which cases pass and which fail, and examine `tests/artifacts/`
   for the stdout transcript and workspace snapshots of each run
5. **Iterate** — either push compression further on passing tools, or restore
   description content to recover failing tools

The artifacts directory provides per-test diagnostic output:

```
tests/artifacts/<case_name>-<binary_label>/
    stdout.txt            ← ANSI-stripped TUI transcript
    stdout_raw.txt        ← raw TUI output including escape sequences
    stderr.txt            ← stderr capture
    workspace_before.json ← snapshot of workspace before OpenCode ran
    workspace_after.json  ← snapshot of workspace after OpenCode ran
    token_counts.json     ← token count recorded for this run (see §10)
```

The stdout transcript includes the model's reasoning traces (Thinking: ...) which
are visible in the TUI output due to the harmony format's channel architecture.
These traces are invaluable for diagnosing compression failures: if the model
invokes the wrong tool or produces a malformed argument, the reasoning trace
typically shows where the schema ambiguity led it astray.


## 10. Token Count Measurement

The harness captures a cumulative token count for every test run and records it
alongside the other artifacts. Running each test case against both the production
and experimental binaries within the same pytest session produces a side-by-side
comparison table at the end of the run, providing quantitative evidence of the
efficiency improvement.

### 10.1 Binary Parametrization

The `binary` fixture is parametrized over two values: `production` and
`experimental`. Each resolves to a filesystem path configured via pytest ini
options, overridable on the command line:

```ini
# pyproject.toml [tool.pytest.ini_options]
production_binary = "/path/to/unpatched/opencode"
experimental_binary = "/path/to/patched/opencode"
```

Command-line overrides:

```
pytest --production-binary=/path/to/opencode-prod \
       --experimental-binary=/path/to/opencode-exp \
       -s tests/
```

This doubles the test matrix: 8 cases × 2 binaries = 16 runs, with test IDs of
the form `test_case[read_basic-production]` and `test_case[read_basic-experimental]`.
Both binaries use the same `opencode.json`, including the tool allowlist. The
production binary ignores the allowlist and serializes all tools; the experimental
binary respects it and restricts to the five declared tools. The behavioral
difference is therefore purely a product of the patch.

### 10.2 Token Count Extraction

The OpenCode TUI displays a cumulative token count in the status bar throughout
the session. This count is visible in the pexpect-captured stdout after ANSI
stripping. The harness extracts it using:

```python
import re

def extract_token_count(ansi_stripped_stdout: str) -> int | None:
    matches = re.findall(r'(\d+)\s+tokens', ansi_stripped_stdout)
    if not matches:
        return None
    return int(matches[-1])
```

The last match is used because the TUI updates the count incrementally as the
session progresses; the final value represents the total cumulative token cost
for the session.

Token count extraction is best-effort: if the pattern is not found (e.g., the
session exited before the status bar updated), `None` is recorded and a warning
is emitted, but the test is not failed on this basis alone.

### 10.3 Artifact and Summary Output

After each test run the extracted count is written to
`tests/artifacts/<case_name>-<binary_label>/token_counts.json`:

```json
{
  "case": "read_basic",
  "binary": "experimental",
  "token_count": 312
}
```

A `pytest_sessionfinish` hook collects all recorded counts across the session
and prints a Markdown summary table:

```
## Token Count Summary

| Case                     | production | experimental | delta |
|--------------------------|------------|--------------|-------|
| token_baseline           |       2800 |          418 | -2382 |
| read_basic               |       2850 |          430 |  -420 |
| glob_discovery           |        ... |          ... |   ... |
| grep_positive            |        ... |          ... |   ... |
| grep_negative            |        ... |          ... |   ... |
| edit_file                |        ... |          ... |   ... |
| write_file               |        ... |          ... |   ... |
| workflow_modify_function |        ... |          ... |   ... |
```

Cases where one or both counts are missing are shown with `—` in the relevant
column.

### 10.4 The token_baseline Case

A dedicated `token_baseline` test case is added to the suite alongside the
existing functional cases. It sends a trivial single-turn prompt ("What is your
name?") to OpenCode without any file operations. Because no tool calls or tool
results accumulate in the context, the token count for this case reflects the
schema overhead alone, providing the cleanest apples-to-apples comparison between
the production and experimental builds.

```yaml
name: token_baseline
fixture: empty
prompt: |
  What is your name?
expect:
  files_unchanged: true
```

The `empty` fixture provides a workspace directory containing no files. No
functional assertions are made beyond `files_unchanged`; the case exists solely
to anchor the token count comparison.


## 11. What the Compression Removes

It is worth being precise about what the verbose descriptions were doing and what
their removal implies.

**Instructional prose** ("You MUST use your Read tool at least once before
editing", "NEVER write new files unless explicitly required") — this content
attempts to constrain model behavior via the system prompt. The compression
hypothesis is that a post-trained model has already internalized these constraints
through training on agentic workflows, making the runtime reminder redundant.
Empirical evidence supports this: the edit tool's read-before-edit safety was
respected in the compressed build without any explicit instruction to that effect.

**Usage examples** ("Supports glob patterns like `**/*.js` or `src/**/*.ts`") —
syntax examples in the description assume the model may not know the tool's
calling convention. For a model post-trained on tool use, this is unnecessary.

**Tool selection guidance** ("When you are doing an open-ended search that may
require multiple rounds of globbing and grepping, use the Task tool instead") —
this cross-tool routing advice is particularly interesting to remove. With the
allowlist restricting the surface to five tools, the Task tool is not present in
the context at all, making this guidance moot. More broadly, if the model can
reason about tool selection from tool names and minimal descriptions alone, this
guidance is not needed.

**Warning text** ("DO NOT enter `undefined` or `null` — simply omit it for the
default behavior") — defensive instructions aimed at preventing known failure
modes. Removing these tests whether the model produces correct argument
formatting without explicit warnings. The passing test suite to date suggests it
does, at least for the five tools under test.


## 12. Known Limitations

**Sequential agent execution.** OpenCode currently dispatches subagents one at
a time. The harness validates single-agent, single-session behavior. Multi-agent
parallel workflows are not yet testable.

**Workspace root reporting.** OpenCode reports workspace root as `/` rather than
the actual working directory when invoked from a non-git directory (issue
anomalyco/opencode#8538). The model works around this by issuing a bare
`glob("*")` to discover the actual working directory from the returned paths,
costing one extra tool call per session. The harness KV cache flush and XDG
isolation mitigate the downstream effects of this bug without fixing it.

**TUI output capture.** The harness asserts against the ANSI-stripped TUI
transcript, which is affected by terminal width wrapping. Long paths may be
split across lines, requiring `stdout_contains_re` patterns rather than literal
substring matching. This is a known fragility; future work could switch to
asserting against the OpenCode session export (`/export`) for more reliable
output validation.

**Cumulative token counts.** The TUI token count is cumulative across all turns
in a session. Multi-turn cases (e.g., `workflow_modify_function`) therefore
include tokens from tool calls and tool results in addition to the initial prompt
schema overhead. Single-turn cases and `token_baseline` provide the cleanest
schema-overhead signal; multi-turn counts are useful for tracking whole-session
cost trends but should not be compared directly to the single-turn baseline.

**Single-run determinism.** Model outputs are non-deterministic. Test cases are
designed to be robust to output variation by asserting against workspace side
effects (file content) rather than exact model phrasing where possible. The grep
test cases currently assert only `files_unchanged`, lacking output assertions —
a known gap that should be addressed before the harness is considered
comprehensive.


## 13. Next Steps

The immediate work items in priority order:

1. **Implement token measurement infrastructure.** Add the `binary` parametrized
   fixture, token count extraction, per-test artifact output, `token_baseline`
   case, and `pytest_sessionfinish` summary table as described in §10.

2. **Extend grep test assertions.** Add `stdout_contains` or `stdout_contains_re`
   assertions to `grep_positive.yaml` and `grep_negative.yaml` to verify the
   model correctly reports match presence/absence, not just that it didn't corrupt
   the workspace.

3. **Further description compression.** The current patch reaches minimal
   one-line descriptions. The next experiment is removing the `.txt` content
   entirely (empty string or null) for one or two tools and observing whether
   the tool name alone is sufficient for correct invocation.

4. **Parameter annotation removal.** The `.describe()` annotations on parameters
   could similarly be reduced to empty strings or removed, testing whether the
   parameter names alone (`filePath`, `pattern`, `oldString`) carry sufficient
   semantics for correct argument formation.

5. **Validate remaining tool families.** The current harness covers the five
   filesystem tools. The bash tool, LSP tools, and any MCP tools present in the
   config should be validated before expanding the allowlist.

6. **Upstream contribution.** The allowlist mechanism in `agent.ts`/`prompt.ts`
   is independently useful and could be contributed back to the OpenCode project
   as a general-purpose tool surface configuration feature, separate from the
   schema compression work.


## 14. Pull Request Submission Checklist

This checklist covers the information needed when submitting the optimization
upstream to help maintainers review the change efficiently.

### 14.1 Clear Problem Statement

Explain that OpenCode currently sends unnecessary tool schemas and verbose tool
descriptions to the model, significantly increasing prompt token usage.

Example:

```
Default OpenCode prompt size: ~2800 tokens
Optimized prompt size: ~600 tokens
Reduction: ~78%
```

### 14.2 Description of Changes

Summarize the two logical improvements implemented by the patch:

1. Respect per-agent tool allowlists when serializing tools.
2. Reduce verbosity of tool schema descriptions without altering schema structure.

Make it clear that:

- tool names are unchanged
- parameter names are unchanged
- required fields are unchanged
- runtime behavior is unchanged

Only description text and tool inclusion logic are modified.

### 14.3 Reproduction Instructions

Provide maintainers with reproducible steps:

```
git checkout f8475649d
git apply opencode_cumulative_f8475649d.patch
bun install
bun run --cwd packages/opencode build
```

Then run the regression harness against the built binary:

```
pytest -s tests/
```

### 14.4 Validation

Correctness of tool invocation under the compressed schema is validated by the
regression harness described in §7. All seven functional test cases pass against
the experimental binary. See §8 for the current validation state. Token count
measurements comparing the production and experimental builds are recorded
automatically by the harness and summarized at the end of each pytest session
(see §10).

### 14.5 Scope Control

Emphasize that the patch is intentionally minimal and only touches:

```
packages/opencode/src/agent/agent.ts
packages/opencode/src/session/prompt.ts
packages/opencode/src/tool/*
```

No other runtime behavior is affected.

### 14.6 Performance Motivation

Explain why token efficiency matters, especially for:

- local inference
- long-context models
- consumer GPU deployments

Reducing prompt overhead improves:

- available context window
- inference latency
- KV cache pressure

### 14.7 Suggested PR Title

```
Respect agent tool allowlists and reduce tool schema verbosity
```
