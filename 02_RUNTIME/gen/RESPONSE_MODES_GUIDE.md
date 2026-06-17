# Gen Response Modes & Enforcement Controls — Quick Reference

> **Auth setup (run once per PS session):**
> ```powershell
> $AUTH_HDR = "Authorization: Bearer"
> # Usage: -H "$AUTH_HDR $env:GEN_TOKEN"
> ```

Two independent control systems:
1. **Response Modes** — transform prompt before Claude sees it  
2. **Pretool Stop Enforcement** — allow or block tool execution (budget/guard stops)

---

## Part 1: Response Modes

Three operational modes for controlling how Claude replies, switchable at runtime without restart.

| Mode | Behavior | Use Case |
|------|----------|----------|
| **normal** | Standard Claude workflow (default) | Production use |
| **ollama_gate** | Prepends Ollama validation header; signals local preprocessing pass | Testing/validation pipeline |
| **dummy** | Fixed template response for testing | Test hook integration |

### Check current mode  
```bash
curl -H "$AUTH_HDR $env:GEN_TOKEN" http://127.0.0.1:43123/admin/modes/current
```

### Switch response mode
```bash
# Dummy mode
curl -X POST `
  -H "$AUTH_HDR $env:GEN_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"mode":"dummy"}' `
  http://127.0.0.1:43123/admin/modes/switch

# Ollama gate mode
curl -X POST `
  -H "$AUTH_HDR $env:GEN_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"mode":"ollama_gate"}' `
  http://127.0.0.1:43123/admin/modes/switch

# Back to normal
curl -X POST `
  -H "$AUTH_HDR $env:GEN_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"mode":"normal"}' `
  http://127.0.0.1:43123/admin/modes/switch
```

---

## Part 2: Pretool Stop Enforcement (NEW)

**Default: DISABLED** — All windows can chat freely, stops still audited.

| State | Behavior | Use Case |
|-------|----------|----------|
| **DISABLED** (default) | Budget/bash/file stops bypass; warnings logged | Production (let everyone chat) |
| **ENABLED** | Stops enforced; execution blocked on violations | Strict compliance/testing |

### Check current enforcement
```bash
curl -H "$AUTH_HDR $env:GEN_TOKEN" http://127.0.0.1:43123/admin/modes/enforcement/pretool-stops
```

### Toggle enforcement
```bash
# Enable stops (hard enforcement)
curl -X POST `
  -H "$AUTH_HDR $env:GEN_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"enforce":true}' `
  http://127.0.0.1:43123/admin/modes/enforcement/pretool-stops

# Disable stops (allow all, audit only)
curl -X POST `
  -H "$AUTH_HDR $env:GEN_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"enforce":false}' `
  http://127.0.0.1:43123/admin/modes/enforcement/pretool-stops
```

---

## Part 3: PowerShell Aliases (Optional)

Add to your PowerShell profile for one-liners:

```powershell
# --- RESPONSE MODES ---
function Get-GenMode {
  curl -H "$AUTH_HDR $env:GEN_TOKEN" http://127.0.0.1:43123/admin/modes/current | ConvertFrom-Json | Select-Object currentMode, description
}

function Set-GenMode {
  param([string]$Mode)
  curl -X POST -H "$AUTH_HDR $env:GEN_TOKEN" -H "Content-Type: application/json" -d "{`"mode`":`"$Mode`"}" http://127.0.0.1:43123/admin/modes/switch | ConvertFrom-Json | Select-Object currentMode, previousMode, timestamp
}

# --- PRETOOL STOPS ENFORCEMENT ---
function Get-GenEnforcement {
  curl -H "$AUTH_HDR $env:GEN_TOKEN" http://127.0.0.1:43123/admin/modes/enforcement/pretool-stops | ConvertFrom-Json | Select-Object enforced, description
}

function Set-GenEnforcement {
  param([bool]$Enforce)
  curl -X POST -H "$AUTH_HDR $env:GEN_TOKEN" -H "Content-Type: application/json" -d "{`"enforce`":$($Enforce.ToString().ToLower())}" http://127.0.0.1:43123/admin/modes/enforcement/pretool-stops | ConvertFrom-Json | Select-Object enforced, updated, explanation
}
```

**Usage:**
```powershell
Get-GenMode                              # Check response mode
Set-GenMode dummy                        # Switch mode
Get-GenEnforcement                       # Check stop enforcement
Set-GenEnforcement $false                # Disable enforcement (allow all chats)
Set-GenEnforcement $true                 # Enable enforcement (hard blocks)
```

---

## Environment Startup Defaults

Override at startup (persists until runtime toggle):

```bash
# Set default response mode
$env:GEN_RESPONSE_MODE = "ollama_gate"

# Set default enforcement (default: false = disabled)
$env:GEN_ENABLE_PRETOOL_STOPS = "true"

npm run dev
```

---

## Audit Trail

All changes logged to `gen/logs/gen-audit.jsonl`:
- Mode switches
- Enforcement changes  
- Bypassed stops (with reason)

Access with:
```bash
tail -20 d:\.04_Prism\gen\logs\gen-audit.jsonl
```

---

## Key Design

✅ **No restart needed** — all toggles are runtime  
✅ **Independent controls** — response mode ≠ enforcement  
✅ **Audit preserved** — stops are always logged even when bypassed  
✅ **Default: Open** — stops OFF by default so all windows can chat  
✅ **Easy visual control** — fast API endpoints + PowerShell aliases  
