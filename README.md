# 涛生 Skill

一个儿科医生每天在用的 AI 工作习惯。Claude Code 和 Codex 都能装。

我是涛生，医生，不是程序员。这些 skill 是我在门诊之外写论文、做科普、搭工具时，一条条跟 AI 磨出来的。放出来是为了让同样想把 AI 用进工作的人，直接拿到我现在在用的这一套。

## 当前公开清单

v1.1.2：按作者最新公开范围保留 7 个技能，分为科普写作、协作习惯、视频工作台三组。

## 视频工作台

[在线打开视频工作台](https://taosheng777.github.io/ai/video-workbench/) · [独立 Skill v1.0.1](https://github.com/Taosheng777/video-workbench/tree/v1.0.1)。先选画风、看示例，再复制制作需求。

v1.1.1 调整看板默认分类与显示顺序：先看个人作品，视频和图片优先。taosheng-video 的三个自有 Skill 保留；其余技能不进行上游更新。

## 装上

**Claude Code**

```
/plugin marketplace add Taosheng777/taosheng-skills
/plugin install taosheng-popsci@taosheng-skills
/plugin install taosheng-work@taosheng-skills
/plugin install taosheng-video@taosheng-skills
```

三组按需装，不用全装。更新时在 Claude Code 输入 `/plugin marketplace update taosheng-skills`，再到 `/plugin` 的 Installed 中更新已安装的组；本次视频工作台保留固定快照，不自动追踪上游。

**Codex**

```
codex plugin marketplace add Taosheng777/taosheng-skills
```

然后在 Codex 的插件目录里选 `涛生 Skill`，装你要的那组。

也可以在 [发布页](https://github.com/Taosheng777/taosheng-skills/releases) 下载 ZIP。本地 ZIP 解压后，也可以用 `codex plugin marketplace add ./taosheng-skills` 添加解压目录。命令及清单按 [OpenAI 官方文档](https://developers.openai.com/plugins/build/plugins)与 [Claude Code 官方文档](https://code.claude.com/docs/en/plugin-marketplaces)核验；Claude 端安装仍需读者自己的可用账号。

**其他 AI 工具，或者想挑着装**

```
npx skills add Taosheng777/taosheng-skills
```

会问你装哪几个、装给哪个 AI。需要电脑上装过 Node.js。

**完全不会命令行**

在 Claude Code 或 Codex 里直接说：

> 帮我安装这个 skill：https://github.com/Taosheng777/taosheng-skills/tree/main/plugins/taosheng-work/skills/explaining-in-plain-language

把链接换成下面表里你想要的那个。

## 有哪些

| 组 | skill | 干什么 | 你可以这样说 |
|---|---|---|---|
| 科普写作 | [human-writing](plugins/taosheng-popsci/skills/human-writing) | 中文健康科普：有具体的人、站得住、不灌水 | “把这份材料写成给家长看的科普” |
| 协作习惯 | [explaining-in-plain-language](plugins/taosheng-work/skills/explaining-in-plain-language) | 把技术、机制、你自己的配置讲成外行能拍板的话 | “说人话” |
| 协作习惯 | [stage-reporting](plugins/taosheng-work/skills/stage-reporting) | 阶段完成时用人话汇报：做成了什么、要不要你动手、要你决定什么 | “以后阶段完成用人话汇报” |
| 协作习惯 | [wechat-article-search](plugins/taosheng-work/skills/wechat-article-search) | 搜索微信公众号文章并抓成 Markdown | “搜一下公众号里讲 XX 的文章” |

| 视频工作台 | [video-workbench](plugins/taosheng-video/skills/video-workbench) | 6 个创作入口、102 条固定收藏、示例预览与制作需求组合 | “给这支视频挑风格” |
| 视频工作台 | [med-science-video](plugins/taosheng-video/skills/med-science-video) | 医学科普的事实、脚本、制作与验收 | “做一支面向家长的科普视频” |
| 视频工作台 | [making-videos](plugins/taosheng-video/skills/making-videos) | 从立意与样张到通用短片成片检查 | “把这个观点做成短片” |

**工作流模板**：[医生用 AI 的工作规则](templates/医生用AI的工作规则.md)。这不是 skill，是我自己的全局规则去掉个人信息后的版本，粘进 `CLAUDE.md` 或 `AGENTS.md` 就能用。

**我在用的别人的 skill**：[THIRD_PARTY.md](THIRD_PARTY.md)。都是原作者的作品，链接和安装命令直接指向原作者仓库，你装到的是作者维护的版本。

## 说明

- 个人项目，按我自己的用法写成，没有稳定性承诺和技术支持。
- 医学相关的 skill 帮你整理和写作，不替代临床判断；引用请回原文核对。
- 这些 skill 不收集你的数据。`wechat-article-search` 会访问公开网页搜索结果，可选使用你自己登录的 Firecrawl。
- 自有代码与流程适用 [MIT](LICENSE)，保留署名。第三方媒体按各自许可证；个人作品节选用于本看板展示，不统一改标 MIT。人物形象、商标和第三方配乐不因本包而获得额外授权。详见视频工作台来源页。

更多：[涛生的网站](https://taosheng777.github.io/) · [更新记录](CHANGELOG.md)

我的其他公开仓库：[a-share-mainline-os](https://github.com/Taosheng777/a-share-mainline-os)、[BigA-stock-skills](https://github.com/Taosheng777/BigA-stock-skills)（A 股研究，只提示不下单）、[teach-skill](https://github.com/Taosheng777/teach-skill)（Codex 学习教练）、[deepseek-search-mcp](https://github.com/Taosheng777/deepseek-search-mcp)（DeepSeek 搜索 MCP）。
