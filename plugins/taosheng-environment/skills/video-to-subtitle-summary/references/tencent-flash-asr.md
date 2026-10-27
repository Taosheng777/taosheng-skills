# 腾讯云录音文件识别极速版

## 配置

在 skill 的本地 `.env` 或系统环境中配置，禁止把真实值写进回复、日志、vault 或版本库：

```dotenv
ASR_BACKEND=tencent
TENCENT_APPID=
TENCENT_SECRET_ID=
TENCENT_SECRET_KEY=
```

默认固定使用标准中文引擎 `16k_zh`，开启 `speaker_diarization=1` 与 `word_info=2`。不要自动改用不在标准免费额度内的 `16k_zh_en`。

## 调用与输出

- 接口：`POST https://asr.cloud.tencent.com/asr/flash/v1/<appid>`。
- 输入：脚本统一转为 16 kHz、单声道 MP3；单文件不得超过 100 MB。
- 鉴权：HMAC-SHA1。`appid` 只放 URL 路径，不加入排序签名参数。
- 输出：`tencent-raw.txt`、`tencent-corrected.txt`、`tencent-raw.srt`、`tencent-sentences.tsv`、`tencent-result.json`。
- `tencent-corrected.txt` 初次与原文相同，只允许做有声音、画面或可靠来源支持的最小校订。

## 排错

- 缺配置：只报告缺少哪个环境变量，不展示已配置的值。
- `code 4003 service not opened`：在腾讯云 ASR 控制台开通录音文件识别极速版。
- `code 4004 resource pack exhausted`：确认仍使用 `16k_zh`，并检查标准引擎免费额度或资源包；不要静默切换收费引擎。
- 签名错误：确认 SecretId 与 AppID 属于同一账号，并检查 `appid` 未进入签名参数排序。
- 当前 AppID 对应的 SecretId / SecretKey 曾经明文提供过；重新启用前优先在控制台轮换，再只写入本地 `.env`。
