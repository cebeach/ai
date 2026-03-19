# destilar vision

| Field | Value |
|-------|-------|
| DocumentName | destilar_vision |
| Role | vision |
| Revision | r1 |
| Fingerprint | bccf3f2e62bfc0b90b66c343fd2df4bfb9f0d025d76cb4cbe87056613597e72e |
| Status | draft |
| Timestamp | 2026-03-19T00:26:58 |
| Authors | Chad |

`destilar` is useful as a repository archiver, but its more interesting long-term role is as a **source-ingestion front end for LLM analysis**.

That is, not just:

```text
repo → smaller tarball
```

but:

```text
repo → task-shaped collection → structural metadata → analysis contract
```

And that is a meaningfully different thing.

The design you’ve converged on already points in that direction: a profile-driven, reproducible distillation pipeline with stable archive and metadata contracts, plus an `inspect` mode that previews the same result `build` would materialize.

## 1. The real problem `destilar` solves

The obvious problem is repository size.

The deeper problem is **semantic bandwidth mismatch** between:

* a large codebase
* a user’s current question
* an LLM’s effective working set

Even with a large context window, throwing a raw repo at the model is wasteful because most of the repository is irrelevant to the immediate question.

Your llama.cpp archive is a good example. The full repo is much larger, but the inference path you care about lives in a much narrower surface: `src`, `ggml`, `tools/server`, `common`, selected build files, and supporting metadata. The curated archive cut that to 1701 archived files with 735 tracked files excluded while preserving the core inference path.

That is exactly the pattern `destilar` should generalize.

## 2. From archive tool to ingestion tool

A normal archive tool asks:

> What files should I pack?

A source-ingestion tool asks:

> What information should the model receive to answer a specific class of questions well?

That leads to a different set of goals:

* preserve execution-path relevance
* preserve architectural boundaries
* preserve enough metadata to navigate
* minimize irrelevant surface area
* keep output stable across iterations
* support question-specific profiles

That last point is important.

The right collection for:

```text
How does llama-server reach CUDA kernels?
```

is not the same as the right collection for:

```text
How is llama.cpp built and packaged on Debian?
```

or:

```text
How does OpenCode inject tool schemas?
```

You already have a second example of that in the OpenCode token-efficiency work: the relevant surface there is not “all of OpenCode,” but specifically the tool schema path, prompt assembly path, harness, and measurement infrastructure.

So the real unit of abstraction is not “repository profile,” but closer to:

```text
repository + analysis question class → ingestion profile
```

## 3. Why this matters for local agent runtimes

This lines up very closely with the architecture direction in your local runtime document.

That runtime is explicitly trying to preserve token efficiency by keeping model-facing surfaces small, stable, and predictable, with complexity hidden behind a simple interface.

`destilar` is essentially the same idea, applied to source code ingestion:

* keep the model-facing collection small
* keep the metadata stable
* make reuse explicit
* hide curation complexity behind a profile

In other words:

```text
runtime: small stable capability surface
destilar: small stable source-analysis surface
```

Those are parallel ideas.

I think that is a strong sign the design is on the right track.

## 4. A better mental model: `destilar` produces a question-shaped collection

I would describe the output not merely as an archive, but as a:

> **question-shaped source collection**

That phrase matters because it explains why the profile exists.

The profile is not just a list of paths. It is a hypothesis about:

* what code matters
* what metadata helps navigation
* what reports reduce follow-up turns
* what exclusions reduce noise

That makes `destilar` extremely well suited to AI-assisted reasoning.

Instead of spending 10 turns on:

* “where is the server?”
* “does this repo use examples/server or tools/server?”
* “what files were actually included?”
* “why is the repo large?”
* “which files define the call path?”

the first turn can begin with a curated collection plus supporting manifests.

That is a substantial gain.

## 5. The current output format is already close to a good LLM ingestion format

Your current spec already has the right bones:

```text
{archive_root}/
  source/
  meta/
```

with stable report names and a build contract.

That separation is excellent for LLM work because it distinguishes:

* primary evidence (`source/`)
* navigational evidence (`meta/`)

That is much better than a flat tarball.

The metadata set is also well chosen:

* manifests
* top-level counts
* file extension counts
* entrypoint candidates
* translation units
* size reports

Those are exactly the kinds of artifacts that reduce exploratory thrash in analysis.

So I would say the current `destilar` design is already a strong **v1 ingestion container**.

## 6. What would make it a true LLM ingestion format

To become more explicitly LLM-oriented, I would add three ideas over time.

### A. Explicit analysis intent in the profile

Right now the profile selects files.

Eventually it may help to also declare why.

For example:

```toml
[analysis]
intent = "trace_llama_server_execution_path"
questions = [
  "How does an OpenAI-compatible request reach llama_decode()?,"
  "Where is the GPU compute graph executed?",
  "How is KV cache placement handled?"
]
```

This would not change archive contents directly in v1, but it would do two things:

* make the profile self-documenting
* allow future report generation to become question-aware

I would not add this yet unless you want it, but conceptually it is important.

### B. Stable machine-readable metadata in parallel with text

Right now the reports are text-first.

That is good for humans, but for programmatic or agentic reuse, JSON sidecars would be valuable.

For example:

```text
meta/BUILD_INFO.json
meta/SELECTION_SUMMARY.json
meta/ENTRYPOINT_CANDIDATES.json
```

Not instead of the text files — alongside them.

That would make `destilar` useful not only to a human handing a bundle to ChatGPT, but also to your future runtime or plugins.

### C. Optional analysis seeds

This is the most interesting future enhancement.

For example, `destilar` could optionally generate:

* likely entrypoint files
* likely execution-path files
* likely build-graph files
* likely config files
* likely backend files

You are already halfway there with `ENTRYPOINT_CANDIDATES.txt`.

This could evolve into lightweight “analysis seeds” without becoming a heavyweight static analyzer.

## 7. Where this could plug into your runtime architecture

I think there is a very natural future connection to the runtime design.

Your runtime wants plugins representing bounded contexts like `repo`, `web`, and `memory`, with token-efficient handles and a small model-facing surface.

A future `repo` plugin could use `destilar` outputs as a first-class collection.

Something like:

```text
repo.distill(profile)
→ returns artifact handle

repo.inspect(handle)
→ returns metadata summary

repo.read_chunk(handle, path, offset, limit)
→ reads from distilled source corpus

repo.find(handle, pattern)
→ queries curated collection rather than full repo
```

That would be powerful because it would let the runtime operate on:

* a smaller, task-specific source surface
* with stable metadata
* without repeatedly rediscovering relevance

In that world, `destilar` becomes a precomputation layer for the `repo` context.

That seems very aligned with your overall direction.

## 8. Why this is especially useful on local hardware

This matters more locally than in cloud settings.

Why?

Because on a local 24 GB system, even if the nominal context window is large, **effective cognitive budget still matters**. Your runtime architecture explicitly treats token efficiency as a first-order design constraint for `gpt-oss-20b` on consumer GPUs.

A distilled collection does three things:

* reduces prompt overhead
* reduces reasoning distraction
* increases the chance that the model’s limited working attention stays on the relevant path

So even when a model can technically fit a large collection, distillation still improves quality.

This is analogous to the OpenCode tool-schema work: even if the model can process the full schema, reducing redundant overhead still helps.

## 9. The real value is reproducible analysis state

One of the most important long-term benefits is that a `destilar` profile becomes part of the analysis record.

For a given question, you now have:

* the profile
* the archive
* the metadata
* the commit
* the rationale embodied in the selection rules

That is much better than a transient chat history saying “I think these files matter.”

It makes the analysis reproducible.

That is a big deal for:

* returning to a repo months later
* comparing architectural understanding over time
* sharing curated corpora with other people or future sessions
* grounding design discussions in stable artifacts

## 10. A useful way to categorize future `destilar` profiles

I think there are at least four profile families that will emerge naturally.

### Execution-path profiles

Example:

```text
llama_cpp_inference_path.toml
```

Goal:

```text
request → server → core runtime → backend execution
```

### Build-path profiles

Example:

```text
llama_cpp_build_and_packaging.toml
```

Goal:

```text
how binaries are built, linked, packaged, installed
```

### Architecture profiles

Example:

```text
opencode_tool_schema_path.toml
```

Goal:

```text
where capability surfaces are defined and injected
```

### Behavioral validation profiles

Example:

```text
openai_tool_call_regression.toml
```

Goal:

```text
the smallest source and harness surface needed to reason about regressions
```

This reinforces the idea that the profile is question-shaped, not repo-shaped.

## 11. What I would avoid

There are a few things I would try hard not to let `destilar` become.

### Not a full static analyzer

It should not try to infer a complete call graph or compile database unless that grows naturally later.

### Not a build system

It should not compile or transform the repo.

### Not a general code search replacement

Its job is curation and metadata generation, not being ripgrep with extra steps.

### Not an AI agent itself

It should remain an enabling layer, not absorb the reasoning role.

That keeps the tool crisp.

## 12. My strongest insight

If I had to summarize the most important idea in one sentence:

> `destilar` is best understood as a **task-oriented source distillation format for LLM reasoning**, not merely as an archive generator.

That framing explains:

* why profiles matter
* why metadata matters
* why `inspect` matters
* why reproducibility matters
* why this fits your broader token-efficiency and local-agent work

And it suggests a future where the same method is reusable across many repositories and many analysis questions.

## 13. What I would do next

The next design step I would recommend is not implementation yet, but defining one more conceptual layer for the spec:

### **Analysis Profile Taxonomy**

A short section in the spec that says a profile may be intended for one of a few question classes:

* execution path
* build path
* architecture surface
* behavioral validation

That would make the tool’s true purpose more explicit and help future profiles stay intentional.

After that, implementation can proceed cleanly.

If you want, I can draft **Revision r6** of the design spec next, adding both the **selection engine contract** and a short **LLM ingestion / profile taxonomy** section.
