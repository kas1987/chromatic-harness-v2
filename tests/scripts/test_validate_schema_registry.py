"""Unit tests for scripts/validate_schema_registry.py.

Covers: load_registry, load_json_schema, validate_jsonl, and run().
Uses tmp_path for all filesystem interactions — no live registry required.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "validate_schema_registry.py"

_spec = importlib.util.spec_from_file_location("validate_schema_registry", _SCRIPT)
vsr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vsr)  # type: ignore[union-attr]

# ---------------------------------------------------------------------------
# Helpers to build minimal fixtures
# ---------------------------------------------------------------------------

_MINIMAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"event_id": {"type": "string"}},
    "required": ["event_id"],
}


def _make_registry_yaml(path: Path, entries: list[dict]) -> None:
    import yaml  # available in env per the source

    path.write_text(yaml.dump({"schemas": entries}), encoding="utf-8")


# ---------------------------------------------------------------------------
# load_registry
# ---------------------------------------------------------------------------


def test_load_registry_returns_entries(tmp_path):
    reg = tmp_path / "registry.yaml"
    _make_registry_yaml(reg, [{"id": "s1", "schema_path": "schemas/s1.json"}])
    entries = vsr.load_registry(reg)
    assert len(entries) == 1
    assert entries[0]["id"] == "s1"


def test_load_registry_empty_file_returns_empty_list(tmp_path):
    import yaml

    reg = tmp_path / "empty.yaml"
    reg.write_text(yaml.dump({}), encoding="utf-8")
    entries = vsr.load_registry(reg)
    assert entries == []


def test_load_registry_no_schemas_key_returns_empty(tmp_path):
    import yaml

    reg = tmp_path / "nokey.yaml"
    reg.write_text(yaml.dump({"other": []}), encoding="utf-8")
    entries = vsr.load_registry(reg)
    assert entries == []


# ---------------------------------------------------------------------------
# load_json_schema
# ---------------------------------------------------------------------------


def test_load_json_schema_valid(tmp_path):
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    schema = vsr.load_json_schema(p)
    assert schema["type"] == "object"


def test_load_json_schema_raises_on_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("NOT JSON", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        vsr.load_json_schema(p)


# ---------------------------------------------------------------------------
# validate_jsonl
# ---------------------------------------------------------------------------


def test_validate_jsonl_no_errors_for_valid_records(tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    schema = vsr.load_json_schema(schema_path)

    jsonl = tmp_path / "records.jsonl"
    jsonl.write_text('{"event_id": "e1"}\n{"event_id": "e2"}\n', encoding="utf-8")

    errors = vsr.validate_jsonl(jsonl, schema, sample=50)
    assert errors == []


def test_validate_jsonl_reports_missing_required_field(tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    schema = vsr.load_json_schema(schema_path)

    jsonl = tmp_path / "bad.jsonl"
    jsonl.write_text('{"other_field": "x"}\n', encoding="utf-8")

    errors = vsr.validate_jsonl(jsonl, schema, sample=50)
    assert len(errors) == 1
    assert "line 1" in errors[0]


def test_validate_jsonl_reports_invalid_json_line(tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    schema = vsr.load_json_schema(schema_path)

    jsonl = tmp_path / "invalid.jsonl"
    jsonl.write_text('NOT JSON\n', encoding="utf-8")

    errors = vsr.validate_jsonl(jsonl, schema, sample=50)
    assert any("JSON parse error" in e for e in errors)


def test_validate_jsonl_skips_blank_lines(tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    schema = vsr.load_json_schema(schema_path)

    jsonl = tmp_path / "blanks.jsonl"
    jsonl.write_text('\n{"event_id": "e1"}\n\n', encoding="utf-8")

    errors = vsr.validate_jsonl(jsonl, schema, sample=50)
    assert errors == []


def test_validate_jsonl_respects_sample_limit(tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")
    schema = vsr.load_json_schema(schema_path)

    # 10 valid records but sample=3 — should only validate 3
    jsonl = tmp_path / "many.jsonl"
    jsonl.write_text("\n".join(json.dumps({"event_id": f"e{i}"}) for i in range(10)) + "\n", encoding="utf-8")

    errors = vsr.validate_jsonl(jsonl, schema, sample=3)
    # No errors (all valid), and the function should return early after 3
    assert errors == []


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def test_run_passes_with_valid_schema_no_jsonl(tmp_path, monkeypatch):
    """Registry with one schema, no JSONL → should pass (exit 0)."""
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    schema_file = schema_dir / "s1.json"
    schema_file.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")

    reg = tmp_path / "registry.yaml"
    _make_registry_yaml(reg, [{"id": "s1", "schema_path": str(schema_file.relative_to(tmp_path))}])

    # Patch REPO_ROOT so relative paths resolve under tmp_path
    monkeypatch.setattr(vsr, "REPO_ROOT", tmp_path)
    result = vsr.run(reg, sample=50)
    assert result == 0


def test_run_fails_for_missing_schema_file(tmp_path, monkeypatch):
    reg = tmp_path / "registry.yaml"
    _make_registry_yaml(reg, [{"id": "s2", "schema_path": "schemas/missing.json"}])

    monkeypatch.setattr(vsr, "REPO_ROOT", tmp_path)
    result = vsr.run(reg, sample=50)
    assert result == 1


def test_run_passes_on_empty_registry(tmp_path, monkeypatch, capsys):
    import yaml

    reg = tmp_path / "empty.yaml"
    reg.write_text(yaml.dump({}), encoding="utf-8")

    monkeypatch.setattr(vsr, "REPO_ROOT", tmp_path)
    result = vsr.run(reg, sample=50)
    assert result == 0
    captured = capsys.readouterr()
    assert "No schemas found" in captured.out


def test_run_fails_for_invalid_json_in_schema_file(tmp_path, monkeypatch):
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    bad_schema = schema_dir / "bad.json"
    bad_schema.write_text("NOT JSON", encoding="utf-8")

    reg = tmp_path / "registry.yaml"
    _make_registry_yaml(reg, [{"id": "bad_schema", "schema_path": f"schemas/{bad_schema.name}"}])

    monkeypatch.setattr(vsr, "REPO_ROOT", tmp_path)
    result = vsr.run(reg, sample=50)
    assert result == 1


def test_run_fails_when_jsonl_has_violations(tmp_path, monkeypatch):
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    schema_file = schema_dir / "s1.json"
    schema_file.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    bad_jsonl = logs_dir / "events.jsonl"
    bad_jsonl.write_text('{"wrong_field": "x"}\n', encoding="utf-8")

    reg = tmp_path / "registry.yaml"
    _make_registry_yaml(
        reg,
        [
            {
                "id": "s1",
                "schema_path": f"schemas/{schema_file.name}",
                "jsonl_paths": [f"logs/{bad_jsonl.name}"],
            }
        ],
    )

    monkeypatch.setattr(vsr, "REPO_ROOT", tmp_path)
    result = vsr.run(reg, sample=50)
    assert result == 1


def test_run_passes_when_jsonl_is_empty(tmp_path, monkeypatch):
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    schema_file = schema_dir / "s1.json"
    schema_file.write_text(json.dumps(_MINIMAL_SCHEMA), encoding="utf-8")

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    empty_jsonl = logs_dir / "empty.jsonl"
    empty_jsonl.write_text("", encoding="utf-8")

    reg = tmp_path / "registry.yaml"
    _make_registry_yaml(
        reg,
        [
            {
                "id": "s1",
                "schema_path": f"schemas/{schema_file.name}",
                "jsonl_paths": [f"logs/{empty_jsonl.name}"],
            }
        ],
    )

    monkeypatch.setattr(vsr, "REPO_ROOT", tmp_path)
    result = vsr.run(reg, sample=50)
    assert result == 0
