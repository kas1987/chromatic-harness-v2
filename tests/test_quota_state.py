"""Tests for the Axis P quota state reader (staleness + source abstraction)
and the quota proxy header-parse smoke path.

Per TOKEN_ECONOMY_SPEC §4: consumers depend only on ``quota_state.py``; the
proxy is import-clean + header-parse-smoke tested (no live socket).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"

if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget import quota_proxy  # noqa: E402
from budget.quota_state import (  # noqa: E402
    EMPTY_STATE,
    STALENESS_SECONDS,
    QuotaState,
    QuotaStateReader,
    read_quota_state,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _write(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record), encoding="utf-8")


# --------------------------------------------------------------------------- #
# quota_state.py — parse                                                        #
# --------------------------------------------------------------------------- #


def test_from_dict_parses_full_contract():
    now = _iso(datetime.now(timezone.utc))
    state = QuotaState.from_dict(
        {
            "weekly_pct": 87.5,
            "weekly_reset": "2026-06-02T00:00:00+00:00",
            "session_5h_pct": "12.0",
            "session_5h_reset": "2026-05-30T18:00:00+00:00",
            "representative_claim": "claim-abc",
            "status": "allowed",
            "captured_at": now,
            "source": "proxy",
        }
    )
    assert state.present is True
    assert state.weekly_pct == 87.5
    assert state.session_5h_pct == 12.0  # coerced from str
    assert state.representative_claim == "claim-abc"
    assert state.status == "allowed"
    assert state.source == "proxy"


def test_from_dict_tolerates_partial_record():
    state = QuotaState.from_dict({"weekly_pct": 50, "captured_at": _iso(datetime.now(timezone.utc))})
    assert state.weekly_pct == 50.0
    assert state.session_5h_pct is None
    assert state.present is True


def test_bad_pct_coerces_to_none():
    state = QuotaState.from_dict({"weekly_pct": "not-a-number"})
    assert state.weekly_pct is None


# --------------------------------------------------------------------------- #
# quota_state.py — staleness logic                                             #
# --------------------------------------------------------------------------- #


def test_fresh_state_is_fresh():
    captured = datetime.now(timezone.utc) - timedelta(seconds=30)
    state = QuotaState.from_dict({"weekly_pct": 90, "captured_at": _iso(captured)})
    assert state.is_fresh() is True
    age = state.age_seconds()
    assert age is not None and 25 <= age <= 60


def test_stale_state_is_not_fresh():
    captured = datetime.now(timezone.utc) - timedelta(seconds=STALENESS_SECONDS + 60)
    state = QuotaState.from_dict({"weekly_pct": 90, "captured_at": _iso(captured)})
    assert state.is_fresh() is False


def test_missing_captured_at_is_not_fresh():
    state = QuotaState.from_dict({"weekly_pct": 90})
    assert state.age_seconds() is None
    assert state.is_fresh() is False


def test_empty_state_never_fresh():
    assert EMPTY_STATE.present is False
    assert EMPTY_STATE.is_fresh() is False


def test_z_suffix_timestamp_parsed():
    captured = datetime.now(timezone.utc) - timedelta(seconds=10)
    z = captured.replace(tzinfo=None).isoformat() + "Z"
    state = QuotaState.from_dict({"weekly_pct": 90, "captured_at": z})
    assert state.is_fresh() is True


# --------------------------------------------------------------------------- #
# quota_state.py — reader (mock file) + source abstraction                      #
# --------------------------------------------------------------------------- #


def test_reader_reads_fresh_file(tmp_path):
    path = tmp_path / "quota_state.json"
    _write(
        path,
        {
            "weekly_pct": 88.0,
            "captured_at": _iso(datetime.now(timezone.utc)),
            "source": "proxy",
        },
    )
    reader = QuotaStateReader(path)
    state = reader.read()
    assert state.weekly_pct == 88.0
    assert reader.read_fresh() is not None
    assert reader.is_stale() is False


def test_reader_missing_file_fails_open(tmp_path):
    reader = QuotaStateReader(tmp_path / "nope.json")
    state = reader.read()
    assert state.present is False
    assert reader.read_fresh() is None
    assert reader.is_stale() is True


def test_reader_malformed_json_fails_open(tmp_path):
    path = tmp_path / "quota_state.json"
    path.write_text("{ this is not json", encoding="utf-8")
    reader = QuotaStateReader(path)
    assert reader.read().present is False
    assert reader.is_stale() is True


def test_reader_stale_file_guarded(tmp_path):
    path = tmp_path / "quota_state.json"
    captured = datetime.now(timezone.utc) - timedelta(seconds=STALENESS_SECONDS + 1)
    _write(path, {"weekly_pct": 88.0, "captured_at": _iso(captured)})
    reader = QuotaStateReader(path)
    assert reader.read().present is True  # loaded clean
    assert reader.read_fresh() is None  # but guarded as stale
    assert reader.is_stale() is True


def test_read_quota_state_convenience(tmp_path):
    path = tmp_path / "quota_state.json"
    _write(path, {"weekly_pct": 12.5, "captured_at": _iso(datetime.now(timezone.utc))})
    assert read_quota_state(path).weekly_pct == 12.5


# --------------------------------------------------------------------------- #
# quota_proxy.py — import-clean + header-parse smoke (no live socket)           #
# --------------------------------------------------------------------------- #


class _FakeHeaders:
    """Mimic http.client response header lookup (case-insensitive get)."""

    def __init__(self, mapping: dict[str, str]):
        self._m = {k.lower(): v for k, v in mapping.items()}

    def getheader(self, name: str, default=None):
        return self._m.get(name.lower(), default)


def test_proxy_parse_quota_headers_fraction():
    headers = _FakeHeaders(
        {
            "anthropic-ratelimit-unified-7d-utilization": "0.875",
            "anthropic-ratelimit-unified-5h-utilization": "0.10",
            "anthropic-ratelimit-unified-7d-reset": "2026-06-02T00:00:00Z",
            "anthropic-ratelimit-unified-5h-reset": "2026-05-30T18:00:00Z",
            "anthropic-ratelimit-unified-status": "allowed",
            "anthropic-ratelimit-unified-representative-claim": "claim-xyz",
        }
    )
    record = quota_proxy.parse_quota_headers(headers)
    assert record["weekly_pct"] == 87.5
    assert record["session_5h_pct"] == 10.0
    assert record["status"] == "allowed"
    assert record["representative_claim"] == "claim-xyz"
    assert record["weekly_reset"] == "2026-06-02T00:00:00Z"
    assert record["source"] == "proxy"
    assert record["captured_at"]  # stamped


def test_proxy_parse_quota_headers_percent_form():
    headers = _FakeHeaders({"anthropic-ratelimit-unified-7d-utilization": "42"})
    record = quota_proxy.parse_quota_headers(headers)
    assert record["weekly_pct"] == 42.0


def test_proxy_parse_missing_headers_fail_open():
    record = quota_proxy.parse_quota_headers(_FakeHeaders({}))
    assert record["weekly_pct"] is None
    assert record["session_5h_pct"] is None
    assert record["status"] is None


def test_proxy_write_and_state_reader_roundtrip(tmp_path):
    """End-to-end: proxy writes -> quota_state reader consumes (abstraction)."""
    headers = _FakeHeaders(
        {
            "anthropic-ratelimit-unified-7d-utilization": "0.9",
            "anthropic-ratelimit-unified-status": "allowed",
        }
    )
    record = quota_proxy.parse_quota_headers(headers)
    path = tmp_path / "quota_state.json"
    assert quota_proxy.write_quota_state(record, path) is True

    state = QuotaStateReader(path).read()
    assert state.weekly_pct == 90.0
    assert state.status == "allowed"
    assert state.is_fresh() is True


def test_proxy_build_server_constructs(monkeypatch):
    """Import-clean construction without binding the real port path."""
    server = quota_proxy.build_server(0, host="127.0.0.1")  # port 0 = ephemeral
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert server.RequestHandlerClass.state_path == quota_proxy.DEFAULT_STATE_PATH
    finally:
        server.server_close()
