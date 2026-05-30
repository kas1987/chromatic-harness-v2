"""Tests for Gap A: bd ready queue injection at SessionStart."""

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "session_start", _REPO / "scripts" / "session_start.py"
)
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)  # type: ignore


def test_prints_ready_beads(monkeypatch, capsys):
    monkeypatch.setattr(
        ss, "_bd", lambda args, timeout=20: (0, "chr-1 first\nchr-2 second")
    )
    ss._inject_ready_queue()
    out = capsys.readouterr().out
    assert "Ready beads" in out
    assert "chr-1 first" in out and "chr-2 second" in out


def test_respects_limit(monkeypatch, capsys):
    many = "\n".join(f"chr-{i} t{i}" for i in range(20))
    monkeypatch.setattr(ss, "_bd", lambda args, timeout=20: (0, many))
    ss._inject_ready_queue(limit=3)
    out = capsys.readouterr().out
    assert out.count("chr-") == 3


def test_silent_when_bd_missing(monkeypatch, capsys):
    monkeypatch.setattr(ss, "_bd", lambda args, timeout=20: (127, ""))
    ss._inject_ready_queue()
    assert capsys.readouterr().out == ""


def test_silent_when_empty(monkeypatch, capsys):
    monkeypatch.setattr(ss, "_bd", lambda args, timeout=20: (0, "   "))
    ss._inject_ready_queue()
    assert capsys.readouterr().out == ""
