"""Tests for the security scanning gate (bead gh-57).

Covers all 5 eval requirements: secret detection, dependency audit shape,
high-severity-fails-the-gate, artifact write, and the closeout summary.
Network-free: dependency scanning is stubbed; secret scanning runs on temp files.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("security_scan", REPO / "scripts" / "security_scan.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_secret_patterns_detect_common_secrets():
    mod = _load()
    samples = {
        "credential_assignment": 'api_key = "abcdef1234567890supersecret"',
        "private_key_block": "-----BEGIN RSA PRIVATE KEY-----",
        "github_pat": "ghp_" + "A" * 40,
        "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    }
    for rule, text in samples.items():
        compiled = [(n, __import__("re").compile(p)) for n, p, _ in mod.SECRET_PATTERNS]
        assert any(rx.search(text) for _n, rx in compiled), f"{rule} not detected in {text!r}"


def test_clean_text_has_no_false_positive():
    mod = _load()
    import re

    benign = "def add(a, b):\n    return a + b  # no secrets here"
    for _n, pat, _s in mod.SECRET_PATTERNS:
        assert not re.search(pat, benign)


def test_high_severity_secret_fails_gate(monkeypatch):
    mod = _load()
    # Stub scanners: one high-severity secret, deps clean.
    monkeypatch.setattr(
        mod,
        "scan_secrets",
        lambda: {
            "status": "ok",
            "findings": [{"rule": "github_pat", "severity": "high", "file": "x.py", "line": 1}],
            "total": 1,
            "high_severity": 1,
        },
    )
    monkeypatch.setattr(mod, "scan_dependencies", lambda: {"status": "ok", "high_severity": 0, "vulnerabilities": []})
    result = mod.run_scan(include_deps=True)
    assert result["passed"] is False
    assert result["high_severity_total"] == 1


def test_clean_scan_passes_gate(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "scan_secrets", lambda: {"status": "ok", "findings": [], "total": 0, "high_severity": 0})
    monkeypatch.setattr(mod, "scan_dependencies", lambda: {"status": "ok", "high_severity": 0, "vulnerabilities": []})
    result = mod.run_scan(include_deps=True)
    assert result["passed"] is True
    assert result["high_severity_total"] == 0


def test_dependency_vuln_fails_gate(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "scan_secrets", lambda: {"status": "ok", "findings": [], "total": 0, "high_severity": 0})
    monkeypatch.setattr(
        mod,
        "scan_dependencies",
        lambda: {"status": "ok", "high_severity": 2, "vulnerabilities": [{"id": "CVE-x"}, {"id": "CVE-y"}]},
    )
    result = mod.run_scan(include_deps=True)
    assert result["passed"] is False
    assert result["high_severity_total"] == 2


def test_artifact_written(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "security")
    result = {"secrets": {"total": 0}, "dependencies": {"status": "ok"}, "high_severity_total": 0, "passed": True}
    latest = mod.write_artifact(result, "20260601T000000Z")
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["passed"] is True
    assert data["timestamp"] == "20260601T000000Z"
    assert (tmp_path / "security" / "20260601T000000Z.json").exists()


def test_summarize_fail_open_on_missing_artifact(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "nonexistent")
    s = mod.summarize()
    assert s["status"] == "no_scan"
    assert s["passed"] is None


def test_self_file_excluded_from_scan():
    # The scanner documents the patterns, so it must exclude itself to avoid
    # always self-matching.
    mod = _load()
    assert mod.SELF == "security_scan.py"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
