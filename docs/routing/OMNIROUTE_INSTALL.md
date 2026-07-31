# OmniRoute Install Guide

OmniRoute is a local, OpenAI-compatible gateway that aggregates free and
low-cost LLM providers through one endpoint: `http://localhost:20128/v1`.

This guide covers installation for CHV2 users. For the upstream reference, see
[diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute).

---

## Prerequisites

- One of:
  - Node.js + npm (or pnpm/yarn)
  - Docker
- Network access to `localhost:20128`

---

## Quick install

### npm (recommended)

```bash
npm install -g omniroute
omniroute start
```

### Docker

```bash
docker run -d --name omniroute --restart unless-stopped --stop-timeout 40 \
  -p 20128:20128 diegosouzapw/omniroute
```

---

## CHV2 helper script

A non-destructive helper is provided at `scripts/install_omniroute.py`:

```bash
# Check if OmniRoute is already reachable
python scripts/install_omniroute.py --check

# Show the install command for your platform
python scripts/install_omniroute.py --install --dry-run

# Install and validate
python scripts/install_omniroute.py --install

# Force Docker instead of npm
python scripts/install_omniroute.py --install --method docker
```

The helper never installs without `--install` and never starts a background
service without explicit user action.

---

## Validation

```bash
curl http://localhost:20128/v1/models \
  -H "Authorization: Bearer not-needed"  # pragma: allowlist secret
```

Expected: a JSON list of models.

```bash
curl http://localhost:20128/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer not-needed" \  # pragma: allowlist secret
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello!"}]}'
```

Expected: a chat completion response.

---

## Windows always-on setup (optional)

If you want OmniRoute to start automatically on login:

1. Create a scheduled task that runs `omniroute start` on user logon.
2. Or use Docker with `--restart unless-stopped` and start Docker on boot.

Do **not** run the gateway as a privileged service unless required by your
environment.

---

## CHV2 integration

After installation, CHV2 can route P0/P1 tasks to OmniRoute automatically. The
relevant files are:

- `config/routing/providers.yaml` — registry entry
- `config/routing/omniroute-models.yaml` — allowed model IDs
- `config/routing/routing-table.yaml` — context-aware rank
- `02_RUNTIME/router/adapters/omniroute_adapter.py` — runtime adapter
- `docs/governance/OMNIROUTE_BROKER_POLICY.md` — privacy and usage rules

For OpenCode IDE setup, see `docs/routing/OPENCODE_OMNIROUTE_SETUP.md`.
