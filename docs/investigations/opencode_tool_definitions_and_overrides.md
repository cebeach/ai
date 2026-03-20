# OpenCode Tool Definitions & Overrides

Extracted from opencode repository 3/20/2026 using OpenCode and gpt-oss-20b

## User: Find the code which implements agentic tools

*   The heart of the _agentic_ logic is in `packages/opencode/src/provider/provider.ts`.
    *   It loads a static model list, merges config/secrets, and builds a cache of SDK instances.
    *   Custom loaders per provider decide how to initialise the SDK and whether the provider should be enabled.
    *   The GitLab provider loader turns on the `duo_agent_platform_agentic_chat` flag, which is what makes the LLM capable of calling other agents.

## Where the “agentic” runtime pulls its tool list from

The agentic logic lives in `**packages/opencode/src/tool/registry.ts**`.  
It builds a _single shared state_ (`Instance.state`) that is lazily created the first time any tool is requested.

| **Step** | **What happens** | **Key files / code** |
| --- | --- | --- |
| **1\. Scan the file system** | The registry walks all directories that belong to the current project (`Config.directories()`). In each directory it looks for a `tool` **or** a `tools` folder and loads every `*.ts` / `*.js` file inside it. | `Glob.scanSync("{tool,tools}/*.{js,ts}", …)` |
| **2\. Load each file** | Each file is imported as a module. The module is expected to export a **tool definition** object (`ToolDefinition`). The registry creates a `Tool.Info` object for every exported tool. | `import(process.platform === "win32" ? match : pathToFileURL(match).href)` |
| **3\. Merge with plugins** | Every enabled plugin can also provide tools (`plugin.tool`). Those are pulled in the same way – the registry iterates `Plugin.list()` and pulls `tool` entries from each plugin. | `for (const plugin of plugins) … fromPlugin(id, def)` |
| **4\. Store custom tools** | All discovered tools are stored in the `custom` array that is part of the state. | `const custom = [] as Tool.Info[]` |
| **5\. Build the full tool list** | When the runtime needs a list of tools for a particular model/agent it calls `ToolRegistry.tools(...)`. That function:  <br>1\. Calls `all()` – it builds the final array consisting of:  <br> \* **built‑in tools** (`BashTool`, `ReadTool`, `GrepTool`, …)  <br> \* Any **custom tools** that were loaded in the state.  <br>2\. Filters the list based on the model, agent, and feature‑flags (`codesearch`, `websearch`, `apply_patch`, etc.).  <br>3\. For every remaining tool it calls `init()` (passing an optional `agent` context) to get the tool’s runtime representation (parameters, description, execute function). | `function all()` / `function tools(...)` |

## How a single tool is turned into an executable definition

```
function fromPlugin(id: string, def: ToolDefinition): Tool.Info {
  return {
    id,
    init: async (initCtx) => ({
      parameters: z.object(def.args),
      description: def.description,
      execute: async (args, ctx) => {
        const pluginCtx = {
          ...ctx,
          directory: Instance.directory,
          worktree: Instance.worktree,
        } as unknown as PluginToolContext
        const result = await def.execute(args as any, pluginCtx)
        const out = await Truncate.output(result, {}, initCtx?.agent)
        return {
          title: "",
          output: out.truncated ? out.content : result,
          metadata: { truncated: out.truncated, outputPath: out.truncated ? out.outputPath : undefined },
        }
      },
    }),
  }
}
```

*   The tool module supplies `args` (the shape of the JSON‑schema parameters) and a `description`.
*   The registry builds a `zod` schema from `args`, and the `execute` wrapper forwards the call to the plugin’s `execute` function.
*   The result is post‑processed by `Truncate` so that long outputs are written to a file and the tool call only returns a short summary.

**Registration & caching**

*   The registry’s `register(tool)` function lets code add new tools at runtime (e.g. a plugin may register a tool after the registry has already been initialised).
*   Once a tool’s `init` has been called, it is cached inside the registry so repeated calls for the same tool are cheap.

**TL;DR**

1.  **Scan** the project and global config for `tool`/`tools` folders.
2.  **Import** each file and read its exported `ToolDefinition`.
3.  **Add** those as _custom tools_ in the registry state.
4.  **Merge** with built‑in tools and plugin‑provided tools.
5.  **Filter** by model/agent flags when the runtime requests a list of tools.
6.  **Instantiate** each tool via its `init` method (producing parameters, description, and an `execute` callback).

That is the path from a developer’s `src/.opencode/tool/foo.ts` file (or a plugin) to the tool being available for an agentic LLM call.

  
 

## How is the read tool implemented?

We need to explain how the read tool works. Let's summarize key points.

`**ReadTool**` **– the “read file / directory” agentic tool**

The tool is defined with the generic `Tool.define` helper.  
It accepts a JSON schema (`filePath`, optional `offset` and `limit`) and returns an object with

*   `title` – a short name for the result
*   `output` – an XML‑style string that the LLM can read
*   `metadata` – a preview, truncation flag, and any files that were “loaded”

Below is a high‑level walk‑through of the implementation.

---

### 1\. Parameters & safety

```
parameters: z.object({
  filePath: z.string().describe("The absolute path to the file or directory to read"),
  offset: z.coerce.number().describe("The line number to start reading from (1-indexed)").optional(),
  limit: z.coerce.number().describe("The maximum number of lines to read (defaults to 2000)").optional(),
})
```

*   `offset < 1` → error.
*   `filePath` is coerced to an absolute path – if it’s relative it’s resolved against `Instance.directory`.
*   `title` is the relative path from the project worktree (`Instance.worktree`).

---

### 2\. Permission & directory checks

1.  **Stat the file** – `Filesystem.stat(filepath)` gives us a `Stat` object.
2.  **External‑directory guard** – `assertExternalDirectory` ensures the path is inside the project (unless the caller passed `bypassCwdCheck`).
3.  **Ask the user** – `ctx.ask({ permission: "read", patterns: [filepath], always: ["*"] })` triggers the permission prompt.

---

### 3\. File not found – friendly suggestions

If the file doesn’t exist, the tool:

*   Reads the parent directory.
*   Looks for entries whose names contain the missing file’s basename (case‑insensitive).
*   If up to three matches are found, throws an error with the suggestions.

---

### 4\. Directory handling

If the target is a directory:

1.  List the directory entries (`readdir` with `withFileTypes`).
2.  Convert each entry to a string:
    *   sub‑directory → `name/`
    *   symlink to a directory → `name/`
    *   file → `name`
3.  Sort alphabetically.
4.  Apply `offset` & `limit` to the slice of entries.
5.  Return an XML‑style output:

```xml
<path>/abs/dir</path>
<type>directory</type>
<entries>
  entry1
  entry2
  …
  (Showing 3 of 10 entries)
</entries>
```

`metadata.preview` contains the first 20 entries, and `metadata.truncated` is `true` if the slice was cut off.

---

### 5\. Image / PDF handling

If the file is an image (excluding SVG) or PDF, the tool simply returns a short message and attaches the file as a data URL:

```
{
  title,
  output: "Image read successfully",
  metadata: { preview: "Image read successfully", truncated: false, loaded: [filepath] },
  attachments: [
    { type: "file", mime, url: `data:${mime};base64,${base64bytes}` }
  ]
}
```

---

### 6\. Binary file detection

`isBinaryFile(filepath, size)` checks:

*   Common binary extensions (`.zip`, `.exe`, `.class`, etc.) → binary.
*   If the file is empty → not binary.
*   Reads the first 4096 bytes and counts non‑printable characters; >30 % → binary.

If the file is binary the tool throws `Cannot read binary file`.

---

### 7\. Text file reading

**Streamed, line‑by‑line** – this keeps memory usage low.

```
const stream = createReadStream(filepath, { encoding: "utf8" })
const rl = createInterface({ input: stream, crlfDelay: Infinity })
```

*   `offset` / `limit` are applied after the stream starts.
*   A maximum of `DEFAULT_READ_LIMIT` (2000) lines is kept.
*   Lines longer than `MAX_LINE_LENGTH` (2000) are truncated with a suffix.
*   The cumulative byte size is limited to `MAX_BYTES` (50 KB).
*   If the byte limit is hit, the loop stops and `hasMoreLines` is set true.

After the loop:

*   Each kept line is prefixed with its absolute line number (`offset`‑based).
*   `preview` is the first 20 lines.
*   `metadata.truncated` is true if we ran out of lines or bytes.
*   `output` contains the XML wrapper:

```xml
<path>/abs/file.txt</path>
<type>file</type>
<content>
  1: first line
  2: second line
  ...
</content>
```

If truncated, a footer notes the line range and suggests an `offset` to continue.

---

### 8\. LSP & instruction prompt hooks

*   `LSP.touchFile(filepath, false)` warms the language‑server cache.
*   `FileTime.read(ctx.sessionID, filepath)` records the last‑read timestamp.
*   `InstructionPrompt.resolve(ctx.messages, filepath, ctx.messageID)` returns any “system reminder” instructions that are relevant to the file (e.g. code‑review notes).  
    If present, those instructions are appended inside a `<system-reminder>` block in the output.

---

### 9\. Returned object

```
{
  title: relativePath,
  output: "<xml‑string>",
  metadata: {
    preview: string,          // first ~20 lines or entries
    truncated: boolean,       // true if truncated
    loaded: string[]          // any files that were attached (images/PDFs)
  },
  // optionally `attachments` for image/PDF
}
```

### Bottom line

The ReadTool is a self‑contained, streaming, permission‑aware file reader.  
It:

1.  Validates and normalises the path.
2.  Enforces project boundaries & read permissions.
3.  Handles directories, text, images, PDFs, and binary files differently.
4.  Streams the file, applying line/byte limits, and produces an XML‑style output that the LLM can parse.
5.  Optionally returns an attachment for binary media or a system‑reminder section for LLM context.

## Can custom tools be written to override built-in tools?

**Yes – you can override a built‑in tool with a custom one.**  
The mechanism is the same that you use to add any new tool, but the _name_ you give the custom tool is what determines whether it replaces an existing one.

---

### 1\. Where the tool list lives

| **Component** | **What it does** |
| --- | --- |
| `ToolRegistry.state` | On first use, it scans the project for `/.opencode/tools/**` and `~/.config/opencode/tools/**`. For every file it imports the module, pulls out every exported tool definition, and pushes a `**Tool.Info**` object onto the `custom` array. |
| `ToolRegistry.all()` | Builds the final array of tools that the agent can use. It does a simple concatenation: **\[built‑in tools\] + \[custom tools\]**. |
| `ToolRegistry.tools()` | When the LLM asks “list the available tools” this method calls `all()`, filters by permissions, then calls `init()` on each entry to get the runtime representation. |

The _actual_ lookup that the LLM uses is performed by the `ToolRegistry` itself – it keeps an internal map keyed by tool id. When a tool is added with an id that already exists in the map, the new one _replaces_ the old entry. That is how overrides work.

---

### 2\. How a custom tool is defined

```
// .opencode/tools/bash.ts
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Restricted bash wrapper",
  args: { command: tool.schema.string() },
  async execute(args) {
    // Your custom logic here
    return `blocked: ${args.command}`
  },
})
```

*   **File name → tool name** – the file `bash.ts` creates a tool named `**bash**`.
*   `**tool()**` – the helper from `@opencode-ai/plugin` returns a `Tool.Info` object that contains the id, a zod schema for the arguments and an `execute` function.
*   **Registration** – the file is automatically loaded by `ToolRegistry.state`, so no extra code is needed to register it.

If the same id already exists (for example the built‑in `bash`), the _new_ definition overwrites it in the internal map, so the LLM will now call your custom `bash` instead of the default one.

---

### 3\. When you want to _disable_ but _not replace_ a built‑in tool

*   Give your custom tool a **different name** – e.g. `my_bash` – and simply leave the original `bash` untouched.
*   Or, if you only need to block the built‑in tool for a particular agent, use the **permissions** system (see `/docs/permissions`).
    *   Add `"bash": false` in the agent’s permission list and the LLM will never offer the `bash` tool to that agent, but the built‑in tool remains available to other agents.

---

### 4\. Quick checklist

| **✔** | **What to do** |
| --- | --- |
| 1 | Create a `.opencode/tools/<name>.ts` (or `.js`) file. |
| 2 | Export a tool using `export default tool({ … })` or named exports (`export const foo = tool({ … })`). |
| 3 | Use the same `<name>` as a built‑in tool to override it (or a different name to keep the original). |
| 4 | The tool will automatically appear in the agent’s tool list; the LLM will use the last definition it sees. |
| 5 | If you only want to disable a built‑in tool, add a permission entry (`"bash": false`) instead of overriding it. |

---

### TL;DR

_Custom tools are automatically loaded into the same registry that holds the built‑ins. Because the registry is keyed by tool id, a custom tool that shares an id with a built‑in **replaces** the built‑in. Use a different name if you want to keep the original, or use permissions if you simply want to disable it for a particular agent._

## What are all of the built-in tool names?

### Built‑in tool names (the ones that the agent can call out‑of‑the‑box)

| **Tool ID** | **File that defines it** | **What it does (short)** |
| --- | --- | --- |
| `invalid` | `./tool/invalid.ts` | A “catch‑all” tool that the system uses when a call has malformed arguments. |
| `question` | `./tool/question.ts` | Ask a list of questions to the user and return the answers. |
| `bash` | `./tool/bash.ts` | Execute a shell command (with permission checks, timeout, etc.). |
| `read` | `./tool/read.ts` | Read a file or directory (text, image, PDF, etc.) and return a preview or attachment. |
| `glob` | `./tool/glob.ts` | Find files that match a glob pattern. |
| `grep` | `./tool/grep.ts` | Search file contents with a regular expression. |
| `edit` | `./tool/edit.ts` | Edit a file (appends, replaces, deletes lines). |
| `write` | `./tool/write.ts` | Write data to a file. |
| `task` | `./tool/task.ts` | Create or update a todo‑style task list. |
| `webfetch` | `./tool/webfetch.ts` | Perform an HTTP request (GET/POST). |
| `todowrite` | `./tool/todo.ts` | **(todo‑write)** Write a new todo list into the project. |
| `todoread` | `./tool/todo.ts` | **(todo‑read)** Read the current todo list. |
| `websearch` | `./tool/websearch.ts` | Query the EXA MCP web‑search service. |
| `codesearch` | `./tool/codesearch.ts` | Query the EXA MCP code‑context service. |
| `skill` | `./tool/skill.ts` | Load a domain‑specific skill (a set of instructions & assets). |
| `apply_patch` | `./tool/apply_patch.ts` | Apply a patch (diff) to a file. |
| `lsp` | `./tool/lsp.ts` | (Experimental) Forward a request to the language‑server. |
| `batch` | `./tool/batch.ts` | (Experimental) Batch multiple calls into one. |
| `plan_exit` | `./tool/plan.ts` | (Experimental) Switch the agent to the build mode after a plan is approved. |

> **Note** – The last four (`lsp`, `batch`, `plan_exit`, and the commented‑out `todoread`) are only exposed when the corresponding experimental flag is enabled or the `todoread` tool is explicitly added in `all()`.  
> The default list of built‑in tools is built by `ToolRegistry.all()` which concatenates the above names in the order shown.

---

### How a custom tool can **override** a built‑in one

_The agent uses a single registry that is keyed by the tool ID._  
When a custom tool is loaded (via `.opencode/tools/…` or a plugin), its ID is registered with the same key. If that key already exists (e.g. a built‑in tool with the same name), the new definition **replaces** the old one.  
So to replace the built‑in `bash` tool, you would create a file:

```
// .opencode/tools/bash.ts
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Restricted bash wrapper",
  args: { command: tool.schema.string() },
  async execute(args) {
    return `blocked: ${args.command}`
  },
})
```

The LLM will then call your `bash` implementation instead of the default one.  
If you only want to _disable_ a built‑in tool but keep its original implementation available, use the permissions system (`"bash": false`) rather than overriding it.

## How do I control the tool definition injected into the system prompt for a custom tool?

### The “tool definition” that ends up in the system prompt

When an agent is started the system prompt is assembled by calling

```
ToolRegistry.all()   // → array of Tool.Info objects
```

For every tool the registry does the following

1.  **Builds a** `**Tool.Info**` – the object returned by `Tool.define( id, { … } )`.
2.  **Runs the** `**tool.definition**` **plugin hook**
    
    ```
    await Plugin.trigger("tool.definition", { toolID: t.id }, output)
    ```
    
    – this gives plugins a chance to tweak the _description_ and _parameters_ that will be sent to the LLM.
3.  **Injects the resulting description + Zod‑schema into the system prompt** (as the “tool definitions” section that the LLM sees).

So the content that the agent receives is **exactly** what you put in the `description` field of your tool and the Zod schema you expose via `args`/`parameters`. The plugin hook is the only place where you can change that after the tool has been loaded.

## How to control a custom tool’s definition

| **What you want to change** | **Where to do it** |
| --- | --- |
| **Short‑description** (what appears in the system prompt) | In the `description` property of the `Tool.define` call. |
| **Argument schema** (JSON schema that the LLM must obey) | In the `args` or `parameters` field of the `Tool.define` call. |
| **Post‑processing of the definition** (e.g. add extra context, rename fields, change the schema) | Write a plugin that hooks into `tool.definition`. |
| **Override a built‑in tool** (use the same name) | Give the custom tool the same `id`. The registry will replace the built‑in definition because the plugin hook runs on every tool after it’s created. |
| **Add a custom field to the definition** (not used by the agent but useful for debugging) | Add it to the `output` object in the `tool.definition` hook. |

### Example 1 – Changing the description and schema in the tool file

```
// .opencode/tools/read.ts
import { Tool } from "./tool"
import z from "zod"

export const ReadTool = Tool.define("read", {
  description: "Read a file or directory. Provide an absolute path, and optionally an offset & limit.",
  parameters: z.object({
    filePath: z.string().describe("Absolute path to the file or directory"),
    offset: z.coerce.number().optional().describe("1‑based line number to start from"),
    limit: z.coerce.number().optional().describe("Maximum number of lines to return"),
  }),
  async execute(params, ctx) {
    /* … implementation … */
  },
})
```

The above text and JSON schema are what the LLM sees in the system prompt.

### Example 2 – Tweaking the definition via a plugin

```
// plugins/shorten-read.ts
import { Plugin } from "@opencode-ai/plugin"
import z from "zod"

Plugin.register({
  // runs after every tool has been created
  "tool.definition": async ({ toolID }, output) => {
    if (toolID === "read") {
      // Shorten the description
      output.description = "Read a file or directory, optionally slicing lines."

      // Simplify the schema (e.g. make offset/limit optional and give defaults)
      output.parameters = z.object({
        filePath: z.string().describe("Absolute path to the file or directory"),
        offset: z.coerce.number().default(1).describe("1‑based line number"),
        limit: z.coerce.number().default(2000).describe("Maximum number of lines"),
      })
    }
  },
})
```

Now the system prompt will show the updated description and schema for the `read` tool.

### Recap

*   **Built‑in tool definitions** come from the `Tool.define` calls in `src/tool/*.ts`.
*   **Custom tools** follow the same pattern.
*   The **system prompt** uses the `description` and `parameters` from that definition.
*   To _control_ what appears in the prompt you either
    *   write those fields directly in your tool file, or
    *   hook into the `tool.definition` plugin to modify the output after the tool has been loaded.

That gives you full control over the exact definition that the LLM receives for any custom tool.

## What is the body of the execute(params, ctx) for the ReadTool?

Below is the **complete implementation** of the `execute` method for the `ReadTool`.  
It performs all the safety checks, permission prompts, directory handling, binary detection, streaming read, and returns the formatted XML‑style response that the LLM will consume.

```
async execute(params, ctx) {
  if (params.offset !== undefined && params.offset < 1) {
    throw new Error("offset must be greater than or equal to 1")
  }

  let filepath = params.filePath
  if (!path.isAbsolute(filepath)) {
    filepath = path.resolve(Instance.directory, filepath)
  }
  const title = path.relative(Instance.worktree, filepath)

  const stat = Filesystem.stat(filepath)

  await assertExternalDirectory(ctx, filepath, {
    bypass: Boolean(ctx.extra?.["bypassCwdCheck"]),
    kind: stat?.isDirectory() ? "directory" : "file",
  })

  await ctx.ask({
    permission: "read",
    patterns: [filepath],
    always: ["*"],
    metadata: {},
  })

  if (!stat) {
    const dir = path.dirname(filepath)
    const base = path.basename(filepath)

    const suggestions = await fs
      .readdir(dir)
      .then((entries) =>
        entries
          .filter(
            (entry) =>
              entry.toLowerCase().includes(base.toLowerCase()) ||
              base.toLowerCase().includes(entry.toLowerCase())
          )
          .map((entry) => path.join(dir, entry))
          .slice(0, 3)
      )
      .catch(() => [])

    if (suggestions.length > 0) {
      throw new Error(
        `File not found: ${filepath}\n\nDid you mean one of these?\n${suggestions.join("\n")}`
      )
    }

    throw new Error(`File not found: ${filepath}`)
  }

  if (stat.isDirectory()) {
    const dirents = await fs.readdir(filepath, { withFileTypes: true })
    const entries = await Promise.all(
      dirents.map(async (dirent) => {
        if (dirent.isDirectory()) return dirent.name + "/"
        if (dirent.isSymbolicLink()) {
          const target = await fs
            .stat(path.join(filepath, dirent.name))
            .catch(() => undefined)
          if (target?.isDirectory()) return dirent.name + "/"
        }
        return dirent.name
      })
    )
    entries.sort((a, b) => a.localeCompare(b))

    const limit = params.limit ?? DEFAULT_READ_LIMIT
    const offset = params.offset ?? 1
    const start = offset - 1
    const sliced = entries.slice(start, start + limit)
    const truncated = start + sliced.length < entries.length

    const output = [
      `<path>${filepath}</path>`,
      `<type>directory</type>`,
      `<entries>`,
      sliced.join("\n"),
      truncated
        ? `\n(Showing ${sliced.length} of ${entries.length} entries. Use 'offset' parameter to read beyond entry ${offset + sliced.length})`
        : `\n(${entries.length} entries)`,
      `</entries>`,
    ].join("\n")

    return {
      title,
      output,
      metadata: {
        preview: sliced.slice(0, 20).join("\n"),
        truncated,
        loaded: [] as string[],
      },
    }
  }

  const instructions = await InstructionPrompt.resolve(
    ctx.messages,
    filepath,
    ctx.messageID
  )

  // Exclude SVG (XML-based) and vnd.fastbidsheet (.fbs extension, commonly FlatBuffers schema files)
  const mime = Filesystem.mimeType(filepath)
  const isImage =
    mime.startsWith("image/") &&
    mime !== "image/svg+xml" &&
    mime !== "image/vnd.fastbidsheet"
  const isPdf = mime === "application/pdf"
  if (isImage || isPdf) {
    const msg = `${isImage ? "Image" : "PDF"} read successfully`
    return {
      title,
      output: msg,
      metadata: {
        preview: msg,
        truncated: false,
        loaded: instructions.map((i) => i.filepath),
      },
      attachments: [
        {
          type: "file",
          mime,
          url: `data:<!--FORMULA_INLINE_1773985660285_0-->{Buffer.from(
            await Filesystem.readBytes(filepath)
          ).toString("base64")}`,
        },
      ],
    }
  }

  const isBinary = await isBinaryFile(filepath, Number(stat.size))
  if (isBinary) throw new Error(`Cannot read binary file: ${filepath}`)

  const stream = createReadStream(filepath, { encoding: "utf8" })
  const rl = createInterface({
    input: stream,
    // Note: we use the crlfDelay option to recognize all instances of CR LF
    // ('\r\n') in file as a single line break.
    crlfDelay: Infinity,
  })

  const limit = params.limit ?? DEFAULT_READ_LIMIT
  const offset = params.offset ?? 1
  const start = offset - 1
  const raw: string[] = []
  let bytes = 0
  let lines = 0
  let truncatedByBytes = false
  let hasMoreLines = false
  try {
    for await (const text of rl) {
      lines += 1
      if (lines <= start) continue

      if (raw.length >= limit) {
        hasMoreLines = true
        continue
      }

      const line =
        text.length > MAX_LINE_LENGTH
          ? text.substring(0, MAX_LINE_LENGTH) + MAX_LINE_SUFFIX
          : text
      const size = Buffer.byteLength(line, "utf-8") + (raw.length > 0 ? 1 : 0)
      if (bytes + size > MAX_BYTES) {
        truncatedByBytes = true
        hasMoreLines = true
        break
      }

      raw.push(line)
      bytes += size
    }
  } finally {
    rl.close()
    stream.destroy()
  }

  if (lines < offset && !(lines === 0 && offset === 1)) {
    throw new Error(`Offset ${offset} is out of range for this file (${lines} lines)`)
  }

  const content = raw.map((line, index) => {
    return `${index + offset}: ${line}`
  })
  const preview = raw.slice(0, 20).join("\n")

  let output = [`<path>${filepath}</path>`, `<type>file</type>`, "<content>"].join("\n")
  output += content.join("\n")

  const totalLines = lines
  const lastReadLine = offset + raw.length - 1
  const nextOffset = lastReadLine + 1
  const truncated = hasMoreLines || truncatedByBytes

  if (truncatedByBytes) {
    output += `\n\n(Output capped at ${MAX_BYTES_LABEL}. Showing lines ${offset}-${lastReadLine}. Use offset=${nextOffset} to continue.)`
  } else if (hasMoreLines) {
    output += `\n\n(Showing lines ${offset}-${lastReadLine} of ${totalLines}. Use offset=${nextOffset} to continue.)`
  } else {
    output += `\n\n(End of file - total ${totalLines} lines)`
  }
  output += "\n</content>"

  // just warms the LSP client
  LSP.touchFile(filepath, false)
  await FileTime.read(ctx.sessionID, filepath)

  if (instructions.length > 0) {
    output += `\n\n<system-reminder>\n${instructions
      .map((i) => i.content)
      .join("\n\n")}\n</system-reminder>`
  }

  return {
    title,
    output,
    metadata: {
      preview,
      truncated,
      loaded: instructions.map((i) => i.filepath),
    },
  }
},
```

This is the full body that the LLM executes when it calls the `read` tool.

## Do I have to implement execute() if I override ReadTool, or can I use the build-in execute() for ReadTool?

**Short answer**

*   If you _replace_ the built‑in **ReadTool** (i.e. you provide a custom file that exports a `Tool.define("read", …)`), you **must** supply your own `execute(params, ctx)` – the built‑in implementation is no longer used.
*   If you only want to tweak the _description_ or the _parameter schema_ but keep the same reading logic, you **don’t** need to touch `execute()` at all – just change the description/schema in the tool file or use a `tool.definition` plugin hook.  
    The original `ReadTool.execute` will still be called.

**Why this matters**

| **Scenario** | **What happens** | **How to keep the built‑in logic** |
| --- | --- | --- |
| **Full override** – you write your own tool with `id === "read"` | The registry discards the original `ReadTool` and uses yours. The built‑in code is not executed. | Implement `execute()` exactly as needed, or delegate to the original implementation if you want. |
| **Partial override** – you only change description or parameters | The registry keeps the original `ReadTool` and merges your new description/schema. `execute()` stays the same. | Do **not** export a new tool with the same id. Instead, modify the existing definition in place (or use the `tool.definition` plugin). |
| **Plugin‑based tweak** | A plugin can run after the tool is created (`tool.definition`) and change the description/schema. The built‑in `execute()` remains untouched. | Add a plugin that listens for `tool.definition` and mutates the `output` object. |

**Practical guidance**

1.  **Want to change the description only**
    
    ```
    // .opencode/tools/read.ts
    import { Tool } from "./tool"
    import z from "zod"
    
    export const ReadTool = Tool.define("read", {
      description: "Read a file or directory, optionally slicing lines. (Custom description)",
      parameters: z.object({ /* same schema as before */ }),
      // no execute() here – the default one will be used
    })
    ```
2.  **Want to add a new parameter or change the schema**  
    Update the `parameters` field. The default `execute` still runs.
3.  **Want to** _**replace**_ **the entire tool**
    
    ```
    // .opencode/tools/read.ts
    import { Tool } from "./tool"
    import z from "zod"
    
    export const ReadTool = Tool.define("read", {
      description: "Your custom description",
      parameters: z.object({ /* your new schema */ }),
      async execute(params, ctx) {
        // your own implementation, or delegate to the original via a helper
      },
    })
    ```
4.  **Want to keep the original logic but tweak the prompt**  
    Write a plugin that hooks into `tool.definition` and mutates `output.description` or `output.parameters`.

**Bottom line**

*   **Replacing the tool** → you must provide a new `execute()`.
*   **Just tweaking the definition** → leave `execute()` untouched; the built‑in logic remains.

## Example: A **plugin** that tweaks the _system prompt_ for the built‑in `read` tool

```
// ~/.config/opencode/plugins/read-prompt.ts
import { Plugin } from "@opencode-ai/plugin"

Plugin.register({
  // The hook is called after a tool has been created but before the
  // tool’s description & schema are sent to the LLM.
  "tool.definition": async ({ toolID }, output) => {
    if (toolID !== "read") return

    // 1.  Rewrite the description that the LLM sees
    output.description =
      "Read a file or directory. Supply an absolute path and optional `offset` and `limit` to slice the output."

    // 2.  Adjust the JSON‑schema (the `parameters` field) – here we
    //     add defaults and tighten the constraints.
    output.parameters = {
      filePath: {
        type: "string",
        description: "Absolute path to the file or directory",
      },
      offset: {
        type: "number",
        minimum: 1,
        default: 1,
        description: "1‑based line number to start reading from",
      },
      limit: {
        type: "number",
        default: 2000,
        description: "Maximum number of lines to read",
      },
    }

    // (Optional) add a custom field that the LLM can ignore but you
    // can use for debugging or logging.
    output.custom = {
      injectedBy: "read-prompt.ts",
    }
  },
})
```

**What happens**

| **Step** | **What the code does** | **Result in the system prompt** |
| --- | --- | --- |
| `Plugin.register` | Registers a hook that runs after every tool is loaded. | – |
| `if (toolID !== "read") return` | Only touch the `read` tool. | – |
| `output.description = …` | Replaces the description that the LLM receives. | The LLM will now see the new description. |
| `output.parameters = { … }` | Overwrites the Zod schema that is serialised to JSON and sent to the LLM. | The LLM’s prompt will contain the new JSON schema (with defaults, `minimum`, etc.). |
| `output.custom = …` | Adds an extra field that the LLM ignores, useful for debugging. | No effect on the prompt, but you can inspect it in logs. |

**Where to put the file**

*   **Project‑wide**: `~/.config/opencode/plugins/read-prompt.ts`  
    (the plugin folder is read automatically during startup).
*   **Project‑local**: add the same file under `packages/opencode/plugins/read-prompt.ts` and let the repo contain the plugin.  
    It will be installed automatically by `opencode run` (or `opencode serve`).

**Result**

*   The built‑in **ReadTool** implementation remains **exactly the same** – you didn’t touch `execute()`.
*   The _system prompt_ that the agent receives now contains your custom description and schema, so the LLM knows exactly what arguments to supply when it calls the tool.

That’s all you need to tweak a built‑in tool’s prompt while keeping its original behaviour unchanged.
