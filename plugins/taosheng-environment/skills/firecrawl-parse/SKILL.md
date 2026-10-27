---
name: firecrawl-parse
description: "用户点名 Firecrawl Parse，或本地文档提取失败且云解析适合时，把文档解析为 Markdown。普通本地读取优先现有本地/格式工具；需辨明文件会上传的目标与处理用途。"
allowed-tools:
  - Bash(firecrawl *)
  - Bash(npx firecrawl-cli *)
---

# firecrawl parse

This route uploads the selected document to Firecrawl and saves parsed Markdown locally. Prefer local extraction when it meets the need. For sensitive medical material, first state the material type, purpose, and destination under the task's data-handling rules; proceed only within authorized scope. Supports **PDF, DOCX, DOC, ODT, RTF, XLSX, XLS, HTML/HTM**.

## Quick start

Always save to `.firecrawl/` with `-o` — parsed docs can be hundreds of KB and blow up context if streamed to stdout. Add `.firecrawl/` to `.gitignore`.

```bash
mkdir -p .firecrawl

# File → markdown
firecrawl parse ./paper.pdf -o .firecrawl/paper.md

# AI summary
firecrawl parse ./paper.pdf -S -o .firecrawl/paper-summary.md

# Ask a question about the doc
firecrawl parse ./paper.pdf -Q "What are the main conclusions?" \
  -o .firecrawl/paper-qa.md
```

Then read the output incrementally with `head`, `grep`, or `rg`.

Run `firecrawl parse --help` for the full option list.

**Done when:** the markdown, summary, or answer is written under `.firecrawl/` and you have inspected it with bounded reads.

## Tips

- Quote paths with spaces: `firecrawl parse "./My Doc.pdf" -o .firecrawl/mydoc.md`.
- Max upload size: **50 MB** per file.
- Credits: ~1 per PDF page; HTML is 1 flat.
- Check `.firecrawl/` before re-parsing the same file.
- To check your credit balance (recommended for batch processing and similar workflows), use `firecrawl credit-usage` (requires authentication).

## See also

- [firecrawl-scrape](../firecrawl-scrape/SKILL.md) — same idea for URLs
- [firecrawl-build-scrape](https://github.com/firecrawl/skills/tree/main/skills/build/firecrawl-build-scrape) — building document extraction into an app instead of running it here
