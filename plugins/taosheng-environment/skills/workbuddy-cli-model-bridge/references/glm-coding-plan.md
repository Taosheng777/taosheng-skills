# GLM Coding Plan

Use this path when the user has a **GLM Coding Plan** key (Lite / Pro / Max) and wants `glm-5.3` in WorkBuddy alongside existing models.

This is not 智谱清言 chat OAuth. Do not scrape the chat website, copy cookies, or reuse another CLI's token file.

## Verified route

CLIProxyAPI Homebrew `7.2.135` has no `-zai-login`. Upstream PR `router-for-me/CLIProxyAPI#3928` is still open. Until that flag ships in a stable Homebrew release, use the official OpenAI-compatible Coding Plan endpoint.

| Region | Base URL | Notes |
|---|---|---|
| China mainland (verified) | `https://open.bigmodel.cn/api/coding/paas/v4` | Set CLIProxyAPI per-key `proxy-url: "direct"` so the request does not enter a TUN Fake-IP path |
| International | `https://api.z.ai/api/coding/paas/v4` | Use only when the key was minted on z.ai |

The ordinary platform URL (`/api/paas/v4`) rejects Coding Plan keys with `1113` insufficient balance. Do not fall back to it.

Do not run `authorize glm-coding`. The bundled manifest has no `login_flag`. Put the key only in CLIProxyAPI config, mode `0600`.

## CLIProxyAPI fragment

Append a dedicated compatibility provider. Keep existing `openai-compatibility` entries. Never print the key.

```yaml
openai-compatibility:
  - name: "glm-coding"
    base-url: "https://open.bigmodel.cn/api/coding/paas/v4"
    api-key-entries:
      - api-key: "<coding-plan-key>"
        proxy-url: "direct"
    models:
      - name: "glm-5.3"
        alias: "glm-5.3"
        display-name: "GLM 5.3"
        max-context-length: 1048576
        image: false
        input-modalities: [text]
        output-modalities: [text]
```

Restart the active CLIProxyAPI service once, then confirm `/v1/models` lists `glm-5.3` with `owned_by: glm-coding`.

## Bridge sync

```bash
python3 <skill-dir>/scripts/bridge.py sync --providers glm-coding --apply
```

Live verification on this route:

- text, streaming, tools, and the declared 128000 output-limit probe pass
- image input is off
- the reasoning-control probe fails; leave `supportsReasoning: false`. The upstream may still think internally. Do not advertise a WorkBuddy reasoning toggle.

Preserve every existing managed and manual WorkBuddy model. A second sync must report `glm-5.3` unchanged.

Ask the user to reopen WorkBuddy model settings or start a new conversation.

## Stability rules

- Do not wait for unmerged OAuth as a blocker when a Coding Plan key already exists.
- Do not send this key through a Clash TUN Fake-IP hop on mainland.
- Do not register Fast aliases or extra GLM versions unless the user asked and each ID passed probes.
- Coding Plan keys are limited to vendor-supported coding tools. Report that constraint; do not disguise the client.
