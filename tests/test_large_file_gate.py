"""Tests for scripts/large_file_gate.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import large_file_gate as gate  # noqa: E402

_MB = 1024 * 1024


def test_classify_thresholds():
    assert gate.classify(0, 5, 45) is None
    assert gate.classify(int(4.9 * _MB), 5, 45) is None
    assert gate.classify(int(5 * _MB), 5, 45) == "WARN"
    assert gate.classify(int(44 * _MB), 5, 45) == "WARN"
    assert gate.classify(int(45 * _MB), 5, 45) == "BLOCK"
    assert gate.classify(int(60 * _MB), 5, 45) == "BLOCK"


def test_allowlist_glob():
    pats = ["assets/*.bin", "models/**"]
    assert gate.is_allowlisted("assets/weights.bin", pats)
    assert not gate.is_allowlisted("src/main.py", pats)


def test_load_allowlist(tmp_path: Path):
    (tmp_path / gate.ALLOWLIST_FILE).write_text("# comment\nassets/*.bin\n\n  models/big.pt  \n", encoding="utf-8")
    assert gate.load_allowlist(tmp_path) == ["assets/*.bin", "models/big.pt"]


def test_scan_blocks_oversized(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gate, "ignored_matches", lambda paths: set())
    big = tmp_path / "huge.bin"
    big.write_bytes(b"\0" * int(6 * _MB))
    small = tmp_path / "ok.txt"
    small.write_text("hi", encoding="utf-8")
    findings = gate.scan(["huge.bin", "ok.txt"], tmp_path, warn_mb=1, block_mb=5)
    levels = {rel: lvl for lvl, rel, _ in findings}
    assert levels["huge.bin"] == "BLOCK"
    assert "ok.txt" not in levels


def test_scan_allowlisted_exempt(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gate, "ignored_matches", lambda paths: set())
    (tmp_path / gate.ALLOWLIST_FILE).write_text("huge.bin\n", encoding="utf-8")
    big = tmp_path / "huge.bin"
    big.write_bytes(b"\0" * int(6 * _MB))
    findings = gate.scan(["huge.bin"], tmp_path, warn_mb=1, block_mb=5)
    assert findings == []


def test_scan_blocks_ignored_regression(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gate, "ignored_matches", lambda paths: {"build/out.log"})
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.log").write_text("x", encoding="utf-8")
    findings = gate.scan(["build/out.log"], tmp_path, warn_mb=1, block_mb=5)
    assert findings and findings[0][0] == "BLOCK"
    assert ".gitignore" in findings[0][2]


def test_scan_skips_missing_and_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gate, "ignored_matches", lambda paths: set())
    (tmp_path / "adir").mkdir()
    findings = gate.scan(["does_not_exist", "adir"], tmp_path, warn_mb=1, block_mb=5)
    assert findings == []
