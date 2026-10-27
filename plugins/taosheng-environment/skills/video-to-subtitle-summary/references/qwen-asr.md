# Qwen ASR 配置与排错

## 配置

在 skill `.env` 或进程环境中配置：

```bash
ASR_BACKEND=qwen
DASHSCOPE_API_KEY=your_key
QWEN_LANGUAGE=zh
QWEN_ENABLE_ITN=false
QWEN_ENABLE_WORDS=true

# 可选：业务空间专属地址；不填时使用北京地域公共地址
DASHSCOPE_API_BASE=
DASHSCOPE_COMPATIBLE_BASE=
```

不要在命令参数、聊天、日志、Obsidian、`manifest.json` 或识别结果中写 Key。

## 模型与输出

| 模型 | 选择 | 输入 | 时间戳 |
| --- | --- | --- | --- |
| `qwen3-asr-flash` | ≤ 5 分钟 | Base64 Data URL | 无原生句级时间戳 |
| `qwen3-asr-flash-filetrans` | > 5 分钟，或强制精确字幕 | 临时 OSS URL，异步 | 句级；`enable_words=true` 时含字级 |

短模型生成的 SRT 只有一个覆盖整段音频的 cue，`manifest.timestamp_quality` 为 `whole_audio_only`。需要可定位字幕时强制 `--qwen-model filetrans`。

## 文件

- `qwen-raw.txt`：原始识别文本。
- `qwen-corrected.txt`：最小校订稿；初次生成与原文相同，核对后只改确定错误。
- `qwen-raw.srt`：字幕。
- `qwen-sentences.tsv`：句级时间轴。
- `qwen-result.json`：识别结果；不保存提交、轮询或带签名的临时 URL。
- `manifest.json`：缓存索引和非秘密元数据。
- `写作素材.md`：文章阶段唯一默认输入。

确认文章无误后，`--cleanup-video --confirm-note-reviewed` 只删除 `manifest.owned_video_paths` 中受控目录内的视频，并在 manifest 记录删除时间、路径数量与预计释放字节。音频和所有文字产物继续保留，便于以后修订文章。

## 常见故障

- `DASHSCOPE_API_KEY is not configured`：在本地环境或 `.env` 配置，禁止放入 vault。
- 短模型音频 Base64 后超过 10 MB：改用 `--qwen-model filetrans`。
- `InvalidParameter.DataInspection`：确认临时 OSS 请求已带 `X-DashScope-OssResourceResolve: enable`。
- 任务成功但没有结果 URL：保存终态错误，禁止猜测输出；稍后重试或查官方服务状态。
- 视频已处理却再次计费：先检查稳定 `job_id` 与 `manifest.json`，不要直接加 `--force`。

官方参考：

- https://help.aliyun.com/zh/model-studio/non-realtime-speech-recognition-user-guide
- https://help.aliyun.com/zh/model-studio/qwen-asr-api-reference
- https://help.aliyun.com/zh/model-studio/get-temporary-file-url
