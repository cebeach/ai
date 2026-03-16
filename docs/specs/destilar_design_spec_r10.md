# destilar design specification

Revision: r10
Timestamp: 2026-03-14T22:45:00Z

## 1. Overview

`destilar` is a repository distillation tool designed to extract a high-signal subset of source code and structural metadata from large repositories in order to facilitate architectural analysis and AI-assisted code comprehension.

The tool operates using a **TOML profile** describing:

- the repository being analyzed
- which paths or patterns should be included in the distilled corpus
- which metadata reports should be generated

The result is a curated source bundle plus structural metadata intended to improve the signal-to-noise ratio when analyzing complex software systems.


## 2. Core Workflow

repository
→ profile-driven distillation
→ analysis-ready corpus

Typical usage:

```text
destilar inspect PROFILE.toml
destilar build PROFILE.toml
```

Workflow:

1. Author a `PROFILE.toml` describing the relevant portions of the repository.
2. Run `destilar inspect` to preview file selection and artifact layout.
3. Run `destilar build` to generate a distilled archive and metadata.
4. Use the resulting bundle for human or AI-assisted analysis.


## 3. CLI Commands (v1)

### inspect

Preview the effects of a profile without producing artifacts.

```text
destilar inspect PROFILE.toml
```

Optional arguments:

```text
--repo PATH
--output-dir PATH
--list-files
--list-top N
--json
```

### build

Run the full distillation pipeline and produce artifacts.

```text
destilar build PROFILE.toml
```

Optional arguments:

```text
--repo PATH
--output-dir PATH
--dry-run
--force
```

### show-config

Print the normalized configuration after parsing the profile.

```text
destilar show-config PROFILE.toml
```


## 4. Path Resolution Rules

Repository input resolution order:

1. CLI argument: `--repo`
2. TOML: `paths.input`
3. Current working directory

Output directory resolution order:

1. CLI argument: `--output-dir`
2. TOML: `paths.output`
3. Current working directory

If `paths.output` is relative, it is resolved relative to the profile file location.


## 5. Profile TOML Schema (v1)

### profile section

Required:

```text
name
```

Optional:

```text
description
append_short_commit
generate_readme
```

### paths section

```toml
[paths]
input = "~/repo"
output = "./distill-artifacts"
```

### selection section

```text
include_paths
include_globs
exclude_paths
exclude_globs
```

### analysis section

```text
reports
entrypoint_patterns
translation_unit_extensions
```


## 6. Repository Discovery Contract

Repository root resolution order:

1. CLI argument `--repo`
2. TOML `paths.input`
3. Current working directory

Validation command:

```text
git rev-parse --show-toplevel
```


## 7. Repository Identity Metadata

The following commands are executed:

```text
git rev-parse HEAD
git status --porcelain
git remote -v
```

Generated metadata files:

```text
meta/HEAD_COMMIT.txt
meta/GIT_STATUS.txt
meta/GIT_REMOTES.txt
```


## 8. File Universe Construction

Tracked repository files are obtained via:

```text
git ls-files
```

Define:

```text
U = sorted list of tracked repository files
```

Only files in `U` may be archived.

Submodules are treated as opaque directories in v1.


## 9. Selection Model

Let:

```text
I_paths = matches(include_paths)
I_globs = matches(include_globs)

I = I_paths ∪ I_globs

E_paths = matches(exclude_paths)
E_globs = matches(exclude_globs)

E = E_paths ∪ E_globs

A = I − E
X = U − A
```

Where:

```text
A = archived files
X = excluded files
```

Exclusion rules always take precedence.


## 10. Inspect Command

`destilar inspect` is defined as:

```text
build without writes
```

Inspect output includes:

```text
Profile
Resolved paths
Repository identity
Selection rules
Selection summary
Generated artifacts
Generated reports
Archive layout preview
```

When `--json` is provided, the inspect command emits a machine-readable summary including at minimum:

```text
selection_summary
tracked_files_total
archived_files_total
excluded_files_total
```


## 11. Build Pipeline

Unified pipeline:

```text
profile
→ config normalization
→ path resolution
→ repository discovery
→ git metadata
→ file index
→ selection engine
→ analysis reports
→ build plan
```

Execution diverges:

```text
inspect → render preview
build → execute plan
```


## 12. Archive Naming Algorithm

The archive root name is derived from the profile name.

Base form:

```text
archive_root = profile.name
```

If `append_short_commit = true`, append the repository short commit:

```text
archive_root = "{profile.name}_{short_commit}"
```

Where `short_commit` is the abbreviated commit identifier derived from `HEAD`.

Naming requirements:

- `archive_root` must be deterministic for a given profile and repository state
- `profile.name` must be non-empty
- `profile.name` must not contain path separators
- archive naming must not depend on wall-clock time
- the same `archive_root` is used for both archive and readme outputs

Generated output filenames:

```text
{archive_root}.tar.gz
{archive_root}_readme.txt
```


## 13. Build Output Contract

A successful build produces:

```text
{archive_root}.tar.gz
{archive_root}_readme.txt
```

Archive layout:

```text
archive_root/
  source/
  meta/
```

`source/` contains repository files preserving repo-relative structure.

`meta/` contains generated metadata reports.


## 14. Metadata Reports

Common generated reports include:

```text
BUILD_INFO.txt
HEAD_COMMIT.txt
GIT_STATUS.txt
GIT_REMOTES.txt
MANIFEST_ALL.txt
MANIFEST_ARCHIVED.txt
MANIFEST_EXCLUDED.txt
TREE_TOPLEVEL.txt
COUNTS_BY_DIR.txt
FILES_BY_EXTENSION.txt
ENTRYPOINT_CANDIDATES.txt
TRANSLATION_UNITS.txt
DU_TOPLEVEL.txt
DU_ARCHIVED_PATHS.txt
LARGEST_TRACKED_FILES.txt
LARGEST_EXCLUDED_TRACKED_FILES.txt
TRACKED_SIZE_BY_TOPLEVEL.txt
TRACKED_SIZE_ARCHIVED_VS_EXCLUDED.txt
```

Additional reports may be added via the profile `analysis.reports` field.


## 15. Python Module Architecture

```text
destilar/
  cli.py
  main.py

  profile_loader.py
  path_resolver.py

  repo_discovery.py
  git_metadata.py
  file_index.py

  selection.py
  selectors.py

  planning.py

  inspect_renderer.py
  build_executor.py

  staging.py
  archive_writer.py

  analysis/
      reports.py
      counts.py
      translation_units.py
      entrypoints.py
      disk_usage.py

  output/
      text_output.py
      json_output.py
```

Each module isolates a specific stage of the pipeline.

Architectural rule:

```text
inspect and build share identical upstream logic
inspect = build without writes
```


## 16. Core Data Structures

Key dataclasses:

```text
DistillProfile
ResolvedPaths
RepoInfo
FileRecord
FileIndex
SelectionResult
ReportOutput
BuildPlan
```

`BuildPlan` is the central internal contract. `inspect` previews the plan while `build` executes it.


## 17. Error Handling Contract

Profile validation failures must stop execution before repository analysis begins.

Examples:

- missing required `profile.name`
- invalid TOML syntax
- unsupported field types
- absolute paths in selection rules
- `..` traversal rules in selection rules
- invalid report names

Repository discovery failures must stop execution before file indexing begins.

Examples:

- resolved input path does not exist
- resolved input path is not inside a Git repository
- `git rev-parse --show-toplevel` fails

Git metadata failures must be surfaced as explicit errors.

Examples:

- `git rev-parse HEAD` fails
- `git ls-files` fails
- `git status --porcelain` fails
- `git remote -v` fails

Build output failures must stop artifact production and return a non-zero exit status.

Examples:

- output directory cannot be created
- target artifact already exists and `--force` was not provided
- staging directory creation fails
- archive writing fails
- readme writing fails

Error handling requirements:

- errors must be deterministic and actionable
- errors must identify the failing stage of the pipeline
- partial output files must not be left behind on failed build
- `inspect` must not write artifacts, even on error
- `--json` output should emit machine-readable error information when feasible


## 18. Determinism and Safety Guarantees

The implementation must ensure:

- deterministic file ordering
- deterministic archive structure
- deterministic report generation
- file lists sorted lexicographically
- path normalization before rule evaluation
- rejection of absolute paths in profiles
- rejection of `..` traversal rules
- no filesystem traversal outside repository root
- no inclusion of untracked files


## 19. Performance Characteristics

Let:

```text
N = tracked files
P = path rules
G = glob rules
```

Time complexity:

```text
O(N × (P + G))
```

For typical repositories this is acceptable because rule counts remain small.


## 20. Implementation Status

Components currently defined:

- CLI interface
- profile schema
- repository discovery
- git metadata capture
- file indexing
- selection engine
- archive naming contract
- analysis reports
- artifact layout
- Python module architecture
- error handling contract

`destilar` is **implementation-ready for version 1**.
