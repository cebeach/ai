# OpenCode: Startup Directory Semantics Fix Proposal

| Field | Value |
|-------|-------|
| DocumentName | opencode_startup_directory_fix_proposal |
| Role | proposal |
| Revision | r3 |
| Fingerprint | 511311969b28fecfb851b27f14ff82ec65683441fe01b176c06a36c14dbbb7f7 |
| Status | draft |
| Timestamp | 2026-03-20T03:27:03 UTC |
| Authors | Chad Beach, ChatGPT-5, Claude Sonnet 4.6 |

## 1. Summary

OpenCode conflates two distinct concepts — the **startup directory** (the
directory where OpenCode was invoked, immutable for the lifetime of the process)
and the **working directory** (mutable, may change during execution). The
permission system's `external_directory` check is intended to be relative to
the former, but the runtime historically exposed only the latter under the
ambiguous name `Instance.directory`.

In non-git directories this produces an additional failure mode: `Project.fromDirectory()`
falls back to `worktree = "/"`, causing `Instance.containsPath()` to classify
every absolute path as external, triggering a permission dialog for every tool
call that touches the workspace.

This is the root cause of the spurious permission dialogs observed during
non-interactive test execution from a temporary directory, and a contributing
factor to issue anomalyco/opencode#8538 (*Session lookup fails with
NotFoundError when PTY spawned from non-git directory context*).

This document describes a patch that has been developed and applied. It is a
**tidy** in the sense of Kent Beck's
[*Tidy First?*](https://tidyfirst.substack.com/p/tidy-first-in-one-page) —
a small, structure-only change that makes the code easier to understand and
modify, committed separately from any behavioral change. No existing behavior
changes, no call sites are broken, no interfaces are removed. The patch
introduces an explicit `Instance.startupDirectory` field — immutable, named,
and populated from the correct source — and makes `containsPath()` use it as
the primary permission boundary check. `Instance.directory` is retained as a
legacy alias for backward compatibility with all existing callers.

## 2. Background

### 2.1 How the Startup Directory Is Currently Resolved

In `packages/opencode/src/cli/cmd/tui/thread.ts`, the startup directory is
computed correctly at process initialization:

```typescript
// Resolve relative --project paths from PWD, then use the real cwd after
// chdir so the thread and worker share the same directory key.
const root = Filesystem.resolve(process.env.PWD ?? process.cwd())
const next = args.project
  ? Filesystem.resolve(path.isAbsolute(args.project)
      ? args.project
      : path.join(root, args.project))
  : Filesystem.resolve(process.cwd())
process.chdir(next)
// ...
const cwd = Filesystem.resolve(process.cwd())
```

At this point three conditions hold:

- `args.project` has already been resolved
- `process.chdir(next)` has already succeeded
- `process.cwd()` now reflects the real session start location

So `cwd` is the authoritative, immutable startup directory. It was previously
passed to `Instance.provide({ directory: cwd })` and stored under a name that
does not communicate its immutability or its role as the permission boundary.

### 2.2 The worktree Fallback Problem

`Instance.boot()` calls `Project.fromDirectory()` to resolve the project
boundary. For git repositories this returns the repository root as `worktree`.
For non-git directories it returns:

```typescript
{ id: "global", worktree: "/", sandbox: "/" }
```

The original `containsPath()` checked both `Instance.directory` and
`Instance.worktree`. With `worktree = "/"`, `Filesystem.contains("/", path)`
is always true — every path appears internal in non-git projects. The inverse
failure also existed: when a PTY spawned from a git project later operates from
a non-git directory, the `worktree` diverges from the startup directory, causing
workspace paths to be misclassified as external.

A partial mitigation (the `worktree === "/"` guard) was already present in the
build being tested:

```typescript
containsPath(filepath: string) {
  if (Filesystem.contains(Instance.directory, filepath)) return true
  if (Instance.worktree === "/") return false   // guard against non-git fallback
  return Filesystem.contains(Instance.worktree, filepath)
}
```

This correctly suppresses the `worktree = "/"` false positive but does not
introduce the explicit named concept needed for future code to use unambiguously.

### 2.3 Reproduction via the pytest Harness

The pytest harness provides a reliable reproduction environment. When `pexpect`
spawns OpenCode from a temporary workspace (e.g.
`/tmp/pytest-of-chad/pytest-45/.../workspace`):

1. The workspace has no `.git` directory
2. `Project.fromDirectory()` returns `id: "global"`, `worktree: "/"`
3. Tool calls reference absolute paths within the workspace
4. `assertExternalDirectory()` fires and raises a TUI permission dialog
5. The harness times out waiting for a response

The harness sidesteps this today via two mechanisms:

- **Permission pre-grant** in `opencode.json` — `external_directory: "allow"` suppresses
  the dialog before it reaches the TUI regardless of `containsPath()` output
- **XDG isolation** — ensures no stale session state from prior runs affects path resolution

These workarounds are correct for the test harness but do not fix the underlying
semantics for end users.

## 3. The Patch

The patch modifies two files. It is strictly additive: new fields and properties
are added, existing ones are retained unchanged.

### 3.1 packages/opencode/src/project/instance.ts

**Context interface** — `startupDirectory` added alongside `directory`, with
`directory` explicitly documented as a legacy alias:

```typescript
interface Context {
  /**
   * Legacy field retained for compatibility.
   *
   * Historically, much of the code reads `Instance.directory`.
   * We keep it for now so this refactor stays mechanically small.
   */
  directory: string

  /** Immutable directory where OpenCode started for this instance. */
  startupDirectory: string

  worktree: string
  project: Project.Info
}
```

**`boot()`** — accepts `startupDirectory` and propagates it through both
code paths (pre-supplied project and `Project.fromDirectory()` resolution):

```typescript
function boot(input: {
  directory: string
  startupDirectory: string
  init?: () => Promise<any>
  project?: Project.Info
  worktree?: string
}) {
  return iife(async () => {
    const ctx =
      input.project && input.worktree
        ? {
            // Legacy alias preserved for compatibility with existing callers.
            directory: input.directory,
            // This is the true immutable startup directory captured at init time.
            startupDirectory: input.startupDirectory,
            worktree: input.worktree,
            project: input.project,
          }
        : await Project.fromDirectory(input.directory).then(({ project, sandbox }) => ({
            // Legacy alias preserved for compatibility with existing callers.
            directory: input.directory,
            // This is the true immutable startup directory captured at init time.
            startupDirectory: input.startupDirectory,
            worktree: sandbox,
            project,
          }))
    // ...
  })
}
```

**`Instance.provide()`** — accepts optional `startupDirectory`, defaulting to
`directory` for backward compatibility with existing callers that do not supply it:

```typescript
async provide<R>(input: {
  directory: string
  startupDirectory?: string   // optional — defaults to directory
  init?: () => Promise<any>
  fn: () => R
}): Promise<R> {
  // Normalize the directory once so all later comparisons use canonical paths.
  const directory = Filesystem.resolve(input.directory)

  // Freeze the startup directory exactly once at initialization time.
  // If not provided explicitly yet, fall back to `directory` so behavior
  // remains compatible.
  const startupDirectory = Filesystem.resolve(input.startupDirectory ?? directory)

  // ...
  existing = track(
    directory,
    boot({ directory, startupDirectory, init: input.init }),
  )
  // ...
}
```

**`Instance.startupDirectory` property** — exposed with a clear docstring:

```typescript
get startupDirectory() {
  // Unambiguous immutable startup directory.
  // Future permission and workspace-boundary logic should prefer this field.
  return context.use().startupDirectory
},
```

**`containsPath()`** — primary check updated to use `startupDirectory`. The
`worktree === "/"` guard is preserved unchanged:

```typescript
/**
 * Check if a path is within the project boundary used by permissions.
 *
 * The documented rule is based on the directory where OpenCode was started,
 * so the first containment check should be against the immutable startup directory.
 */
containsPath(filepath: string) {
  // Key semantic fix: compare against immutable startupDirectory,
  // not the ambiguously named legacy `directory` field.
  if (Filesystem.contains(Instance.startupDirectory, filepath)) return true
  // Non-git projects set worktree to "/" which would match any absolute path.
  // Skip worktree check in this case to preserve external_directory permissions.
  if (Instance.worktree === "/") return false
  return Filesystem.contains(Instance.worktree, filepath)
}
```

**`reload()`** — updated with the same `startupDirectory ?? directory` pattern
for consistency:

```typescript
async reload(input: {
  directory: string
  startupDirectory?: string
  // ...
}) {
  const directory = Filesystem.resolve(input.directory)
  const startupDirectory = Filesystem.resolve(input.startupDirectory ?? directory)
  // ...
}
```

**Note on `state()`:** The `state()` method retains `Instance.directory` as its
partition key deliberately, as changing this would affect state lifecycle
management for all existing callers and is outside the scope of this tidy:

```typescript
state<S>(init: () => S, dispose?: (state: Awaited<S>) => Promise<void>): () => S {
  return State.create(() => Instance.directory, init, dispose)  // deliberately unchanged
},
```

### 3.2 packages/opencode/src/cli/cmd/tui/thread.ts

`cwd` is now passed explicitly as `startupDirectory` at the `Instance.provide()`
call site, with a comment explaining the invariants that make it authoritative
at this point:

```typescript
const config = await Instance.provide({
  directory: cwd,
  // At this point `cwd` is the confirmed canonical startup directory:
  // - args.project (the optional positional project path) has already been resolved
  // - process.chdir(next) has already succeeded
  // - process.cwd() now reflects the real session start location
  //
  // We store it explicitly under an immutable name so future readers can
  // distinguish "startup directory" from mutable process working-directory state.
  startupDirectory: cwd,
  fn: () => TuiConfig.get(),
})
```

## 4. What This Is and Is Not

This patch is an instance of what Kent Beck calls a *tidy* in
[*Tidy First?*](https://tidyfirst.substack.com/p/tidy-first-in-one-page) — a
small, structure-only change that makes the code easier to understand or
modify, separated from any behavioral change. Beck's principle is that tidies
should be committed independently, before the behavior change they enable, so
that code review can clearly distinguish "this changes structure" from "this
changes behavior." This patch follows that discipline exactly: it introduces
`startupDirectory` as a named, immutable concept without changing what any
existing code does.

**This is:**
- A tidy — naming an already-correctly-computed value explicitly
- A foundation for future work — `Instance.startupDirectory` is now available
  for any code that needs to reason about the original invocation context
- Backward compatible — all existing callers of `Instance.provide()` that do not
  pass `startupDirectory` receive the same behavior as before via the
  `?? directory` fallback
- Low risk — two files modified, no interfaces removed, no call sites broken

**This is not:**
- A fix for the session storage key problem in #8538 (that requires keying
  sessions on `startupDirectory` rather than `project.id`, a larger change)
- A fix for `Project.fromDirectory()` returning `worktree = "/"` for non-git
  directories (that is a separate concern in the project discovery logic)
- A refactor — `Instance.directory` continues to exist and work exactly as before

## 5. Testing with the pytest Harness

The harness provides a controlled reproduction of the permission dialog failure.
Once the patch is included in a build, the `external_directory: "allow"`
pre-grant in `tools/opencode/opencode.json` can be removed and the test suite
run to validate:

```bash
# Remove external_directory from the permission block in opencode.json, then:
pytest -s tests/
```

All seven tests passing without the pre-grant is the definitive validation
signal: it proves that `Instance.containsPath()` correctly classifies workspace
paths as internal for every tool call in every test case.

If any test triggers a permission dialog, the `tests/artifacts/<case>/stdout.txt`
transcript will show the exact path that failed the check, providing a precise
diagnostic for further investigation.

## 6. Relationship to #8538

The issue title — *Session lookup fails with NotFoundError when PTY spawned from
non-git directory context* — describes a downstream symptom: sessions stored
under a git project ID cannot be found when a subsequent lookup uses
`project.id = "global"` from a non-git context. The `startupDirectory` patch
does not fix this directly.

What it provides is the semantic foundation: with a stable, named startup
directory available, a future change could key session storage on
`startupDirectory` rather than `project.id`, ensuring consistent lookup
regardless of what directory subsequent tool calls or PTY sessions operate from.
PR #9474 (cross-project session lookup with fallback search) addresses the
symptom correctly. The `startupDirectory` approach addresses the underlying
semantic ambiguity that produces the symptom.

## 7. Priority and Scope

This fix is low priority relative to the token efficiency work. The harness
sidesteps the issue cleanly and all seven test cases pass. No active failures
depend on this fix.

The patch is a candidate upstream contribution to OpenCode. Its small scope
(two files, additive only, fully backward compatible) and clear commentary make
it straightforward to review. It should be proposed after the token efficiency
work is validated and a PR is ready for that work, as the two patches are
independent and can be submitted separately.
