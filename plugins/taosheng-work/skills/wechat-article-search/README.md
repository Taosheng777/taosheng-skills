# wechat-article-search

搜索微信公众号文章并抓取全文为干净 Markdown。**本地直连链路纯 Python 标准库；本地限流时可自动切换已登录的 Firecrawl CLI。**

微信公众号沉淀了大量高质量中文内容——尤其在医学、心理、法律等专业领域，很多内容在中文互联网上没有别的公开来源。但这些内容既不被主流搜索引擎有效索引，也无法被常规爬虫获取。这个工具解决这个问题。

给 AI 编程助手（Claude Code、Codex、Cursor 等）用时，它会成为一个可调用的中文优质信源。

```bash
python3 scripts/wxsearch.py "延长哀伤障碍 DSM-5-TR 诊断标准" --fetch 3 -o out
```

```
[1/3] 搜索：延长哀伤障碍 DSM-5-TR 诊断标准
      共 10 条
  1. 根据DSM-5-TR修改的延长哀伤量表PG-13-R
     哀伤疗愈之家 | 2023-10-26 11:30
  2. 延长哀伤障碍的诊断标准记忆要点
     首医的小精卫们 | 2026-03-29 00:00
  ...
[2/3] 解析真实链接并抓全文（前 3 篇）
  1. ✓ 2880 字 — out/根据DSM-5-TR修改的延长哀伤障碍问卷PG-13-R.md
  2. ✓ 1718 字 — out/延长哀伤障碍的诊断标准记忆要点.md
  3. ✓ 8046 字 — out/延长哀伤障碍及其治疗.md
```

## 安装

只使用本地直连链路时，需要 Python 3.10+，没有别的依赖。默认 `auto` 要在限流时继续完成任务，则需本机已有可用的 Firecrawl CLI；它是可选备用通道，会消耗 Firecrawl credits。

```bash
git clone https://github.com/<your-name>/wechat-article-search.git
cd wechat-article-search
python3 scripts/wxsearch.py --help

# 可选：确认备用通道已登录
firecrawl --status
```

### 作为 AI 助手的技能

| 工具 | 装法 |
|---|---|
| **Claude Code / Claude** | 整个目录放进 `~/.claude/skills/wechat-article-search/`，`SKILL.md` 会被自动识别 |
| **Codex** | 仓库里的 `AGENTS.md` 会被自动读取；或把内容并入你项目的 `AGENTS.md` |
| **Cursor / 其他** | 把 `AGENTS.md` 内容贴进对应的规则文件 |

## 用法

```bash
# 只列清单（不消耗抓取，先看值不值得抓）
python3 scripts/wxsearch.py "关键词"

# 抓前 5 篇全文
python3 scripts/wxsearch.py "关键词" --fetch 5 -o 输出目录

# 限最近 30 天
python3 scripts/wxsearch.py "关键词" --days 30 --fetch 3

# 搜公众号而非文章
python3 scripts/wxsearch.py "丁香园" --type gzh

# 管道给其他程序
python3 scripts/wxsearch.py "关键词" --fetch 3 --json | jq '.[].title'

# 强制测试备用通道；完全禁用备用通道则改成 direct
python3 scripts/wxsearch.py "关键词" --backend firecrawl --fetch 1

# 直接读一篇文章链接（短链 /s/xxx 或长链 /s?__biz=… 均可）
python3 scripts/wxsearch.py "https://mp.weixin.qq.com/s/..." -o 输出目录
```

| 参数 | 说明 |
|---|---|
| `--fetch N` / `-f` | 抓前 N 篇全文。默认 0，只出清单 |
| `--type` / `-t` | `article`（默认）或 `gzh`（搜公众号） |
| `--days N` / `-d` | 限最近 N 天 |
| `--page N` / `-p` | 翻页，每页约 10 条 |
| `--outdir` / `-o` | 输出目录，每篇一个 `.md`，另有 `_results.json` 索引 |
| `--json` | JSON 输出到 stdout，便于管道 |
| `--backend` | `auto`（默认）、`direct`（只走本地零依赖链路）或 `firecrawl`（强制远端） |
| `--min-delay` / `--max-delay` | 请求间隔秒数，默认 1.0–2.2 |
| `--doctor` | 自检。**抓不到东西时先跑这个**，它会告诉你是工具坏了还是 IP 被限流 |

### 抓不到东西时先跑自检

```bash
python3 scripts/wxsearch.py --doctor
```

```
wxsearch 1.3.0 自检

[1/4] Python 环境        ✓ 3.14.4（仅标准库）
[2/4] 解析逻辑（离线）   ✓ 列表解析 / 正文转换 / 拦截判别 均正常
[3/4] 搜狗首页可达      ✓ 6437 字节
[4/4] 搜索链路          ✗ 被反爬拦截

诊断：工具正常，当前 IP 被搜狗限流。
      短时间大量请求会触发，恢复可能需要数小时。
      换网络（如手机热点）可立即验证这一点。
```

第 2 步是**离线**的——不碰网络就能验证解析逻辑是否被搜狗改版打坏。所以你总能分清「工具坏了」和「本地网络被限」这两件事。`--doctor` 只诊断本地直连，不调用 Firecrawl；即使返回 2，正常 `auto` 命令仍会尝试备用通道。

**建议先不带 `--fetch` 跑一遍**，看标题、公众号和摘要判断价值，再决定抓哪几篇。

输出的 Markdown 带出处头：

```markdown
# 延长哀伤障碍的诊断标准记忆要点

> 公众号：打工的老精卫们　发布：2026-03-29 00:00
>
> 原文：https://mp.weixin.qq.com/s?src=11&...

---

（正文）
```

## 工作原理

本地直连是四步状态链：

```
搜狗微信首页          → 拿 ABTEST / SUID cookie，并确保 SUV 存在
  ↓ Referer: 首页
搜索列表页            → 标题 / 公众号 / 时间 / 摘要 / 跳转链
  ↓ Referer: 列表页
weixin.sogou.com/link → JS 里 url += '...' 分片，拼接后剔除混淆用的 '@'
  ↓ Referer: 跳转链
mp.weixin.qq.com/s?…  → 提取 div#js_content，转 Markdown
```

默认 `auto` 在任何一步被本地限流时使用下列备用路径：

```
普通搜狗网页索引       → 只保留 mp.weixin.qq.com/s 直达结果
  ↓ 本地仍失败
Firecrawl 远端抓搜索页 → 仍只解析微信公众号直达结果
  ↓ 本地微信正文被拦
Firecrawl 远端抓原文   → 提取标题、公众号、发布时间和正文
```

这不是把用户要求改成普通网页搜索：普通搜狗只承担发现微信直达 URL 的作用，最终交付仍是 `mp.weixin.qq.com` 原文。Firecrawl 也只在前序链路失败时启用。

直接传文章链接时跳过搜索：先本地直连取正文（不带 Referer），被拦时 `auto` 改用 Firecrawl 抓同一链接。

Firecrawl 远端看到的是**英文界面**：发布时间显示为 `Sep 17, 2026, 8:08 PM`（渲染端时区），文中视频会被渲染成带 `Close`、`Video Details` 等按钮的播放器。因此 Firecrawl 正文优先解析它返回的原始 HTML：与本地直连同一套 `div#js_content` 解析，整块剔除 `video_iframe` 播放器，时间取页面里的时间戳 `ct`。原始 HTML 缺正文容器时才退回解析 Markdown。

### 三个关键点

搞错任何一个，整条链路都会失败：

**1. 必须先落地首页建立完整 cookie 会话。** 只手工造一个 `SUV` cookie 不够——服务器种的 `ABTEST` 和 `SUID` 同样被校验。缺了它们，跳转链会返回 `antispider` 拦截页。这是最常见的失败原因，也是很多同类工具取不到正文的根本原因。

**2. 逐级设置 Referer。** 首页 → 列表页 → 跳转链 → 文章页，每一跳的 `Referer` 都要指向上一跳。

**3. 如果你改用浏览器自动化：必须用 `fetch()`，不能用导航。** 让浏览器 `goto`/点击跳转链，它会自动 `location.replace` 跳向微信，微信据此判定为爬虫并跳转到 `wappoc_appmsgcaptcha` 验证码页，必然失败。页内 `fetch()` 只取 HTML 不触发导航，可以通过。

### 混淆细节

搜狗把真实 URL 拆成多段 JS 字符串拼接，并插入 `@` 字符干扰：

```javascript
url += 'https://mp.weixin.qq.com/s?src=11&timestamp=';
url += '17855@73223&ver=6877&signature=';
```

拼接后须 `.replace(/@/g, '')`。

## 已知限制

- **时间筛选是"尽力而为"。** 冷门关键词在指定时间内文章不足时，搜狗会用旧文补位。需要精确筛选就按结果里的 `time` 字段自行过滤。
- **每页约 10 条**，用 `--page` 翻页。
- **拿到的文章链接是带签名的时效链接**（`src=11&timestamp=…&signature=…`），不是永久短链，隔一段时间会失效。要长期保存请存正文而非 URL。
- **部分文章返回「该内容已被发布者删除」**，属正常情况，工具会标记为 `deleted`。
- **有两道独立的本地限流，别搞混：**
  - *搜狗侧*——影响专用搜索。`auto` 会先改走普通搜狗，必要时再用 Firecrawl 抓同一结果页。
  - *微信侧*——只影响本地取正文。`auto` 会改用 Firecrawl 抓同一篇微信原文。直接请求用户给的链接（不经搜狗跳转）时拦时放，实测（2026-09）同一短链连续请求出现过拦、拦、放、拦。

  实测（家用宽带单 IP，2026-08）：一天内累计取正文约 12–15 篇后，微信侧开始拦截。搜狗侧在密集请求下也会跟着收紧——一旦触发就是**确定性拦截**（同一查询连试 10 次全被拦，响应长度精确一致），不是概率性放行，重试没有意义。恢复可能需要数小时。

  排查阶段尤其要克制：诊断本身如果连打几十次请求，会把原本间歇性的拦截打成持续拦截。**怀疑出问题时先跑 `--doctor`（只发 2 个本地请求），别反复撞同一接口。** 默认 `auto` 会自动换路；若环境没有登录 Firecrawl，则运行 `firecrawl --status` 排查，或用 `--backend direct` 明确只测本地链路。

  **要批量抓就分几次、隔开时段跑**，并拉大间隔（`--min-delay 3 --max-delay 6`）。把这个工具当作精挑细选的取文器，而不是批量爬虫——先出清单，只抓真正需要的那几篇，是最稳的用法。
- 本工具**不会**也**不应该**破解或提交任何验证码。Firecrawl 是独立公开抓取出口，不是验证码求解器。
- **覆盖面受限于搜狗索引**，不等同于微信客户端「搜一搜」的全量结果。

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功（`--fetch` 时至少取到 1 篇正文） |
| 1 | 一般错误；或指定了 `--fetch` 但一篇都没取到（非拦截原因） |
| 2 | 本地与备用链路均被限流或拦截 |

## 内容可靠性提示

公众号文章是二手转述，用于专业场景时务必注意：

- **核对版本。** 医学诊断标准跨版本改动很大。实测中遇到过标题写「诊断标准」、正文却是 DSM-IV（1994/2000）内容的文章，标题完全看不出来。拿错版本比没有更危险。
- **优先采信标了出处的。** 引了 PMID、期刊卷期的文章可信度显著更高。
- **正式用途请回到一手来源。** 本工具适合发现线索和获取中文解读，不能替代官方手册、原始文献或临床指南。

## 致谢

搜狗微信搜索 + 自造 SUV cookie 这个基本思路，参考了腾讯 WorkBuddy 内置的 `wechat-article-search` skill。但该实现只做到列表检索——它用裸 HTTP 请求跳转链，没有建立完整 cookie 会话，因此取正文功能实际是失效的。本项目补上了会话链与 Referer 链，打通了从搜索到正文的完整链路。

## License

MIT
