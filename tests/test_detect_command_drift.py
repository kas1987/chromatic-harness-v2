"""Tests for scripts/detect_command_drift.py.

All tests are network-free and file-system-hermetic via tmp_path fixtures.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "detect_command_drift.py"

# ---------------------------------------------------------------------------
# Minimal YAML fixtures
# ---------------------------------------------------------------------------

_REGISTRY_CLEAN = """\
version: 0.1.0
commands:
  - name: /go
    purpose: Start work.
    authority_source: queue
    script: scripts/go_mode.py
    mutation: conditional
    required_gates: [confidence]
    logs_to: null
    allowed: true
    forbidden_logic: []
  - name: /audit
    purpose: Audit.
    authority_source: harness_health
    script: null
    mutation: none
    required_gates: []
    logs_to: null
    allowed: true
    forbidden_logic: []
"""

_RULES_CLEAN = """\
version: 0.1.0
required_commands:
  - /go
  - /audit
"""

_MATRIX_CLEAN = """\
# Matrix

| Command | Purpose |
|---|---|
| `/go` | Start work |
| `/audit` | Audit |
"""


# ---------------------------------------------------------------------------
# Loader helper
# ---------------------------------------------------------------------------


def _load(monkeypatch, tmp_path: Path):
    """Load detect_command_drift in isolation, redirect all paths to tmp_path."""
    spec = importlib.util.spec_from_file_location("detect_command_drift", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Avoid polluting the real module cache across tests
    sys.modules.pop("detect_command_drift", None)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "REGISTRY_PATH", tmp_path / "registry.yaml")
    monkeypatch.setattr(mod, "RULES_PATH", tmp_path / "rules.yaml")
    monkeypatch.setattr(mod, "COMMANDS_DIR", tmp_path / "commands")
    monkeypatch.setattr(mod, "MATRIX_PATH", tmp_path / "matrix.md")
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(mod, "ARTIFACT_PATH", tmp_path / "artifacts" / "latest.json")
    return mod


def _write_defaults(tmp_path: Path) -> None:
    """Write the clean fixture files and a stub go_mode.py."""
    (tmp_path / "registry.yaml").write_text(_REGISTRY_CLEAN, encoding="utf-8")
    (tmp_path / "rules.yaml").write_text(_RULES_CLEAN, encoding="utf-8")
    (tmp_path / "matrix.md").write_text(_MATRIX_CLEAN, encoding="utf-8")
    (tmp_path / "commands").mkdir(exist_ok=True)
    # create the referenced script so script_missing check passes
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "go_mode.py").write_text("# stub\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Clean state
# ---------------------------------------------------------------------------


class TestCleanState:
    def test_clean_registry_returns_clean_status(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        assert report["overall_status"] == "clean"
        assert report["error_count"] == 0
        assert report["warn_count"] == 0

    def test_report_includes_registry_command_count(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        assert report["registry_commands"] == 2


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


class TestErrors:
    def test_required_command_missing_from_registry_is_error(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Add /ship to required_commands but not registry
        rules = (tmp_path / "rules.yaml").read_text()
        rules += "  - /ship\n"
        (tmp_path / "rules.yaml").write_text(rules, encoding="utf-8")
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        assert report["overall_status"] == "error"
        kinds = [f["kind"] for f in report["findings"]]
        assert "rules_not_in_registry" in kinds
        ship_finding = next(f for f in report["findings"] if f.get("command") == "/ship")
        assert ship_finding["severity"] == "error"

    def test_script_missing_is_error(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Remove the go_mode.py stub
        (tmp_path / "scripts" / "go_mode.py").unlink()
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        assert report["overall_status"] == "error"
        kinds = [f["kind"] for f in report["findings"]]
        assert "script_missing" in kinds

    def test_duplicate_command_name_is_error(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Write registry with /go twice
        dup_registry = (
            _REGISTRY_CLEAN
            + """\
  - name: /go
    purpose: Duplicate.
    authority_source: queue
    script: null
    mutation: none
    required_gates: []
    logs_to: null
    allowed: true
    forbidden_logic: []
"""
        )
        (tmp_path / "registry.yaml").write_text(dup_registry, encoding="utf-8")
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        assert report["overall_status"] == "error"
        kinds = [f["kind"] for f in report["findings"]]
        assert "duplicate_names" in kinds

    def test_null_script_is_not_script_missing_error(self, monkeypatch, tmp_path):
        """null script field should not trigger script_missing (command has no script)."""
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        # /audit has script: null — should not raise script_missing
        script_missing = [f for f in report["findings"] if f["kind"] == "script_missing"]
        assert not any(f["command"] == "/audit" for f in script_missing)

    def test_bd_script_is_not_script_missing_error(self, monkeypatch, tmp_path):
        """script: bd should not trigger script_missing (bd is an external binary)."""
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Extend registry and rules with a /queue command whose script is 'bd'
        queue_entry = """\
  - name: /queue
    purpose: Queue.
    authority_source: bd_queue
    script: bd
    mutation: conditional
    required_gates: []
    logs_to: null
    allowed: true
    forbidden_logic: []
"""
        (tmp_path / "registry.yaml").write_text(_REGISTRY_CLEAN + queue_entry, encoding="utf-8")
        (tmp_path / "rules.yaml").write_text(_RULES_CLEAN + "  - /queue\n", encoding="utf-8")
        (tmp_path / "matrix.md").write_text(_MATRIX_CLEAN.rstrip() + "\n| `/queue` | Queue |\n", encoding="utf-8")
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        script_missing = [f for f in report["findings"] if f["kind"] == "script_missing"]
        assert not any(f["command"] == "/queue" for f in script_missing)


# ---------------------------------------------------------------------------
# Warning conditions
# ---------------------------------------------------------------------------


class TestWarnings:
    def test_registry_command_not_in_rules_is_warn(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # rules only requires /go; /audit is in registry but not required_commands
        (tmp_path / "rules.yaml").write_text("version: 0.1.0\nrequired_commands:\n  - /go\n", encoding="utf-8")
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        kinds = [f["kind"] for f in report["findings"]]
        assert "registry_not_in_rules" in kinds
        warn = next(f for f in report["findings"] if f["kind"] == "registry_not_in_rules")
        assert warn["severity"] == "warn"
        assert warn["command"] == "/audit"

    def test_deployed_command_not_in_registry_is_warn(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Put a .claude/commands/foobar.md that isn't in registry
        (tmp_path / "commands" / "foobar.md").write_text("# foobar\n", encoding="utf-8")
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        kinds = [f["kind"] for f in report["findings"]]
        assert "deployed_ungoverned" in kinds
        warn = next(f for f in report["findings"] if f["kind"] == "deployed_ungoverned")
        assert warn["severity"] == "warn"
        assert warn["command"] == "/foobar"

    def test_matrix_missing_registry_command_is_warn(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Matrix only has /go; /audit is in registry but not in matrix
        (tmp_path / "matrix.md").write_text(
            "# Matrix\n\n| Command | Purpose |\n|---|---|\n| `/go` | Go |\n",
            encoding="utf-8",
        )
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        stale = [f for f in report["findings"] if f["kind"] == "matrix_stale"]
        assert any(f["command"] == "/audit" for f in stale)
        assert all(f["severity"] == "warn" for f in stale)

    def test_matrix_has_command_not_in_registry_is_warn(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Add /ghost to matrix but not registry
        extra = _MATRIX_CLEAN + "| `/ghost` | Ghost command |\n"
        (tmp_path / "matrix.md").write_text(extra, encoding="utf-8")
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        stale = [f for f in report["findings"] if f["kind"] == "matrix_stale"]
        assert any(f["command"] == "/ghost" for f in stale)

    def test_missing_matrix_file_no_error(self, monkeypatch, tmp_path):
        """If matrix file is absent, matrix check is skipped (no error, just no warn)."""
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        (tmp_path / "matrix.md").unlink()
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        # No matrix_stale findings when file is absent
        stale = [f for f in report["findings"] if f["kind"] == "matrix_stale"]
        assert stale == []

    def test_missing_commands_dir_no_error(self, monkeypatch, tmp_path):
        """If .claude/commands/ doesn't exist, deployed_ungoverned check produces no findings."""
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        import shutil

        shutil.rmtree(tmp_path / "commands")
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        deployed = [f for f in report["findings"] if f["kind"] == "deployed_ungoverned"]
        assert deployed == []


# ---------------------------------------------------------------------------
# Artifact and summarize
# ---------------------------------------------------------------------------


class TestArtifact:
    def test_write_artifact_creates_file(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        mod.write_artifact(report)
        artifact = tmp_path / "artifacts" / "latest.json"
        assert artifact.exists()
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert "overall_status" in data
        assert "findings" in data

    def test_summarize_reads_artifact(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        report = mod.run_checks(
            registry_path=tmp_path / "registry.yaml",
            rules_path=tmp_path / "rules.yaml",
            commands_dir=tmp_path / "commands",
            matrix_path=tmp_path / "matrix.md",
            repo=tmp_path,
        )
        mod.write_artifact(report)
        summary = mod.summarize()
        assert "command_drift" in summary
        assert "clean" in summary

    def test_summarize_fail_open_when_no_artifact(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        # No artifact written
        summary = mod.summarize()
        assert "command_drift" in summary
        assert "unknown" in summary


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCli:
    def test_clean_exits_0(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        monkeypatch.setattr(mod, "REGISTRY_PATH", tmp_path / "registry.yaml")
        monkeypatch.setattr(mod, "RULES_PATH", tmp_path / "rules.yaml")
        monkeypatch.setattr(mod, "COMMANDS_DIR", tmp_path / "commands")
        monkeypatch.setattr(mod, "MATRIX_PATH", tmp_path / "matrix.md")
        monkeypatch.setattr(mod, "REPO", tmp_path)
        rc = mod.main(["--no-write", "--quiet"])
        assert rc == 0

    def test_error_exits_1(self, monkeypatch, tmp_path):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        # Remove the referenced script to trigger error
        (tmp_path / "scripts" / "go_mode.py").unlink()
        monkeypatch.setattr(mod, "REGISTRY_PATH", tmp_path / "registry.yaml")
        monkeypatch.setattr(mod, "RULES_PATH", tmp_path / "rules.yaml")
        monkeypatch.setattr(mod, "COMMANDS_DIR", tmp_path / "commands")
        monkeypatch.setattr(mod, "MATRIX_PATH", tmp_path / "matrix.md")
        monkeypatch.setattr(mod, "REPO", tmp_path)
        rc = mod.main(["--no-write", "--quiet"])
        assert rc == 1

    def test_output_is_valid_json(self, monkeypatch, tmp_path, capsys):
        mod = _load(monkeypatch, tmp_path)
        _write_defaults(tmp_path)
        monkeypatch.setattr(mod, "REGISTRY_PATH", tmp_path / "registry.yaml")
        monkeypatch.setattr(mod, "RULES_PATH", tmp_path / "rules.yaml")
        monkeypatch.setattr(mod, "COMMANDS_DIR", tmp_path / "commands")
        monkeypatch.setattr(mod, "MATRIX_PATH", tmp_path / "matrix.md")
        monkeypatch.setattr(mod, "REPO", tmp_path)
        mod.main(["--no-write"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "overall_status" in data
        assert "findings" in data
        assert "generated_at" in data


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
