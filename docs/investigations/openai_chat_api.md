# OpenAI Chat API

Extracted from llama.cpp repository 3/20/2026 using OpenCode and gpt-oss-20b

## Identify source code which defines how a Request must be structured

So the request structure is defined by the OpenAI chat API: it expects "model", "messages", optional "max\_tokens", "temperature", "top\_p", "stream", etc. The code that parses it is in oaicompat\_chat\_params\_parse. The question: "Identify source code which defines how a Request must be structured". So the answer: the request parsing code is in server-common.cpp, function oaicompat\_chat\_params\_parse, which validates fields: messages array, role, content, optional tools, tool\_choice, stream, etc. The request structure is defined by the OpenAI API spec, but code defines it. So we can summarise that the source code that defines how a request must be structured is in `server-common.cpp` (function `oaicompat_chat_params_parse`) and `server-context.cpp` where the request body is parsed and validated. Also the `server_routes` class registers handlers that call this function.

Thus, we should list the relevant files and code snippets.

**Where the “shape” of a request is enforced**

| File | What it does | Key lines |
| --- | --- | --- |
| `tools/server/server-common.cpp` | `**oaicompat_chat_params_parse**` – the single place that validates an OpenAI‑style chat request and turns it into a `llama_params` structure. | Lines 889‑1125 (the function body) |
| `tools/server/server-context.cpp` | The HTTP handler for `/v1/chat/completions` (and the other OAI‑compatible endpoints) calls `oaicompat_chat_params_parse` after parsing the raw JSON body. | Lines 3601‑3638 (the `post_chat_completions` lambda) |
| `tools/server/server-models.h` / `server-models.cpp` | Registers the route handlers that ultimately forward the request to `handle_completions_impl`. | `init_routes()` in `server-context.cpp` (lines 3213‑3218) |

### What `oaicompat_chat_params_parse` checks

*   **Required fields**
    *   `"messages"` – an array; each element must contain `"role"` and either `"content"` or `"tool_calls"` (assistant messages).
    *   `"model"` – required on the outer request (validated earlier in `server-context.cpp`).
*   **Optional fields** (validated or passed through)
    *   `"stream"` – boolean, controls streaming.
    *   `"tool_choice"` – string, only accepted if `--jinja` flag is set.
    *   `"tools"` – array (must be empty unless `--jinja`).
    *   `"stop"` – string or array; converted to an array.
    *   `"response_format"` – handles `"json_object"` or `"json_schema"`; disallows mixing with `"grammar"`.
    *   `"json_schema"` / `"grammar"` – mutually exclusive.
    *   `"chat_template_kwargs"` – merges command‑line overrides.
    *   `"parallel_tool_calls"`, `"add_generation_prompt"`, `"enable_thinking"`, `"reasoning_format"` – additional flags.
*   **File/media handling** – parses `"content"` arrays for `"image_url"` and `"input_audio"` objects, loads the referenced files (or decodes base64), and replaces them with a `media_marker` token.
*   **Output** – a JSON object (`llama_params`) that contains all the parameters expected by `handle_completions_impl`, e.g. `prompt`, `stop`, `chat_format`, `n_probs`, `parse_tool_calls`, etc.

### Summary

The request must be a JSON object that follows the OpenAI Chat Completion API (i.e. includes `"model"`, `"messages"` with `"role"`/`"content"` pairs, and optional streaming, tool, and formatting options). The code that _defines_ these requirements is the `oaicompat_chat_params_parse` function in `**server-common.cpp**`, together with the HTTP handler in `**server-context.cpp**` that calls it. These two files together enforce the request structure and translate it into the internal `llama_params` format used by the inference engine.

## What is the JSON schema for an OpenAI Chat Completion API Request?

**JSON‑Schema for an OpenAI‑style Chat Completion request**

```
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OpenAI Chat Completion API Request",
  "description": "The request body accepted by the llama‑server `/v1/chat/completions` endpoint (and the other OAI‑compatible chat endpoints).  The schema covers the fields that are validated in `oaicompat_chat_params_parse()` (see *server‑common.cpp*).",
  "type": "object",
  "required": ["model","messages"],
  "properties": {
    "model": {
      "type": "string",
      "description": "The name or path of the model to use.  Must match a loaded model."
    },

    "messages": {
      "type": "array",
      "description": "The chat turn history.  Each element is a message object.",
      "items": {
        "type": "object",
        "required": ["role"],
        "properties": {
          "role": {
            "enum": ["system","user","assistant","tool"],
            "description": "The role of the message."
          },

          "content": {
            "oneOf": [
              { "type": "string" },
              {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["type"],
                  "properties": {
                    "type": {
                      "enum": ["text","image_url","input_audio"],
                      "description": "Content block type."
                    },

                    /* text block */
                    "text": {
                      "type": "string",
                      "description": "Plain‑text content."
                    },

                    /* image block */
                    "image_url": {
                      "type": "object",
                      "description": "Image supplied via an HTTP or data URL.",
                      "required": ["url"],
                      "properties": {
                        "url": { "type": "string" },
                        "detail": {
                          "enum": ["auto","low","high"],
                          "description": "Optional detail level; only accepted when `--mmproj` is enabled."
                        }
                      },
                      "additionalProperties": false
                    },

                    /* audio block */
                    "input_audio": {
                      "type": "object",
                      "description": "Audio supplied via base64 data.",
                      "required": ["data","format"],
                      "properties": {
                        "data":   { "type": "string" },
                        "format": { "enum": ["wav","mp3"] }
                      },
                      "additionalProperties": false
                    }
                  },
                  "additionalProperties": false
                }
              }
            ]
          },

          /* assistant messages may optionally contain tool calls */
          "tool_calls": {
            "type": "array",
            "description": "List of tool calls produced by the assistant.",
            "items": {
              "type": "object",
              "required": ["id","name","arguments"],
              "properties": {
                "id":       { "type": "string" },
                "name":     { "type": "string" },
                "arguments":{ "type": "string" }
              },
              "additionalProperties": false
            }
          }
        },
        "additionalProperties": false
      }
    },

    /* generation parameters – all optional */
    "temperature": { "type":"number","minimum":0,"maximum":2 },
    "top_p":       { "type":"number","minimum":0,"maximum":1 },
    "top_k":       { "type":"integer","minimum":0 },
    "max_tokens":  { "type":"integer","minimum":0 },
    "n":           { "type":"integer","minimum":1 },
    "stream":      { "type":"boolean" },

    "stop": {
      "oneOf": [
        { "type":"string" },
        { "type":"array","items":{"type":"string"} }
      ]
    },

    "presence_penalty": { "type":"number" },
    "frequency_penalty":{ "type":"number" },

    "logit_bias": {
      "type":"object",
      "additionalProperties": { "type":"number" }
    },

    "user": { "type":"string" },

    /* logprobs */
    "logprobs":    { "type":"boolean" },
    "top_logprobs":{ "type":"integer","minimum":1 },

    /* seed */
    "seed": { "type":"integer" },

    /* tools */
    "tools": {
      "type":"array",
      "items": {
        "type":"object",
        "required": ["type"],
        "properties": {
          "type": { "enum":["function"] },

          "function": {
            "type":"object",
            "required":["name","description","parameters"],
            "properties": {
              "name":        { "type":"string" },
              "description": { "type":"string" },
              "parameters":  { "type":"object" }   // any JSON‑schema
            },
            "additionalProperties": false
          }
        },
        "additionalProperties": false
      }
    },

    /* tool_choice */
    "tool_choice": {
      "oneOf": [
        { "type":"string","enum":["auto","none"] },
        {
          "type":"object",
          "required":["type","function"],
          "properties": {
            "type": { "enum":["function"] },
            "function": {
              "type":"object",
              "required":["name"],
              "properties": { "name": { "type":"string" } },
              "additionalProperties": false
            }
          },
          "additionalProperties": false
        }
      ]
    },

    /* response format */
    "response_format": {
      "type":"object",
      "required":["type"],
      "properties": {
        "type": { "enum":["json_object","json_schema","text"] },
        "schema":   { "type":"object" },
        "json_schema": { "type":"object" }
      },
      "additionalProperties": false
    },

    /* template overrides */
    "chat_template_kwargs": { "type":"object" },

    /* tool‑call behaviour */
    "parallel_tool_calls": { "type":"boolean" },
    "add_generation_prompt": { "type":"boolean" },

    /* reasoning / thinking flags */
    "enable_thinking": { "type":"boolean" },
    "reasoning_format": { "type":"string" },

    /* legacy fields */
    "json_schema": { "type":"object" },
    "grammar": { "type":"string" }
  },

  "additionalProperties": false,

  "errorMessage": {
    "required": {
      "model": "The 'model' field is required.",
      "messages": "The 'messages' field is required."
    },
    "properties": {
      "model": "The 'model' field must be a string.",
      "messages": "The 'messages' field must be an array of message objects."
    }
  }
}
```

### Notes

*   The schema is intentionally _strict_ – it follows the exact checks performed in `oaicompat_chat_params_parse()`.
*   **Mutual exclusions** – the server rejects a request that contains both `response_format` (with `type` other than `"text"`) and a non‑empty `grammar` field. That logic is not expressed in the schema but is part of the validation.
*   The schema accepts all fields that are forwarded to the internal llama‑cpp inference engine (`max_tokens`, `temperature`, `top_p`, `top_k`, `n`, `stop`, `presence_penalty`, `frequency_penalty`, `logit_bias`, `logprobs`, `top_logprobs`, `seed`, etc.).
*   The `messages` array allows the OpenAI‑style content blocks (`text`, `image_url`, `input_audio`) used by the multimodal extensions.
*   The `tools`, `tool_choice`, and `response_format` objects mirror the OpenAI API, so the request can be used for function‑calling, tool‑calling, or JSON‑schema responses.

Save this JSON schema wherever you need to validate or document the request format (e.g., in a Swagger/OpenAPI spec or a JSON‑schema validator).
