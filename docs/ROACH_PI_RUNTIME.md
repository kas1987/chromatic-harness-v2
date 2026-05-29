# roach-pi Runtime (Option C)

Chromatic wraps [roach-pi](https://github.com/tmdgusya/roach-pi) as a pluggable executor via `RoachPiAdapter`.

## Layout

| Path | Role |
|------|------|
| `.gitmodules` | Submodule pin to `tmdgusya/roach-pi` |
| `02_RUNTIME/runtime-engines/roach-pi/` | Submodule checkout (or README placeholder) |
| `02_RUNTIME/adapters/roach-pi-adapter.ts` | Hardened adapter (magnets + CMP gates) |
| `02_RUNTIME/adapters/roach-pi-loader.ts` | Submodule detection, scope guards, timeouts |
| `02_RUNTIME/adapters/roach_pi_guard.py` | Python health/scope checks for CI |

## Modes

| Mode | When | Behavior |
|------|------|----------|
| **stub** | Submodule not initialized | Mock execution; full magnet telemetry |
| **submodule** | `extensions/agentic-harness/` present | Ready for real execute wiring |

## Initialize

```powershell
powershell -File scripts/init_roach_pi_submodule.ps1
```

```bash
./scripts/init_roach_pi_submodule.sh
```

## Health

```bash
python scripts/roach_pi_status.py
```

## Hardening (adapter)

- Scope paths must be relative, no `..`, must stay under repo root
- Mission timeout (`timeout_seconds`, default 1800s)
- `ROACH_PI_ROOT` env override for custom checkout path
- `runtime_info.mode` on every `ExecutionResult`

See [OPTION_C_INTEGRATION_ARCHITECTURE.md](../00_SOURCE_OF_TRUTH/OPTION_C_INTEGRATION_ARCHITECTURE.md).
