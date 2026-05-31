#!/usr/bin/env python3
"""Portfolio token forecaster — Axis P (prepaid quota) projection + ROI fold-in.

This is bead **B6** of the TOKEN_ECONOMY_SPEC token/quota control plane. It does
NOT rebuild aggregation: it extends the EXISTING ``forecast_latest.json`` contract
(built by ``scripts/budget_forecast_snapshot.py``) with an ``axis_prepaid`` block
and folds the two seed tools (``quota_roi.py`` C×T ROI card, ``weekly_budget.py``
ccusage ``$`` forecast) into the same report.

Per spec §1/§6 the **primary** budget is the prepaid weekly Claude quota (Axis P),
target ≥90% weekly utilization. The risk semantics are **INVERTED**: a projected
weekly close BELOW 90% is RED (under-utilizing a prepaid depleting asset), at/above
90% is GREEN. This is the opposite of the Axis D ($-ceiling) risk in the base
snapshot, where over-cap is RED.

Inputs (all reuse, never re-aggregate):
  - ``forecast_latest.json``           — base control-plane shape (extended here).
  - ``quota_state.json``               — read ONLY through ``quota_state.py``'s
                                          source-abstracted reader (spec §4); the
                                          weekly % is the verified-only Axis P signal.
  - ``ledger.jsonl``                   — normalized postings (B3) for the ROI card.
  - ``budget_forecast_accuracy.py``    — variance/accuracy (spec §6 "emit variance").

Usage:
  python tools/portfolio_token_forecast.py [--write] [--ccusage]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BUDGET_DIR = REPO / "07_LOGS_AND_AUDIT" / "budget"
FORECAST_LATEST = BUDGET_DIR / "forecast_latest.json"
LEDGER = BUDGET_DIR / "ledger.jsonl"
DEFAULT_OUT = FORECAST_LATEST

# Reuse the spec target; do NOT introduce a new target key (spec §9).
TARGET_PCT = 90.0

# Fold in the C×T ROI routing card verbatim from quota_roi.py (seed tool).
ROI_ROUTING_CARD = [
    {
        "c_level": "C1 mechanical",
        "example": "format/convert/extract, frontmatter, json->table",
        "tier": "T0 local (llama3.2/ollama)",
        "quota": "FREE - quota-neutral",
        "spends_quota": False,
    },
    {
        "c_level": "C2 structured",
        "example": "single-file change, smoke test, 1-file PR review (<=3 files)",
        "tier": "T0-T2 local / cheap API",
        "quota": "FREE / tiny $",
        "spends_quota": False,
    },
    {
        "c_level": "C3 reasoning",
        "example": "multi-file integration, root-cause, refactor (<=10 files)",
        "tier": "T3 Claude Sonnet (cloud)",
        "quota": "SPENDS QUOTA - high ROI",
        "spends_quota": True,
    },
    {
        "c_level": "C4 creative",
        "example": "brainstorm, design, architecture, research synth (unbounded)",
        "tier": "T4 Claude Opus / native",
        "quota": "SPENDS QUOTA - highest ROI",
        "spends_quota": True,
    },
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _load_module(name: str, path: Path):
    """Load a sibling reuse module without polluting sys.modules permanently."""
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:  # pragma: no cover - defensive
        return None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses (which resolve cls.__module__ via
    # sys.modules) load correctly under @dataclass with string annotations.
    import sys

    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:  # pragma: no cover - defensive fail-open
        sys.modules.pop(name, None)
        return None
    return module


def _read_quota_state(quota_state_path: Path | str | None):
    """Read Axis P signal through the source-abstracted quota_state.py reader."""
    reader_mod = _load_module(
        "quota_state", REPO / "02_RUNTIME" / "budget" / "quota_state.py"
    )
    if reader_mod is None:  # pragma: no cover - defensive
        return None
    reader = reader_mod.QuotaStateReader(quota_state_path)
    return reader.read()


def _parse_reset_days(reset: str | None, *, now: datetime) -> float | None:
    """Best-effort: turn a weekly_reset ISO timestamp into days remaining."""
    if not reset:
        return None
    try:
        dt = datetime.fromisoformat(str(reset).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (dt - now).total_seconds() / 86400.0)


def build_axis_prepaid(
    quota_state: Any,
    *,
    now: datetime,
    week_days: float = 7.0,
    target_pct: float = TARGET_PCT,
) -> dict[str, Any]:
    """Project the prepaid weekly quota close with INVERTED risk semantics.

    Mirrors ``quota_roi.py``'s deterministic linear pacing: project the close at
    the current %/day pace, compute the pace needed to reach target. ``status`` is
    inverted — projected close < target → ``red`` (under-utilizing the prepaid
    asset); >= target → ``green``.
    """
    # Manual seeds are valid for 24h; proxy captures expire in the normal 5min window.
    _ttl = 86400 if getattr(quota_state, "source", None) == "manual" else 300
    fresh = bool(
        quota_state is not None and quota_state.is_fresh(now=now, max_age_seconds=_ttl)
    )
    weekly_pct = quota_state.weekly_pct if quota_state is not None else None
    reset_at = quota_state.weekly_reset if quota_state is not None else None

    block: dict[str, Any] = {
        "weekly_quota_pct": weekly_pct,
        "target_pct": target_pct,
        "pace_needed": None,
        "projected_close_pct": None,
        "reset_at": reset_at,
        "status": "unknown",
        "fresh": fresh,
        "source": getattr(quota_state, "source", "absent"),
    }

    # No usable / fresh Axis P signal → conservative: treat as under (RED) but
    # flagged stale so the controller backs off rather than trusting a dead proxy.
    if weekly_pct is None or not fresh:
        block["status"] = "stale" if weekly_pct is None else "red"
        return block

    reset_days = _parse_reset_days(reset_at, now=now)
    if reset_days is None:
        reset_days = 1.0
    reset_days = max(reset_days, 1e-9)
    elapsed = max(week_days - reset_days, 1e-9)

    cur_pace = weekly_pct / elapsed  # %/day so far
    projected = min(100.0, weekly_pct + cur_pace * reset_days)
    remaining_to_target = max(0.0, target_pct - weekly_pct)
    pace_needed = remaining_to_target / reset_days  # %/day needed

    block["pace_needed"] = round(pace_needed, 4)
    block["projected_close_pct"] = round(projected, 4)
    block["current_pace_pct_per_day"] = round(cur_pace, 4)
    block["reset_days"] = round(reset_days, 4)
    # INVERTED: under target = red (bad, prepaid asset wasted); at/above = green.
    block["status"] = "green" if projected >= target_pct else "red"
    block["under_by_pct"] = round(max(0.0, target_pct - projected), 4)
    return block


def build_roi_card(ledger_path: Path | str | None = None) -> dict[str, Any]:
    """Fold in quota_roi.py's C×T routing card, attributed against ledger.jsonl.

    Reuses the B3 ledger postings to count quota-spending (Axis P) vs quota-neutral
    (Axis F local) events per cost center, so the static card is grounded in real
    attribution rather than synthetic load.
    """
    rows = _read_jsonl(Path(ledger_path) if ledger_path else LEDGER)
    by_axis: dict[str, int] = {}
    by_c_level: dict[str, int] = {}
    for r in rows:
        axis = str(r.get("axis", "")).upper()
        if axis:
            by_axis[axis] = by_axis.get(axis, 0) + 1
        cc = r.get("cost_center") if isinstance(r.get("cost_center"), dict) else {}
        c_level = cc.get("c_level")
        if c_level:
            by_c_level[str(c_level)] = by_c_level.get(str(c_level), 0) + 1
    return {
        "routing_card": ROI_ROUTING_CARD,
        "ledger_events_by_axis": by_axis,
        "ledger_events_by_c_level": by_c_level,
        "ledger_rows": len(rows),
        "note": "spend prepaid Axis-P quota on highest complexity (C3/C4); keep C1/C2 on free local",
    }


def build_dollar_forecast(*, run_ccusage: bool = False) -> dict[str, Any]:
    """Fold in weekly_budget.py's ccusage $ forecast (Axis D estimator only).

    By default this reads the already-computed Axis D projection from the base
    ``forecast_latest.json`` (no subprocess). When ``--ccusage`` is passed it
    invokes ``weekly_budget.py``'s deterministic ccusage model directly.
    """
    if not run_ccusage:
        base = _read_json(FORECAST_LATEST)
        fc = base.get("forecast") if isinstance(base.get("forecast"), dict) else {}
        weekly = (
            (base.get("limits") or {}).get("weekly")
            if isinstance(base.get("limits"), dict)
            else {}
        ) or {}
        return {
            "source": "forecast_latest.json",
            "end_of_week_usd": fc.get("end_of_week_usd"),
            "weekly_cap_usd": weekly.get("cap_usd"),
            "weekly_utilization_forecast": fc.get("weekly_utilization_forecast"),
            "axis": "D",
            "note": "ccusage $ is the Axis D estimator only; Axis P comes from quota_state",
        }
    # Direct ccusage path (live; non-deterministic environment dependent).
    wb = _load_module(
        "weekly_budget", Path.home() / ".claude" / "bin" / "weekly_budget.py"
    )
    if wb is None:  # pragma: no cover - defensive
        return {
            "source": "ccusage",
            "error": "weekly_budget.py not importable",
            "axis": "D",
        }
    try:  # pragma: no cover - requires ccusage/npx at runtime
        # weekly_budget.py is CLI-shaped; reuse its primitives directly.
        cap = wb.load_cap(None)
        import datetime as _dt

        today = _dt.date.today()
        weekly = wb.run_ccusage("weekly")
        weeks = (
            wb.totals_only(weekly.get("weekly", weekly))
            if hasattr(wb, "totals_only")
            else []
        )
        return {
            "source": "ccusage",
            "cap_usd": cap,
            "as_of": today.isoformat(),
            "axis": "D",
            "weeks_seen": len(weeks),
        }
    except Exception as exc:  # pragma: no cover
        return {"source": "ccusage", "error": str(exc), "axis": "D"}


def build_variance() -> dict[str, Any]:
    """Emit forecast variance via the EXISTING budget_forecast_accuracy.py (spec §6)."""
    acc = _load_module(
        "budget_forecast_accuracy", REPO / "scripts" / "budget_forecast_accuracy.py"
    )
    if acc is None:  # pragma: no cover - defensive
        return {"error": "budget_forecast_accuracy.py not importable"}
    try:
        payload = acc.build_accuracy()
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": str(exc)}
    return {
        "status": payload.get("status"),
        "metrics": payload.get("metrics"),
        "coverage": payload.get("coverage"),
        "recommendations": payload.get("recommendations"),
    }


def build_report(
    *,
    now: datetime | None = None,
    quota_state_path: Path | str | None = None,
    ledger_path: Path | str | None = None,
    forecast_latest_path: Path | str | None = None,
    run_ccusage: bool = False,
) -> dict[str, Any]:
    """Extend forecast_latest.json with axis_prepaid + ROI + $ + variance."""
    now_utc = (now or _now()).astimezone(timezone.utc)

    base_path = Path(forecast_latest_path) if forecast_latest_path else FORECAST_LATEST
    report = _read_json(base_path)  # the canonical control-plane shape (reused)

    quota_state = _read_quota_state(quota_state_path)
    report["axis_prepaid"] = build_axis_prepaid(
        quota_state, now=now_utc, target_pct=TARGET_PCT
    )
    report["roi_card"] = build_roi_card(ledger_path)
    report["dollar_forecast"] = build_dollar_forecast(run_ccusage=run_ccusage)
    report["forecast_variance"] = build_variance()
    report["portfolio_forecast_generated_at"] = now_utc.isoformat()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Portfolio token forecast (Axis P + ROI fold-in)"
    )
    parser.add_argument(
        "--write", action="store_true", help="Write extended forecast_latest.json"
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output artifact path")
    parser.add_argument(
        "--ccusage", action="store_true", help="Invoke ccusage live (Axis D $)"
    )
    args = parser.parse_args(argv)

    report = build_report(run_ccusage=args.ccusage)
    if args.write:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
