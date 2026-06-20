# Multi-Machine Harness Operations

How to run `chromatic-harness-v2` consistently across Desktop (KSPC, E: drive) and Laptop (C: drive).

---

## Architecture overview

```
┌──────────────────────────────────┐   ┌──────────────────────────────────┐
│  DESKTOP (KSPC)                  │   │  LAPTOP                          │
│                                  │   │                                  │
│  E:\.02_chromatic-harness-v2    │   │  C:\chromatic-harness-v2         │
│  ├── (same GitHub clone)         │   │  ├── (same GitHub clone)         │
│  ├── HARNESS_ROOT=E:\...         │   │  ├── HARNESS_ROOT=C:\...         │
│  └── MCP: local profile          │   │  └── MCP: local profile          │
│                                  │   │      (or remote → desktop API)   │
│  E:\v3-Harness---Desktop        │   │  C:\v3-Harness---Laptop          │
│  └── beads DB, EPICs, decisions  │   │  └── beads DB, EPICs, decisions  │
│                                  │   │                                  │
│  FastAPI API (port 7700) ────────┼───┼──► HTTP calls from laptop        │
│  (optional, run as server)       │   │   (requires Tailscale)           │
└──────────────────────────────────┘   └──────────────────────────────────┘
         ↕ git push/pull                          ↕ git push/pull
         GitHub: kas1987/chromatic-harness-v2
```

---

## Mode 1 — Local (default, no Tailscale needed)

Both machines clone the harness from GitHub and run all services locally. State is per-machine.

**On each machine, run once:**
```powershell
powershell -File scripts\bootstrap_machine.ps1
powershell -File scripts\switch_mcp_profile.ps1 local
```

**Keep in sync:**
```powershell
git pull
```

**MCP profile:** `config/mcp-profiles/local.json` — stdio transport, spawned per IDE session.

---

## Mode 2 — Remote (Desktop as server, Laptop as client)

Desktop runs the FastAPI API permanently. Laptop connects to it via Tailscale. Shared runtime state (missions, agents, route decisions).

### Prerequisites

1. Tailscale installed and logged in on both machines: `tailscale login`
2. Desktop Tailscale IP noted: `tailscale ip -4` (something like `100.x.x.x`)

### Desktop setup

```powershell
# Start FastAPI server (keep this terminal open, or use pm2/nssm for persistence)
powershell -File scripts\start_harness_api.ps1 -Port 7700

# Firewall: allow port 7700 on private networks
netsh advfirewall firewall add rule name="Harness API" dir=in action=allow protocol=TCP localport=7700
```

### Laptop setup

```powershell
# Set env vars (add to PowerShell profile for persistence)
[System.Environment]::SetEnvironmentVariable("HARNESS_API_HOST", "100.x.x.x", "User")
[System.Environment]::SetEnvironmentVariable("HARNESS_API_URL",  "http://100.x.x.x:7700", "User")

# Switch to remote MCP profile
powershell -File scripts\switch_mcp_profile.ps1 remote
```

### Verify

```powershell
# From laptop
curl http://$env:HARNESS_API_HOST:7700/health
```

---

## MCP profiles

| Profile | Transport | When to use |
|---------|-----------|-------------|
| `local` | stdio (per-session process) | Default — single machine, no network needed |
| `remote` | SSE + HTTP env var | Laptop connecting to desktop's running API |

Switch: `scripts\switch_mcp_profile.ps1 [local\|remote]`

---

## What stays per-machine (never centralized)

| Resource | Why |
|----------|-----|
| `v3-Harness---Desktop` beads DB | Machine-local issue tracking; different work, no merge |
| `v3-Harness---Laptop` beads DB | Same |
| Budget ledger (`07_LOGS_AND_AUDIT/budget/`) | Per-session spend tracking |
| Session logs, handoffs | Ephemeral; not meaningful to share |

## What CAN be centralized (Mode 2)

| Resource | Desktop service |
|----------|-----------------|
| Missions / magnet events | FastAPI `/missions` |
| Route decisions | FastAPI `/route` |
| Agent profiles | FastAPI `/agents` |

---

## Startup checklist (desktop as server)

- [ ] `tailscale status` — shows both machines as peers
- [ ] `powershell -File scripts\start_harness_api.ps1` running (or managed by pm2)
- [ ] `curl http://localhost:7700/health` returns `{"status":"ok"}`
- [ ] Laptop: `$env:HARNESS_API_URL` points at desktop Tailscale IP
