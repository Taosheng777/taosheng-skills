---
name: markitdown
description: "用本地 MarkItDown 把文档转成 Markdown/text；适用于主要需要文本提取且转换有帮助的读取、摘要或比较。纯文本直接读；Word/PDF/PPTX 的布局审阅、编辑和最终交付以及表格公式分析，由对应格式 Skill 主导，不强制先转换。"
---

# MarkItDown

Use the local `markitdown` CLI when text conversion is the useful first step. Do not convert plain Markdown/text/CSV unnecessarily, or preempt a format-specific editing, layout, or formula workflow. Prefer converting documents to Markdown/text before reasoning over them, then inspect original pages only when layout, figures, tables, formulas, annotations, or OCR quality matter.

## Workflow

1. Confirm the file exists and identify the file type.
2. Create a task-local output directory, usually under `work/`, unless the user specified another location.
3. Convert with `markitdown`:

```bash
markitdown input.pdf -o work/input.md
```

4. Read the generated Markdown with normal text tools such as `sed`, `rg`, or targeted section extraction.
5. If the Markdown is empty, garbled, missing pages, or clearly loses structure, fall back to the best available extractor for that file type, then inspect screenshots or OCR only for the affected pages.
6. For user-facing deliverables, cite or reference the original source file and page/section when possible, not only the generated Markdown.

## Commands

Check availability:

```bash
command -v markitdown
markitdown --version
```

Convert a single file:

```bash
markitdown "/path/to/file.pdf" -o "work/file.md"
```

Convert to stdout for a quick preview:

```bash
markitdown "/path/to/file.pdf" | sed -n '1,120p'
```

## Quality Checks

After conversion, verify enough of the result before relying on it:

- Compare page count or major section headings against the original when available.
- Search for expected title, author, abstract, table captions, references, and appendix headings.
- Treat very short output from a long PDF as a failed extraction.
- For scanned PDFs or image-only pages, use OCR or page screenshots instead of assuming Markdown is complete.
- For tables and formulas, use Markdown as a navigation aid and verify critical values against the original PDF page.

## Local Assumption

This machine currently has `markitdown` available as a CLI and Python package. If unavailable in a future environment, use the best local text extraction fallback such as `fitz`/PyMuPDF, `pypdf`, `pdfplumber`, or document-specific tools.
