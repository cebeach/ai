# OpenCode Repo Structure

Extracted from opencode repository 3/20/2026 using OpenCode and gpt-oss-20b

## How is the OpenCode Repo

This file sets up Cloudflare resources using SST. The repo structure: packages/ contain web, util, ui, storybook, slack, plugin, script, etc. There's also infra. There's also README files.

User wants understanding structure. We can explain high level: root contains infrastructure config (sst, bunfig, etc), packages for various modules: web app, util functions, UI components, storybook, slack integration, plugin, script, docs, containers, etc. There's also .github workflows. Provide explanation. Also mention infra folder defines Cloudflare resources using SST. Provide overview of packages. We can summarize.

We should not edit anything. Just output explanation.

**High‑level view of the Opencode repository**

```
/home/chad/build/opencode/
├── infra/                # Cloudflare/SST infrastructure
│   ├── app.ts            # main Cloudflare Worker + Astro + StaticSite
│   ├── stage.ts          # stage/region helpers
│   ├── console.ts
│   ├── secret.ts
│   └── enterprise.ts
├── packages/             # Monorepo of individual packages
│   ├── web/              # Astro website (docs) – `packages/web`
│   ├── util/             # tiny utility library – `packages/util`
│   ├── ui/               # UI component library – `packages/ui`
│   ├── storybook/        # Storybook dev‑environment – `packages/storybook`
│   ├── slack/            # Slack integration helpers – `packages/slack`
│   ├── plugin/           # SST “plugin” package – `packages/plugin`
│   ├── script/           # Helper scripts – `packages/script`
│   ├── extensions/       # VS Code / Zed extensions – `packages/extensions`
│   ├── identity/         # Static assets (icons, etc.) – `packages/identity`
│   ├── docs/             # Documentation sources – `packages/docs`
│   └── containers/        # Docker/Tauri images – `packages/containers`
├── .github/              # GitHub Actions, issue templates, CODEOWNERS
├── sst-env.d.ts          # Shared type definitions for SST
├── bunfig.toml            # Bun package manager config
├── package.json           # Root package.json (scripts, dev dependencies, etc.)
├── tsconfig.json          # TypeScript compiler config (root)
├── README*.md             # Multilingual README files
└── AGENTS.md              # Internal instructions for the assistant agents
```

### `infra/`

*   `app.ts` – the **entry point** for Cloudflare deployment.
    *   Declares secrets (`sst.Secret`) for GitHub, Discord, Feishu, etc.
    *   Creates a Cloudflare **Worker** (`api`) that hosts the API under `api.<domain>`.
    *   Sets up an **Astro** site (`Web`) for the docs under `docs.<domain>`.
    *   Defines a **StaticSite** (`WebApp`) for the main front‑end under `app.<domain>`.
    *   Uses SST’s `$app.stage` helper to adjust migration tags per environment.
*   `stage.ts` – helper utilities for stage/region handling.

### `packages/`

The repo is organised as a **monorepo** with multiple focused packages:

| Package | Purpose | Key files |
| --- | --- | --- |
| `web` | Astro‑based documentation site | `astro.config.mjs` |
| `util` | Small, pure TypeScript helpers (`retry`, `slug`, `encode`, …) | `src/*.ts` |
| `ui` | UI component library (mostly React components) | `vite.config.ts` |
| `storybook` | Development playground for UI components | `.storybook/*` |
| `slack` | Slack bot integration (handler, events) | `src/index.ts` |
| `plugin` | SST plugin (provides custom CLI commands) | `src/*` |
| `script` | Utility scripts (build, release, etc.) | `src/index.ts` |
| `extensions` | Editor extensions (VS Code, Zed) | `extension.toml`, `src/extension.ts` |
| `identity` | Static assets (icons) | PNG/SVG files |
| `docs` | Markdown documentation used by the Astro site | `src/*.mdx` |
| `containers` | Docker/Tauri container definitions | Dockerfiles, `script/build.ts` |

### Build & Deployment

*   **Bun** is used as the runtime (`bunfig.toml`, `package.json` scripts).
*   SST is the cloud‑infrastructure framework (`sst` imports in `infra/app.ts`).
*   GitHub Actions drive CI/CD (`.github/workflows/*`).
*   The `scripts` folder contains helper scripts (e.g., `packages/script/src/index.ts`).

### Key Config Files

*   `sst-env.d.ts` – shared type definitions used by SST resources.
*   `tsconfig.json` – root TS config, extended by each package’s `tsconfig.json`.
*   `.github` contains workflows, issue templates, and CODEOWNERS for repository management.
*   `AGENTS.md` holds internal instructions for the assistant’s behaviour.

---

**In short:**  
The repo is a monorepo that combines a Cloudflare‑based backend (`infra/`), a static/React front‑end (`packages/web`, `packages/ui`), a set of utility libraries (`packages/util`, `packages/slack`, `packages/plugin`), documentation (`packages/docs`), and various build/deployment tools. All infrastructure is declared in SST (TypeScript) and deployed via Cloudflare workers/sites, while the code lives in the `packages/` tree. The CI/CD pipeline is managed through GitHub Actions.
