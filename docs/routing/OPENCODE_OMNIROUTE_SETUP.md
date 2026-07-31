# OmniRoute + OpenCode Setup

This guide wires [OpenCode](https://opencode.ai) to the local OmniRoute gateway
so you can run agentic coding workflows against free-tier models.

> **CHV2 privacy reminder:** OmniRoute is approved for **P0/P1** tasks only.
> Do not route secrets, credentials, or regulated data through free-tier
> providers. See `docs/governance/OMNIROUTE_BROKER_POLICY.md`.

---

## 1. Install OmniRoute

### npm (recommended)

```bash
npm install -g omniroute
```

Then start it:

```bash
omniroute start
```

### Docker

```bash
docker run -d --name omniroute --restart unless-stopped --stop-timeout 40 \
  -p 20128:20128 diegosouzapw/omniroute
```

### CHV2 helper script

```bash
python scripts/install_omniroute.py --check
python scripts/install_omniroute.py --install
```

---

## 2. Validate the gateway

```bash
curl http://localhost:20128/v1/models \
  -H "Authorization: Bearer not-needed"  # pragma: allowlist secret
```

You should see a JSON list of available models.

---

## 3. Configure OpenCode

Create or edit your OpenCode config.

### Windows

```cmd
notepad %USERPROFILE%\.config\opencode\opencode.json
```

### macOS / Linux

```bash
mkdir -p ~/.config/opencode
${EDITOR:-nano} ~/.config/opencode/opencode.json
```

Paste this provider block (preserving any other providers you already have):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "omniroute": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "OmniRoute",
      "options": {
        "baseURL": "http://localhost:20128/v1",
        "apiKey": "not-needed"  # pragma: allowlist secret
      },
      "models": {
        "auto": { "name": "Auto-Combo" },
        "auto-coding": { "id": "auto/coding", "name": "Auto Coding" },
        "deepseek-flash": { "id": "oc/deepseek-v4-flash-free", "name": "DeepSeek V4 Flash" },
        "qwen3-coder": { "id": "oc/qwen3-coder-free", "name": "Qwen 3 Coder" },
        "deepseek-r1": { "id": "oc/deepseek-r1-free", "name": "DeepSeek R1" },
        "kimi-k2-thinking": { "id": "oc/kimi-k2-thinking-free", "name": "Kimi K2 Thinking" }
      }
    }
  }
}
```

> **URL normalisation:** `baseURL` must end in exactly one `/v1`. If you copy a
> stale config with `/v1/v1/`, requests will 404. Re-run the generator or fix it
> by hand.

---

## 4. Start OpenCode

```bash
opencode
```

Select an OmniRoute model in the UI and send a test prompt. OpenCode will call
`http://localhost:20128/v1/chat/completions`; OmniRoute handles provider
selection and auto-fallback.

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Invalid API key` | OmniRoute has `REQUIRE_API_KEY=true`. Create a key in the OmniRoute dashboard or set it to `false` for local use. |  # pragma: allowlist secret
| `404` with `/v1/v1/` | Regenerate the config; the baseURL has a doubled suffix. |
| Model list empty | The selected model is not enabled in OmniRoute. Use `auto` or check the dashboard. |
| Gateway unreachable | Run `python scripts/install_omniroute.py --check` and confirm port 20128 is open. |

---

## 6. Integration with CHV2 routing

Once OmniRoute is running, the CHV2 router can also fall back to it for
P0/P1 tasks. The adapter is registered at
`02_RUNTIME/router/adapters/omniroute_adapter.py` and the model allowlist lives
in `config/routing/omniroute-models.yaml`.

For CHV2 agent work, prefer the harness router over pointing tools directly at
OmniRoute — that keeps privacy classes, audit logging, and fallback chains
consistent.
