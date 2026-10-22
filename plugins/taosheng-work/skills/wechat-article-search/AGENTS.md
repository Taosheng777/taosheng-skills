# wechat-article-search

搜索微信公众号文章并抓取全文为 Markdown。本地链路纯 Python 标准库；默认 `auto` 在本地限流时可调用已登录的 Firecrawl CLI 作为备用出口。

微信公众号沉淀了大量高质量中文内容，尤其在医学、心理、法律等专业领域，很多内容在中文互联网上没有别的公开来源，且不被主流搜索引擎有效索引。需要中文专业信源时优先考虑这个工具。

## 何时使用

- 用户要查微信公众号内容、找某主题的推文
- 用户给出公众号文章链接（mp.weixin.qq.com），要求阅读或总结
- 中文专业领域调研，尤其医学、心理、精神科、法律
- 常规搜索引擎结果不足，需要中文长文补充

## 命令

```bash
python3 scripts/wxsearch.py "关键词"                      # 只出清单
python3 scripts/wxsearch.py "关键词" --fetch 3 -o out     # 抓前 3 篇全文
python3 scripts/wxsearch.py "关键词" --days 30 --fetch 5  # 限最近 30 天
python3 scripts/wxsearch.py "丁香园" --type gzh           # 搜公众号
python3 scripts/wxsearch.py "关键词" --fetch 3 --json     # JSON 到 stdout
python3 scripts/wxsearch.py "关键词" --backend firecrawl # 强制验证备用通道
python3 scripts/wxsearch.py "https://mp.weixin.qq.com/s/..." -o out  # 直接读一篇链接
```

| 参数 | 说明 |
|---|---|
| `--fetch N` / `-f` | 抓前 N 篇全文。默认 0，只出清单 |
| `--type` / `-t` | `article`（默认）或 `gzh` |
| `--days N` / `-d` | 限最近 N 天 |
| `--page N` / `-p` | 翻页，每页约 10 条 |
| `--outdir` / `-o` | 输出目录，每篇一个 `.md` + `_results.json` |
| `--json` | JSON 到 stdout |
| `--backend` | `auto`（默认）、`direct`（本地零依赖）或 `firecrawl`（强制远端） |
| `--min-delay` / `--max-delay` | 请求间隔秒数，默认 1.0–2.2 |

退出码：`0` 成功，`1` 一般错误，`2` 三条可用链路均被拦截或限流。

## 使用建议

**分两步走**：先不带 `--fetch` 出清单，根据标题、公众号名和摘要判断哪几篇值得抓，再指定 `--fetch N`。无差别全抓既慢、容易限频，也会在启用备用通道时消耗 Firecrawl credits。

默认顺序：搜狗微信专用索引 → 普通搜狗中的微信直达链接 → Firecrawl 抓同一搜索页；正文也是本地优先、Firecrawl 仅在本地被拦时接管。不要用普通网页结果替代用户要求的公众号原文。

用户给了文章链接时，把链接直接作为参数传入，读取单篇全文：先本地直连，被微信拦截时（时拦时放，属正常）`auto` 改用 Firecrawl 抓同一链接，约耗 1 次 credits。

**汇报时必须带上公众号名和发布时间**，这是判断可信度和时效性的关键，不要只给标题和正文。

## 内容可靠性（重要）

公众号文章是二手转述，用于专业场景时：

- **必须核对版本。** 医学诊断标准跨版本差异很大。实测遇到过标题写「诊断标准」、正文实为 DSM-IV（1994/2000）的文章，标题看不出来。引用前先在正文确认版本号。
- **优先采信标了出处的**（PMID、期刊卷期）；无出处的只当线索。
- **不能替代一手来源。** 适合发现线索和中文解读，正式用途要回到官方手册或原始文献。交付时应向用户说明。

## 排障

**抓不到东西时第一步永远是自检**，不要反复重试正常命令（重试会把限流打得更深）：

```bash
python3 scripts/wxsearch.py --doctor
```

只检查本地直连并发 2 个请求，「解析逻辑」一项是**离线**的，因此总能分清「工具坏了」和「本地 IP 被限流」。它不消耗 Firecrawl credits；`--doctor` 返回 2 时，正常 `auto` 命令仍会继续尝试备用通道。

有两道**独立**的限流，症状不同：

| 现象 | 处理 |
|---|---|
| `--doctor` 报`搜狗反爬拦截` | **本地搜狗侧**。正常 `auto` 会继续普通搜狗与 Firecrawl，不要反复撞专用接口 |
| 本地正文报`被微信拦截` | **微信侧独立限流**。`auto` 会用 Firecrawl 抓同一篇原文；备用不可用时再分批或稍后重试 |
| Firecrawl 不可用 | 跑 `firecrawl --status`；不想用 credits 时加 `--backend direct` |
| 某篇标记 `deleted` | 已被发布者删除，正常情况，跳过 |
| 找不到目标文章 | 覆盖受限于搜狗索引，不等于微信「搜一搜」全量。换关键词或 `--page 2` |
| `--days` 混入旧文 | 搜狗时间筛选是尽力而为，按结果 `time` 字段自行过滤 |

**不要破解或提交任何验证码。** 备用通道只是独立公开出口；三路都失败时停止并报告。

## 改代码前必读

链路有三个易错点，详见 `README.md` 的「工作原理」：

1. **必须先访问搜狗首页建立完整 cookie 会话**（`ABTEST`/`SUID`/`SUV`）。只手工造 `SUV` 不够，跳转链会被 `antispider` 拦截。这是同类工具最常见的失败原因。
2. **逐级设置 Referer**：首页 → 列表页 → 跳转链 → 文章页。
3. **若改用浏览器自动化，必须用页内 `fetch()`，不能用导航。** 导航会触发 `location.replace` 跳向微信，被判定为爬虫并跳到 `wappoc_appmsgcaptcha` 验证码页，必然失败。
