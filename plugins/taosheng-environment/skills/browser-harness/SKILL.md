---
name: browser-harness
description: Direct browser control through the locally installed browser-harness command. Use when the user mentions browser-harness, browser harness, @browser-harness, Chrome CDP, local Chrome automation, scraping, testing, screenshots, downloads, or interacting with live web pages through the browser-harness skill instead of Codex Browser or generic Playwright.
---

# browser-harness

Use this wrapper to route Codex to the local browser-harness checkout and command.

Source of truth:
- `~/Documents/Codex/tools/browser-harness/SKILL.md`
- `~/Documents/Codex/tools/browser-harness/install.md`
- `~/Documents/Codex/tools/browser-harness/interaction-skills/`

本机默认浏览器接入（用户2026-09-22指定）：主力是 Microsoft Edge。普通 Edge 点击、搜索和填写任务，先读取 `~/.codex/skills/jev-browser/SKILL.md`，使用已连通的原生 Edge 扩展执行，JEV选择动作、轻量模型补文字。该适配不需要CDP；不要为它开启或绕过被浏览器工具拒绝的内部调试设置。仅用户明确指定 browser-harness/CDP 或独立Chrome流程时使用下面的CLI路线；同样不得绕过已有安全拒绝。

Workflow:
1. Read `~/Documents/Codex/tools/browser-harness/SKILL.md` completely before browser work.
2. Read `~/Documents/Codex/tools/browser-harness/install.md` only for setup, connection, or troubleshooting.
3. Read the relevant file under `~/Documents/Codex/tools/browser-harness/interaction-skills/` when a specific browser mechanic is needed.
4. Invoke `browser-harness` directly from `$PATH` with heredoc form for multiline commands.
5. Prefer `new_tab(url)` for first navigation so the user's active tab is not clobbered.
6. Do not fall back to Codex Browser or generic Playwright unless browser-harness is unavailable, cannot connect, or the user explicitly asks for a different browser surface.

Example:

```bash
browser-harness <<'PY'
new_tab("https://example.com")
wait_for_load()
print(page_info())
PY
```
