# llama.cpp Repository Overview

Extracted from llama.cpp repository 3/20/2026 using OpenCode and gpt-oss-20b

## How is the llama.cpp Repository Structured?

**Repository Overview –** `**llama.cpp**`

| Section | What you’ll find | Key files / directories |
| --- | --- | --- |
| **Root** | Project entry point, build scripts, license & readme | `README.md`, `CONTRIBUTING.md`, `LICENSE`, `Makefile`, `CMakeLists.txt`, `build-xcframework.sh` |
| **Source** | Core C/C++ implementation of the llama inference engine | `common/` – core engine (`*.cpp`, `*.h`, `*.cuh`)   <br>`common/argsort.cpp`, `common/arg.h`, `common/download.cpp`, `common/json‑schema‑to‑grammar.cpp`, etc. |
| **Tools** | Command‑line utilities that use the library | `tools/cli/` – `llama-cli` (interactive & batch inference)  <br>`tools/server/` – `llama-server` (OpenAI‑API compatible HTTP server)  <br>`tools/perplexity/` – perplexity calculator  <br>`tools/llama‑bench/` – benchmark harness  <br>`tools/completion/` – CLI completion helpers |
| **Examples** | Minimal working examples that link against the library | `examples/simple/` – basic text‑completion demo  <br>`examples/llama.android` – Android example  <br>`examples/llama‑android` (Android build scripts) |
| **Docs** | Build instructions, backend support, performance tips, etc. | `docs/` – `build.md`, `docker.md`, `android.md`, `token_generation_performance_tips.md`, `ggml.md` |
| **Multimodal / UI** | Assets, shaders, and UI examples | `media/` – PNG/SVG logos  <br>`docs/ops.md` – operation diagrams |
| **Bindings / Frontends** | External language bindings and community projects | `docs/development/HOWTO‑add‑model.md` – model‑adding guide  <br>`docs/development/token_generation_performance_tips.md` – performance tuning |
| **GitHub integration** | CI, release, and community links | `tools/quantize/README.md` – quantization scripts  <br>`docs/ops.md` – operation diagrams |

**High‑level flow**

1.  **Core engine** (`common/`) implements tokenization, model loading, GPU/CPU kernels, and inference logic.
2.  **Tools** wrap the engine for typical use cases:
    *   `llama-cli` – interactive chat or text‑completion from the terminal.
    *   `llama-server` – lightweight HTTP server exposing a subset of the OpenAI API.
    *   `llama‑bench` – measures throughput/latency of different backends.
3.  **Examples** show how to embed the library into a C/C++ application.
4.  **Docs** provide build instructions, backend selection, performance tuning, and guidelines for adding new models or bindings.

**Key directories**

```
├─ common/          # Core library
├─ tools/           # CLI, server, benchmark, etc.
│   ├─ cli/
│   ├─ server/
│   ├─ perplexity/
│   ├─ llama‑bench/
│   └─ quantize/
├─ examples/        # Minimal use‑case examples
├─ docs/            # Build, backend, and dev docs
├─ media/           # Logos and illustrations
├─ grammars/        # Sample grammar files for constrained generation
├─ scripts/         # Helper scripts (e.g., build‑xcframework.sh)
├─ .github/         # Actions, issue templates, etc.
└─ README.md        # Project overview & quick start
```

This structure keeps the _core inference engine_ isolated from the various _user‑facing tools_ and _examples_, while documentation and community resources are organized in dedicated directories. The project is intentionally modular so that adding new back‑ends, bindings, or example applications can be done by extending the appropriate sub‑directory without touching unrelated code.

## How is llama-server structured?

`**llama‑server**` **– high‑level structure**

```
tools/
├─ server/
│   ├─ server.cpp                # main entry point – parses flags, builds routes, starts HTTP server
│   ├─ server-context.{h,cpp}    # holds the per‑request state (llama context, queue, etc.)
│   ├─ server-http.{h,cpp}       # thin wrapper around the embedded HTTP library (cpp‑httplib)
│   ├─ server-models.{h,cpp}    # model‑loading, router‑mode logic, LLM instance manager
│   ├─ server-queue.{h,cpp}      # thread‑pool & request queue for concurrent inference
│   ├─ server-threads.{h,cpp}     # helper for background worker threads
│   ├─ server-cors-proxy.{h,cpp} # experimental CORS proxy used by the web‑UI
│   └─ server-common.{h,cpp}     # shared utilities (e.g. error formatting, JSON helpers)
└─ server/webui/…                # the client UI that talks to the HTTP API (React/Vite)
```

### 1\. Main flow (`server.cpp`)

| Step | What happens | Key files |
| --- | --- | --- |
| **Parse CLI** | Uses `common_params_parse` to read options like `-m`, `-port`, `-n_parallel`, etc. | `common_params.h` (in `common/`) |
| **Initialize server context** | `server_context` holds the llama context, tokeniser, and inference queue. | `server-context.h/cpp` |
| **HTTP server init** | `server_http_context` wraps cpp‑httplib, configures sockets, CORS, and routes. | `server-http.h/cpp` |
| **Route registration** | `server_routes` (in `server-models.h`) exposes the OpenAI‑compatible endpoints (`/v1/chat/completions`, `/v1/embeddings`, etc.) and delegates to the inference queue. | `server-models.h/cpp` |
| **Router mode** | If no model is specified (`params.model.path.empty()`), the process becomes a _router server_: it manages multiple child servers and forwards requests. | `server-models.h/cpp` (`server_models_routes` class) |
| **Start HTTP loop** | `ctx_http.start()` launches the listener thread; `ctx_server.start_loop()` blocks until termination. | `server-http.cpp`, `server-queue.cpp` |
| **Graceful shutdown** | Signal handler (`SIGINT/SIGTERM`) stops the HTTP thread, unloads models, and frees the backend. | `server.cpp` (lines 21‑40, 219‑229, 245‑250) |

### 2\. Key components

| Component | Responsibility | How it fits |
| --- | --- | --- |
| `**server-http**` | Low‑level HTTP server using cpp‑httplib. Handles request parsing, response writing, and basic CORS support. | The entry point for all API calls. |
| `**server-models**` | Model loader and router logic. In single‑model mode it loads a single gguf file into `llama_context`; in router mode it manages a pool of child servers. | Provides the `routes` object that exposes all `/v1/*` endpoints. |
| `**server-queue**` | Thread‑pool & request queue. Every inference request is enqueued and processed by worker threads that share the llama context. | Allows concurrent inference while preserving thread‑safety. |
| `**server-context**` | Holds the actual `llama_context`, tokeniser, and other per‑server state. Also provides helper functions for inference, tokenisation, and memory tracking. | Core of the server – everything that needs to be shared across threads. |
| `**server-cors-proxy**` | Experimental CORS proxy used by the web UI to talk to remote servers. | Optional, enabled via `--webui-mcp-proxy`. |
| `**server-common**` | Shared utilities: error formatting, JSON helpers, and log macros. | Used by all server modules. |

### 3\. Typical request flow

1.  **Client → HTTP** – a POST to `/v1/chat/completions`.
2.  `**server-http**` parses the request body, validates JSON, and forwards it to the handler registered in `server-models`.
3.  `**server-models**` constructs a `server_request` and pushes it onto the `server-queue`.
4.  **Worker thread** (from `server-queue`) pulls the request, runs inference on the shared `llama_context`, and writes back the JSON response.
5.  `**server-http**` sends the response to the client.

### 4\. Router mode

*   No model is loaded in the router process.
*   The router keeps a registry of child servers (`server_models_routes`).
*   API requests are proxied to the appropriate child server based on the `model` field in the request.
*   The router also exposes `/models`, `/props`, `/lora-adapters`, etc., to manage the child servers.

### 5\. Configuration & flags

```
llama-server [options] -m <model.gguf> [--port 8080] [--n_parallel 4] [--router-mode]
```

*   `-m` – path to a GGUF model (or omitted for router mode).
*   `--router-mode` – start in router mode (`--model` omitted).
*   `--n_parallel` – number of parallel decoding threads.
*   `--webui-mcp-proxy` – enable the experimental CORS proxy for the Web UI.
*   `--embedding` – enable embedding mode (requires `-n_batch` <= `-n_ubatch`).

---

**Bottom line**

`llama‑server` is a thin HTTP façade built on top of the core llama inference engine. Its code is split into a few small, well‑named modules:

*   **HTTP handling** (`server-http`),
*   **Model & router logic** (`server-models`),
*   **Concurrency & queue** (`server-queue`),
*   **Shared state** (`server-context`), and
*   **Utilities** (`server-common`).

The `main` (`server.cpp`) glues these together, parses CLI flags, starts the HTTP listener, and cleanly shuts everything down on SIGINT/SIGTERM. The router mode adds a thin layer of request‑proxying so multiple model instances can be managed from a single control plane.
