"""Smoke tests for log_integrity_check.py (gh-85 / NW-RG-085).

Tests build/verify chain logic in isolation using tmp files.
Network-free and does not touch the real audit log.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("log_integrity_check", REPO / "scripts" / "log_integrity_check.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["log_integrity_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj) + "\n")


def _make_log(tmp_path: Path, lines: list[dict], monkeypatch) -> tuple:
    """Write a JSONL log inside a fake repo root so relative_to() works."""
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    log = fake_repo / "test.jsonl"
    _write_jsonl(log, lines)
    mod = _load()
    monkeypatch.setattr(mod, "REPO", fake_repo)
    return mod, log


def test_sha256_is_hex_string():
    mod = _load()
    digest = mod._sha256(b"hello")
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_sha256_deterministic():
    mod = _load()
    assert mod._sha256(b"test") == mod._sha256(b"test")


def test_build_chain_single_line(tmp_path, monkeypatch):
    mod, log = _make_log(tmp_path, [{"event": "boot", "ts": "2026-01-01T00:00:00Z"}], monkeypatch)
    result = mod.build_chain(log)
    assert isinstance(result, dict)
    assert "entry_count" in result
    assert result["entry_count"] == 1
    assert "chain_hash" in result
    assert "genesis_hash" in result


def test_build_chain_multi_line(tmp_path, monkeypatch):
    entries = [{"seq": i, "val": f"entry-{i}"} for i in range(5)]
    mod, log = _make_log(tmp_path, entries, monkeypatch)
    result = mod.build_chain(log)
    assert result["entry_count"] == 5


def test_verify_chain_passes_for_unmodified(tmp_path, monkeypatch):
    mod, log = _make_log(tmp_path, [{"a": 1}, {"b": 2}, {"c": 3}], monkeypatch)
    stored = mod.build_chain(log)
    verify = mod.verify_chain(log, stored)
    assert verify["status"] == "ok"


def test_verify_chain_detects_tampering(tmp_path, monkeypatch):
    mod, log = _make_log(tmp_path, [{"a": 1}, {"b": 2}], monkeypatch)
    stored = mod.build_chain(log)
    # Tamper: change a value
    _write_jsonl(log, [{"a": 1}, {"b": 99}])
    verify = mod.verify_chain(log, stored)
    assert verify["status"] == "tampered"


def test_verify_chain_detects_truncation(tmp_path, monkeypatch):
    mod, log = _make_log(tmp_path, [{"a": 1}, {"b": 2}, {"c": 3}], monkeypatch)
    stored = mod.build_chain(log)
    # Truncate: remove last line
    _write_jsonl(log, [{"a": 1}, {"b": 2}])
    verify = mod.verify_chain(log, stored)
    assert verify["status"] == "tampered"


def test_run_build_returns_dict(monkeypatch):
    """run_build() wraps build_chain over LOG_TARGETS dict; returns summary."""
    mod = _load()
    # LOG_TARGETS is a dict[str, Path]; patch to empty dict for deterministic test
    monkeypatch.setattr(mod, "LOG_TARGETS", {})
    result = mod.run_build()
    assert isinstance(result, dict)


def test_write_status_artifact(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path)
    # Constant is MANIFEST_PATH (not INTEGRITY_ARTIFACT)
    monkeypatch.setattr(mod, "MANIFEST_PATH", tmp_path / "log_integrity_latest.json")
    dummy = {"status": "ok", "targets": [], "tampered_count": 0}
    path = mod.write_status_artifact(dummy)
    assert path.exists()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
