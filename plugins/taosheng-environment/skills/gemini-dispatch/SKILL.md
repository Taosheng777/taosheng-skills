---
name: gemini-dispatch
description: 当用户说「交给 Gemini」「问问 Gemini」「用 Gemini 跑」「agy」「Antigravity」时使用；需要第二个模型交叉核对当前结论、需要 Google 搜索作为第二条线索来源时使用；长文档、大批量材料的摘要/翻译/抽取/格式转换想省当前模型额度时使用；泛称「交给另一个 AI」「找第二个 AI」且没点名 GLM/kimi/混元等 WorkBuddy 模型时也用。需要溯源的最终事实结论、写文件改代码、要求 Gemini 4 Argon 但 agy models 里还没有时不用。
---

# Gemini 任务分发（Antigravity CLI）

## Overview

本机装有 Google 官方 Antigravity CLI（`agy`，`~/.local/bin/agy`），已用用户的 Google AI Pro 账号登录。无头模式一次一问、跑完退出，**消耗的是订阅额度，不按 token 另外付费**。Gemini CLI（`@google/gemini-cli`）2026-06-18 起已不服务 AI Pro 账号，不要装、不要用。

本 skill 本体在 `~/.claude/skills/gemini-dispatch/`，随 claude-skills 仓库用 git 管理并备份到 GitHub 私有仓库；共享目录 `~/.agents/skills/gemini-dispatch/` 是一份同内容副本（不是软链，2026-10-22 查实），Codex 从那里读；改一边要同步另一边。改动后在 `~/.claude/skills` 提交。泛称「交给另一个 AI」默认走这里；用户点名 GLM / kimi / minimax / deepseek / 混元，或要微信公众号正文时，Claude 侧走 workbuddy-dispatch。Gemini 额度用尽或被限流时，先告诉用户，再问是否改用 WorkBuddy（那边扣积分或余额）。

## 调用：一律用封装脚本

```bash
G=~/.agents/skills/gemini-dispatch/scripts/gemini_ask.py
$G "问题"                                # 纯问答
$G "总结 /abs/path/报告.pdf 的结论" -d /abs/path   # 读文件必须用 -d 放开所在目录
$G "抽取…" -s '{"type":"object",...}'     # 结构化：stdout 即 JSON
$G "…" -m gemini-3.8-flash-low --raw /tmp/out.json
```

**扫描版 PDF（没有文字层）**：直接给 PDF，Gemini 读不出字会想执行命令转换，被拦下（退出码 3）。先用 PyMuPDF 把页面渲染成图片，再用 `-d` 放开图片目录，prompt 里写明"逐张读取 p01.png…，只用读文件"：

```bash
python3 -c "import fitz,sys;d=fitz.open(sys.argv[1]);[p.get_pixmap(matrix=fitz.Matrix(1100/p.rect.width,1100/p.rect.width)).save(f'{sys.argv[2]}/p{i:02d}.png') for i,p in enumerate(d,1)]" 输入.pdf 输出目录
```

判断有没有文字层：`fitz.open(f)[0].get_text().strip()` 为空即是扫描件。实测 18 页中文扫描书：264 秒，约占 5 小时额度 1%。

stdout 只有结果；stderr 一行 `[gemini] model=… 秒数 in= out= conv=`。脚本在空临时目录里跑 agy，Gemini 默认读不到调用方项目。直接调 `agy -p` 会踩两个坑：权限被拒时 exit 0 且回复为空；在项目目录里跑会读进项目文件。

| 退出码 | 含义 | 处理 |
|---|---|---|
| 0 | 成功 | — |
| 2 | 调用失败/返回异常 | 看 stderr；额度类错误告诉用户，不要循环重试 |
| 3 | 工具权限被拒，结果为空 | 读文件：加 `-d`；要写文件：本 skill 不做 |
| 4 | 未登录/登录失效 | 让用户在终端运行 `agy` 选 Google OAuth；授权码由用户自己粘进终端 |

## 选模型

| 模型 | 用途 |
|---|---|
| `gemini-3.8-flash-high`（默认） | 交叉核对、长文理解、看图审片等需要判断的活 |
| `gemini-3.8-flash-medium/low` | 量大、规则明确的机械活（翻译、格式转换） |

列表随账号和时间变化，以 `agy models` 为准。**2026-10-22 实测**：Google 已于 10 月中旬把 Gemini 3.1 Pro 从个人订阅撤下（论坛员工 10-16 答复），Pro 账号的 agy 只剩 3.8 Flash 三档，传 `gemini-3.1-pro-high` 会直接报错。员工说付费非试用的 Pro 账号也会有 **Gemini 4 Argon**（Medium/High），但本账号 `agy models` 里暂时没有；用户问起时先 `agy models | grep -i argon`，出现后用同一任务对比 Flash 再改默认值。Flash 偶有编造（审片实测 21 条里 1 条凭空捏造），结论照旧要核。

列表里还有 Claude Sonnet/Opus 4.6 和 GPT-OSS，扣的是 Google 订阅里“Claude and GPT models”那组额度，不动用户的 Claude 订阅。

## 适合 / 不适合

适合：第二意见（同一问题独立作答，再比对分歧）；Google 搜索作为线索；长 PDF/长文摘要；批量翻译、抽取、格式转换。

不适合：
- **需要溯源的最终事实结论**：Gemini 的回答只算线索。它的搜索来源是 `vertexaisearch.cloud.google.com/grounding-api-redirect/…` 跳转链接，引用前必须自己打开、核到原文。
- **未经核对就直接用数字**：实测扫描书里约 20 个数字错了 1 个，Gemini 把相邻句子的两个数拼成了一个区间（2026-10-01）。剂量、参考值、误差范围这类临床数值，转给用户前必须对照原文或原图核对。
- **写文件、改代码**：不加 `--dangerously-skip-permissions`，产出由本会话自己落盘。
- **依赖本会话上下文的活**：它是独立进程，背景必须在 prompt 里写全。

## 额度与节流

- 每次调用有约 5k–13k input token 的固定开销（实测）。批量活合并成一次调用，让它一次返回结构化结果，不要逐条循环。
- 个人 AI Pro 账号：串行调用，不并发、不跑无人值守的长循环，否则会撞 TPM/RPM 限制并可能触发滥用检测（Google 员工 2026-09-25 论坛答复）。用外部编排工具调用官方 agy 是允许的，但禁止读取或复用 `~/.gemini` 下的 OAuth 令牌。
- 查剩余额度：`agy -p /usage`（不耗额度）。Gemini Flash 和 Pro 共用一组周额度和 5 小时额度，按 token 成本比例扣；Claude/GPT 模型另算一组。大任务前后各查一次，就能告诉用户这一单花了多少。

## 边界

- 敏感医学资料：发给 Gemini 即交给 Google 处理，首次使用按全局规则先提醒资料类型、用途和去向。
- 不要把证件号、token、密钥写进 prompt。
