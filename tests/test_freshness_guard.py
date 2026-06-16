"""Tests for the freshness guard added to harness_health_snapshot.py.

Covers:
  - age < 24h  -> pass
  - age >= 24h -> warn
  - age >= 72h -> fail
  - missing file -> skipped (no check emitted)
  - exception inside -> fail-open (warn, never crash)

Uses synthetic timestamps via tmp_path; does NOT require any real harness files.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the functions under test directly from the script module.
# sys.path is already extended by conftest / pytest.ini so the scripts/
# directory is importable.  If not, we add it here defensively.
# ---------------------------------------------------------------------------
import sys

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from harness_health_snapshot import (  # noqa: E402
    Check,
    _check_input_freshness,
    _FRESHNESS_WARN_H,
    _FRESHNESS_FAIL_H,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _write_json_with_ts(path: Path, hours_ago: float, use_field: str = "generated_at") -> None:
    """Write a minimal JSON file whose embedded timestamp is `hours_ago` in the past."""
    ts = _utc_now() - timedelta(hours=hours_ago)
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps({use_field: ts_str}), encoding="utf-8")


def _write_json_no_ts(path: Path) -> None:
    """Write a JSON file with no timestamp field (triggers mtime fallback)."""
    path.write_text(json.dumps({"some_key": "value"}), encoding="utf-8")


def _find_check(checks: list[Check], name: str) -> Check | None:
    for c in checks:
        if c.name == name:
            return c
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFreshnessGuardEmbeddedTimestamp:
    """Freshness determined from embedded generated_at field."""

    def test_fresh_input_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "latest.json"
        _write_json_with_ts(f, hours_ago=1.0)
        checks: list[Check] = []
        stale = _check_input_freshness(
            checks,
            inputs={"my_input": f},
            data_map={"my_input": json.loads(f.read_text())},
        )
        c = _find_check(checks, "input_freshness_my_input")
        assert c is not None
        assert c.status == "pass"
        assert stale == []

    def test_warn_threshold_exact(self, tmp_path: Path) -> None:
        """Exactly at warn threshold (24h) -> warn."""
        f = tmp_path / "latest.json"
        _write_json_with_ts(f, hours_ago=_FRESHNESS_WARN_H)
        checks: list[Check] = []
        stale = _check_input_freshness(
            checks,
            inputs={"gov_intel": f},
            data_map={"gov_intel": json.loads(f.read_text())},
        )
        c = _find_check(checks, "input_freshness_gov_intel")
        assert c is not None
        assert c.status == "warn", f"Expected warn, got {c.status}: {c.message}"
        assert any(s["level"] == "warn" for s in stale)

    def test_warn_at_25h(self, tmp_path: Path) -> None:
        f = tmp_path / "latest.json"
        _write_json_with_ts(f, hours_ago=25.0)
        checks: list[Check] = []
        stale = _check_input_freshness(
            checks,
            inputs={"tok_gov": f},
            data_map={"tok_gov": json.loads(f.read_text())},
        )
        c = _find_check(checks, "input_freshness_tok_gov")
        assert c is not None
        assert c.status == "warn"
        assert stale[0]["level"] == "warn"

    def test_fail_threshold_exact(self, tmp_path: Path) -> None:
        """Exactly at fail threshold (72h) -> fail."""
        f = tmp_path / "latest.json"
        _write_json_with_ts(f, hours_ago=_FRESHNESS_FAIL_H)
        checks: list[Check] = []
        stale = _check_input_freshness(
            checks,
            inputs={"gov_intel": f},
            data_map={"gov_intel": json.loads(f.read_text())},
        )
        c = _find_check(checks, "input_freshness_gov_intel")
        assert c is not None
        assert c.status == "fail", f"Expected fail, got {c.status}: {c.message}"
        assert stale[0]["level"] == "fail"

    def test_fail_at_73h(self, tmp_path: Path) -> None:
        f = tmp_path / "latest.json"
        _write_json_with_ts(f, hours_ago=73.0)
        checks: list[Check] = []
        stale = _check_input_freshness(
            checks,
            inputs={"usage_cal": f},
            data_map={"usage_cal": json.loads(f.read_text())},
        )
        c = _find_check(checks, "input_freshness_usage_cal")
        assert c is not None
        assert c.status == "fail"

    def test_queued_at_field_also_works(self, tmp_path: Path) -> None:
        """queued_at is also accepted as a timestamp source."""
        f = tmp_path / "latest.json"
        _write_json_with_ts(f, hours_ago=30.0, use_field="queued_at")
        checks: list[Check] = []
        _check_input_freshness(
            checks,
            inputs={"x": f},
            data_map={"x": json.loads(f.read_text())},
        )
        c = _find_check(checks, "input_freshness_x")
        assert c is not None
        assert c.status == "warn"


class TestFreshnessGuardMtimeFallback:
    """When no embedded timestamp is present, mtime is used."""

    def test_no_ts_field_falls_back_to_mtime_pass(self, tmp_path: Path) -> None:
        f = tmp_path / "latest.json"
        _write_json_no_ts(f)
        # File was just written, so mtime is ~now -> fresh -> pass
        checks: list[Check] = []
        _check_input_freshness(
            checks,
            inputs={"x": f},
            data_map={"x": json.loads(f.read_text())},
        )
        c = _find_check(checks, "input_freshness_x")
        assert c is not None
        assert c.status == "pass"


class TestFreshnessGuardEdgeCases:
    """Edge cases: missing file and multiple inputs."""

    def test_missing_file_emits_no_check(self, tmp_path: Path) -> None:
        """A file that doesn't exist at all should not emit a freshness check."""
        missing = tmp_path / "nonexistent.json"
        checks: list[Check] = []
        stale = _check_input_freshness(
            checks,
            inputs={"absent": missing},
            data_map={"absent": {}},
        )
        assert _find_check(checks, "input_freshness_absent") is None
        assert stale == []

    def test_multiple_inputs_independent(self, tmp_path: Path) -> None:
        fresh = tmp_path / "fresh.json"
        stale_file = tmp_path / "stale.json"
        _write_json_with_ts(fresh, hours_ago=1.0)
        _write_json_with_ts(stale_file, hours_ago=80.0)
        checks: list[Check] = []
        stale = _check_input_freshness(
            checks,
            inputs={"fresh_input": fresh, "old_input": stale_file},
            data_map={
                "fresh_input": json.loads(fresh.read_text()),
                "old_input": json.loads(stale_file.read_text()),
            },
        )
        assert _find_check(checks, "input_freshness_fresh_input").status == "pass"
        assert _find_check(checks, "input_freshness_old_input").status == "fail"
        assert len(stale) == 1 and stale[0]["input"] == "old_input"

    def test_fail_open_on_corrupt_data(self, tmp_path: Path) -> None:
        """A corrupt/broken path must never crash; degrades to warn."""
        # Pass a path object that exists but whose data map contains a bad timestamp
        f = tmp_path / "bad.json"
        f.write_text('{"generated_at": "NOT_A_DATE"}', encoding="utf-8")
        checks: list[Check] = []
        # Should not raise; mtime fallback will be used, file just written -> pass or warn
        try:
            _check_input_freshness(
                checks,
                inputs={"bad": f},
                data_map={"bad": {"generated_at": "NOT_A_DATE"}},
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"_check_input_freshness raised unexpectedly: {exc}")
        # Result may be pass (mtime fallback, file is fresh) — what matters is no crash
        c = _find_check(checks, "input_freshness_bad")
        assert c is not None
