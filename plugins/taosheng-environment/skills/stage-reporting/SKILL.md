---
name: stage-reporting
description: 当用户询问或要求“阶段完成后用人话汇报”“给项目装汇报机制”时，先检查全局主动规则；全局已覆盖时默认不改项目。只有用户明确要求严格拦截、Stop hook 或项目级兜底时，才为当前项目安装或维护可选 hook。也用于诊断误拦、漏拦和回归测试；不用于直接修改全局规则。
---

# 阶段汇报机制

阶段汇报在实际完成阶段或最终交付时，简短说明做成了什么、如何验证，以及会影响使用的实质缺口。有用户必须决定的事项才列出选择和后果；没有则说明无需操作。类比只在帮助理解时使用，不为凑固定模板增加文件、检查或新工作。普通问答、只读核验、诊断和中间进度不套阶段模板。

全局默认来自工作流系统并投影到

- `~/.codex/AGENTS.md`
- `~/.claude/CLAUDE.md`

项目级 `Stop hook` 只是显式选择的严格兜底，不是默认方案。Codex 的 `Stop` 拦截会创建一条表现得像新用户消息的 continuation prompt，因此会多一次生成；用户没有明确接受这一代价时不得安装。

## 路由

1. 用户只是希望“以后阶段完成用人话汇报”：检查全局文件是否已覆盖阶段完成的汇报语义，不匹配固定标题；已覆盖就说明自动生效，不改项目。
2. 用户明确要求“严格拦截／兜底 hook／漏了就自动重写”：再按下节安装当前项目 hook。
3. 用户要求全局调整：不要运行本 Skill 的安装器；Codex 执行规则源文件在 `09-AI工作流系统/adapters/codex/AGENTS.md`，与 `~/.codex/AGENTS.md` 同步；共享 core 不随 Codex 调整自动修改；用户明确要求修改全局规则即授权对应范围，沿用同一任务中的授权，不重复确认。超出该范围的新增全局行为再询问。
4. 诊断误拦或漏拦：先把真实原句加入回归语料，再做最小判据修改；不为单个例子堆通用正则。

## 严格模式安装

1. 确认用户明确选择严格模式且目标是当前项目；不要修改 `~/.codex/hooks.json` 或全局 `AGENTS.md`。
2. 先查看项目现有 `AGENTS.md` 与 `.codex/hooks.json`，保留其他规则和 hook。
3. 运行本 Skill 的安装器：

```bash
python3 ~/.codex/skills/stage-reporting/scripts/install.py <项目根目录>
```

安装器会：

- 在项目 `AGENTS.md` 中新增或更新带标记的“项目级严格阶段汇报兜底”。
- 新增或合并 `.codex/hooks.json` 的 `Stop` hook。
- 写入 `.codex/hooks/plain_stage_report.py`。

判据的唯一来源是 `scripts/plain_stage_report.py`，安装器把它原样复制进项目。
**改判据改这一份，再重装**；不要就地改项目里的副本，否则下次重装被覆盖。
Claude Code 侧预留一份严格模式副本 `~/.claude/hooks/plain_stage_report.py`（当前未在 settings 中启用），判据变了仍要同步。

## 验证

- 修改 hook 判据或安装器时跑 `python3 scripts/test_plain_stage_report.py`，必须全绿；只改本 Skill 的说明或路由文字时，核对语义、引用和范围，不触发 hook 安装或业务测试。
- 实际安装或修改 hook 配置后，用 `python3 -m json.tool <项目>/.codex/hooks.json` 验证 JSON。
- 实际安装或更新判据后，`diff` 项目副本与 `scripts/plain_stage_report.py`，必须逐字节一致。
- Git 项目再运行 `git diff --check`。

## 汇报用户

严格模式才说明三件事：安装到了哪个项目、Codex 拦截会产生一次 continuation、用户还需在 `/hooks` 中审核并信任新 hook。不要代替用户绕过 hook 信任。普通全局模式只说明新会话自动生效，不让用户逐项目重复安装。
