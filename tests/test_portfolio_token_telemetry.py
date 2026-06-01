"""BEAD B3: posting engine (tools/portfolio_token_telemetry.py).

Asserts, against a small fixture ``today.json`` + a routes sample, that:
  * ledger rows are emitted with axis stamping (P / D / F) per the spec,
  * the today.json → daily.jsonl bridge writes the expected $ total,
  * the ``unknown_usage`` confidence band is carried (never hidden),
  * each row carries a ``decision_id`` join key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import portfolio_token_telemetry as ptt  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def pricing_file(tmp_path: Path) -> Path:
    data = {
        "data": {
            "claude-sonnet-4-6": {
                "name": "claude-sonnet-4-6",
                "input": 3,
                "output": 15,
                "cache_write_5m": 3.75,
                "cache_read": 0.3,
            }
        },
        "timestamp": 1780158038141,
    }
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def today_file(tmp_path: Path) -> Path:
    data = {
        "data": [
            {
                "timestamp": "2026-05-30T06:31:17.142Z",
                "usage": {
                    "inputTokens": 1_000_000,
                    "outputTokens": 0,
                    "cacheCreationInputTokens": 0,
                    "cacheReadInputTokens": 0,
                },
                "costUSD": 3.0,
                "model": "claude-sonnet-4-6",
            },
            {
                # Unknown model (not in pricing) -> unknown band, never dropped.
                "timestamp": "2026-05-30T06:32:00.000Z",
                "usage": {"inputTokens": 5, "outputTokens": 5},
                "costUSD": None,
                "model": "<synthetic>",
            },
        ]
    }
    p = tmp_path / "today.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def providers_file(tmp_path: Path) -> Path:
    data = {
        "version": "2.0",
        "providers": {
            "ollama": {"type": "local"},
            "openai": {"type": "frontier"},
        },
    }
    p = tmp_path / "providers.yaml"
    import yaml

    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


@pytest.fixture
def routes_file(tmp_path: Path) -> Path:
    events = [
        # native_claude -> Axis P
        {
            "timestamp": "2026-05-30T07:00:00+00:00",
            "request_id": "r1",
            "caller": "gate.py",
            "task_type": "coding",
            "repo": "harness",
            "selected_provider": "native_claude",
            "selected_model": "claude-opus-4-8",
            "cost_estimate_usd": 0.0,
        },
        # openai -> Axis D (frontier)
        {
            "timestamp": "2026-05-30T07:01:00+00:00",
            "request_id": "r2",
            "caller": "gate.py",
            "task_type": "review",
            "repo": "harness",
            "selected_provider": "openai",
            "selected_model": "gpt-x",
            "cost_estimate_usd": 0.42,
        },
        # ollama -> Axis F (local)
        {
            "timestamp": "2026-05-30T07:02:00+00:00",
            "request_id": "r3",
            "caller": "gate.py",
            "task_type": "scaffold",
            "repo": "harness",
            "selected_provider": "ollama",
            "selected_model": "llama3.2:3b",
            "cost_estimate_usd": 0.0,
        },
        # mock / null cost -> unknown band, conservative Axis D
        {
            "timestamp": "2026-05-30T07:03:00+00:00",
            "request_id": "r4",
            "caller": "gate.py",
            "task_type": "coding",
            "repo": "harness",
            "selected_provider": "mock",
            "selected_model": "mock-v1",
            "cost_estimate_usd": None,
        },
    ]
    p = tmp_path / "routes_20260530.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return p


# ── Tests ─────────────────────────────────────────────────────────────────--
def test_today_rows_axis_p_and_unknown_band(today_file, pricing_file):
    pricing = ptt.load_pricing(pricing_file)
    rows = ptt.today_rows(ptt._read_json(today_file), pricing)
    assert len(rows) == 2
    known, unknown = rows[0], rows[1]
    # Native Claude session usage is Axis P regardless of dollar-equivalent.
    assert known.axis == "P"
    assert known.confidence == "known"
    assert known.usd == 3.0
    assert known.tokens == 1_000_000
    # Synthetic / unpriced model is carried as unknown — never hidden.
    assert unknown.confidence == "unknown"
    assert unknown.axis == "P"


def test_route_rows_axis_stamping(routes_file, providers_file, pricing_file):
    registry = ptt.load_provider_registry(providers_file)
    pricing = ptt.load_pricing(pricing_file)
    rows = ptt.route_rows(ptt._iter_jsonl(routes_file), registry, pricing)
    by_provider = {r.cost_center.t_level: r for r in rows}
    assert by_provider["native_claude"].axis == "P"
    assert by_provider["openai"].axis == "D"
    assert by_provider["openai"].usd == 0.42
    assert by_provider["ollama"].axis == "F"
    # mock / null cost -> unknown confidence, conservative D ceiling.
    mock = next(r for r in rows if r.source == "routes" and r.confidence == "unknown")
    assert mock.axis == "D"


def test_every_row_has_decision_id(today_file, pricing_file, providers_file, routes_file):
    rows = ptt.build_ledger_rows(
        today_path=today_file,
        pricing_path=pricing_file,
        providers_path=providers_file,
        routes_files=[routes_file],
    )
    assert rows, "expected non-empty ledger"
    assert all(r.decision_id for r in rows)
    # routes events reuse their request_id-derived join key deterministically.
    assert any(r.source == "routes" for r in rows)
    assert any(r.source == "today" for r in rows)


def test_confidence_band_reports_unknown(today_file, pricing_file, providers_file, routes_file):
    rows = ptt.build_ledger_rows(
        today_path=today_file,
        pricing_path=pricing_file,
        providers_path=providers_file,
        routes_files=[routes_file],
    )
    band = ptt.confidence_band(rows)
    assert band.total_events == 6  # 2 today + 4 routes
    assert band.unknown_events == 2  # synthetic + mock
    assert band.unknown_pct > 0
    # Axis bucket totals are present.
    assert set(band.by_axis).issubset({"P", "D", "F"})


def test_bridge_today_to_daily(today_file, pricing_file, tmp_path):
    budget_dir = tmp_path / "budget"
    budget_dir.mkdir()
    total = ptt.bridge_today_to_daily(today_path=today_file, pricing_path=pricing_file, budget_dir=budget_dir)
    assert total == 3.0  # 3.0 known + 0.0 unknown
    daily = budget_dir / "daily.jsonl"
    assert daily.is_file()
    lines = [json.loads(ln) for ln in daily.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert any(r.get("note") == "unknown_usage" for r in lines)
    assert any(r["source"].startswith("today:") for r in lines)


def test_post_ledger_writes_canonical_rows(today_file, pricing_file, providers_file, routes_file, tmp_path):
    budget_dir = tmp_path / "budget"
    rows = ptt.build_ledger_rows(
        today_path=today_file,
        pricing_path=pricing_file,
        providers_path=providers_file,
        routes_files=[routes_file],
    )
    out = ptt.post_ledger(rows, budget_dir=budget_dir)
    assert out.is_file()
    written = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(written) == len(rows)
    sample = written[0]
    # Canonical contract fields (spec section 3).
    for key in (
        "decision_id",
        "ts",
        "axis",
        "cost_center",
        "tokens",
        "usd",
        "quota_delta_pct",
    ):
        assert key in sample
    for cc_key in ("repo", "agent", "tool", "mcp", "model", "c_level", "t_level"):
        assert cc_key in sample["cost_center"]
