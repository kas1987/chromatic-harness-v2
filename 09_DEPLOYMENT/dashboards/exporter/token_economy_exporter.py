"""BEAD B8: token economy exporter - chromatic_* metrics + weekly P&L.

Per ``08_PDRS/TOKEN_ECONOMY_SPEC.md`` section 8, this module reads the canonical
``forecast_latest.json`` (B6) and ``ledger.jsonl`` (B3) and emits the
already-named ``chromatic_*`` metric series (see ``09_DEPLOYMENT/dashboards/grafana/README.md``
+ ``09_DEPLOYMENT/dashboards/n8n/README.md``) plus three derived views:

  * a **3-column weekly P&L** - Axis P (prepaid quota %), Axis D (dollar-billed
    API $), Axis F (free-local $-equivalent offload value);
  * a **utilization gauge** of the projected weekly close against the 90% line
    (inverted risk: a projected close < 90% is RED - under-use is the variance);
  * a **per-cost-center ROI table** keyed by ``cost_center`` from the ledger.

It is **reuse-first**: it does NOT re-implement aggregation or forecasting. It
only reads the posted ``ledger.jsonl`` rows + the ``forecast_latest.json``
contract and renders. Output is Prometheus text exposition format (default) or
the JSON shape the grafana/n8n READMEs consume (``--format json``).

The ``axis_prepaid`` block (spec section 3/6) is read when present; when the
forecast has not yet been extended with it, the exporter falls back to the
existing ``limits.weekly`` target shape so it stays runnable against today's
contract.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parent.parent.parent
_BUDGET_DIR = _REPO / "07_LOGS_AND_AUDIT" / "budget"
_DEFAULT_FORECAST = _BUDGET_DIR / "forecast_latest.json"
_DEFAULT_LEDGER = _BUDGET_DIR / "ledger.jsonl"

# Inverted-risk setpoint: under-use of the prepaid quota is the tracked variance.
TARGET_PCT = 90.0

# Canonical chromatic_* series names (grafana/n8n READMEs).
METRIC_COST_ESTIMATE = "chromatic_model_cost_estimate"
METRIC_QUOTA_PCT = "chromatic_quota_utilization_pct"
METRIC_QUOTA_TARGET = "chromatic_quota_target_pct"
METRIC_QUOTA_PROJECTED = "chromatic_quota_projected_close_pct"
METRIC_PNL_QUOTA = "chromatic_pnl_axis_p_quota_pct"
METRIC_PNL_API_USD = "chromatic_pnl_axis_d_api_usd"
METRIC_PNL_LOCAL_USD = "chromatic_pnl_axis_f_local_offload_usd"
METRIC_ROI_USD = "chromatic_cost_center_usd"
METRIC_ROI_TOKENS = "chromatic_cost_center_tokens"
METRIC_UNKNOWN_PCT = "chromatic_unknown_usage_pct"


# ── Loaders ──────────────────────────────────────────────────────────────────
def load_forecast(path: Path = _DEFAULT_FORECAST) -> dict[str, Any]:
    """Read ``forecast_latest.json`` (the canonical control-plane contract)."""
    if not Path(path).is_file():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_ledger(path: Path = _DEFAULT_LEDGER) -> list[dict[str, Any]]:
    """Read the normalized ``ledger.jsonl`` rows posted by B3."""
    rows: list[dict[str, Any]] = []
    if not Path(path).is_file():
        return rows
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ── Derived views ────────────────────────────────────────────────────────────
@dataclass
class WeeklyPnL:
    """3-column weekly P&L (spec section 8)."""

    axis_p_quota_pct: float  # Axis P - prepaid weekly quota utilization %
    axis_d_api_usd: float  # Axis D - dollar-billed API spend (USD)
    axis_f_local_offload_usd: float  # Axis F - free-local $-equivalent offload


@dataclass
class UtilizationGauge:
    """Projected weekly close vs the 90% line (inverted risk)."""

    current_pct: float
    projected_close_pct: float
    target_pct: float = TARGET_PCT
    status: str = "green"  # green | red - RED when projected close < target

    @property
    def gap_to_target_pct(self) -> float:
        return round(self.target_pct - self.projected_close_pct, 6)


@dataclass
class CostCenterRow:
    """One per-cost-center ROI row keyed by the ledger ``cost_center``."""

    key: str
    axis: str
    usd: float = 0.0
    tokens: int = 0
    events: int = 0

    @property
    def usd_per_1k_tokens(self) -> float:
        if self.tokens <= 0:
            return 0.0
        return round(self.usd / (self.tokens / 1000.0), 6)


@dataclass
class EconomyReport:
    pnl: WeeklyPnL
    gauge: UtilizationGauge
    cost_centers: list[CostCenterRow] = field(default_factory=list)
    unknown_pct: float = 0.0
    cost_estimate_usd: float = 0.0


def _axis_prepaid(forecast: dict[str, Any]) -> dict[str, Any]:
    """Return the ``axis_prepaid`` block, synthesizing from ``limits.weekly``.

    B6 extends ``forecast_latest.json`` with a first-class ``axis_prepaid`` block.
    Until that lands the exporter must still run, so we fall back to the existing
    weekly target shape (``limits.weekly`` / ``forecast.weekly_utilization``).
    """
    block = forecast.get("axis_prepaid")
    if isinstance(block, dict) and block:
        return block
    weekly = (forecast.get("limits", {}) or {}).get("weekly", {}) or {}
    fc = forecast.get("forecast", {}) or {}
    projected = float(fc.get("weekly_utilization_forecast", 0.0) or 0.0)
    # Existing forecast carries utilization as a fraction in [0,1]; normalize.
    if 0.0 < projected <= 1.0:
        projected *= 100.0
    current = float(weekly.get("current_usd", 0.0) or 0.0)
    cap = float(weekly.get("cap_usd", 0.0) or 0.0)
    current_pct = round((current / cap) * 100.0, 6) if cap else 0.0
    return {
        "weekly_quota_pct": current_pct,
        "target_pct": float((weekly.get("target_policy", {}) or {}).get("target_default_pct", TARGET_PCT)),
        "projected_close_pct": round(projected, 6),
        "reset_at": forecast.get("generated_at", ""),
    }


def _cost_center_key(cc: dict[str, Any]) -> str:
    """Stable display key from a ledger ``cost_center`` (repo/agent/model)."""
    parts = [str(cc.get(field_, "") or "") for field_ in ("repo", "agent", "model")]
    key = "/".join(p for p in parts if p)
    return key or "unattributed"


def build_report(forecast: dict[str, Any], ledger: list[dict[str, Any]]) -> EconomyReport:
    """Compute the P&L, gauge, and per-cost-center ROI table from the inputs."""
    prepaid = _axis_prepaid(forecast)
    target = float(prepaid.get("target_pct", TARGET_PCT) or TARGET_PCT)
    current_pct = float(prepaid.get("weekly_quota_pct", 0.0) or 0.0)
    projected = float(prepaid.get("projected_close_pct", current_pct) or 0.0)

    # Aggregate ledger by axis (reuse the posted rows - do not re-aggregate raw).
    api_usd = 0.0  # Axis D
    local_usd = 0.0  # Axis F (dollar-equivalent offload value)
    cost_estimate_usd = 0.0
    unknown = 0
    total = 0
    centers: dict[tuple[str, str], CostCenterRow] = {}
    for row in ledger:
        axis = str(row.get("axis", "") or "")
        usd = float(row.get("usd", 0.0) or 0.0)
        tokens = int(row.get("tokens", 0) or 0)
        total += 1
        if str(row.get("confidence", "")) == "unknown":
            unknown += 1
        if axis == "D":
            api_usd += usd
            cost_estimate_usd += usd
        elif axis == "F":
            local_usd += usd
        # Axis P usd is a dollar-equivalent, not billed - excluded from $ cost.

        cc = row.get("cost_center", {}) or {}
        key = _cost_center_key(cc)
        ckey = (key, axis or "?")
        center = centers.get(ckey)
        if center is None:
            center = CostCenterRow(key=key, axis=axis or "?")
            centers[ckey] = center
        center.usd = round(center.usd + usd, 6)
        center.tokens += tokens
        center.events += 1

    gauge = UtilizationGauge(
        current_pct=round(current_pct, 6),
        projected_close_pct=round(projected, 6),
        target_pct=target,
        # Inverted risk: under-utilization (projected < target) is RED.
        status="red" if projected < target else "green",
    )
    pnl = WeeklyPnL(
        axis_p_quota_pct=round(current_pct, 6),
        axis_d_api_usd=round(api_usd, 6),
        axis_f_local_offload_usd=round(local_usd, 6),
    )
    cost_centers = sorted(centers.values(), key=lambda c: (-c.usd, -c.tokens, c.key))
    unknown_pct = round((unknown / total) * 100.0, 6) if total else 0.0
    return EconomyReport(
        pnl=pnl,
        gauge=gauge,
        cost_centers=cost_centers,
        unknown_pct=unknown_pct,
        cost_estimate_usd=round(cost_estimate_usd, 6),
    )


# ── Renderers ────────────────────────────────────────────────────────────────
def _metric_line(name: str, value: float, labels: dict[str, str] | None = None) -> str:
    if labels:
        label_str = ",".join(f'{k}="{_escape(str(v))}"' for k, v in labels.items())
        return f"{name}{{{label_str}}} {value}"
    return f"{name} {value}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_prometheus(report: EconomyReport) -> str:
    """Render the report as Prometheus text exposition format."""
    lines: list[str] = []

    def add(help_: str, type_: str, name: str) -> None:
        lines.append(f"# HELP {name} {help_}")
        lines.append(f"# TYPE {name} {type_}")

    add("Estimated dollar-billed (Axis D) model cost.", "gauge", METRIC_COST_ESTIMATE)
    lines.append(_metric_line(METRIC_COST_ESTIMATE, report.cost_estimate_usd))

    add("Current weekly prepaid quota utilization %.", "gauge", METRIC_QUOTA_PCT)
    lines.append(_metric_line(METRIC_QUOTA_PCT, report.gauge.current_pct))

    add("Weekly prepaid quota target % (the 90% line).", "gauge", METRIC_QUOTA_TARGET)
    lines.append(_metric_line(METRIC_QUOTA_TARGET, report.gauge.target_pct))

    add("Projected weekly close % (inverted risk).", "gauge", METRIC_QUOTA_PROJECTED)
    lines.append(_metric_line(METRIC_QUOTA_PROJECTED, report.gauge.projected_close_pct))

    add("Weekly P&L Axis P - prepaid quota %.", "gauge", METRIC_PNL_QUOTA)
    lines.append(_metric_line(METRIC_PNL_QUOTA, report.pnl.axis_p_quota_pct))

    add(
        "Weekly P&L Axis D - dollar-billed API spend (USD).",
        "gauge",
        METRIC_PNL_API_USD,
    )
    lines.append(_metric_line(METRIC_PNL_API_USD, report.pnl.axis_d_api_usd))

    add(
        "Weekly P&L Axis F - free-local offload value ($-equivalent).",
        "gauge",
        METRIC_PNL_LOCAL_USD,
    )
    lines.append(_metric_line(METRIC_PNL_LOCAL_USD, report.pnl.axis_f_local_offload_usd))

    add("Unknown-attribution usage share (%).", "gauge", METRIC_UNKNOWN_PCT)
    lines.append(_metric_line(METRIC_UNKNOWN_PCT, report.unknown_pct))

    add("Per-cost-center spend / $-equivalent (USD).", "gauge", METRIC_ROI_USD)
    add("Per-cost-center token volume.", "gauge", METRIC_ROI_TOKENS)
    for cc in report.cost_centers:
        labels = {"cost_center": cc.key, "axis": cc.axis}
        lines.append(_metric_line(METRIC_ROI_USD, cc.usd, labels))
        lines.append(_metric_line(METRIC_ROI_TOKENS, cc.tokens, labels))

    return "\n".join(lines) + "\n"


def render_json(report: EconomyReport) -> dict[str, Any]:
    """Render the JSON shape the grafana/n8n READMEs consume."""
    return {
        "metrics": {
            METRIC_COST_ESTIMATE: report.cost_estimate_usd,
            METRIC_QUOTA_PCT: report.gauge.current_pct,
            METRIC_QUOTA_TARGET: report.gauge.target_pct,
            METRIC_QUOTA_PROJECTED: report.gauge.projected_close_pct,
            METRIC_PNL_QUOTA: report.pnl.axis_p_quota_pct,
            METRIC_PNL_API_USD: report.pnl.axis_d_api_usd,
            METRIC_PNL_LOCAL_USD: report.pnl.axis_f_local_offload_usd,
            METRIC_UNKNOWN_PCT: report.unknown_pct,
        },
        "weekly_pnl": {
            "axis_p_quota_pct": report.pnl.axis_p_quota_pct,
            "axis_d_api_usd": report.pnl.axis_d_api_usd,
            "axis_f_local_offload_usd": report.pnl.axis_f_local_offload_usd,
        },
        "utilization_gauge": {
            "current_pct": report.gauge.current_pct,
            "projected_close_pct": report.gauge.projected_close_pct,
            "target_pct": report.gauge.target_pct,
            "gap_to_target_pct": report.gauge.gap_to_target_pct,
            "status": report.gauge.status,
        },
        "cost_center_roi": [
            {
                "cost_center": cc.key,
                "axis": cc.axis,
                "usd": cc.usd,
                "tokens": cc.tokens,
                "events": cc.events,
                "usd_per_1k_tokens": cc.usd_per_1k_tokens,
            }
            for cc in report.cost_centers
        ],
        "unknown_usage_pct": report.unknown_pct,
    }


# ── Entry point ──────────────────────────────────────────────────────────────
def export(
    *,
    forecast_path: Path = _DEFAULT_FORECAST,
    ledger_path: Path = _DEFAULT_LEDGER,
    fmt: str = "prometheus",
) -> str:
    """Load inputs, build the report, render in the requested format."""
    report = build_report(load_forecast(forecast_path), load_ledger(ledger_path))
    if fmt == "json":
        return json.dumps(render_json(report), indent=2, ensure_ascii=False)
    return render_prometheus(report)


def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="chromatic token economy exporter")
    parser.add_argument("--forecast", type=Path, default=_DEFAULT_FORECAST)
    parser.add_argument("--ledger", type=Path, default=_DEFAULT_LEDGER)
    parser.add_argument("--format", choices=("prometheus", "json"), default="prometheus")
    args = parser.parse_args(list(argv) if argv is not None else None)
    sys.stdout.write(export(forecast_path=args.forecast, ledger_path=args.ledger, fmt=args.format))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
