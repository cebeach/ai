# llama-server Slots: Architecture, KV Cache, and Concurrency Model

Revision: r1
Timestamp: 2026-03-13 22:45:00

## 1. Overview

This brief documents the slot system in llama-server (llama.cpp), covering its
architecture, relationship to the KV cache, the concurrency model it enables,
and the API for managing slot state programmatically. It is intended as a
reference for developers working with llama-server in multi-session or
multi-agent contexts.

The findings here are grounded in direct source analysis of llama.cpp
(`tools/server/`, `src/llama-context.cpp`, `src/llama-kv-cache*.cpp`,
`common/arg.cpp`) at commit `35bee031e` (HEAD as of 2026-03-13).


## 2. What Is a Slot?

A **slot** is a conversation handle — a reserved position in llama-server's
scheduling queue that can hold one active conversation's state. The slot count
is controlled by the `--parallel` flag (short: `-np`):

```bash
llama-server --parallel 8 --kv-unified ...
```

When `--parallel` is not specified, llama-server auto-detects and defaults to
`n_parallel = 4` with `kv_unified = true` (hardcoded in `server.cpp`):

```cpp
// tools/server/server.cpp
if (params.n_parallel < 0) {
    LOG_INF("%s: n_parallel is set to auto, using n_parallel = 4 and kv_unified = true\n", __func__);
    params.n_parallel = 4;
    params.kv_unified = true;
}
```

Slots are initialized at server startup and logged explicitly:

```
srv    load_model: initializing slots, n_slots = 8
slot   load_model: id  0 | task -1 | new slot, n_ctx = 131072
slot   load_model: id  1 | task -1 | new slot, n_ctx = 131072
...
```

The llama.cpp codebase does not provide a formal prose definition of "slot".
The concept emerges from reading `server-context.cpp`, `server-task.h`, and
the slot lifecycle management code.


## 3. Slots and the KV Cache

### 3.1 The KV Cache

The KV (key-value) cache stores the attention key and value tensors computed
for every token in every active conversation. Reusing these cached tensors for
subsequent tokens in the same conversation is the primary source of inference
efficiency — without it, every new token would require recomputing attention
over the entire context history from scratch.

### 3.2 kv_unified: Shared vs. Partitioned Cache

llama-server supports two KV cache allocation modes, controlled by
`--kv-unified` (`-kvu`) / `--no-kv-unified` (`-no-kvu`):

**Unified mode (`kv_unified = true`):**
The server allocates a single shared KV cache pool sized by `--ctx-size`. All
slots draw from this pool dynamically. Adding more slots does not increase the
total pool size — it only increases the number of concurrent scheduling
positions. The context size per slot equals the full `--ctx-size`.

```
llama_context: kv_unified = true
llama_kv_cache: size = 1632.00 MiB (131072 cells, 12 layers, 4/1 seqs)
```

**Non-unified mode (`kv_unified = false`):**
The pool is partitioned equally across slots. Each slot receives
`ctx_size / n_parallel` tokens. This is the default when `--parallel` is
specified explicitly without `--kv-unified`.

```
llama_context: kv_unified = false
llama_kv_cache: size = 1632.00 MiB (16384 cells, 12 layers, 8/8 seqs)
# Each of 8 slots gets 16384 tokens = 131072 / 8
```

The context size calculation from `llama-context.cpp`:

```cpp
if (cparams.kv_unified) {
    cparams.n_ctx_seq = cparams.n_ctx;          // full context per slot
} else {
    cparams.n_ctx_seq = cparams.n_ctx / cparams.n_seq_max;  // divided equally
}
```

**For production use, `--kv-unified` is strongly recommended when setting
`--parallel` explicitly.** Without it, each slot's effective context window is
reduced by a factor of `n_parallel`.

### 3.3 KV Cache Cost Across Slot Counts (gpt-oss-20b MXFP4, Q8_0 KV)

Empirically measured on RTX 4090 with `--ctx-size 131072`:

| `--parallel` | `kv_unified` | Total KV (non-SWA) | Context per slot | VRAM free after load |
|---|---|---|---|---|
| 4 (auto) | true | 1,632 MiB | 131,072 tokens | 8,625 MiB |
| 8 | true | 1,632 MiB | 131,072 tokens | 8,544 MiB |
| 16 | true | 1,632 MiB | 131,072 tokens | 8,501 MiB |
| 8 | false | 1,632 MiB | 16,384 tokens | 8,506 MiB |

The total KV pool size is **identical** across all unified configurations.
The slot count in unified mode is essentially free from a VRAM perspective —
only the SWA cache and compute buffer scale slightly with `n_seqs`.

### 3.4 Architecture-Specific KV Cache: Hybrid SWA Models

gpt-oss-20b uses a hybrid sliding window attention (SWA) architecture with two
distinct KV caches:

- **Non-SWA cache**: 12 full-attention layers, sized by `--ctx-size`. Grows
  linearly with context length.
- **SWA cache**: 12 sliding-window layers, fixed at `n_parallel × window_size`
  cells (128 tokens per slot). Essentially constant regardless of context
  length.

At Q8_0 quantization with `--ctx-size 131072` and `--parallel 8`:

```
Non-SWA: 1,632.00 MiB  (204 MiB/slot)
SWA:        25.50 MiB  (  3 MiB/slot)
Total:    1,657.50 MiB
```

### 3.5 Scaling the KV Pool

To increase the total shared pool (spending more VRAM on cache capacity), scale
`--ctx-size`. At Q8_0 with 12 full-attention layers, 8 KV heads, and 64-dim
heads, the cost is approximately:

```
12 layers × 8 heads × 64 dim × 2 (K+V) × 1 byte (Q8_0) ≈ 0.012 MiB/token
```

With ~7,500 MiB usable headroom on an RTX 4090 after loading gpt-oss-20b:

```
7,500 / 0.012 ≈ 625,000 additional tokens
```

A practical upper bound is `--ctx-size 786432` (6 × 131,072), which keeps
total KV well within the available headroom.


## 4. The Concurrency Model: Slots Are Not Threads

### 4.1 The Thread Analogy and Where It Breaks Down

The intuitive analogy for slots is CPU threads — each slot handles one
conversation independently, and more slots mean more capacity. This analogy
holds for **concurrency** (how many conversations can be in flight
simultaneously) but breaks down completely for **throughput**.

With CPU threads:
- Each thread runs on a dedicated core
- Adding threads adds compute capacity
- N threads can process N tasks simultaneously in true parallel

With llama-server slots:
- All active sequences are batched into a **single GPU forward pass**
- There is no separate compute path per slot
- The GPU processes all sequences together, not independently
- Adding slots does **not** add compute capacity

The batched forward pass is the fundamental unit of GPU work in llama.cpp.
When multiple slots have pending tokens, the server collects them into a single
batch and runs one inference pass over all of them together. This is why
`--batch-size` (`-b`) and `--ubatch-size` (`-ub`) matter: they control how
many tokens can be processed in a single pass, not how many conversations exist.

### 4.2 What Slots Actually Buy

Slots enable **conversation interleaving** — the server can hold the KV cache
state for multiple conversations simultaneously and service them in round-robin
or priority order without evicting one to make room for another.

Practical benefits:

- **Multiple simultaneous users or sessions**: each gets a dedicated slot with
  its own KV cache state, up to the pool capacity
- **Subagent concurrency**: when an orchestrating agent fires multiple subagent
  requests concurrently, each lands on a separate slot without queuing
- **Harness test isolation**: each test run occupies its own slot, preventing
  KV cache state from one test leaking into another
- **Reduced queuing latency**: with more slots than concurrent users, requests
  are never blocked waiting for a free slot

### 4.3 Throughput Implications

Because the GPU batches all active sequences together, throughput (tokens per
second) is largely determined by the model size and GPU compute capacity, not
the slot count. What changes with slot count is **latency distribution** under
concurrent load: with more slots, more requests can be in-flight simultaneously,
but each individual request may experience slightly higher latency as the batch
size increases.

For a single-user agentic workload (one conversation at a time), slots beyond
the concurrency requirement have no throughput effect.


## 5. Slot Lifecycle and KV Cache State

Each slot maintains its KV cache state across requests within a session,
enabling the LCP (Longest Common Prefix) cache reuse that makes multi-turn
conversations efficient. When a new request arrives on a slot, the server
computes the LCP between the new prompt and the cached prompt, and reuses any
matching prefix.

When a slot finishes processing a request, its KV cache is **not automatically
cleared** — the cached tokens remain available for reuse on the next request to
that slot. This is intentional for single-session use but problematic for test
harnesses or multi-tenant scenarios where sessions must be isolated.

The `try_clear_idle_slots()` function in `server-context.cpp` can evict idle
slot caches when the pool is under pressure, but only in unified mode and only
when space is needed — it is not a guaranteed cleanup mechanism.


## 6. KV Cache Flush API

llama-server exposes a slot management API that allows per-slot KV cache erasure.
This requires the server to be started with `--slot-save-path` pointing to any
writable directory (the flag gates the endpoint regardless of whether
save/restore functionality is used):

```bash
llama-server --slot-save-path /tmp/llama-slots ...
```

### 6.1 API Endpoint

```
POST /slots/{id}?action=erase&id_slot={id}
```

Note: `action` and `id_slot` are **query parameters**, not JSON body fields.
This is non-obvious and inconsistent with REST conventions — the body is
ignored for the erase action.

Example curl invocation:

```bash
curl -s -X POST "http://127.0.0.1:8001/slots/0?action=erase&id_slot=0"
# Response: {"id_slot": 0, "n_erased": 0}
```

`n_erased` reflects the number of cached tokens cleared. A value of 0 means
the slot was already idle with no cached state.

To flush all slots:

```bash
for i in 0 1 2 3 4 5 6 7; do
    curl -s -X POST "http://127.0.0.1:8001/slots/${i}?action=erase&id_slot=${i}"
done
```

### 6.2 Python Implementation

The following function discovers the slot count dynamically from the `/slots`
endpoint and flushes all slots. This is suitable for use as a pytest fixture or
a utility function in any test harness:

```python
import requests


def flush_llama_kv_cache(base_url: str = "http://127.0.0.1:8001") -> dict:
    """Erase all llama-server KV cache slots.

    Requires the server to be started with --slot-save-path <any-writable-dir>.
    The flag gates the POST /slots endpoint regardless of whether save/restore
    is actually used.

    Action and id_slot are passed as query parameters, not JSON body fields:
        POST /slots/{id}?action=erase&id_slot={id}

    Args:
        base_url: Base URL of the llama-server instance.

    Returns:
        Dict mapping slot_id to the server's erase response for that slot.

    Raises:
        requests.HTTPError: If the /slots GET or any erase POST fails.
    """
    slots_resp = requests.get(f"{base_url}/slots", timeout=5)
    slots_resp.raise_for_status()

    results = {}
    for slot in slots_resp.json():
        slot_id = slot["id"]
        erase_resp = requests.post(
            f"{base_url}/slots/{slot_id}",
            params={"action": "erase", "id_slot": slot_id},
            timeout=5,
        )
        erase_resp.raise_for_status()
        results[slot_id] = erase_resp.json()

    return results


if __name__ == "__main__":
    results = flush_llama_kv_cache()
    for slot_id, result in results.items():
        n_erased = result.get("n_erased", "?")
        print(f"  slot {slot_id}: {n_erased} tokens erased")
```

### 6.3 pytest Fixture

For use in a pytest harness where KV cache isolation between tests is required:

```python
import os
import warnings
import requests
import pytest

DEFAULT_LLAMA_SERVER_URL = "http://127.0.0.1:8001"


@pytest.fixture(autouse=True)
def flush_llama_kv_cache() -> None:
    """Erase all llama-server KV cache slots before each test.

    Without this, the model's KV cache accumulates context from prior tests
    within the same pytest session, causing stale workspace paths and file
    content from earlier tests to bleed into subsequent ones.

    Requires llama-server to be started with --slot-save-path.
    If the server is unreachable or the endpoint is unavailable, a warning
    is issued but the test is not failed — the flush is best-effort.
    """
    llama_url = os.environ.get("LLAMA_SERVER_URL", DEFAULT_LLAMA_SERVER_URL)
    try:
        slots_resp = requests.get(f"{llama_url}/slots", timeout=5)
        slots_resp.raise_for_status()
        for slot in slots_resp.json():
            slot_id = slot["id"]
            requests.post(
                f"{llama_url}/slots/{slot_id}",
                params={"action": "erase", "id_slot": slot_id},
                timeout=5,
            )
    except Exception as exc:
        warnings.warn(
            f"Could not flush llama-server KV cache: {exc}. "
            "Tests may be affected by stale context from prior runs.",
            UserWarning,
            stacklevel=2,
        )
```


## 7. Recommended Configuration

For a single-user agentic workload on an RTX 4090 with gpt-oss-20b MXFP4:

```bash
llama-server \
  --model /path/to/model.gguf \
  --n-gpu-layers 99 \
  --ctx-size 131072 \
  --parallel 8 \
  --kv-unified \
  --flash-attn on \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --slot-save-path /tmp/llama-slots \
  --port 8001 \
  --host 127.0.0.1
```

This provides 8 concurrent conversation slots, each with the full 131,072-token
context window, at the same VRAM cost as the default 4-slot auto configuration.
The `--slot-save-path` flag enables the KV cache flush API at no additional cost.


## 8. Future Work: Parallel Agents in OpenCode

OpenCode's session orchestration (`session/prompt.ts`) currently dispatches
subagents sequentially — one subtask at a time via `tasks.pop()` followed by
`await taskTool.execute(...)`. The system prompt explicitly caps parallelism:
`"You can launch up to 1 agent(s) in parallel."` This limit is parameterized
rather than hardcoded, indicating intentional future extensibility.

When this limit is raised, llama-server's slot pool is the correct mechanism
to support concurrent subagent requests — each subagent invocation would
occupy one slot for its duration, with no changes required to the server
configuration. A pool of 8–16 unified slots would comfortably support 4–8
concurrent subagents on a single RTX 4090 with gpt-oss-20b.

The infrastructure investment in `--parallel 8 --kv-unified` is therefore
directly aligned with OpenCode's anticipated parallel agent roadmap.
