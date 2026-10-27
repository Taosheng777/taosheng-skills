# 完整技能清单

当前版本：2.0.0；共 102 个技能入口。

| 技能 | 用途 |
|---|---|
| [a-stock-data](plugins/taosheng-environment/skills/a-stock-data/SKILL.md) | 编写代码获取真实 A 股行情、研究与市场数据时使用；提供可复用端点和数据源降级方案。无需取数的概念或投资观点讨论不加载。 |
| [academic-plotting](plugins/taosheng-environment/skills/academic-plotting/SKILL.md) | Generates publication-quality figures for ML papers from research context. Given a paper section or descriptio |
| [academic-research-suite](plugins/taosheng-environment/skills/academic-research-suite/SKILL.md) | 学术研究、论文写作修订和同行评审工作流；用于需要 ARS 研究流程、实验规划或 /ars-* 命令的任务。 |
| [agent-reach](plugins/taosheng-environment/skills/agent-reach/SKILL.md) | 多平台与平台专项搜索、抓取和内容获取；用户点名 Agent Reach，或需要小红书、X、B站、Reddit、YouTube、GitHub 跨仓库等平台能力时使用。普通网页、单个官网和官方文档优先原生联网，资料已有时直接 |
| [brainstorming-research-ideas](plugins/taosheng-environment/skills/brainstorming-research-ideas/SKILL.md) | Guides researchers through structured ideation frameworks to discover high-impact research directions.  |
| [browser-harness](plugins/taosheng-environment/skills/browser-harness/SKILL.md) | Direct browser control through the locally installed browser-harness command.  |
| [carl-idea-king](plugins/taosheng-environment/skills/carl-idea-king/SKILL.md) | 详见技能说明 |
| [codex-cli-model-bridge](plugins/taosheng-environment/skills/codex-cli-model-bridge/SKILL.md) | Install, audit, repair, and manage Codex custom model |
| [creative-thinking-for-research](plugins/taosheng-environment/skills/creative-thinking-for-research/SKILL.md) | Applies cognitive science frameworks for creative thinking to CS and AI research ideation.  |
| [cross-domain-borrow](plugins/taosheng-environment/skills/cross-domain-borrow/SKILL.md) | 跨领域借解提示语原文。用户在本行业里想不出解法、需要从其他领域借鉴机制时使用。触发词包括 跨领域、别的行业怎么解决、换个视角、类比一下、借鉴其他领域、有没有类似的问题被解决过。产出至少三个远距离领域的同构案例和可迁移机制 |
| [eli5](plugins/taosheng-environment/skills/eli5/SKILL.md) | 大图小字讲解法提示语原文。用户想快速看懂一个陌生主题、希望图多字少地讲清楚、提到 eli5 或完全不懂某个东西时使用。要图、要一个能打开的页面时用它，只要文字讲清楚就不用它。触发词包括 大图小字、eli5、当我什么都不懂 |
| [expert-panel](plugins/taosheng-environment/skills/expert-panel/SKILL.md) | 专家会诊提示语原文。用户的问题需要多个互补专业视角配合、单一视角给不出好方案时使用。触发词包括 专家会诊、多个视角看看、找几个专家、多学科分析、组个专家团、让他们互相质疑。产出三种互补视角的分歧点和综合方案，含适用条件、 |
| [explaining-in-plain-language](plugins/taosheng-environment/skills/explaining-in-plain-language/SKILL.md) | 用户说「说人话」「用人话给我解释一下」「能不能说人话」「讲清楚点」「我不是程序员出身」时使用；他让你解释一个他不熟悉的系统、机制、技术名词、医学概念，或解释他自己的某套流程/配置/数据时使用；他要把某个东西讲给外行同事或 |
| [fact-check](plugins/taosheng-environment/skills/fact-check/SKILL.md) | 事实核查提示语原文。用户想核实一个说法、观点、结论、数据或方案是否成立时使用。触发词包括 事实核查、帮我核查、这是真的吗、查证一下、有没有幻觉、这个数据靠谱吗、审查这个观点、fact check。需要联网核查，产出五档可 |
| [firecrawl](plugins/taosheng-environment/skills/firecrawl/SKILL.md) | 使用 Firecrawl CLI 搜索、抓取、站点映射与批量提取。用户点名 Firecrawl，或任务需要批量/结构化抓取、原生获取不足且 Firecrawl 适合时使用；普通网页与官方文档优先原生/领域工具，本地文件不 |
| [firecrawl-agent](plugins/taosheng-environment/skills/firecrawl-agent/SKILL.md) | 详见技能说明 |
| [firecrawl-build](plugins/taosheng-environment/skills/firecrawl-build/SKILL.md) | 把已选定的 Firecrawl 接入应用代码。适用于用户点名、现有项目使用 Firecrawl，或方案评估确认它满足网页提取需求的任务；不因应用需要联网就自动安装 SDK、开账户或替换数据后端。 |
| [firecrawl-build-interact](plugins/taosheng-environment/skills/firecrawl-build-interact/SKILL.md) | 在已采用或明确选定 Firecrawl 的应用中实现 /interact 点击、表单和分页；仅用于该后端的应用集成，不接管普通浏览器操作。 |
| [firecrawl-build-onboarding](plugins/taosheng-environment/skills/firecrawl-build-onboarding/SKILL.md) | Get Firecrawl credentials and SDK setup into a project.  |
| [firecrawl-build-scrape](plugins/taosheng-environment/skills/firecrawl-build-scrape/SKILL.md) | 在已采用或明确选定 Firecrawl 的应用中实现 /scrape 单页正文、HTML、链接或结构化提取；不因普通应用输入有 URL 就选择该供应商。 |
| [firecrawl-build-search](plugins/taosheng-environment/skills/firecrawl-build-search/SKILL.md) | 在已采用或明确选定 Firecrawl 的应用中实现 /search 检索与结果提取。普通一次性搜索和未确定供应商的应用选型不触发。 |
| [firecrawl-crawl](plugins/taosheng-environment/skills/firecrawl-crawl/SKILL.md) | 详见技能说明 |
| [firecrawl-developer-index](plugins/taosheng-environment/skills/firecrawl-developer-index/SKILL.md) | 在已选择 Firecrawl 的开发资料检索流程中搜索 issues、PR、README 和文档；适用于点名该索引或常规源码/官方文档检索不足，不接管所有 API、库和错误问题。 |
| [firecrawl-download](plugins/taosheng-environment/skills/firecrawl-download/SKILL.md) | 详见技能说明 |
| [firecrawl-interact](plugins/taosheng-environment/skills/firecrawl-interact/SKILL.md) | 在 Firecrawl scrape 结果上通过 scrape ID 继续点击、表单和分页；用户选择 Firecrawl 或原生读取不足时使用，不接管用户指定浏览器和已有会话。 |
| [firecrawl-map](plugins/taosheng-environment/skills/firecrawl-map/SKILL.md) | 详见技能说明 |
| [firecrawl-monitor](plugins/taosheng-environment/skills/firecrawl-monitor/SKILL.md) | 创建或管理 Firecrawl 托管的网站变化监控、webhook/email 告警；用于用户明确选择 Firecrawl 监控或维护已有 Firecrawl monitor。普通提醒、追踪和回访优先宿主 automat |
| [firecrawl-parse](plugins/taosheng-environment/skills/firecrawl-parse/SKILL.md) | 用户点名 Firecrawl Parse，或本地文档提取失败且云解析适合时，把文档解析为 Markdown。普通本地读取优先现有本地/格式工具；需辨明文件会上传的目标与处理用途。 |
| [firecrawl-research-index](plugins/taosheng-environment/skills/firecrawl-research-index/SKILL.md) | 使用 Firecrawl research paper index 做语义文献检索、相关扩展与文内核验，适用于用户点名或现有文献检索不足且该索引适合的任务；不替代所有文献任务的领域检索工具。通过 firecrawl_re |
| [firecrawl-scrape](plugins/taosheng-environment/skills/firecrawl-scrape/SKILL.md) | 通过已选定的 Firecrawl 提取已知 URL 正文或 JS 页面；用于用户点名、批量抓取或原生读取不足的后备，不因出现 URL 就强制触发。 |
| [firecrawl-search](plugins/taosheng-environment/skills/firecrawl-search/SKILL.md) | 在已选择 Firecrawl 的检索流程中搜索网页并提取正文；用户点名或原生检索不足时使用。普通实时问答与官方文档核验不因此自动切换供应商。 |
| [first-principles](plugins/taosheng-environment/skills/first-principles/SKILL.md) | 第一性原理提示语原文。用户的方案在反复打补丁、陷入路径依赖、想回到问题本质重新推导时使用。触发词包括 第一性原理、回到本质、从头推一遍、别打补丁了、推倒重来、这么做的根本原因是什么。产出原方案里只在修补表面的部分，加一条 |
| [gemini-dispatch](plugins/taosheng-environment/skills/gemini-dispatch/SKILL.md) | 当用户说「交给 Gemini」「问问 Gemini」「用 Gemini 跑」「agy」「Antigravity」时使用；需要第二个模型交叉核对当前结论、需要 Google 搜索作为第二条线索来源时使用；长文档、大批量材料 |
| [geo-sleuth](plugins/taosheng-environment/skills/geo-sleuth/SKILL.md) | Geolocate or chronolocate a photo with tool-verified reasoning (where was this taken / when was it taken / pho |
| [gzh-design](plugins/taosheng-environment/skills/gzh-design/SKILL.md) | 微信公众号文章排版引擎，将 Markdown 转换为可直接粘贴到公众号编辑器的 HTML。主题风格从 references/theme-index.md 注册的自定义主题库中选取，自动章节编号、关键词下划线标记、引言卡片 |
| [hand-drawn](plugins/taosheng-environment/skills/hand-drawn/SKILL.md) | 制作手绘插画、提示词和逐笔绘制视频；用于手绘板、白板动画、持笔手跟随描线、分部位上色，以及多条手绘视频的差异化重做。按内容设计画面和绘制过程，复用引擎并核验成片。只要提示词时不生图，普通视频剪辑不触发。 |
| [hatch-pet](plugins/taosheng-environment/skills/hatch-pet/SKILL.md) | 从角色图或品牌参考创建、修复并验证 Codex v2 动画宠物；支持完整 spritesheet、动画验收与安装包。 |
| [hidden-talent](plugins/taosheng-environment/skills/hidden-talent/SKILL.md) | 深度天赋挖掘提示语原文。用户想找到自己被忽视或压抑的天赋、怀疑自己没有天赋、想要一份个人天赋使用说明书时使用。这是一次半小时以上的多轮深度对话，一次只问一个问题，最多十个主问题，最后产出一万字左右的说明书。 |
| [hithink-finance](plugins/taosheng-environment/skills/hithink-finance/SKILL.md) | 当用户或 Agent 需要通过同花顺金融数据服务获取、查询、同步、分析或导出 A 股行情、财报、估值、指数、板块、基金、特色数据或本地 DuckDB 数据，或需要选择、安装、配置、诊断 REST API、MCP、hith |
| [hithink-finance-data](plugins/taosheng-environment/skills/hithink-finance-data/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 管理本地 DuckDB：初始化、同步、状态、校验、迁移、修复、清理、删除、只读 SQL、导出；远端实时数据转对应业务 skill。 |
| [hithink-finance-financials](plugins/taosheng-environment/skills/hithink-finance-financials/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 查询 A 股利润表、资产负债表、现金流量表、财务指标、年度/季度报告窗口；价格行情转 hithink-finance-market，指数财务不在本 skil |
| [hithink-finance-fund](plugins/taosheng-environment/skills/hithink-finance-fund/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 查询基金档案、公司、经理、财务、诊断、资讯、募集、持仓、净值、收益、持有人结构、ETF/LOF 快照和 ETF 历史；A 股行情转 hithink-fina |
| [hithink-finance-index](plugins/taosheng-environment/skills/hithink-finance-index/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 查询同花顺指数/概念/行业/地域/特色指数目录、指数成分股、指数快照和指数历史；个股行情转 hithink-finance-market，股票代码搜索转 h |
| [hithink-finance-market](plugins/taosheng-environment/skills/hithink-finance-market/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 获取 A 股集合竞价快照与短期基准、普通行情快照、历史 K 线、交易日历、复权因子、公司行动和本地全市场面板；涨跌停、炸板、热榜、龙虎榜、异动和游资机构榜转 |
| [hithink-finance-research](plugins/taosheng-environment/skills/hithink-finance-research/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 基于已有本地数据做中立研究准备、面板导出、只读 SQL、描述性统计和可复现实证数据集；不用于实时取数、荐股、择时、组合建议或投资结论。 |
| [hithink-finance-shared](plugins/taosheng-environment/skills/hithink-finance-shared/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 做安装后自检、API Key 认证、配置、版本更新、诊断、卸载、Skills 安装/同步/移除，以及 JSON 输出、安全和大结果处理规则；不要用于行情、财 |
| [hithink-finance-special-data](plugins/taosheng-environment/skills/hithink-finance-special-data/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 查询特色数据：涨停池、跌停池、炸板池、连板天梯、个股异动、异动原因、飙升榜、热股榜、热度历史/趋势、龙虎榜、游资和机构榜；普通行情转 hithink-fin |
| [hithink-finance-symbol](plugins/taosheng-environment/skills/hithink-finance-symbol/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 处理标的目录、股票/指数代码搜索、名称或 ticker 到 thscode 的消歧、A 股或指数代码表分页导出；行情价格转 hithink-finance- |
| [hithink-finance-valuation](plugins/taosheng-environment/skills/hithink-finance-valuation/SKILL.md) | 用于 Agent 通过 hithink-finance CLI 查询 A 股当前估值快照，包括市盈率、市净率、市销率和市现率；历史估值、ROE 和投资建议不在本 skill 范围。 |
| [horizontal-vertical-analysis](plugins/taosheng-environment/skills/horizontal-vertical-analysis/SKILL.md) | 横纵分析法提示语原文。用户想深度研究一个陌生的产品、公司、人物、技术、行业或事件时使用。触发词包括 横纵分析、深度研究、帮我搞懂这家公司、研究一下这个赛道、写份研究报告、纵向历史横向对比、deep research。建议 |
| [huashu-motion](plugins/taosheng-environment/skills/huashu-motion/SKILL.md) | Motion graphics, launch videos and explainers as editable code. A director picks the motion language for your  |
| [human-writing](plugins/taosheng-environment/skills/human-writing/SKILL.md) | 只在两种情况使用。一是写或改中文科普文章（公众号科普、给家长或大众看的健康科普稿）；二是用户点名要用 human-writing 或活人感写作。其余中文写作一律不触发，用模型原生写法，包括口播、视频旁白、演讲稿、人物档案 |
| [inversion](plugins/taosheng-environment/skills/inversion/SKILL.md) | 逆向法提示语原文。用户担心方案有坑、想提前排雷、做风险预案、检验计划健壮性时使用。触发词包括 逆向法、怎么会失败、提前排雷、风险预案、什么会出错、怎么才能搞砸、反面思考、inversion、防护措施、保证失败。产出保证失 |
| [jev-browser](plugins/taosheng-environment/skills/jev-browser/SKILL.md) | 用户在 Microsoft Edge 中需要多步搜索、点击、填写或翻页时，用 JEV 选择动作、轻量模型填字，在原生浏览器工具内连续执行并核验。也用于明确指定 JEV 或 jev-ultrafast；单次明确点击直接执行 |
| [johari-window](plugins/taosheng-environment/skills/johari-window/SKILL.md) | 乔哈里视窗协作提示语原文。用户想设定 AI 的协作方式、抱怨回答不贴需求、嫌追问太多或不问就猜、希望先判断信息状态再回应时使用。触发词包括 乔哈里、视窗、开放区、盲区、隐藏区、未知区、协作模式、别猜我的需求、先搞清楚再答 |
| [karpathy-guidelines](plugins/taosheng-environment/skills/karpathy-guidelines/SKILL.md) | Behavioral guidelines to reduce common LLM coding mistakes.  |
| [kaz-leader](plugins/taosheng-environment/skills/kaz-leader/SKILL.md) | 把一句话的想法拆成 AI agent 能独立跑完的目标任务书。用户说「帮我给 agent 写个目标」「帮我详细拆一下这个目标」「写个任务书/brief 给 agent」「写个 goal 提示词」「让 agent 自己跑这 |
| [kaz-neat-freak](plugins/taosheng-environment/skills/kaz-neat-freak/SKILL.md) | 详见技能说明 |
| [laoyeye](plugins/taosheng-environment/skills/laoyeye/SKILL.md) | 用户说“老爷爷”“呼叫老爷爷”“问问老爷爷”“让老爷爷看看”或 laoyeye 请求帮助时使用。结合当前处境，从收录的25种提示词与skill中匹配并执行合适的方法。中文称呼表示调用技能；日常谈论现实老人、否定调用或仅引 |
| [leader](plugins/taosheng-environment/skills/leader/SKILL.md) | 为用户明确请求的 agent 目标、任务书、brief 或 Goal 提示词定义目标、范围、验收和接力。先利用现有材料与环境核实必要事实，只澄清会实质改变任务的缺失信息；交付可直接复制执行的简洁任务书。普通“帮我做某事” |
| [life-design](plugins/taosheng-environment/skills/life-design/SKILL.md) | 人生设计术提示语原文。基于斯坦福人生设计方法，用户想看清现在的位置、分清重力问题和可设计的真问题、规划未来五年时使用。这是一次多轮深度对话，六到九个主问题，最后产出八千到一万两千字的个人人生设计蓝图和三个奥德赛计划。 |
| [making-videos](plugins/taosheng-environment/skills/making-videos/SKILL.md) | 制作或修改讲解、叙事、宣传与社会主题短片，把主题、文章或剧本做成可审阅的视觉方案、样片和成片；覆盖画风、镜头、声音与实际验片。纯文字写作和真实拍摄旅行素材的常规剪辑不使用。 |
| [markitdown](plugins/taosheng-environment/skills/markitdown/SKILL.md) | 用本地 MarkItDown 把文档转成 Markdown/text；适用于主要需要文本提取且转换有帮助的读取、摘要或比较。纯文本直接读；Word/PDF/PPTX 的布局审阅、编辑和最终交付以及表格公式分析，由对应格式 |
| [matt-diagnosing-bugs](plugins/taosheng-environment/skills/matt-diagnosing-bugs/SKILL.md) | Diagnosis loop for hard bugs and performance regressions.  |
| [matt-grill-me](plugins/taosheng-environment/skills/matt-grill-me/SKILL.md) | A relentless interview to sharpen a plan or design. |
| [matt-grilling](plugins/taosheng-environment/skills/matt-grilling/SKILL.md) | Grill the user relentlessly about a plan, decision, or idea.  |
| [matt-teach](plugins/taosheng-environment/skills/matt-teach/SKILL.md) | Teach the user a new skill or concept, within this workspace. |
| [med-science-video](plugins/taosheng-environment/skills/med-science-video/SKILL.md) | 制作医学与健康科普、医院或科室介绍视频，将文章或讲稿转成可审阅的脚本、样片与成片；负责医学事实、画面核验及审阅边界。纯文字科普和非医学短片不使用。 |
| [memory-parable](plugins/taosheng-environment/skills/memory-parable/SKILL.md) | 记忆寓言提示语原文，重点是记住，理解交给别的，寓言讲完还会逐个隐喻对应，无聊的时候拿来消遣也合适。用户想用故事记住一个抽象或陌生的概念，或者只是无聊想让 AI 讲个有意思的东西时使用。触发词包括 记忆寓言、用故事帮我记、 |
| [migrate-to-codex](plugins/taosheng-environment/skills/migrate-to-codex/SKILL.md) | Migrate supported instruction files, skills, agents, and MCP config into Codex project and global files. |
| [minimax-h3-director](plugins/taosheng-environment/skills/minimax-h3-director/SKILL.md) | 统筹用户的 MiniMax H3 视频，从想法、剧本分镜、本地生成、剪辑声音到完整成片；续做、修改或归档 H3 项目时也用。Codex 负责创作与调度，Gemini 批量检查画面，脚本核验技术项。不接管普通视频转写或纯音 |
| [minimum-experiment](plugins/taosheng-environment/skills/minimum-experiment/SKILL.md) | 最小实验提示语原文。用户纠结的事情靠继续想已经不会更清楚、需要用现实反馈来验证时使用。触发词包括 最小实验、先试试、怎么验证、别空想了、跑个实验、小成本试错、七天验证、已经反复纠结过很多轮、想了很久还是选不出来。产出待验 |
| [nature-academic-search](plugins/taosheng-environment/skills/nature-academic-search/SKILL.md) | 详见技能说明 |
| [nature-citation](plugins/taosheng-environment/skills/nature-citation/SKILL.md) | 为稿件分段寻找 Nature/CNS 及其子刊的支撑文献，核验论据与引用对应，并导出参考文献管理器文件。 |
| [nature-data](plugins/taosheng-environment/skills/nature-data/SKILL.md) | 编写或审阅 Nature 系列稿件的数据可用性声明、数据共享方案及数据集引用；处理仓储选择和受限数据说明。 |
| [nature-figure](plugins/taosheng-environment/skills/nature-figure/SKILL.md) | 用 Python 或 R 制作、修订和验证期刊投稿级科研图，尤其 Nature 系列；保留可复现源文件与实际导出。不用于仪表盘或设计类信息图。 |
| [nature-paper2ppt](plugins/taosheng-environment/skills/nature-paper2ppt/SKILL.md) | 将科研论文或阅读材料制作成可交付的中文学术 PPTX，适用于文献汇报、组会和学术分享，包含图证据选择与渲染验收。 |
| [nature-polishing](plugins/taosheng-environment/skills/nature-polishing/SKILL.md) | 将学术草稿润色、重组或翻译为 Nature 风格英文；适用于论文段落、章节和标题的论证与语言修改。 |
| [no-fluff-output](plugins/taosheng-environment/skills/no-fluff-output/SKILL.md) | 直给输出法提示语原文。用户抱怨 AI 说话啰嗦绕圈子、想要更直接可执行的回答、看长篇容易走神时使用。触发词包括 别废话、直接说重点、说结论、别绕弯子、有话直说、别来虚的、先说怎么做、拒绝废话、ADHD 友好、专注力不够。 |
| [parable](plugins/taosheng-environment/skills/parable/SKILL.md) | 寓言故事提示语原文，帮你理解并记住一个概念，最后带两道检验题。用户看了几遍还是不懂、别人解释过还是没听懂、直接解释已经失败过时使用。触发词包括 用寓言讲讲、讲个故事帮我理解、给我打个比方、寓言、5 分钟搞懂、看了几遍还是 |
| [pdf](plugins/taosheng-environment/skills/pdf/SKILL.md) |  |
| [playwright](plugins/taosheng-environment/skills/playwright/SKILL.md) |  |
| [presenting-conference-talks](plugins/taosheng-environment/skills/presenting-conference-talks/SKILL.md) | Generates conference presentation slides (Beamer LaTeX PDF and editable PPTX) from a compiled paper with speak |
| [project-to-chatgpt](plugins/taosheng-environment/skills/project-to-chatgpt/SKILL.md) | 将指定本地项目接入已有只读 MCP，供本人在 ChatGPT 中讨论；支持新增或停用项目、核对可读范围、检查连接与实际查询验收。仅讨论可行性时不修改配置，不用于泛化 MCP 开发或把每个项目重新建成独立服务。 |
| [qiaomu-bento-ppt](plugins/taosheng-environment/skills/qiaomu-bento-ppt/SKILL.md) | 创建或编辑乔木风格、可离线编辑的单文件 .bento.html 演示；用于明确要求 bento 幻灯片的任务，不用于 PPTX 或 bento 应用源码开发。 |
| [reverse-engineer-anything](plugins/taosheng-environment/skills/reverse-engineer-anything/SKILL.md) | Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA. Use s |
| [reverse-teardown](plugins/taosheng-environment/skills/reverse-teardown/SKILL.md) | 反向拆解提示语原文。用户看到一个优秀的产品、网页、方案、流程、数据看板或作品，想学会它为什么有效时使用。触发词包括 反向拆解、拆解这个、它为什么做得好、我想模仿、逆向拆解、拆解这个好范例、这个牛在哪。产出可复用规律加一份 |
| [socratic-inquiry](plugins/taosheng-environment/skills/socratic-inquiry/SKILL.md) | 苏格拉底式问诊提示语原文。用户说不清自己到底想问什么、问题一团乱、想先把问题问清楚再动手时使用。触发词包括 苏格拉底、苏格拉底式提问、帮我问诊、帮我理清问题、我不知道该问什么、先别给建议、我到底想问什么。一次只问一个问题 |
| [stage-reporting](plugins/taosheng-environment/skills/stage-reporting/SKILL.md) | 当用户询问或要求“阶段完成后用人话汇报”“给项目装汇报机制”时，先检查全局主动规则；全局已覆盖时默认不改项目。只有用户明确要求严格拦截、Stop hook 或项目级兜底时，才为当前项目安装或维护可选 hook。也用于诊断 |
| [steelman-both-sides](plugins/taosheng-environment/skills/steelman-both-sides/SKILL.md) | 双向钢人论证提示语原文。用户在两个选项之间犹豫不决、需要做决策时使用。触发词包括 钢人、双向钢人、steelman、两个选项选哪个、帮我做个决定、正反两面都说最强理由、我该选 A 还是 B。产出两边的最强论证、真正分歧、 |
| [stock-buddy](plugins/taosheng-environment/skills/stock-buddy/SKILL.md) | 个人投资分析（双档）。常规档：主线论证（提名答辩/主线体检/退潮复核）、单标的与板块速查、持仓体检，给状态层+信号判定+纪律护栏+危险信号。金融专家模式（opt-in，先确认）：5-agent 蜂群做五维深度分析，给明确 |
| [stock-daily](plugins/taosheng-environment/skills/stock-daily/SKILL.md) | 投资笔记 v3 的唯一日更技能——复盘。当用户要求回顾最新交易日的盘面、主线、持仓或操作时使用，触发表达包括“复盘”“今日复盘”“收盘复盘”“看下今天”“今天盘面怎么样”，以及**不点名具体主线**的泛问“主线还活着吗” |
| [stock-screener](plugins/taosheng-environment/skills/stock-screener/SKILL.md) | 载体筛选（v3 主用）——给定一条已立项主线，筛出可买载体（ETF + 龙头股）并做强弱排序，附排序理由，写回主线页「载体清单」。也保留 v2 的策略选股工具库（放量突破/低位反转/业绩成长/主力异动等条件筛股）。只筛不 |
| [sweety-handdraw-video](plugins/taosheng-environment/skills/sweety-handdraw-video/SKILL.md) | 根据主题、文章或讲解稿制作带封面的完整手绘讲解视频。按内容设计分镜、插画与文字，以实际配音安排逐字、分部位描线和填色，检查后交付视频。用于手绘视频、白板动画、文章转手绘讲解；不用于只生成静态插画或只写口播稿。 |
| [teach](plugins/taosheng-environment/skills/teach/SKILL.md) | 以真实工作或学习材料为起点，通过短课、先答后教、证据核对、迁移练习和跨会话进度记录帮助用户掌握可迁移能力。仅在用户明确调用 $teach 时使用；普通解释、项目执行和未点名 teach 的学习请求不自动触发。 |
| [two-layer-explain](plugins/taosheng-environment/skills/two-layer-explain/SKILL.md) | 双层解释法提示语原文。用户遇到听不懂的概念、名词、报错、技术栈，想要一次讲透时使用。触发词包括 双层解释、小白版、专业版、通俗讲一遍、把我当小白、这个概念是什么意思、讲讲什么是、贴着代码或文档问、这个报错什么意思、马上就 |
| [video-to-subtitle-summary](plugins/taosheng-environment/skills/video-to-subtitle-summary/SKILL.md) | 将抖音等短视频链接或本地视频、音频转为高准确率中文转写、字幕、最小校订稿和一篇以用户共鸣点为中心的可读文章；支持腾讯云极速版与 Qwen ASR、持久缓存、关键帧复核、YouTube 字幕、AI Douyin 历史任务、 |
| [video-workbench](plugins/taosheng-environment/skills/video-workbench/SKILL.md) | 打开或使用涛生的视频工作台，按题材挑选视频画风、动效与制作流程，组合可复制的制作需求。用于视频风格选型、样片浏览和看板使用；不替代实际渲染工具，不自动安装或更新上游技能。 |
| [wechat-article-search](plugins/taosheng-environment/skills/wechat-article-search/SKILL.md) | 搜索微信公众号文章并抓取全文为 Markdown。当用户要查微信公众号内容、搜公众号文章、找某个主题的公众号推文、给出公众号文章链接要求阅读或总结，或需要中文优质长文信源（尤其医学、心理、精神科、法律等专业领域，这些内容 |
| [wechatide-skill](plugins/taosheng-environment/skills/wechatide-skill/SKILL.md) | 详见技能说明 |
| [workbuddy-cli-model-bridge](plugins/taosheng-environment/skills/workbuddy-cli-model-bridge/SKILL.md) | Install, audit, repair, and manage a loopback-only CLIProxyAPI |
| [workbuddy-dispatch](plugins/taosheng-environment/skills/workbuddy-dispatch/SKILL.md) | 当用户明确说「分发给 WorkBuddy / codebuddy / GLM / kimi / minimax / deepseek」，或点名要这些模型做交叉验证、批量翻译/摘要/格式转换、后台长跑任务时使用。用户需要混 |
