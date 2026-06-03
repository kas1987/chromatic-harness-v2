"""Tests for router pipeline I/O stage."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "02_RUNTIME"))

import pytest

from router.pipeline.io import read_stdin, emit_advisory, emit_deny


# ── read_stdin ───────────────────────────────────────────────────────────────


def test_read_stdin_valid_json():
    """Parses a valid JSON object from stdin."""
    payload = json.dumps({"tool_name": "Bash", "description": "run tests"})
    with patch("sys.stdin", io.StringIO(payload)):
        result = read_stdin()
    assert result == {"tool_name": "Bash", "description": "run tests"}


def test_read_stdin_empty_returns_empty_dict():
    """Returns empty dict when stdin is empty."""
    with patch("sys.stdin", io.StringIO("")):
        result = read_stdin()
    assert result == {}


def test_read_stdin_malformed_json_returns_empty_dict():
    """Returns empty dict on malformed JSON (fail-open)."""
    with patch("sys.stdin", io.StringIO("{not: valid")):
        result = read_stdin()
    assert result == {}


def test_read_stdin_json_array_returns_empty_dict():
    """Returns empty dict when JSON root is a list, not a dict."""
    with patch("sys.stdin", io.StringIO("[1, 2, 3]")):
        result = read_stdin()
    assert result == {}


def test_read_stdin_json_string_returns_empty_dict():
    """Returns empty dict when JSON root is a bare string."""
    with patch("sys.stdin", io.StringIO('"just a string"')):
        result = read_stdin()
    assert result == {}


def test_read_stdin_nested_dict():
    """Correctly parses nested dict structures."""
    payload = json.dumps({"a": {"b": {"c": 42}}, "list": [1, 2]})
    with patch("sys.stdin", io.StringIO(payload)):
        result = read_stdin()
    assert result["a"]["b"]["c"] == 42
    assert result["list"] == [1, 2]


def test_read_stdin_unicode_preserved():
    """Unicode content in JSON is preserved."""
    payload = json.dumps({"msg": "héllo wörld 中文"})
    with patch("sys.stdin", io.StringIO(payload)):
        result = read_stdin()
    assert result["msg"] == "héllo wörld 中文"


def test_read_stdin_whitespace_only_returns_empty():
    """Returns empty dict for whitespace-only stdin."""
    with patch("sys.stdin", io.StringIO("   \n\t  ")):
        result = read_stdin()
    # json.loads raises on whitespace → empty dict
    assert result == {}


# ── emit_advisory ─────────────────────────────────────────────────────────────


def test_emit_advisory_writes_valid_json(capsys):
    """emit_advisory writes parseable JSON to stdout."""
    emit_advisory("test advisory message")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "hookSpecificOutput" in data
    assert data["hookSpecificOutput"]["additionalContext"] == "test advisory message"


def test_emit_advisory_no_permission_decision(capsys):
    """emit_advisory does not include a permissionDecision key."""
    emit_advisory("some context")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "permissionDecision" not in data["hookSpecificOutput"]


def test_emit_advisory_empty_string(capsys):
    """emit_advisory handles an empty advisory string."""
    emit_advisory("")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["hookSpecificOutput"]["additionalContext"] == ""


def test_emit_advisory_unicode(capsys):
    """emit_advisory preserves unicode characters."""
    emit_advisory("advisory with unicode: héllo 中文")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "héllo" in data["hookSpecificOutput"]["additionalContext"]


def test_emit_advisory_no_stderr(capsys):
    """emit_advisory does not write to stderr."""
    emit_advisory("quiet advisory")
    captured = capsys.readouterr()
    assert captured.err == ""


# ── emit_deny ────────────────────────────────────────────────────────────────


def test_emit_deny_sets_deny_decision(capsys):
    """emit_deny sets permissionDecision to 'deny'."""
    emit_deny("too expensive")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_emit_deny_includes_deny_reason(capsys):
    """emit_deny embeds the advisory in denyReason."""
    emit_deny("use cheaper tier")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "use cheaper tier" in data["hookSpecificOutput"]["denyReason"]


def test_emit_deny_includes_additional_context(capsys):
    """emit_deny also sets additionalContext to the advisory."""
    emit_deny("budget exceeded")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["hookSpecificOutput"]["additionalContext"] == "budget exceeded"


def test_emit_deny_deny_reason_contains_prefix(capsys):
    """emit_deny prepends 'Use cheaper tier instead.' to denyReason."""
    emit_deny("advisory text")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["hookSpecificOutput"]["denyReason"].startswith("Use cheaper tier instead.")


def test_emit_deny_unicode(capsys):
    """emit_deny handles unicode in advisory."""
    emit_deny("Coût trop élevé")
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "Coût" in data["hookSpecificOutput"]["additionalContext"]


def test_emit_deny_no_stderr(capsys):
    """emit_deny does not write to stderr."""
    emit_deny("quiet deny")
    captured = capsys.readouterr()
    assert captured.err == ""


# ── round-trip: read_stdin → emit_advisory ────────────────────────────────────


def test_round_trip_advisory(capsys):
    """Reading a hook payload and emitting advisory preserves the contract."""
    hook_payload = {
        "tool_name": "Bash",
        "description": "run heavy analysis",
        "input": {"command": "python analyze.py"},
    }
    with patch("sys.stdin", io.StringIO(json.dumps(hook_payload))):
        parsed = read_stdin()

    advisory = f"tool={parsed['tool_name']} desc={parsed['description']}"
    emit_advisory(advisory)
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert "Bash" in out["hookSpecificOutput"]["additionalContext"]
    assert "heavy analysis" in out["hookSpecificOutput"]["additionalContext"]
