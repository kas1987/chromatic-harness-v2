"""BEAD B3: portfolio token telemetry — the posting engine.

Per ``08_PDRS/TOKEN_ECONOMY_SPEC.md`` section 5, this module normalizes raw
usage signals into the canonical ``ledger.jsonl`` posting output and bridges the
``today.json`` + ccusage spend stream into the existing ``daily.jsonl`` sink
(fixing the ``$0``-forecast-while-today.json-shows-spend gap).

It is **reuse-first**: it does NOT re-implement aggregation or forecasting. It
only POSTS normalized rows. Downstream consumers (``budget_forecast_snapshot``,
the exporter) read those rows.

Pipeline:
  1. ``bridge_today_to_daily()`` — parse ``~/.claude/powerline/usage/today.json``
     (ccusage event shape) and append per-event ``$`` rows to
     ``07_LOGS_AND_AUDIT/budget/daily.jsonl`` via ``BudgetLedger.append_daily``.
  2. ``build_ledger_rows()`` — join ``routes_*.jsonl`` × ``providers.yaml``
     (``type`` → axis, via :mod:`router.billing_axis`) × ``pricing.json`` to
     backfill ``cost_estimate_usd`` and stamp ``billing_axis``; fold in the
     ``today.json`` native-Claude stream as Axis ``P`` rows.
  3. Each row carries a ``decision_id`` join key and is classified into an
     ``unknown_usage`` confidence band (never silently hidden).
  4. ``post_ledger()`` — emit ``07_LOGS_AND_AUDIT/budget/ledger.jsonl``.

Ledger row shape (spec section 3)::

    {decision_id, ts, axis, cost_center{repo,agent,tool,mcp,model,c_level,t_level},
     tokens, usd, quota_delta_pct}

with two telemetry extensions kept alongside (never replacing) the canonical
fields: ``source`` (``today`` | ``routes``) and ``confidence`` (``known`` |
``unknown``).
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

# ``02_RUNTIME`` is on pythonpath (pytest.ini / conftest); import the B2 axis.
_REPO = Path(__file__).resolve().parent.parent
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from router.billing_axis import classify as classify_axis  # noqa: E402

# ── Default paths (all overridable, for tests / alternate roots) ────────────
_DEFAULT_TODAY = Path.home() / ".claude" / "powerline" / "usage" / "today.json"
_DEFAULT_PRICING = Path.home() / ".claude" / "powerline" / "usage" / "pricing.json"
_DEFAULT_PROVIDERS = _REPO / "config" / "routing" / "providers.yaml"
_DEFAULT_ROUTES_DIR = _REPO / "07_LOGS_AND_AUDIT" / "routing"
_DEFAULT_BUDGET_DIR = _REPO / "07_LOGS_AND_AUDIT" / "budget"

# Cache-pricing keys (per-million-token rates) used to backfill usd.
_RATE_KEYS = ("input", "output", "cache_write_5m", "cache_read")


# ── Cost center / ledger row dataclasses ────────────────────────────────────
@dataclass
class CostCenter:
    repo: str = ""
    agent: str = ""
    tool: str = ""
    mcp: str = ""
    model: str = ""
    c_level: str | None = None
    t_level: str | None = None


@dataclass
class LedgerRow:
    decision_id: str
    ts: str
    axis: str  # P | D | F
    cost_center: CostCenter
    tokens: int
    usd: float
    quota_delta_pct: float | None
    source: str  # today | routes
    confidence: str  # known | unknown

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["usd"] = round(self.usd, 6)
        if self.quota_delta_pct is not None:
            d["quota_delta_pct"] = round(self.quota_delta_pct, 6)
        return d


# ── Loaders ─────────────────────────────────────────────────────────────────
def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_pricing(path: Path = _DEFAULT_PRICING) -> dict[str, dict]:
    """Return the ``model -> rate`` table from powerline ``pricing.json``."""
    if not Path(path).is_file():
        return {}
    try:
        return _read_json(Path(path)).get("data", {}) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_provider_registry(path: Path = _DEFAULT_PROVIDERS) -> dict[str, dict]:
    """Return the ``providers.yaml`` registry (``id -> cfg``)."""
    if not Path(path).is_file():
        return {}
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("providers", {}) or {}


def _iter_jsonl(path: Path) -> Iterable[dict]:
    if not Path(path).is_file():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


# ── Cost backfill ─────────────────────────────────────────────────────────--
def estimate_usd_from_usage(model: str, usage: dict, pricing: dict[str, dict]) -> float | None:
    """Estimate USD from a ccusage-style ``usage`` block + pricing table.

    Rates in ``pricing.json`` are per-MILLION tokens. Returns ``None`` when the
    model is absent from the pricing table (caller marks ``unknown``).
    """
    rate = pricing.get(model)
    if not rate:
        return None
    inp = float(usage.get("inputTokens", 0) or 0)
    out = float(usage.get("outputTokens", 0) or 0)
    cw = float(usage.get("cacheCreationInputTokens", 0) or 0)
    cr = float(usage.get("cacheReadInputTokens", 0) or 0)
    cost = (
        inp * float(rate.get("input", 0))
        + out * float(rate.get("output", 0))
        + cw * float(rate.get("cache_write_5m", rate.get("input", 0)))
        + cr * float(rate.get("cache_read", 0))
    ) / 1_000_000.0
    return cost


def _usage_tokens(usage: dict) -> int:
    return int(
        (usage.get("inputTokens", 0) or 0)
        + (usage.get("outputTokens", 0) or 0)
        + (usage.get("cacheCreationInputTokens", 0) or 0)
        + (usage.get("cacheReadInputTokens", 0) or 0)
    )


def _decision_id(*parts: Any) -> str:
    """Stable join key from event identity (request_id when present, else hash)."""
    raw = "|".join(str(p) for p in parts if p not in (None, ""))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# ── today.json (native Claude session) → Axis P rows ────────────────────────
def today_rows(today: dict, pricing: dict[str, dict]) -> list[LedgerRow]:
    """Map ccusage ``today.json`` events to Axis-P ledger rows.

    Native Claude in-session usage is **Axis P** (prepaid quota): the dollar
    figure is a *dollar-equivalent* carried in ``usd`` for offload/ROI math, not
    a billed charge. Events whose ``model`` is not in ``pricing.json`` (e.g.
    ``<synthetic>``) are stamped ``unknown`` — never dropped.
    """
    rows: list[LedgerRow] = []
    for ev in today.get("data", []) or []:
        model = str(ev.get("model", "") or "")
        usage = ev.get("usage", {}) or {}
        ts = str(ev.get("timestamp", "") or "")
        reported = ev.get("costUSD")
        est = estimate_usd_from_usage(model, usage, pricing)
        # Prefer ccusage's own costUSD; fall back to our estimate.
        usd = float(reported) if reported is not None else (est or 0.0)
        known = (model in pricing) and (reported is not None or est is not None)
        rows.append(
            LedgerRow(
                decision_id=_decision_id("today", ts, model, usd),
                ts=ts,
                axis="P",
                cost_center=CostCenter(model=model, agent="native_claude", repo=""),
                tokens=_usage_tokens(usage),
                usd=usd,
                quota_delta_pct=None,  # filled by forecast layer from quota_state
                source="today",
                confidence="known" if known else "unknown",
            )
        )
    return rows


# ── routes_*.jsonl → axis-stamped rows ──────────────────────────────────────
def route_rows(
    routes: Iterable[dict],
    registry: dict[str, dict],
    pricing: dict[str, dict],
) -> list[LedgerRow]:
    """Join routing events with the axis classifier + pricing backfill."""
    rows: list[LedgerRow] = []
    for ev in routes:
        provider = str(ev.get("selected_provider", "") or "")
        model = str(ev.get("selected_model", "") or "")
        ts = str(ev.get("timestamp", "") or "")
        # A real provider is required to assign an axis; blank/mock → unknown.
        if provider and provider != "mock":
            axis = classify_axis(provider, registry=registry)
            confidence = "known"
        else:
            axis = "D"  # conservative ceiling for unattributable events
            confidence = "unknown"

        cost = ev.get("cost_estimate_usd")
        usd = float(cost) if cost is not None else 0.0
        if cost is None:
            confidence = "unknown"  # null cost is the gate.py:427 backfill gap

        decision_id = ev.get("decision_id") or _decision_id("routes", ts, ev.get("request_id"), provider, model)
        rows.append(
            LedgerRow(
                decision_id=str(decision_id),
                ts=ts,
                axis=axis,
                cost_center=CostCenter(
                    repo=str(ev.get("repo", "") or ""),
                    agent=str(ev.get("caller", "") or ""),
                    tool=str(ev.get("task_type", "") or ""),
                    model=model,
                    c_level=ev.get("c_level") or ev.get("c_class"),
                    t_level=ev.get("t_level") or provider,
                ),
                tokens=0,  # routes carry no token counts (cost is pre-estimated)
                usd=usd,
                quota_delta_pct=None,
                source="routes",
                confidence=confidence,
            )
        )
    return rows


def _routes_files(routes_dir: Path) -> list[Path]:
    return sorted(Path(routes_dir).glob("routes_*.jsonl"))


def build_ledger_rows(
    *,
    today_path: Path = _DEFAULT_TODAY,
    pricing_path: Path = _DEFAULT_PRICING,
    providers_path: Path = _DEFAULT_PROVIDERS,
    routes_dir: Path = _DEFAULT_ROUTES_DIR,
    routes_files: list[Path] | None = None,
) -> list[LedgerRow]:
    """Build the full normalized ledger (today.json + all routes files)."""
    pricing = load_pricing(pricing_path)
    registry = load_provider_registry(providers_path)

    rows: list[LedgerRow] = []
    if Path(today_path).is_file():
        rows.extend(today_rows(_read_json(Path(today_path)), pricing))

    files = routes_files if routes_files is not None else _routes_files(routes_dir)
    for rf in files:
        rows.extend(route_rows(_iter_jsonl(rf), registry, pricing))
    return rows


# ── Confidence band summary (never hide the unknown share) ──────────────────
@dataclass
class ConfidenceBand:
    total_events: int = 0
    known_events: int = 0
    unknown_events: int = 0
    total_usd: float = 0.0
    unknown_usd: float = 0.0
    by_axis: dict[str, float] = field(default_factory=dict)

    @property
    def unknown_pct(self) -> float:
        if not self.total_events:
            return 0.0
        return round(100.0 * self.unknown_events / self.total_events, 2)


def confidence_band(rows: list[LedgerRow]) -> ConfidenceBand:
    band = ConfidenceBand()
    for r in rows:
        band.total_events += 1
        band.total_usd += r.usd
        band.by_axis[r.axis] = round(band.by_axis.get(r.axis, 0.0) + r.usd, 6)
        if r.confidence == "known":
            band.known_events += 1
        else:
            band.unknown_events += 1
            band.unknown_usd += r.usd
    band.total_usd = round(band.total_usd, 6)
    band.unknown_usd = round(band.unknown_usd, 6)
    return band


# ── today.json → daily.jsonl bridge (wires the ledger.py stub) ──────────────
def bridge_today_to_daily(
    *,
    today_path: Path = _DEFAULT_TODAY,
    pricing_path: Path = _DEFAULT_PRICING,
    budget_dir: Path = _DEFAULT_BUDGET_DIR,
) -> float:
    """Append per-event ``$`` rows from today.json into ``daily.jsonl``.

    Reuses :meth:`BudgetLedger.append_daily` (spec reuse map) rather than
    writing the sink format by hand. Returns total USD bridged. This is the
    concrete wiring the ``ingest_claude_usage_hook()`` stub (ledger.py:228) was
    a placeholder for.

    Idempotent: today.json is the *full* current-day snapshot, so this bridge
    re-reads the same events on every governance loop. Each event's stable
    ``decision_id`` is recorded in the sink; already-posted ids are skipped, so
    re-runs do not N-count (the daily.jsonl inflation bug). Real event
    timestamps are preserved so spend lands on the day it happened.
    """
    from budget.ledger import BudgetLedger  # local import: optional dep path

    if not Path(today_path).is_file():
        return 0.0
    pricing = load_pricing(pricing_path)
    rows = today_rows(_read_json(Path(today_path)), pricing)

    ledger = BudgetLedger(repo_root=Path(budget_dir).parent.parent)
    # Redirect the sink to the requested budget_dir (test isolation).
    ledger.daily_log = Path(budget_dir) / "daily.jsonl"

    # Build the set of already-posted decision_ids so re-runs never double-count.
    seen: set[str] = set()
    if ledger.daily_log.is_file():
        for line in ledger.daily_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                did = json.loads(line).get("decision_id", "")
            except json.JSONDecodeError:
                continue
            if did:
                seen.add(did)

    total = 0.0
    for r in rows:
        if r.decision_id in seen:
            continue
        note = "" if r.confidence == "known" else "unknown_usage"
        ledger.append_daily(
            r.usd,
            source=f"today:{r.cost_center.model or 'unknown'}",
            note=note,
            decision_id=r.decision_id,
            timestamp=r.ts,
        )
        seen.add(r.decision_id)
        total += r.usd
    return round(total, 6)


# ── Emit ledger.jsonl ───────────────────────────────────────────────────────
def post_ledger(
    rows: list[LedgerRow],
    *,
    budget_dir: Path = _DEFAULT_BUDGET_DIR,
) -> Path:
    """Write the normalized ledger to ``07_LOGS_AND_AUDIT/budget/ledger.jsonl``."""
    out = Path(budget_dir) / "ledger.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    return out


def run(
    *,
    today_path: Path = _DEFAULT_TODAY,
    pricing_path: Path = _DEFAULT_PRICING,
    providers_path: Path = _DEFAULT_PROVIDERS,
    routes_dir: Path = _DEFAULT_ROUTES_DIR,
    budget_dir: Path = _DEFAULT_BUDGET_DIR,
    bridge: bool = True,
) -> dict[str, Any]:
    """Full posting run: bridge today→daily, build + post ledger, return summary."""
    bridged = 0.0
    if bridge:
        bridged = bridge_today_to_daily(today_path=today_path, pricing_path=pricing_path, budget_dir=budget_dir)
    rows = build_ledger_rows(
        today_path=today_path,
        pricing_path=pricing_path,
        providers_path=providers_path,
        routes_dir=routes_dir,
    )
    ledger_path = post_ledger(rows, budget_dir=budget_dir)
    band = confidence_band(rows)
    return {
        "ledger_path": str(ledger_path),
        "rows": len(rows),
        "bridged_usd": bridged,
        "confidence_band": asdict(band),
        "unknown_pct": band.unknown_pct,
    }


def main(argv: list[str] | None = None) -> int:
    summary = run()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
