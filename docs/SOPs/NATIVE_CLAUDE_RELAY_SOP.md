# SOP: native_claude Relay Server

**Mission:** M3-RELAY-001  
**Purpose:** Bridge the Windows Claude Code CLI to the harness router so C3/C4 tasks route to Axis P (prepaid quota) instead of falling through to Axis D (billed).

---

## When to run this

Run the relay whenever you are working in a Windows session with Claude Code authenticated and want C3/C4 tasks to use your prepaid quota instead of billed Gemini/claude_api fallback.

---

## Start the relay

```powershell
# In a dedicated terminal (keep it running in the background)
python scripts/native_claude_relay.py
```

Expected output:
```
native_claude_relay: listening on http://127.0.0.1:9090
```

Verify health:
```powershell
curl http://127.0.0.1:9090/health
# → {"status": "ok"}
```

---

## Activate in your shell session

```powershell
$env:NATIVE_CLAUDE_RELAY_URL = "http://127.0.0.1:9090"
```

Or add to your `.env` (copy from `09_DEPLOYMENT/.env.example` → `09_DEPLOYMENT/.env`):
```
NATIVE_CLAUDE_RELAY_URL=http://127.0.0.1:9090
```

---

## Verify routing

```powershell
# Trigger a C3 dispatch and confirm native_claude is selected
python -m router.cli dispatch --c-level C3 --message "hello" --dry-run
# Look for: selected_provider: native_claude
```

After a real dispatch, confirm Axis P traffic in the governance loop:
```powershell
python scripts/token_governance_closed_loop.py
# Then check:
Get-Content 07_LOGS_AND_AUDIT/token_governance/latest.json | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('by_axis',{}))"
# P value should be > 0 and growing
```

---

## Port conflict

If port 9090 is taken:
```powershell
$env:NATIVE_CLAUDE_RELAY_PORT = "9191"
$env:NATIVE_CLAUDE_RELAY_URL = "http://127.0.0.1:9191"
python scripts/native_claude_relay.py
```

---

## Stop / rollback

```powershell
# Stop relay: Ctrl+C in the relay terminal
# Deactivate routing:
Remove-Item Env:NATIVE_CLAUDE_RELAY_URL
# Router automatically falls through to next available provider (Gemini / claude_api)
```

No persistent state. No code changes needed to roll back.

---

## Security model

- Relay binds to `127.0.0.1` only — not accessible from other machines
- No credentials stored by the relay process
- Prompt content passes through in-memory only, never written to disk
- Subprocess uses `shell=False` (no injection risk)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `claude CLI not found on PATH` | `claude` not on PATH in relay's terminal | Run relay from a terminal where `claude --version` works |
| `relay returns 500 on every /complete` | Claude Code not authenticated | Run `claude auth` first |
| Axis P still 0 after relay started | `NATIVE_CLAUDE_RELAY_URL` not set in harness env | Check `.env` or set the env var in the harness terminal |
| Port already in use | Another process on 9090 | Set `NATIVE_CLAUDE_RELAY_PORT=9191` and update `NATIVE_CLAUDE_RELAY_URL` |
