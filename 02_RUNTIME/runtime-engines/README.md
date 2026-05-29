# Runtime Engines

Git submodules for pluggable executors (Option C).

| Engine | Path | Upstream |
|--------|------|----------|
| roach-pi | `roach-pi/` | https://github.com/tmdgusya/roach-pi |

## Initialize roach-pi

```powershell
powershell -File scripts/init_roach_pi_submodule.ps1
```

```bash
./scripts/init_roach_pi_submodule.sh
```

## Health check

```bash
python scripts/roach_pi_status.py
```

When the submodule is missing, the hardened adapter runs in **stub** mode (mock execution + full magnet telemetry).
