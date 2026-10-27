# Troubleshooting and rollback

Classify the failing layer before changing credentials or reinstalling software.

## `cliproxy_missing`

Run `bootstrap --apply`. If Homebrew is absent, install it interactively from its official source, then rerun bootstrap. Do not pipe an unverified installer into a shell.

## `public_bind_requires_approval`

The existing config does not explicitly bind to loopback. Determine whether another local or remote client depends on the current bind. If remote access is unintended, rerun:

```bash
python3 <skill-dir>/scripts/bridge.py bootstrap --apply --allow-rebind-local
```

If remote access is intentional, stop. This Skill does not manage remotely exposed proxies.

## `bridge_secret_missing`

Run `bootstrap --apply`. This creates a dedicated local client key and adds it to the top-level CLIProxyAPI `api-keys` list without replacing existing keys.

Provider OAuth changes do not require a new bridge key.

## Proxy is running but `/v1/models` fails

Check, in order:

1. endpoint port from the active config
2. dedicated client key exists in both bridge state and CLIProxyAPI config
3. active process is using the config file reported by `audit`
4. config is valid and service logs show a successful reload

Avoid editing a second, inactive config file. Homebrew and manual LaunchAgent deployments commonly use different paths.

## GLM Coding Plan key returns `1113` or missing `glm-5.3`

The key is a coding-subscription credential, not a general BigModel balance pack. Use `https://open.bigmodel.cn/api/coding/paas/v4` on mainland or `https://api.z.ai/api/coding/paas/v4` internationally. The ordinary `/api/paas/v4` URL is the wrong product.

Do not run `authorize glm-coding`. Homebrew CLIProxyAPI 7.2.135 has no `-zai-login`. Add the `glm-coding` compatibility provider, restart the existing proxy once, then `sync --providers glm-coding --apply`. Follow [glm-coding-plan.md](glm-coding-plan.md).

If the route works only after leaving TUN Fake-IP, set that provider entry's `proxy-url: "direct"`. Do not send chatgpt.com DIRECT as a workaround.

Leave `supportsReasoning` off when the reasoning-control probe fails. Internal thinking can still occur.

## Provider models are missing

Run `authorize <provider>` again only when the Provider has no auth file or an authenticated request fails. A CLI login outside CLIProxyAPI is not proof that the proxy has a usable grant.

After OAuth, query `/v1/models` again. If the expected model is absent, it may be unavailable under the account, renamed upstream, excluded by config, or in cooldown. Do not create a fake alias to a nonexistent model.

## Quota recovered but `503 auth_unavailable` persists

Some Provider quota or balance failures can leave CLIProxyAPI's in-memory auth route marked unavailable after the Provider's usage page shows capacity again. Treat this as a runtime-state recovery only when the evidence sequence is:

1. the original upstream response is a quota or balance error such as `402`, `429`, or `usage balance exhausted`
2. later requests fail with `503 auth_unavailable` for the same Provider and model
3. the user confirms the Provider quota has reset or capacity is available again

Inspect only status codes and redacted error fields. Never print request bodies, prompts, images, authorization headers, OAuth URLs, account identifiers, or token-file contents.

Recover the existing deployment in this order:

1. identify the active process, config, and service manager reported by `audit`; do not restart a second deployment
2. restart the existing service once (for a Homebrew-owned deployment, use `brew services restart cliproxyapi`)
3. poll `audit` until the loopback proxy is reachable; an immediate first audit may race service startup
4. confirm the affected model returned to `/v1/models`
5. run `sync --providers <affected-provider> --apply` without `--skip-probes`
6. verify text, streaming, declared optional capabilities, and an idempotent second sync

Keep both the dedicated WorkBuddy client key and the Provider OAuth files unchanged during this recovery. If the upstream quota error persists, stop and report that capacity is still unavailable. Reauthorize only for missing auth or an authentication-specific failure such as `401` or `invalid_grant`; a quota error is not evidence that OAuth expired.

## Text works but images or tools fail

This is a capability-path failure. Keep the model registered only if text and streaming work; set the failed optional capability to `false`. Check:

- whether WorkBuddy sent `image_url` or `tool_choice`
- whether CLIProxyAPI selected the intended Provider route
- whether an alias collided with another Provider
- whether the upstream model supports the feature through this protocol

Do not declare the capability based on the upstream model alone.

## WorkBuddy shows reasoning headings instead of a full thought process

Reasoning controls and reasoning visibility are separate. A successful reasoning probe proves that the route accepts the control; it does not grant access to a Provider's private chain of thought. WorkBuddy can display only the reasoning summary or progress events that the compatible API returns.

For teaching or recording, ask the model to put an explicit problem decomposition, assumptions, checks, and decision rationale in its normal answer. Do not describe a generated explanation as hidden chain of thought.

## A requested Fast model is absent

Upgrade or inspect CLIProxyAPI before creating aliases. A working Fast route requires both a distinct client-visible alias and a Provider-supported priority/latency control. For OAuth-backed Codex routes, current CLIProxyAPI supports `oauth-model-alias` plus a matching `payload.override` rule that injects `service_tier: priority`. Any alias that remaps `gpt-5.6-sol` must set `fork: true`; otherwise the native ID disappears from `/v1/models` and Codex Desktop fails with `unknown provider for model gpt-5.6-sol`. WorkBuddy may keep `gpt-5.6-sol-standard` / `gpt-5.6-sol-fast` as extra aliases, but Codex itself must keep requesting `gpt-5.6-sol`.

After configuring the alias through CLIProxyAPI's documented configuration or loopback Management API, rerun `/v1/models` and the full bridge probes. Do not register the alias if it is missing from the model list or if the route behaves like an unsupported model.

## Manual WorkBuddy model conflict

The bridge refuses to overwrite an existing model ID it does not own. Preserve the manual entry. Resolve by choosing a distinct verified alias or explicitly migrating that entry after comparing every field and backing up the file.

## WorkBuddy does not show the new model

Confirm `models.json` is valid JSON, mode `0600`, and the current WorkBuddy log recorded a model-config reload. Reopen model settings or start a new conversation. Rewriting identical JSON will not fix a stale application cache.

## Rollback

Credential-bearing backups use:

```text
<filename>.backup-YYYYMMDD-HHMMSS
```

To roll back:

1. stop the affected write or service restart
2. verify the backup belongs to the current source file
3. preserve the failed version for diagnosis outside any repository
4. atomically restore the backup with mode `0600`
5. restart or wait for hot reload
6. rerun `audit` and a text probe

Never roll back OAuth files by copying tokens from another CLI. Reauthorize through the Provider instead.
