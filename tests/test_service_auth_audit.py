"""Smoke tests for service_auth_audit.py (gh-87 / NW-RG-087).

Network-free: mocks socket probes so tests pass regardless of what services
are actually running on CI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("service_auth_audit", REPO / "scripts" / "service_auth_audit.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["service_auth_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_risk_level_ok_for_localhost():
    mod = _load()
    # service_auth_audit uses "name" key (not "service") in per-service dicts
    svc = {"name": "ollama", "port": 11434, "secure_default": True}
    risk = mod._risk_level(svc, "127.0.0.1", True)
    assert risk == "ok"


def test_risk_level_critical_for_all_interfaces():
    mod = _load()
    svc = {"name": "ollama", "port": 11434, "secure_default": True}
    risk = mod._risk_level(svc, "0.0.0.0", True)
    assert risk == "critical"


def test_risk_level_ok_when_not_running():
    mod = _load()
    svc = {"name": "neo4j_http", "port": 7474, "secure_default": False}
    risk = mod._risk_level(svc, None, False)
    assert risk == "ok"


def test_audit_service_offline_service():
    """Offline service should produce ok risk and running=False."""
    mod = _load()
    svc = {
        "name": "comfyui",
        "description": "Test",
        "port": 18188,  # unlikely to be open
        "secure_default": False,
        "notes": "",
    }
    with (
        patch.object(mod, "_is_port_open", return_value=False),
        patch.object(mod, "_get_listening_address", return_value=None),
    ):
        result = mod.audit_service(svc)
    assert result["running"] is False
    assert result["risk"] == "ok"


def test_audit_service_localhost_binding():
    """Service bound to 127.0.0.1 should report ok risk."""
    mod = _load()
    svc = {
        "name": "ollama",
        "description": "Ollama LLM server",
        "port": 11434,
        "secure_default": True,
        "notes": "",
    }
    with (
        patch.object(mod, "_is_port_open", return_value=True),
        patch.object(mod, "_get_listening_address", return_value="127.0.0.1"),
    ):
        result = mod.audit_service(svc)
    assert result["running"] is True
    assert result["listen_address"] == "127.0.0.1"
    assert result["risk"] == "ok"


def test_run_audit_returns_schema():
    """run_audit() should return a dict with expected top-level keys."""
    mod = _load()
    # Patch out network probes so test is deterministic
    with (
        patch.object(mod, "_is_port_open", return_value=False),
        patch.object(mod, "_get_listening_address", return_value=None),
    ):
        result = mod.run_audit()
    assert isinstance(result, dict)
    assert "schema_version" in result
    assert "overall_risk" in result
    assert "findings" in result
    assert isinstance(result["findings"], list)


def test_run_audit_no_critical_when_offline():
    """With all services offline the overall risk must not be critical."""
    mod = _load()
    with (
        patch.object(mod, "_is_port_open", return_value=False),
        patch.object(mod, "_get_listening_address", return_value=None),
    ):
        result = mod.run_audit()
    assert result["critical_count"] == 0
    assert result["overall_risk"] in ("low", "ok")


def test_write_artifact_creates_files(tmp_path, monkeypatch):
    """write_artifact() should write service_auth_latest.json in ARTIFACT_DIR."""
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path)
    dummy = {
        "schema_version": 1,
        "timestamp": "20260601T000000Z",
        "overall_risk": "low",
        "findings": [],
    }
    path = mod.write_artifact(dummy)
    # write_artifact writes to ARTIFACT_DIR/service_auth_latest.json
    assert path.exists()
    assert path.parent == tmp_path


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
