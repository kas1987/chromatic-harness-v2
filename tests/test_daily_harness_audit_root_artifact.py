"""Tests for root artifact hygiene integration in daily_harness_audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import daily_harness_audit as dha


def test_daily_audit_emits_root_artifact_hygiene_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    # Presence gate for optional script execution.
    (scripts_dir / "root_artifact_hygiene.py").write_text("# stub\n", encoding="utf-8")

    monkeypatch.setattr(dha, "CORE_FILES", [])
    monkeypatch.setattr(dha, "CORE_SCRIPTS", [])
    monkeypatch.setattr(dha, "OPTIONAL_COMMANDS", [])

    def fake_run_cmd(_root: Path, cmd: list[str], timeout: int = 45):
        if cmd[:2] == ["python", "scripts/root_artifact_hygiene.py"]:
            return {
                "cmd": cmd,
                "returncode": 0,
                "stdout": "\n".join(
                    [
                        "ROOT_ARTIFACT_HYGIENE: mode=DRY_RUN",
                        "ROOT_ARTIFACT_HYGIENE: planned=3",
                        "ROOT_ARTIFACT_HYGIENE: applied=0",
                        "ROOT_ARTIFACT_HYGIENE: report=/tmp/report.json",
                    ]
                ),
                "stderr": "",
                "ok": True,
            }
        return {
            "cmd": cmd,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "ok": True,
        }

    monkeypatch.setattr(dha, "run_cmd", fake_run_cmd)

    result = dha.audit(root)
    summary = result.get("root_artifact_hygiene") or {}

    assert summary.get("mode") == "DRY_RUN"
    assert summary.get("planned") == 3
    assert summary.get("report") == "/tmp/report.json"

    findings = result.get("findings") or []
    codes = {f.get("code") for f in findings}
    assert "root_artifact_hygiene_drift" in codes
