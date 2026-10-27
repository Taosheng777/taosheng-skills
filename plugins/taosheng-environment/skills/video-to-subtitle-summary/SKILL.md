---
name: video-to-subtitle-summary
description: 将抖音等短视频链接或本地视频、音频转为高准确率中文转写、字幕、最小校订稿和一篇以用户共鸣点为中心的可读文章；支持腾讯云极速版与 Qwen ASR、持久缓存、关键帧复核、YouTube 字幕、AI Douyin 历史任务、明确写入 Obsidian，以及用户审核确认后安全删除工作流缓存视频。用户发送视频链接或本地媒体，提出视频转文字、视频总结、保存读书笔记、查看视频任务，或确认文章无误并要求删除原视频时使用。
---

# 视频转写与读书笔记

把可重复步骤交给脚本，只让模型阅读一份精简写作素材。禁止打印或复制 API Key、token、cookie、账号与登录态。

## 默认路线

1. 先问或提取用户最有感触的点。用户未说明时继续转写，但不要替用户虚构共鸣；成文时把可能的触动写成开放问题。
2. 对抖音或本地媒体运行：

```bash
python3 "$HOME/.codex/skills/video-to-subtitle-summary/scripts/video_notes.py" \
  "{URL_OR_FILE}" \
  --title "{TITLE}" \
  --author "{AUTHOR}" \
  --resonance "{USER_RESONANCE}"
```

3. 读取命令返回的 `writing_brief`，不要默认读取视频、完整 JSON、SRT 或全部关键帧。
4. 只在关键标题、引文、专有名词与分享文案冲突时查看 `manifest` 中的 `review_frames`，并对 `manifest.outputs.corrected_text` 指向的文件做最小校订。不要润色原始转写。
5. 根据 `写作素材.md` 写一篇自足文章：用户共鸣点是主轴，视频其余内容是背景；默认少量大章节，不拆知识卡。
6. 只有用户当轮明确要求写入私人知识库时，才执行附件导出并写文章：

```bash
python3 "$HOME/.codex/skills/video-to-subtitle-summary/scripts/video_notes.py" \
  "{URL_OR_FILE}" \
  --title "{TITLE}" \
  --author "{AUTHOR}" \
  --resonance "{USER_RESONANCE}" \
  --export-vault "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记"
```

7. 写入前在 `10-文章/` 按来源 URL 查重；已有文章时更新原文。把文章写入 `10-文章/`，把导出结果中的 `corrected_wikilink` 放在文末来源区。
8. 把文章路径和完成状态交给用户检查，然后停止。初次“整理并写入”、文章已经生成或用户预先说“以后可以删除”，都不等于删除授权。
9. 只有用户在看过文章后再次明确表示“确认无误，可以删除原视频”，才运行：

```bash
python3 "$HOME/.codex/skills/video-to-subtitle-summary/scripts/video_notes.py" \
  "{ORIGINAL_URL_OR_FILE}" \
  --cleanup-video \
  --confirm-note-reviewed
```

10. 报告删除路径数量和预计释放空间。用户要求修改文章时，先修改并重新等待确认，不执行清理。

## 缓存与省 token 规则

- 默认缓存：`~/.cache/video-to-subtitle-summary/jobs/{job_id}/`。
- `manifest.json` 状态完整时直接复用，不重新解析、下载或调用 ASR。仅用户明确要求重跑时加 `--force`。
- 下载超时、截断、空文件或拿到网页时直接报错，不留下缓存视频；链接恢复后按原命令重跑即可，不需要 `--force`。
- `--force` 重跑后，未手改的校订稿跟随新识别结果；输出含 `corrected_text_preserved: true` 时保留了之前的人工校订，要告诉用户新识别结果没有覆盖校订稿。
- 缓存只有整段时间戳时，`--qwen-model filetrans` 会报错；用户确认需要精确时间轴并接受重新计费后再加 `--force`。
- 同一视频重复导出时沿用第一次的附件目录；同日同标题的其他视频另建带 `job_id` 的目录，不会互相覆盖。
- 同一任务的转写、导出与清理使用进程锁；遇到 `Job already running` 时等待当前任务结束，不绕过锁或另建缓存重复计费。进程退出后自动释放锁，锁文件本身无需删除。状态文件使用原子替换，写入中断保留完整旧版。
- `--adopt-dir` 不得指向当前任务目录；已有任务直接用原来源命令复用缓存。
- 原视频、音频和关键帧留在缓存，不复制进 Obsidian；正式写入只导出原始转写、最小校订稿、SRT、句级时间轴和完整识别结果。
- 用户审核文章并另行确认后，删除工作流拥有的缓存视频和对应 `/tmp/video_analysis/{job_id}/video.*`；保留音频、转写、字幕、识别 JSON、写作素材和 Obsidian 内容。不得删除用户原始目录中的本地视频。
- 不把完整 API JSON 或长 SRT 放进模型上下文。一般只读 `写作素材.md`；核对单句时再按时间戳局部读取。
- 复用已有临时结果时使用 `--adopt-dir`，避免再次计费：

```bash
python3 "$HOME/.codex/skills/video-to-subtitle-summary/scripts/video_notes.py" \
  "{ORIGINAL_URL}" --adopt-dir "{EXISTING_JOB_DIR}" \
  --title "{TITLE}" --author "{AUTHOR}" --resonance "{USER_RESONANCE}"
```

## ASR 选择

- 默认 `ASR_BACKEND=tencent`，调用腾讯云录音文件识别极速版，固定使用标准中文引擎 `16k_zh`、说话人分离和词级时间戳；不下载本地模型。
- 腾讯后端需要本地配置 `TENCENT_APPID`、`TENCENT_SECRET_ID`、`TENCENT_SECRET_KEY`。缺任一项就停止并提示配置，不在回复、日志或 vault 中展示值。
- 不自动切换到收费的大模型引擎 `16k_zh_en`。用户明确授权并确认计费后，才另行改造。
- Qwen 免费额度当前不可用；只有用户确认额度恢复后才显式设置 `ASR_BACKEND=qwen`。短音频可用 `qwen3-asr-flash`，需要精确时间轴时加 `--qwen-model filetrans`。
- 用户接受准确率下降且不想使用云端时，才显式设置 `ASR_BACKEND=faster-whisper`。脚本会清除代理变量，避免缺少 `socksio` 时失败。
- 读取配置或排错时，按后端查看 [腾讯云极速版参考](references/tencent-flash-asr.md) 或 [Qwen ASR 参考](references/qwen-asr.md)。

## 其他平台与命令

- YouTube：优先运行 `scripts/download_youtube_subtitles.py` 抓现成字幕；无字幕时再把下载的音频交给 `video_notes.py`。
- AI Douyin 历史任务：运行 `scripts/list_ai_douyin_tasks.py`，不得显示 Key。
- 小红书/B 站：可沿用 AI Douyin 解析；下载失败时再使用原有平台工具，不要为了总结盲目安装新依赖。

## 输出边界

- 分开保留原始转写与最小校订稿；校订只改能由声音、画面或可靠来源确认的错误。
- 分享文案与视频画面冲突时，以实际画面和语音为准，并在必要时注明判断依据。
- 关键帧可能含账号号码；默认不写入 vault。
- 删除视频是独立的破坏性步骤。必须同时满足：任务完成、校订稿存在、用户已审阅后明确确认、目标位于受控缓存或对应任务临时目录。任一条件缺失都拒绝删除。
- 不把密钥写死在代码。腾讯凭证使用 `TENCENT_APPID` / `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY`；Qwen 备用 endpoint 使用 `DASHSCOPE_API_BASE` 与 `DASHSCOPE_COMPATIBLE_BASE` 配置。
- 真实外发文章、邮件或公开发布前必须等待用户明确确认。
