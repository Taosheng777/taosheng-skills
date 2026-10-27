# 接入操作

入口：`python3 ~/.codex/skills/project-to-chatgpt/scripts/manage.py`。以下 `<入口>` 代指该命令。

## 项目范围文件

```json
{
  "id": "paper-project",
  "name": "论文项目",
  "root": "/实际项目绝对路径",
  "enabled": true,
  "description": "现行稿与聚合结果；旧稿和原始个体记录不在此次范围",
  "include_paths": ["README.md", "progress.md", "current/"],
  "exclude_paths": ["current/private/"],
  "status_files": ["README.md", "progress.md"]
}
```

示例路径必须换成实际存在的文件。目录末尾 `/` 表示整棵子目录；文件不带 `/` 表示仅该文件。配置中的路径按大小写不敏感匹配，防止 macOS 上大小写变体绕过排除。全局的隐藏目录、凭据文件、链接等限制继续生效。

## 登记、检查和停用

```sh
<入口> registry list
<入口> registry upsert --manifest /实际范围.json
<入口> registry upsert --manifest /实际范围.json --apply
<入口> probe --project paper-project --file README.md --file current/manuscript.docx --deny current/private/records.csv --query 论文关键词 --output /本次work/协议验收.json
<入口> connection stop
<入口> connection start
<入口> connection status
```

停用一个项目：`<入口> registry disable --id paper-project --apply`，然后停止并恢复连接。停用不会删除项目文件。新增项目仅配置变化，7 个工具签名保持不变。

隔离测试用 `registry --config /测试目录/config.json ...` 和 `probe --config /测试目录/config.json ...`，不写真实配置、不连接真实隧道。配置备份在配置文件旁的 `config-backups/`，恢复时明确选择本次变更前版本。

运行配置文件为 `~/Library/Application Support/LocalWorkMCP/config.json`。连接和秘密值由独立运行目录管理，勿把密钥复制到 Skill 或模型提示中。

## ChatGPT 验收请求示例

> 请使用“本地工作资料（只读）”插件，先列出项目，然后只读取 paper-project 的当前进度和现行稿。简要说明研究问题、现行版本和未解决事项，附相对路径、行号、完整 SHA-256、读取时间。不要读取其他项目，不运行代码或修改文件；工具不可用或读取被截断时如实说明。

发送前将项目 ID、读取目标和问题换成刚登记的实际项目。不要在提示中预填希望模型给出的研究数字，以免无法判断是否真正读到了资料。

## 需要额外适配时

数据库、API 指标、图片视觉或特殊格式不等于普通目录读取。评估是否复用原有工具或增加窄接口；不自动开放任意 SQL、Shell、整机目录或写入工具。工具签名若变化，需要重新检查客户端发现与 ChatGPT 刷新。
