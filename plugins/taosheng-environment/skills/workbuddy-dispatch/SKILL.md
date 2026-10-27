---
name: workbuddy-dispatch
description: 当用户明确说「分发给 WorkBuddy / codebuddy / GLM / kimi / minimax / deepseek」，或点名要这些模型做交叉验证、批量翻译/摘要/格式转换、后台长跑任务时使用。用户需要混元 Hunyuan、或需要微信公众号正文而本会话抓取被 captcha 拦截时也用；Gemini 额度用尽且用户同意改用 WorkBuddy 时也用。泛称「交给另一个 AI」且没点名模型时改用 gemini-dispatch。不要用于需要溯源的事实检索。
---

# WorkBuddy 任务分发

本机 WorkBuddy（`com.tencent.workbuddy.mac`，Electron）内置腾讯 CodeBuddy CLI（`@genie/agent-cli`），是独立进程、独立登录态，可作为子 agent 承接任务并回流结果。

**与 `workbuddy-cli-model-bridge` 的分工**：那个技能把外部 CLI 模型注册**进** WorkBuddy（加模型、修模型、CLIProxyAPI）；本技能把任务派**给** WorkBuddy 执行。模型缺失或失效时转那个技能处理，不要在本技能里改 bridge 配置。用户的 `custom-local:*` 模型即由该 bridge 注册。

## 授权与分发范围

调用前从当前请求和已确认的任务记录中确定模型、费用来源、任务范围和预算。
同一任务内，这些授权跨轮次持续有效；已授权的续跑、必要重试和批次内后续工作
不重复询问。用户已指定模型及对应调用范围时，直接准备输入、执行并验收。

只有缺少会影响实际费用的选择，或准备改变模型、第三方去向、预算或任务范围时，
才说明具体变化并等待明确授权。未回复不等于同意；没有成本授权的收费测试也不能先跑。
等待时可以整理输入、定义验收、检查已有结果，不暂停无依赖工作。询问方式以当前
宿主实际可用工具为准，不假定某个平台永久缺少输入工具。

### 二、派活前先定验收标准

`AGENTS.md` 要求 subagent 用在「输入、输出和验收标准明确」的前提下。分发给 WorkBuddy 同理：**派活前先想清楚拿回来的结果怎么判断对错**，否则等于花钱买一段无法验证的文本。

## 三档成本：钱从不同地方出

| 档位 | 模型 | 成本来源 | 通道 |
|---|---|---|---|
| 免费 | `Hy4` `Hy3`（混元） | 限时免费（2026-09-04 用户确认，随时可能结束） | **仅 GUI**，无 CLI 自动回流 |
| 用户自有余额 | `custom-local:deepseek-v4-pro`<br>`custom-local:deepseek-v4-flash`（flash 已实测调通） | 用户自配 DeepSeek API。**无缓存折扣** | CLI ✅ |
| WorkBuddy 积分 | `glm-5.1` `glm-5.0` `glm-4.7` `glm-5v-turbo` `glm-5.0-turbo` `kimi-k2.5` `minimax-m2.7` `deepseek-v3-2-volc` `auto` | 消耗积分 | CLI ✅ |

**当前所记的免费混元走 GUI、无 CLI 自动回流；能否读取 GUI 结果需核当前工具能力，CLI 成本按本次实际渠道核验。** 问用户时把这个取舍讲清楚，别只报模型名。

### 实测备注（2026-09-04）

- `custom-local:deepseek-v4-flash` 已验证调通，耗时约 6.7s；`glm-5.1` 约 3.2s。
- **custom-local 档没有缓存**：实测 `cache_read_input_tokens` 为 0，每次调用约 6.5k input token 全额计费（system prompt 占绝大部分）。走积分的 glm 档命中缓存（6144 token 走 cache_read）。
- **批量任务优先按上下文容量和可验证性合并调用。** 避免每个小项单独调用；超过容量或需要隔离失败时可分成有界批次，沿用已批准预算。

## CLI 调用

```bash
CB="/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/codebuddy"
cd <可写目录>   # 根目录只读，不 cd 会报 read-only file system
node "$CB" -p "任务描述" --model <用户选定的模型> --output-format json --tools "" --max-turns 3 </dev/null > out.json 2>&1
python3 -c "import json;print(json.load(open('out.json'))[-1]['result'])"
```

结果在 JSON 数组**最后一条**的 `result` 字段；同一条还有 `session_id`（可 `--resume` 续接）、`is_error`、`total_cost_usd`、`usage`。

常用参数：`--tools ""` 禁用全部工具（纯问答最安全）｜`--bg` 后台跑｜`--max-turns N`｜`--effort <minimal|low|medium|high|xhigh|max>`｜`--system-prompt`｜`--add-dir`

## 要结构化输出：用 prompt 约束，别用 --json-schema

`--json-schema` 在 `--help` 里存在，但**实测不生效**。三种组合均失败：`--tools ""`（报错「StructuredOutput 不是一个我拥有的工具」）、`--tools "StructuredOutput"`、默认全工具（都退化成自然语言）。

可靠做法是 prompt 硬约束后自行解析：

```bash
node "$CB" -p '任务描述。严格只输出JSON，格式为 {"key":"value"}。禁止输出任何解释文字，禁止用markdown代码块包裹。' \
  --model <用户选定的模型> --output-format json --tools "" --max-turns 1 </dev/null > out.json 2>&1
```

实测返回干净 JSON 可直接解析；解析时保留剥 markdown 代码块的容错步骤。

## Deep Link 调用（GUI，可用混元）

```bash
P=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "任务描述")
open "workbuddy://task?action=start&prompt=$P"
```

支持 `prompt` `cwd` `skills` `connectorIds`；另有 `workbuddy://switch-model?modelId=xxx`。

**Deep Link 发起成功只是派发，不等于已取得结果。** 先用当前可用且已授权的 UI/结果读取能力核验进度并取回内容；只有实际无法读取时，才说明具体阻塞并请用户把结果提供回来。不得假装已拿到，也不因无 CLI 回流就默认要求手工搬运。

## 适合分发

- 多模型交叉验证：同一问题让 GLM 也答一遍，比对分歧
- 批量低风险处理：批量翻译、摘要、格式转换（省本会话上下文）
- 独立可并行的子任务（配 `--bg`）
- 中文文案润色

## 不要分发

- **需要溯源的事实检索** —— 第二个模型的答案无法独立验证，多一个模型不等于多一份证据，反而可能污染已能溯源的结论。宁可自己查。
- **敏感医学资料** —— 第三方模型服务，按 `AGENTS.md` 敏感医学资料条款处理；真实外发须等明确确认。
- **依赖本会话上下文的任务** —— 它是独立进程，上下文传不过去，必须在 prompt 里显式带全。

## GUI 无需运行

实测（2026-09-04，WorkBuddy GUI 完全退出状态）：`glm-5.1` 与 `custom-local:deepseek-v4-flash` 两档**均可正常调用**，且调用结束后**不残留任何 WorkBuddy 进程**——CLI 用完即走，不会把 GUI 拉回后台。

**不要因为要分发任务就让用户去打开 WorkBuddy。** 只有走 Deep Link（GUI 通道）时才需要它运行。

## 排障

路径失效（WorkBuddy 更新频繁，曾在同一天 5.5.2→5.5.3）：

```bash
ls /Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/
```

报认证错误 = 未登录，让用户在 WorkBuddy GUI 登录一次；`~/.codebuddy/user-state.json` 是登录态。模型本身不可用（而非未登录）转 `workbuddy-cli-model-bridge`。

## Common Mistakes

| 错误 | 后果 |
|---|---|
| 未获成本授权就启动收费调用 | 引入用户未批准的费用 |
| 把未回复当成批准后执行依赖动作 | 缺少真实授权；可继续的只是无依赖准备工作 |
| 纯问答不加 `--tools ""` | 子 agent 可能擅自读写文件 |
| 在只读目录下跑 | 报 read-only file system，先 cd 到可写目录 |
| 直接 cat 整个 JSON | 输出含完整 system prompt，白烧几千 token |
| 每个小项单独调用且不控制批次 | 重复固定开销；按容量合批并保留预算界限 |
| 用 `--json-schema` 要结构化结果 | 实测不生效，会退化成自然语言 |
| 拿 Deep Link 当同步调用 | 结果根本没回来，别编造 |
