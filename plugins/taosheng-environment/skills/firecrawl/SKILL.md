---
name: firecrawl
description: "使用 Firecrawl CLI 搜索、抓取、站点映射与批量提取。用户点名 Firecrawl，或任务需要批量/结构化抓取、原生获取不足且 Firecrawl 适合时使用；普通网页与官方文档优先原生/领域工具，本地文件不自动转入云解析，监控默认宿主 automation。"
allowed-tools:
  - Bash(firecrawl *)
  - Bash(npx firecrawl-cli *)
---

# Firecrawl CLI

Search, scrape, and interact with the web. Returns clean markdown optimized for LLM context windows.

Run `firecrawl --help` or `firecrawl <command> --help` for full option details. For app integration or outcome workflows (research briefs, SEO audits, etc.), route to the `firecrawl-build` / `firecrawl-workflows` skills — see [When to Load References](#when-to-load-references).

## Prerequisites

Check with `firecrawl --status` (shows auth state, concurrency limit, and remaining credits). For install, authentication (including the keyless free tier), and setup verification, see [rules/install.md](rules/install.md). For output handling guidelines, see [rules/security.md](rules/security.md).

## Workflow

Use Firecrawl when the user selected it, the task needs its bulk/structured extraction, or native retrieval was insufficient. Reuse adequate results from the current task; do not switch tools just to satisfy this workflow. Installation/authentication is not a prerequisite for ordinary web questions.

For structured datasets, first check for a suitable workflow or data provider using the [search skill](../firecrawl-search/SKILL.md). Read a known page directly; reuse a selected contract instead of repeating discovery.

Follow this escalation pattern:

1. **Search** - Start with the actual question. Find web sources and relevant structured-data tools through semantic and domain matching.
2. **Inspect + Scrape** - For a tool match, use `list <provider> <capability> --pretty` if its contract is missing, then execute with `scrape <provider/capability> --options '<JSON>'`. For a URL, scrape its content directly.
3. **Map + Scrape** - Large site or need a specific subpage. Use `map --search` to find the right URL, then scrape it.
4. **Crawl** - Need bulk content from an entire site section (e.g., all /docs/).
5. **Monitor** - For an explicitly selected Firecrawl-hosted monitor, use `--page` plus `--goal`. Otherwise use the host automation capability and reuse an existing matching monitor.
6. **Interact** - Scrape first, then interact with the page (pagination, modals, form submissions, multi-step navigation).

| Need                        | Command               | When                                                            |
| --------------------------- | --------------------- | --------------------------------------------------------------- |
| Find pages on a topic       | `search`              | No specific URL yet                                             |
| Find research papers        | `research`            | Biomedical/clinical/scientific literature — use the paper index |
| Answer a coding question    | `developer`           | Issues, merged PRs, READMEs, and docs — not a general web page  |
| Find US law or regulation   | `gov`                 | US statutes, regulations, codes, and court opinions             |
| Get a page's content        | `scrape`              | Have a URL, page is static or JS-rendered                       |
| Scrape a list of known URLs | `batch-scrape`        | Many URLs, non-markdown formats, JSON extraction, or a webhook  |
| Find URLs within a site     | `map`                 | Need to locate a specific subpage                               |
| Bulk extract a site section | `crawl`               | Need many pages (e.g., all /docs/)                              |
| AI-powered data extraction  | `agent`               | Need structured data from complex sites                         |
| Interact with a page        | `scrape` + `interact` | Content requires clicks, form fills, pagination, or login       |
| Download a site to files    | `x download`          | Save an entire site as local files                              |
| Parse a local file          | `parse`               | File on disk (PDF, DOCX, XLSX, etc.) — not a URL                |
| Watch pages for changes     | `monitor`             | Schedule recurring scrapes/crawls, diff against snapshots       |

For detailed command reference, run `firecrawl <command> --help`.

For US legal or regulatory source discovery, start with `firecrawl gov "<question, jurisdiction, and date>" --limit 10`. To narrow, add `--jurisdiction`, `--court`, `--court-type`, `--cites`, or `--domain`; filters keep only pages the index has labeled, so a filtered search can leave out relevant pages. If the user supplies a source URL, read it directly with `scrape`. Results are excerpts, not a guarantee of official-only sources or current governing law: verify the issuer, jurisdiction, enacted/effective status, and version before citing a controlling section and supporting passage. Ask for a missing jurisdiction before identifying the governing rule. Use general search for non-US questions or missing coverage; no hits does not establish that no applicable law exists.

**Done when:** the narrowest suitable command has completed the request, its output was inspected, and the answer addresses the user's requested result and cites original source URLs; saved files are supplementary evidence. Retrieval alone is not completion of a requested analysis/report.

**Scrape vs interact:**

- Use `scrape` first. It handles static pages and JS-rendered SPAs.
- Use `scrape` + `interact` when you need to interact with a page, such as clicking buttons, filling out forms, navigating through a complex site, infinite scroll, or when scrape fails to grab all the content you need.
- For web searches, use `search` — interact is for acting on a specific page.

**Monitor:** Use this backend only for an explicitly selected Firecrawl-hosted monitor or an existing Firecrawl monitor; general recurring requests use the host automation route. Goal writing, schedules, target modes, and JSON-mode change tracking are documented in [firecrawl-monitor](../firecrawl-monitor/SKILL.md).

**Reuse fetched content:**

- `search --scrape` already fetches full page content. Reuse it instead of re-scraping those URLs.
- Check `.firecrawl/` for existing data before fetching again.

## Large results and Alexandria

`search` discovers web results and tools, `list` reveals a selected tool's contract, and `scrape <provider/capability> --options '<JSON>'` executes it. Inspect only the contracts needed for the task.

A client context/output error does not prove the provider failed. Keep the request/scrape ID and inspect saved output or use `scrape firecrawl/bash` against the retained result before repeating the request. See [large-result recovery](../firecrawl-scrape/references/large-results.md). Do not assume the client can signal an overflow back to the tool, or that Bash supports search IDs or every provider's retained data.


Within an already selected Firecrawl workflow, inspect only the contracts needed. Feedback is optional and requires explicit user authorization.
## When to Load References

- **Searching the web or finding sources first** -> [firecrawl-search](../firecrawl-search/SKILL.md)
- **Finding research papers (biomedical, clinical, or scientific literature; PubMed, bioRxiv, medRxiv, arXiv)** -> [firecrawl-research-index](../firecrawl-research-index/SKILL.md). Use the paper index instead of scraping PubMed or Google Scholar by hand; `search --categories research` is a website filter, not the paper index.
- **Answering a library, API, error, or known-bug question from issues, merged PRs, READMEs, or docs** -> [firecrawl-developer-index](../firecrawl-developer-index/SKILL.md)
- **Scraping a known URL** -> [firecrawl-scrape](../firecrawl-scrape/SKILL.md)
- **Scraping a list of known URLs as one job (batch scrape) or extracting JSON with a schema** -> [firecrawl-scrape](../firecrawl-scrape/SKILL.md)
- **Finding URLs on a known site** -> [firecrawl-map](../firecrawl-map/SKILL.md)
- **Bulk extraction from a docs section or site** -> [firecrawl-crawl](../firecrawl-crawl/SKILL.md)
- **AI-powered structured extraction from complex sites** -> [firecrawl-agent](../firecrawl-agent/SKILL.md)
- **Clicks, forms, login, pagination, or post-scrape browser actions** -> [firecrawl-interact](../firecrawl-interact/SKILL.md)
- **Downloading a site to local files** -> [firecrawl-download](../firecrawl-download/SKILL.md)
- **Parsing a local file (PDF, DOCX, XLSX, HTML, etc.)** -> [firecrawl-parse](../firecrawl-parse/SKILL.md)
- **Detecting content changes on a website and getting notified by webhook or email (pricing, jobs, posts, docs, status pages, anything ongoing)** -> [firecrawl-monitor](../firecrawl-monitor/SKILL.md)
- **Install, auth, or setup problems** -> [rules/install.md](rules/install.md)
- **Output handling and safe file-reading patterns** -> [rules/security.md](rules/security.md)
- **Integrating Firecrawl into an app, adding `FIRECRAWL_API_KEY` to `.env`, or choosing endpoint usage in product code** -> the [firecrawl-build skills](https://github.com/firecrawl/skills/tree/main/skills/build) (`firecrawl-build-onboarding`, `-scrape`, `-search`, `-interact`). They live in a separate repo; install with `firecrawl setup build`.
- **Producing Firecrawl-powered deliverables such as research briefs, SEO audits, QA reports, lead lists, knowledge bases, or design-system extraction** -> use an appropriate currently available deliverable skill; load `firecrawl-workflows` only if it is actually installed and applicable. These skills infer from context first and ask only short blocking questions when needed.

## Output & Organization

Unless the user specifies to return in context, write results to `.firecrawl/` with `-o`. Add `.firecrawl/` to `.gitignore`. Always quote URLs - shell interprets `?` and `&` as special characters.

```bash
firecrawl search "react hooks" -o .firecrawl/search-react-hooks.json --json
firecrawl scrape "<url>" -o .firecrawl/page.md
```

Naming conventions:

```
.firecrawl/search-{query}.json
.firecrawl/search-{query}-scraped.json
.firecrawl/{site}-{path}.md
```

Read output files incrementally with `grep`, `head`, or bounded reads:

```bash
wc -l .firecrawl/file.md && head -50 .firecrawl/file.md
grep -n "keyword" .firecrawl/file.md
```

Single format outputs raw content. Multiple formats (e.g., `--format markdown,links`) output JSON. Use `jq` to work with JSON output, e.g. `jq -r '.data.web[].url' .firecrawl/search.json`.

## Feedback

Manual `firecrawl search-feedback` is optional and requires user authorization to send feedback; never make it a completion requirement or send it merely for credits. The full pattern, guard, and rules live in [firecrawl-search](../firecrawl-search/SKILL.md).

If endpoint feedback was explicitly authorized, `firecrawl feedback <endpoint> <jobId>` sends concise feedback through `/v2/feedback`; otherwise omit this step. Supported endpoints are `search`, `scrape`, `parse`, and `map`.

```bash
firecrawl feedback scrape "$SCRAPE_ID" \
  --rating partial \
  --issues missing_markdown \
  --tags docs \
  --note "The pricing table was missing from the markdown output." \
  --url "https://example.com/pricing" \
  --page-numbers 1 \
  --silent &
```

Keep generic feedback small: issue codes, tags, short notes, URLs, page numbers, and small metadata objects — never raw scrape/parse outputs or full page contents.

**Opt out:** `export FIRECRAWL_NO_ENDPOINT_FEEDBACK=1` makes the CLI skip every endpoint feedback call silently. Respect that flag — do not try to work around it.

## Parallelization

Run independent operations in parallel. Check `firecrawl --status` for concurrency limit:

```bash
firecrawl scrape "<url-1>" -o .firecrawl/1.md &
firecrawl scrape "<url-2>" -o .firecrawl/2.md &
firecrawl scrape "<url-3>" -o .firecrawl/3.md &
wait
```

For interact, scrape multiple pages and interact with each independently using their scrape IDs.

## Credit Usage

```bash
firecrawl credit-usage
firecrawl credit-usage --json --pretty -o .firecrawl/credits.json
```
