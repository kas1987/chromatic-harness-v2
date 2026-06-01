"""Tests for harness_health_check.py — the runtime cockpit (issue #79).

Network-free: TCP probes are monkeypatched; integrity checks run against
tmp_path fixtures. Verifies the pass/warn/fail contract, read-only default,
JSON+Markdown output, and the fail-open summarize().
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("harness_health_check", REPO / "scripts" / "harness_health_check.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Register before exec: @dataclass field introspection looks the module up in
    # sys.modules via cls.__module__, which is None for an unregistered module.
    sys.modules["harness_health_check"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── endpoint parsing ─────────────────────────────────────────────────────────


def test_parse_hostport_variants():
    mod = _load()
    assert mod._parse_hostport("127.0.0.1:11434") == ("127.0.0.1", 11434)
    assert mod._parse_hostport("http://localhost:8000/api") == ("localhost", 8000)
    assert mod._parse_hostport("https://host:7687") == ("host", 7687)
    assert mod._parse_hostport("no-port") is None
    assert mod._parse_hostport("host:notaport") is None


# ── service checks (probe monkeypatched) ─────────────────────────────────────


def test_service_reachable_is_pass(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "probe_tcp", lambda h, p, timeout=0.6: True)
    c = mod.check_service("ollama", "OLLAMA_URL", "127.0.0.1:11434")
    assert c.status == "pass"


def test_service_unreachable_is_warn_not_fail(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "probe_tcp", lambda h, p, timeout=0.6: False)
    c = mod.check_service("neo4j", "NEO4J_URL", "127.0.0.1:7687")
    assert c.status == "warn"  # optional service down must never FAIL the cockpit


def test_service_unparseable_endpoint_warns(monkeypatch):
    mod = _load()
    monkeypatch.setenv("RUDALO_URL", "garbage-no-port")
    c = mod.check_service("rudalo", "RUDALO_URL", "127.0.0.1:8800")
    assert c.status == "warn"


# ── integrity checks ─────────────────────────────────────────────────────────


def test_routing_log_detects_corruption(monkeypatch, tmp_path):
    mod = _load()
    rd = tmp_path / "routing"
    rd.mkdir()
    (rd / "routes_20260601.jsonl").write_text('{"ok":1}\n{bad json\n', encoding="utf-8")
    monkeypatch.setattr(mod, "ROUTING_DIR", rd)
    c = mod.check_routing_log()
    assert c.status == "fail"
    assert "corrupt" in c.message


def test_routing_log_clean_passes(monkeypatch, tmp_path):
    mod = _load()
    rd = tmp_path / "routing"
    rd.mkdir()
    (rd / "routes_20260601.jsonl").write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
    monkeypatch.setattr(mod, "ROUTING_DIR", rd)
    c = mod.check_routing_log()
    assert c.status == "pass"
    assert c.value["lines"] == 2


def test_routing_log_missing_fails(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "ROUTING_DIR", tmp_path / "nope")
    assert mod.check_routing_log().status == "fail"


def test_skill_inventory_counts(monkeypatch, tmp_path):
    mod = _load()
    sk = tmp_path / ".agents" / "skills" / "demo"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("# skill", encoding="utf-8")
    monkeypatch.setattr(mod, "REPO", tmp_path)
    c = mod.check_skill_inventory()
    assert c.status == "pass" and c.value == 1


# ── aggregation + output contract ────────────────────────────────────────────


def test_run_all_shape_and_exit_semantics(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "probe_tcp", lambda h, p, timeout=0.6: True)
    result = mod.run_all()
    assert set(result) >= {"generated_at_utc", "overall_status", "readiness_score", "counts", "checks"}
    assert result["overall_status"] in {"green", "yellow", "red"}
    # one check per service + 6 integrity checks (incl. lease status)
    assert len(result["checks"]) == len(mod.SERVICES) + 6


def test_to_markdown_renders_table(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "probe_tcp", lambda h, p, timeout=0.6: True)
    md = mod.to_markdown(mod.run_all())
    assert "# Harness Health Dashboard Cockpit" in md
    assert "| Check | Status | Message |" in md


def test_write_artifact_and_summarize_roundtrip(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "probe_tcp", lambda h, p, timeout=0.6: True)
    result = mod.run_all()
    jp, mp = mod.write_artifact(result)
    assert jp.exists() and mp.exists()
    s = mod.summarize()
    assert s["status"] == "ok"
    assert s["overall_status"] == result["overall_status"]


def test_summarize_no_scan_fail_open(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "empty")
    s = mod.summarize()
    assert s["status"] == "no_scan"


if __name__ == "__main__":
    import pytest
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
