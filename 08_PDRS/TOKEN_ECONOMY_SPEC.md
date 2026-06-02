# TOKEN_ECONOMY_SPEC — Consolidated Token/Quota Utilization Control Plane

**Status:** v1 draft · **Beads:** `mc-65kxl` (dashboard + utilization control plane), `mc-i1i8k` (portfolio token economy + forecasting) · **Date:** 2026-05-30

> Derived from the `token-control-plane-design` workflow (7-agent survey →
> 3-lens design panel → synthesis). CPA/budget-first spine + routing-feedback
> actuation graft. **Reuse-first:** built ON TOP OF the existing
> `forecast_latest.json` contract — fix the INPUT, don't rebuild aggregation.

## 1. Objective & Doctrine

The **primary budget is the prepaid weekly Claude plan quota** (the `/usage`
panel: "Weekly · all models · N% · resets in Dd"), **target ≥90% weekly
utilization**. Per the router matrix, native Claude is **$0 marginal in-session**
— so the quota is a **prepaid depleting asset**, and the tracked variance is
*under*-utilization (risk semantics **invert**: a projected weekly close below
90% is RED). Dollar spend on API-billed providers is a *separate, secondary*
hard-ceiling constraint. Free local models are quota-neutral and tracked only
for offload value.

## 2. Three-Axis Chart of Accounts

A single authoritative `billing_axis` field arbitrates every usage event:

| Axis | Name | Members | Unit | Constraint |
|------|------|---------|------|------------|
| **P** | Prepaid quota | `native_claude` (type:native, cost 0.00) | % of weekly unified quota | **PRIMARY setpoint, ≥90%**; under-use = variance |
| **D** | Dollar-billed API | `claude_api`, `gemini`, `openai`, `openrouter`, `together` (type:cloud) | USD (pricing.json) | HARD CEILING: `agent_budget.yaml` daily $25 / monthly $400 |
| **F** | Free local | `ollama`, `lmstudio` (type:local, cost 0.00) | $0 / quota-neutral | tracked for offload value only |

This reconciles the prior contradiction between `quota_roi.py` (native = free
sunk cost) and the `$`-ledger (all spend marginal): native Claude is neither
"free" nor "marginal $" — it is **Axis P, booked against the weekly %**.

## 3. Canonical Data Contract

- **`forecast_latest.json`** (EXISTING — `scripts/budget_forecast_snapshot.py`):
  keep as the canonical control-plane shape. Extend with an `axis_prepaid` block:
  `{weekly_quota_pct, target_pct: 90, pace_needed, projected_close_pct, reset_at, status (inverted)}`.
- **`quota_state.json`** (NEW — `~/.claude/powerline/usage/quota_state.json`):
  `{weekly_pct, weekly_reset, session_5h_pct, session_5h_reset, representative_claim, status, captured_at}`.
- **`ledger.jsonl`** (NEW — normalized posting output):
  `{decision_id, ts, axis, cost_center{repo,agent,tool,mcp,model,c_level,t_level}, tokens, usd, quota_delta_pct}`.

`decision_id` is the join key, stamped at the `gate.py` write point, joining
`ledger.jsonl` ⇆ `routes_*.jsonl` ⇆ `today.json`.

## 4. Capture Layer

`02_RUNTIME/budget/quota_proxy.py` — a **transparent fail-open reverse proxy** at
`ANTHROPIC_BASE_URL=http://127.0.0.1:PORT` forwarding to `api.anthropic.com`,
reading `anthropic-ratelimit-unified-7d-utilization` / `-5h` / `-reset` /
`-status` / `-representative-claim` headers into `quota_state.json`. Plain
HTTP→HTTPS forward (no MITM CA). **Source-abstracted** (`quota_state.py` reader)
so the producer can later swap to native OTEL (anthropic #16942) or statusline
(#20636) without touching consumers. This is the **verified-only** deterministic
source of the weekly % — it is not currently in any local file.

## 5. Ledger / Posting Engine

`tools/portfolio_token_telemetry.py`:
1. Wire the existing `ingest_claude_usage_hook()` stub (`ledger.py:228`) to bridge
   `~/.claude/powerline/usage/today.json` + ccusage → `07_LOGS_AND_AUDIT/budget/daily.jsonl`
   (fixes the `$0`-forecast-while-today.json-shows-spend gap).
2. Join `routes_*.jsonl` × `config/routing/providers.yaml` (type+cost) ×
   `pricing.json` to backfill the null `cost_estimate_usd` (`gate.py:427`) and
   stamp `billing_axis`.
3. Attribute each event via `decision_id` to a cost center.
4. Emit `ledger.jsonl` + `chromatic_*` metrics. Carry an `unknown_usage`
   confidence band (today.json is ~71% unknown — never silently hide it).

## 6. Forecast Layer

`tools/portfolio_token_forecast.py`: extends `forecast_latest.json` with the
`axis_prepaid` projection, folds in `quota_roi.py`'s C×T ROI card and
`weekly_budget.py`'s ccusage `$` forecast, and emits variance via the existing
`budget_forecast_accuracy.py`. **Inverted risk:** projected close <90% → RED.

## 7. Control Loop

`02_RUNTIME/control_plane/controller.py` — proportional controller with a
**deadband around 90%** and **rate-limited (hysteresis) threshold moves** to
prevent oscillation. Reads `quota_state.json` + `forecast_latest.json`, honors
**both** the 5h and 7d windows (backs off near reset), has a **5-minute
staleness guard** (falls back to conservative thresholds if the proxy is
stale/down), and writes `07_LOGS_AND_AUDIT/control_plane/routing_policy_overlay.json`
— dynamic C→T threshold knobs.

`gate.py` reads the overlay on the next PreToolUse exactly as it already reads
`transfer_packet.json` `budget.decision`, and finally invokes the
existing-but-unwired `BudgetGate.estimate`. Logic:
- projected prepaid <90% near reset → **lower** the C→T bar so C3/C4 routes to
  `native_claude` (spend the prepaid asset);
- 5h/7d lockout risk → **raise** the bar, spill C1/C2 to local then cheapest API;
- Axis D `$` caps are a hard ceiling regardless.

Every overlay change is logged to the routes audit for backtesting.

## 8. Dashboard & Metrics

`09_DEPLOYMENT/dashboards/exporter/token_economy_exporter.py` reads `forecast_latest.json` /
`ledger.jsonl` and emits the already-named `chromatic_*` series into the
existing `grafana/` + `n8n/` placeholders: a **3-column weekly P&L** (quota %,
API $, local-offload $-equivalent), a **utilization gauge vs the 90% line**, and
a **per-cost-center ROI table**.

## 9. Config Extensions

`config/agent_budget.yaml`: add per-provider **prepaid flags** and the quota
reset binding. **Reuse** the existing `weekly_target_utilization_pct_default: 90`
(do not introduce a new target key).

## 10. Risks & Mitigations

- **Proxy SPOF** → fail-open (never block the API path); staleness guard on reader.
- **Header instability** → source-abstraction; verify `weekly_pct` against `/usage`.
- **71% unknown attribution** → explicit confidence band, never hidden.
- **Controller oscillation** → deadband + hysteresis + rate limiting.
- **5h vs 7d** → controller honors both; backs off near reset.
- **ccusage ≠ quota** → ccusage is the Axis D `$` estimator only; Axis P comes
  solely from the proxy.

## 11. Reuse Map & Out-of-Scope

**Reuse:** `forecast_latest.json` (contract), `agent_budget.yaml` (caps/targets),
`BudgetLedger.append_daily()` + `daily.jsonl` (sink), `pricing.json` (cost table),
`budget_forecast_accuracy.py` (variance), `token_governance_closed_loop.py`
(scheduler shell), `quota_roi.py` + `weekly_budget.py` (seed tools, folded in).
**Out-of-scope for v1:** LiteLLM / Langfuse / Helicone / OTel collector — Axis D
is fully covered by `providers.yaml` + `pricing.json` with zero new infra. Noted
only as a future producer swap behind `quota_state.py`'s source abstraction.

## 12. Bead Mapping & Build Order

| Bead | Artifact | Depends on |
|------|----------|-----------|
| **B1** (mc-i1i8k) | This spec — the contract | — |
| **B2** ★ | `02_RUNTIME/router/billing_axis.py` 3-way classifier + tests | B1 |
| **B3** | `tools/portfolio_token_telemetry.py` posting engine + ingest wiring | B2 |
| **B4** (mc-65kxl) | EDIT `gate.py`: populate `cost_estimate_usd`+`billing_axis` @427, invoke BudgetGate | B2 |
| **B5** | `quota_proxy.py` + `quota_state.py` (fail-open, staleness, abstraction) | B1 |
| **B6** (mc-i1i8k) | `tools/portfolio_token_forecast.py` axis_prepaid + ROI fold-in + variance | B3, B5 |
| **B7** | `control_plane/controller.py` + `routing_policy_overlay.json`; gate reads overlay | B5, B6 |
| **B8** (mc-65kxl) | `09_DEPLOYMENT/dashboards/exporter/token_economy_exporter.py` chromatic_* + P&L | B3, B6 |
| **B9** | EDIT `token_governance_closed_loop.py`: chain proxy→telemetry→forecast→controller→exporter | B3,B5,B6,B7,B8 |
| **B10** | EDIT `agent_budget.yaml`: prepaid flags + quota reset binding | B1 |

**★ Highest-ROI first step (B2):** the `billing_axis` classifier is the single
field every other component joins on — zero new infra, zero request-path risk,
fully unit-testable against `providers.yaml` today. It resolves the
quota-vs-`$` contradiction in code, and unblocks B3, B4, and B6.
