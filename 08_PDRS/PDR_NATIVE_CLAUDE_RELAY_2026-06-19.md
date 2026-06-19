# PDR — native_claude relay server + routing completion

**Status:** draft · **Mission:** `M3-RELAY-001` · **Date:** 2026-06-19

> Stand up a localhost HTTP relay that makes C3/C4 traffic reach Axis P (prepaid quota) on Windows, complete the routing table for desktop/server contexts, and eliminate the per-event import overhead in telemetry.

---

## 1. Problem

Three gaps remain after the SWOT session (2026-06-19):

**Gap 1 (Critical):** `native_claude` is first in the routing table for C3/C4 laptop/remote contexts, but on Windows `shutil.which("claude")` passes the availability check while `subprocess` dispatch fails with WinError 2. Result: every C3/C4 call silently falls through to Axis D (billed Gemini or claude_api). Axis P utilization is 15% against a 90% target; Axis D overrun is ~$103/week.

**Gap 2 (Minor):** `context_desktop` and `context_server` routing entries still don't include `native_claude` for C3/C4. The routing fix applied in the SWOT session was laptop-only.

**Gap 3 (Minor):** `_infer_levels()` in `tools/portfolio_token_telemetry.py` inserts `scripts/` onto `sys.path` and imports `token_level_inference` on every call — which runs once per ledger row (11k+ rows). Repeated `sys.path.insert` + module import in a tight loop.

---

## 2. Reuse Survey

| Asset | Location | Role |
|-------|----------|------|
| `native_claude_adapter.py` | `02_RUNTIME/router/adapters/` | Already implements relay mode — do NOT touch |
| `provider_selector._native_claude_available()` | `02_RUNTIME/router/provider_selector.py` | Already checks `NATIVE_CLAUDE_RELAY_URL` first — do NOT touch |
| `routing-table.yaml` | `09_DEPLOYMENT/config/routing/` | Extend desktop/server entries only |
| `token_level_inference.py` | `scripts/` | Already complete — only add `lru_cache` wrapper in the caller |
| `_infer_levels()` | `tools/portfolio_token_telemetry.py` | Refactor: cache the function reference at module level |
| FastAPI / stdlib `http.server` | PyPI / stdlib | Use for relay; prefer stdlib if FastAPI not installed |

**Not reusing:** MCP handler `_smart_truncate`, LiteLLM `headroom_callback.py` — those are separate concerns already shipped.

---

## 3. Non-Goals

- Will NOT change `native_claude_adapter.py` or `provider_selector.py` — both are already correct.
- Will NOT add TLS, authentication, or multi-user support to the relay — localhost-only is the security model.
- Will NOT route the relay through LiteLLM — native_claude bypasses LiteLLM by design (Axis P = no marginal cost).
- Will NOT add the relay as a Docker container — it runs on the Windows host, bridged via `host.docker.internal`.
- Will NOT fix the 90% Axis P target in this mission — that's a steady-state outcome after adoption; the acceptance criterion is ≥ 50% in the first governance loop.

---

## 4. Design

### B2: `scripts/native_claude_relay.py`

Minimal HTTP server (stdlib `http.server` with no external deps, or FastAPI if available). Exposes two endpoints:

```
GET  /health        → 200 {"status": "ok"}
POST /complete      → 200 {"result": "<assistant text>", "model": "<model>", "latency_ms": N}
                    → 500 {"error": "<message>"} on CLI failure
```

`/complete` request body (matches `native_claude_adapter._complete_relay` payload):
```json
{ "prompt": "string", "model": "claude-sonnet-4-6", "system": "optional string" }
```

Invokes `claude -p "<prompt>" --model <model>` via `subprocess.run` with `shell=False`, captures stdout, returns it as `result`. Timeout: 60 s (matches adapter default). Binds to `127.0.0.1:9090` (configurable via `NATIVE_CLAUDE_RELAY_PORT`).

### B3: routing-table.yaml additions

```yaml
context_desktop:
  speed:
    C3: [native_claude, ollama_local:qwen2.5-coder:14b, ...]
    C4: [native_claude, openrouter:..., ...]
  balance:
    C3: [native_claude, ollama_local:qwen2.5-coder:14b, ...]
    C4: [native_claude, gemini:gemini-2.5-pro, ...]

context_server:
  speed:
    C3: [native_claude, ollama_local:gemma2:27b, ...]
    C4: [native_claude, claude_api:sonnet, ...]
  balance:
    C3: [native_claude, ollama_local:qwen2.5-coder:14b, ...]
    C4: [native_claude, ollama_local:gemma2:27b, ...]
```

### B4: `_infer_levels` caching

Replace the current per-call import pattern in `portfolio_token_telemetry.py` with a module-level cached function:

```python
import functools

@functools.lru_cache(maxsize=64)
def _infer_levels(model: str | None):
    try:
        _scripts = _REPO / "scripts"
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from token_level_inference import infer_levels
        c, t, _ = infer_levels(model)
        return c, t
    except Exception:
        return None, None
```

`lru_cache(maxsize=64)` covers the ~10 model names seen in practice; no TTL needed (inference rules are static constants).

---

## 5. Integration / Actuation Edge  ⚠️ MANDATORY

**What runtime path calls this?**

`native_claude_adapter.py` reads `NATIVE_CLAUDE_RELAY_URL` at `__init__` time. When set, `_use_relay()` returns `True` and every `complete()` call goes to `POST {relay_url}/complete` instead of spawning a subprocess. `provider_selector._native_claude_available()` also checks this env var first — so the provider appears available and gets selected. No hook or scheduler changes needed; the env var is the activation gate.

**How will we PROVE it is live?**

1. Start relay: `python scripts/native_claude_relay.py`
2. `curl http://127.0.0.1:9090/health` → `{"status": "ok"}`
3. Set `$env:NATIVE_CLAUDE_RELAY_URL = "http://127.0.0.1:9090"` in the shell running the harness
4. Trigger a C3 dispatch via `python -m router.cli dispatch --c-level C3 --message "hello"`
5. Observe `selected_provider: native_claude` in the routing log
6. Run `python scripts/token_governance_closed_loop.py`
7. `jq .confidence_band.unknown_pct 07_LOGS_AND_AUDIT/token_governance/latest.json` → value < 30%
8. `jq .by_axis.P 07_LOGS_AND_AUDIT/token_governance/latest.json` → value > 0 and growing

---

## 6. Lean Impact  ⚠️ MANDATORY

| Question | Answer |
|----------|--------|
| Boot tax? | Zero — relay is a separate process, not imported at harness startup |
| Always-on vs event-driven? | Relay is always-on (one lightweight process); harness side is event-driven (only calls relay when C3/C4 dispatches occur) |
| On-demand vs always-injected? | On-demand — `NATIVE_CLAUDE_RELAY_URL` env var gates activation; unset = zero impact |
| Swappable producer? | Yes — relay is a thin wrapper; swap `claude -p` for any OpenAI-compatible endpoint without touching the adapter |
| `agent_token_audit.py` baseline | lru_cache removes repeated import overhead; delta should be ≤ 0 tokens/boot (no new boot-time imports) |

---

## 7. Decomposition

| Bead | Artifact | Depends on |
|------|----------|------------|
| **B1** ★ | This PDR + `MISSIONS/M3-RELAY-001-native-claude-routing.yaml` | — |
| **B2** | `scripts/native_claude_relay.py` + `tests/test_native_claude_relay.py` | B1 |
| **B3** | `09_DEPLOYMENT/config/routing/routing-table.yaml` (desktop/server) | B1 |
| **B4** | `tools/portfolio_token_telemetry.py` (lru_cache) + telemetry regression test | B1 |
| **B5** | `docs/SOPs/NATIVE_CLAUDE_RELAY_SOP.md` + `.env.example` update | B2 |
| **B6** | Integration smoke test (relay live, C3 dispatch confirmed, ledger row axis=P) | B2, B3, B4 |

★ = B2 is the highest-ROI step — relay server unblocks all Axis P routing with zero schema changes.

---

## 8. Tests & Hardening

- **Unit tests:** `tests/test_native_claude_relay.py` — `/health` returns 200; `/complete` with a mock CLI command returns `{"result": ..., "model": ..., "latency_ms": ...}`; timeout path returns 500 with error message.
- **Routing regression:** `tests/test_routing_context_pure_functions.py` must stay green after B3 edits.
- **Telemetry regression:** `tests/test_portfolio_token_telemetry.py` — `confidence_band` output unchanged; `_infer_levels("claude-sonnet-4-6")` called twice returns same result (cache hit).
- **Fail-open:** If relay is down, `native_claude_adapter.health()` returns `reachable=False`; `provider_selector` filters it out; routing falls to next provider. No user-visible error.
- **Security:** Relay binds to `127.0.0.1` only. No credentials in relay process. Prompt content passes through in-memory only, never written to disk. Subprocess uses `shell=False` to prevent injection.
- **Staleness:** No state to go stale — relay is stateless; each `/complete` is an independent subprocess invocation.

---

## 9. Definition of Done

- [ ] B2: `scripts/native_claude_relay.py` written and `tests/test_native_claude_relay.py` green
- [ ] B3: `routing-table.yaml` context_desktop/context_server C3/C4 updated; routing tests green
- [ ] B4: `_infer_levels` uses `lru_cache`; telemetry tests green
- [ ] B5: `docs/SOPs/NATIVE_CLAUDE_RELAY_SOP.md` written; `.env.example` has `NATIVE_CLAUDE_RELAY_URL`
- [ ] B6: Integration smoke test passed — relay live, C3 dispatch routes to `native_claude`, ledger row shows `axis=P`
- [ ] `pytest tests/ -x` green (no regressions)
- [ ] `review-daemon` approved
- [ ] PR merged to `feat/command-center-p1-p2`, `bd close M3-RELAY-001`

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `claude -p` subprocess still fails inside relay on some Windows configs | Low | Test on actual machine before B6; relay returns 500 and router falls to Axis D as before — degraded not broken |
| Port 9090 conflict | Low | `NATIVE_CLAUDE_RELAY_PORT` env var overrides default |
| `lru_cache` masks a model name typo (wrong inference cached) | Very low | Cache key is the model string; typos produce the same wrong result with or without cache |
| Desktop context has local GPU inference available — native_claude-first may be slower than Ollama | Medium | `balance` mode already defaults to `low` speed on battery; GPU inference is C3-capable; user can override via `user-preferences.yaml` `provider_blocklist` or `provider_preference` |
| Relay process not started → silent fallback to Axis D | Medium | B5 SOP documents the startup step; consider adding relay health check to `session_boot_automation.py` as a future follow-on |

---

## 11. Rollback

- **Relay:** Stop the process (`Ctrl+C`). No state written. Router falls through to Axis D as before.
- **Env var:** `Remove-Item Env:NATIVE_CLAUDE_RELAY_URL`. Zero code change.
- **Routing table:** `git revert` the B3 commit. `routing-table.yaml` is the only changed file.
- **lru_cache:** `git revert` the B4 commit. `portfolio_token_telemetry.py` is the only changed file.
- No database migrations, no persistent state changes, no schema version bumps.
