# 涛生完整技能环境

把我现在使用的技能和协作习惯整理成一套可安装的环境。**v2.0.0 包含 102 个技能入口，老爷爷和它调用的 25 种方法都在包内。** 这次提供完整技能文件，不再只是放第三方推荐链接。

## 最省事的装法

把这段话复制给电脑上的 AI：

> 帮我完整安装 https://github.com/Taosheng777/taosheng-skills 的 v2.0.0。先阅读 README，安装 taosheng-environment 完整版，不要只添加市场或只装旧分组；确认 laoyeye 及配套方法可被发现。按我正在使用的 AI 工具选择安装目录，保留已有配置；再运行安装检查，按我的用途补齐缺少的工具。账号和服务权限由我自己登录配置。

装好后重开一个会话，说：**“老爷爷，我有个想法，但不知道从哪里开始。”**

### Claude Code

```text
/plugin marketplace add Taosheng777/taosheng-skills
/plugin install taosheng-environment@taosheng-skills
```

已经添加过市场的，先执行 `/plugin marketplace update taosheng-skills`，再安装完整版。旧的三个小分组可在插件管理器中停用，避免同名技能重复。

### Codex

```sh
codex plugin marketplace add Taosheng777/taosheng-skills
codex plugin add taosheng-environment@taosheng-skills
```

也可以在插件目录里安装 **「涛生完整技能环境 / taosheng-environment」**。添加市场只是登记来源，选中并安装完整版后，技能才会进入环境。

### 其他 AI：一次选择全部技能

```sh
npx skills add Taosheng777/taosheng-skills --skill '*'
```

按提示选择目标 AI 和项目/全局目录。已在空白项目中实测发现并安装102项。

### 直接复制安装（可验证、可备份）

需要 Git 和 Python 3.10+。在任意工作目录执行：

```sh
git clone --branch v2.0.0 --depth 1 https://github.com/Taosheng777/taosheng-skills.git
cd taosheng-skills
python3 scripts/install.py --target codex
```

Claude Code 将最后一行改成 `--target claude`；通用共享目录使用 `--target shared`。Windows 可用 `py -3` 代替 `python3`。

安装器会校验包内文件摘要，完整复制技能，并输出安装数量及工具检查结果。**不会改你的模型、账号、代理或密钥。** 已有同名技能内容不同时会停止；确认需要替换，再加 `--replace`，旧文件会先备份。

若也想使用我的中文沟通、Markdown 文档、验收和协作习惯，可选：

```sh
python3 scripts/install.py --target codex --rules-file ~/.codex/AGENTS.md
# Claude Code 可改为 --target claude --rules-file ~/.claude/CLAUDE.md
```

规则只追加在独立标记区，保留已有内容并备份原文件。

## 装进去的是哪些能力

| 类别 | 代表技能 |
|---|---|
| 思考与决策 | 老爷爷、点子王、专家会诊、事实核查、第一性原理、最小实验、双向钢人 |
| 学习与表达 | 说人话、Human Writing、Stage Reporting、双层解释、寓言、学习教练 |
| 科研 | 学术研究工作流、文献检索、引用核验、学术润色、科研作图、论文转 PPT |
| 开发与协作 | 写任务书、文档收尾、查 Bug、代码行为准则、小程序开发工具链 |
| 网页与资料 | Agent Reach、Firecrawl 系列、公众号检索、MarkItDown、照片定位 |
| 视频与演示 | 视频工作台、医学科普与短片流程、花叔动效、手绘视频、字幕、Bento |
| 投资研究 | 复盘、主线分析、载体筛选、A 股取数、同花顺接入 |
| 本机 AI 协作 | Gemini / WorkBuddy 调度、模型桥接、浏览器适配、只读项目接入 |

完整逐项清单见 [CATALOG.md](CATALOG.md)，每个技能都能在 `plugins/taosheng-environment/skills/` 找到实际文件。

## 安装后还缺什么

```sh
python3 scripts/install.py --doctor --target codex
```

技能是工作方法和脚本，账号、付费额度、浏览器登录、官方应用插件及大型软件需要使用者自己的环境。[ENVIRONMENT.md](ENVIRONMENT.md) 列了逐类补齐方法。安装器不把“文件复制成功”冒充“所有外部服务已登录可用”。

本机 100 个个人/共享技能入口中，98 个进入本包；1 项私人技能不分发，1 项无头剪映受原许可限制不能作为公开合集打包。另保留公开版已有的 Human Writing 和 3 项视频技能，所以总共 102 个。官方应用自带的插件不从托管缓存复制，请在自己的应用内安装授权。

## 来源与许可

- 老爷爷与思考方法：[LearnPrompt/laoyeye](https://github.com/LearnPrompt/laoyeye)，保留其中 [Matt Pocock](https://github.com/mattpocock/skills)、[数字生命卡兹克](https://github.com/KKKKhazix/khazix-skills)、[卡尔](https://github.com/LearnPrompt/partner-skill)、[ayghri](https://github.com/ayghri/i-have-adhd) 及其他原作者的出处与原许可。
- 学术研究：[Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills)、experiment-agent；含 **CC BY-NC 4.0** 内容，仅限非商业使用。
- 科研辅助：[Orchestra Research / AI Research Skills](https://github.com/Orchestra-Research/AI-Research-SKILLs)。
- 检索与浏览：[Agent Reach](https://github.com/Panniantong/Agent-Reach)、[Firecrawl](https://github.com/firecrawl/skills)、[Browser Harness](https://github.com/browser-use/browser-harness)、[MarkItDown](https://github.com/microsoft/markitdown)、[Geo Sleuth](https://github.com/Oldcircle/geo-sleuth)、[REA](https://github.com/morluto/rea)。
- 创作：[花叔动效](https://github.com/alchaincyf/huashu-motion)、[手绘视频](https://github.com/threerocks/sweety-handdraw-video)、[乔木 Bento](https://github.com/joeseesun/qiaomu-bento-ppt)、[公众号排版](https://github.com/isjiamu/gzh-design-skill)，其中公众号排版沿用 AGPL-3.0。
- 数据：[A 股数据](https://github.com/simonlin1212/a-stock-data)；同花顺、微信开发者工具相关内容保留其官方出处和本机适配。
- 其余本机定制与适配保留文件内原有署名；分发来源记录见 [SOURCES.json](SOURCES.json)。未找到独立上游的适配不会冒称全新原创或擅自授予第三方内容 MIT 许可。

**不是整个包统一 MIT。** 根目录许可仅覆盖自有分发工具；各组件的原许可证、NOTICE、字体和素材条款继续有效，详见 [NOTICE.md](NOTICE.md)。无头剪映不在包内，个人使用请从 [原作者仓库](https://github.com/mcncarl/jianying-headless) 获取并遵守其条款。

这些是个人使用的工作流。医学工具用于资料整理和写作，不替代临床判断；投资工具不下单、不构成投资建议。未验证的结果应由使用者核实。
