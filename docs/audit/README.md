# Audit docs index

Hook and pre-session audit artifacts for Chromatic Harness v2.

| Doc | Purpose |
|-----|---------|
| [HOOK_ARCHITECTURE.md](HOOK_ARCHITECTURE.md) | Layer model, best practices, what is not a hook |
| [HOOK_AUDIT_LATEST.md](HOOK_AUDIT_LATEST.md) | Latest `audit_hooks.py` report (regenerate below) |

**Regenerate hook audit:**

```bash
python scripts/audit_hooks.py --markdown > docs/audit/HOOK_AUDIT_LATEST.md
```

**CI guards:** `python scripts/check_agent_operations.py` (requires `HOOK_ARCHITECTURE.md`).
