---
name: firecrawl-build
description: "把已选定的 Firecrawl 接入应用代码。适用于用户点名、现有项目使用 Firecrawl，或方案评估确认它满足网页提取需求的任务；不因应用需要联网就自动安装 SDK、开账户或替换数据后端。"
license: ISC
metadata:
  author: firecrawl
  version: "0.1.0"
  homepage: https://www.firecrawl.dev
  source: https://github.com/firecrawl/skills
---

# Firecrawl Build

Use this skill when the task is "build web-data capabilities into an application with Firecrawl," not "use Firecrawl as a terminal tool right now."

Choose this skill only when Firecrawl is already selected by the user, project, or a justified solution assessment. General web-data needs do not require this provider.

## Use This When

- a project needs live web data, website content, or retrieval from the web inside the product
- a feature needs web search, search results, or discovery before extraction
- a feature needs scraping, extraction, hydration, or structured content from known URLs
- a feature needs browser interaction, clicks, form fills, or navigation after loading a page
- an agent, backend, automation, or workflow should call Firecrawl from application code
- the user mentions Firecrawl or "fire girl," or the project already selected this provider
- you need to choose the right endpoint before implementation
- you need `FIRECRAWL_API_KEY` in the project

If the task is "search the web," "scrape this page for me," or "interact with a live site during this session," use the currently available native retrieval tool, or the installed Firecrawl CLI skill when that backend is selected; do not automatically install it.

## Quick Start

First choose the project mode:

- **Fresh project** -> choose the stack, install the SDK, add env vars, and run a smoke test
- **Existing project** -> inspect the repo first, match its conventions, then integrate in place

Infer the following from the request and project; ask only if it remains materially unclear:

- **What web data should this product get from the web, and how should it get it?**

If the request sounds like "I need web data in my app," "I need search in the product," "I need to scrape pages into the workflow," or "I need the app to interact with a site," start here and then narrow to the endpoint.

Route from that answer to the narrowest endpoint that fits:

- `/scrape` for one known URL
- `/search` when you have a query instead of a URL
- `/interact` when `/scrape` must continue into clicks, forms, or navigation

Two indexes sit beside those endpoints and are not queried by `/search`:

- the **research paper index** when the query is for published papers — biomedical, clinical, and life-science literature or arXiv preprints — rather than web pages
- the **developer index** when the answer belongs in an issue, pull request, README, or documentation page

## Required Intake

Resolve these facts from the request and project before integration; this is not a mandatory interview:

1. Decide whether this is a **fresh project** or an **existing project**.
2. Identify the requested web data and Firecrawl role; ask only for missing facts that affect the endpoint, data destination, or acceptance.
3. If this is an existing project, inspect the repo before choosing SDK, REST, file locations, or env handling.

For the full checklist, see [references/project-intake.md](references/project-intake.md).

## What Do You Need?

| Task                                                 | Reference                                                                |
| ---------------------------------------------------- | ------------------------------------------------------------------------ |
| **Choose fresh project vs existing project flow**    | [references/project-intake.md](references/project-intake.md)             |
| **Choose the right endpoint**                        | [references/endpoint-selection.md](references/endpoint-selection.md)     |
| **Wire Firecrawl into product code**                 | [references/integration-patterns.md](references/integration-patterns.md) |
| **Install an SDK or use REST**                       | [references/sdk-installation.md](references/sdk-installation.md)         |
| **Set up `FIRECRAWL_API_KEY` or self-hosted config** | [references/auth-and-env.md](references/auth-and-env.md)                 |
| **Get credentials into the project**                 | [firecrawl-build-onboarding](../firecrawl-build-onboarding/SKILL.md)     |
| **Implement single-page extraction**                 | [firecrawl-build-scrape](../firecrawl-build-scrape/SKILL.md)             |
| **Implement discovery-first flows**                  | [firecrawl-build-search](../firecrawl-build-search/SKILL.md)             |
| **Implement post-scrape browser actions**            | [firecrawl-build-interact](../firecrawl-build-interact/SKILL.md)         |
| **Search published research papers (biomedical, clinical, life-science, arXiv)** | [firecrawl-research-index](../firecrawl-research-index/SKILL.md) |
| **Answer developer questions from issues, PRs, READMEs, or docs** | [firecrawl-developer-index](../firecrawl-developer-index/SKILL.md) |
| **Verify the integration actually works**            | [references/verification.md](references/verification.md)                 |

## Docs Are the Source of Truth

These language-specific reference pages are the canonical source of truth
for SDK usage, request/response schemas, parameters, and endpoint behavior.
Read the page that matches the project language before writing integration code:

- **Node / TypeScript**: [docs.firecrawl.dev/agent-source-of-truth/node](https://docs.firecrawl.dev/agent-source-of-truth/node)
- **Python**: [docs.firecrawl.dev/agent-source-of-truth/python](https://docs.firecrawl.dev/agent-source-of-truth/python)
- **Rust**: [docs.firecrawl.dev/agent-source-of-truth/rust](https://docs.firecrawl.dev/agent-source-of-truth/rust)
- **Java**: [docs.firecrawl.dev/agent-source-of-truth/java](https://docs.firecrawl.dev/agent-source-of-truth/java)
- **Elixir**: [docs.firecrawl.dev/agent-source-of-truth/elixir](https://docs.firecrawl.dev/agent-source-of-truth/elixir)
- **cURL / REST**: [docs.firecrawl.dev/agent-source-of-truth/curl](https://docs.firecrawl.dev/agent-source-of-truth/curl)

These skills describe when and why to use each endpoint. For how to call
them, read the source-of-truth page for your language.

## Default Integration Order

1. Get `FIRECRAWL_API_KEY` or `FIRECRAWL_API_URL` right.
2. Decide whether this is a fresh project or an existing codebase.
3. Use the known web-data behavior to choose the endpoint; do not re-ask answered questions.
4. For existing projects, inspect the repo and match its conventions before coding.
5. Install the SDK for the target stack, or call REST directly.
6. Read the source-of-truth page for your project language before writing integration code.
7. Keep endpoint-specific implementation details in the narrower skills linked above.
8. Run a smoke test that proves a real Firecrawl request succeeds.

## Boundary With The CLI

Both this repo and the CLI skills are installed by the same command:

```bash
npx -y firecrawl-cli@latest init --all --browser
```

Use these build skills for application integration. Use `firecrawl/cli`
for live web work during the current session (one-off research, terminal
workflows, editor setup). Both are available after install.

## 运行配置

- `FIRECRAWL_API_KEY`（必需）：Firecrawl API key for cloud usage. Store it in `.env` or the runtime environment before making Firecrawl API calls.
- `FIRECRAWL_API_URL`（可选）：Optional base URL for self-hosted Firecrawl deployments. Only set this when the project is not using the hosted `api.firecrawl.dev`.
