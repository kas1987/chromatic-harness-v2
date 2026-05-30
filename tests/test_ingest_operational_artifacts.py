"""Tests for ingest_operational_artifacts.py — field mapping, outcome rules, idempotency."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ingest_operational_artifacts as ingest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _make_source_cfg(
    tmp_path: Path,
    rows: list[dict],
    *,
    outcome_field: str = "result",
    success_values: list[str] | None = None,
    failure_values: list[str] | None = None,
    learning_field: str = "learning_name",
    fallback_field: str = "task_id",
    confidence_field: str = "",
    confidence_threshold: float = 0.0,
    skip_keys: list[str] | None = None,
) -> dict:
    artifact = tmp_path / "artifact.jsonl"
    _write_jsonl(artifact, rows)
    return {
        "id": "test_source",
        "path": str(artifact),
        "format": "jsonl",
        "skip_rows_with_keys": skip_keys or [],
        "outcome_rule": {
            "field": outcome_field,
            "success_values": success_values or ["success", "ok"],
            "failure_values": failure_values or ["fail", "error"],
            "confidence_field": confidence_field,
            "confidence_success_threshold": confidence_threshold,
        },
        "learning_ref": {
            "strategy": "field",
            "field": learning_field,
            "fallback_field": fallback_field,
            "fallback_prefix": "task:",
        },
        "canonical_fields": {
            "timestamp_utc": "timestamp",
            "rig_id": "task_id",
            "notes": "test_ingest",
        },
    }


# --- _determine_outcome ---


def test_outcome_success_on_success_value() -> None:
    rule = {
        "field": "result",
        "success_values": ["success"],
        "failure_values": ["fail"],
    }
    assert ingest._determine_outcome({"result": "success"}, rule) == "applied_success"


def test_outcome_failure_on_failure_value() -> None:
    rule = {
        "field": "result",
        "success_values": ["success"],
        "failure_values": ["fail"],
    }
    assert ingest._determine_outcome({"result": "fail"}, rule) == "applied_failure"


def test_outcome_none_when_no_match() -> None:
    rule = {
        "field": "result",
        "success_values": ["success"],
        "failure_values": ["fail"],
    }
    assert ingest._determine_outcome({"result": "pending"}, rule) is None


def test_outcome_confidence_threshold_success() -> None:
    rule = {
        "field": "result",
        "success_values": [],
        "failure_values": [],
        "confidence_field": "confidence_score",
        "confidence_success_threshold": 75.0,
    }
    assert (
        ingest._determine_outcome({"confidence_score": 80.0}, rule) == "applied_success"
    )


def test_outcome_confidence_threshold_miss() -> None:
    rule = {
        "field": "result",
        "success_values": [],
        "failure_values": [],
        "confidence_field": "confidence_score",
        "confidence_success_threshold": 75.0,
    }
    assert ingest._determine_outcome({"confidence_score": 60.0}, rule) is None


# --- _extract_learning_ref ---


def test_extract_learning_ref_from_field() -> None:
    ref_cfg = {
        "strategy": "field",
        "field": "learning_name",
        "fallback_field": "task_id",
        "fallback_prefix": "task:",
    }
    name, path = ingest._extract_learning_ref({"learning_name": "my-learning"}, ref_cfg)
    assert name == "my-learning"
    assert "my-learning" in path


def test_extract_learning_ref_fallback_to_task_id() -> None:
    ref_cfg = {
        "strategy": "field",
        "field": "learning_name",
        "fallback_field": "task_id",
        "fallback_prefix": "task:",
    }
    name, path = ingest._extract_learning_ref({"task_id": "T-42"}, ref_cfg)
    assert name == "task:T-42"
    assert path == ""


def test_extract_learning_ref_empty_when_no_fields() -> None:
    ref_cfg = {
        "strategy": "field",
        "field": "learning_name",
        "fallback_field": "task_id",
        "fallback_prefix": "task:",
    }
    name, path = ingest._extract_learning_ref({}, ref_cfg)
    assert name == ""


# --- _is_skip_row ---


def test_skip_row_matches_key() -> None:
    assert ingest._is_skip_row({"_comment": "header"}, ["_comment"]) is True


def test_skip_row_no_match() -> None:
    assert ingest._is_skip_row({"result": "success"}, ["_comment"]) is False


# --- _load_seen_keys ---


def test_load_seen_keys_extracts_idempotency_keys(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    rows = [
        {"idempotency_key": "abc123", "event_type": "applied_success"},
        {"idempotency_key": "def456", "event_type": "applied_failure"},
        {"event_type": "applied_success"},  # no key — ignored
    ]
    _write_jsonl(log, rows)
    seen = ingest._load_seen_keys(log)
    assert "abc123" in seen
    assert "def456" in seen
    assert len(seen) == 2


def test_load_seen_keys_empty_when_no_log(tmp_path: Path) -> None:
    seen = ingest._load_seen_keys(tmp_path / "missing.jsonl")
    assert seen == set()


# --- _process_source (integration) ---


def test_process_source_emits_success_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage_log = tmp_path / "usage.jsonl"
    monkeypatch.setattr(ingest, "USAGE_LOG", usage_log)
    monkeypatch.setattr(ingest, "REPO", tmp_path)

    rows = [
        {
            "timestamp": "2026-05-30T00:00:00Z",
            "result": "success",
            "learning_name": "my-learning",
            "task_id": "T-1",
        }
    ]
    cfg = _make_source_cfg(tmp_path, rows)
    cfg["path"] = str(tmp_path / "artifact.jsonl")

    stats = ingest._process_source(cfg, set(), dry_run=False)
    assert stats["emitted"] == 1
    assert stats["skipped_no_outcome"] == 0

    events = [json.loads(ln) for ln in usage_log.read_text().splitlines() if ln.strip()]
    assert len(events) == 1
    assert events[0]["event_type"] == "applied_success"
    assert events[0]["learning_name"] == "my-learning"
    assert "idempotency_key" in events[0]


def test_process_source_deduplicates_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage_log = tmp_path / "usage.jsonl"
    monkeypatch.setattr(ingest, "USAGE_LOG", usage_log)
    monkeypatch.setattr(ingest, "REPO", tmp_path)

    rows = [
        {
            "timestamp": "2026-05-30T00:00:00Z",
            "result": "success",
            "learning_name": "dup-learning",
            "task_id": "T-1",
        }
    ]
    cfg = _make_source_cfg(tmp_path, rows)
    cfg["path"] = str(tmp_path / "artifact.jsonl")

    seen: set[str] = set()
    ingest._process_source(cfg, seen, dry_run=False)
    stats2 = ingest._process_source(cfg, seen, dry_run=False)

    assert stats2["emitted"] == 0
    assert stats2["skipped_dup"] == 1


def test_process_source_dry_run_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage_log = tmp_path / "usage.jsonl"
    monkeypatch.setattr(ingest, "USAGE_LOG", usage_log)
    monkeypatch.setattr(ingest, "REPO", tmp_path)

    rows = [
        {
            "timestamp": "2026-05-30T00:00:00Z",
            "result": "success",
            "learning_name": "x",
            "task_id": "T-1",
        }
    ]
    cfg = _make_source_cfg(tmp_path, rows)
    cfg["path"] = str(tmp_path / "artifact.jsonl")

    stats = ingest._process_source(cfg, set(), dry_run=True)
    assert stats["emitted"] == 1
    assert not usage_log.is_file()


def test_process_source_skips_failure_rows_without_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "REPO", tmp_path)

    rows = [
        {"timestamp": "2026-05-30T00:00:00Z", "result": "pending", "learning_name": "x"}
    ]
    cfg = _make_source_cfg(tmp_path, rows)
    cfg["path"] = str(tmp_path / "artifact.jsonl")

    stats = ingest._process_source(cfg, set(), dry_run=True)
    assert stats["skipped_no_outcome"] == 1
    assert stats["emitted"] == 0


def test_process_source_skips_rows_with_skip_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "REPO", tmp_path)

    rows = [
        {"_comment": "header row"},
        {
            "timestamp": "2026-05-30T00:00:00Z",
            "result": "success",
            "learning_name": "x",
        },
    ]
    cfg = _make_source_cfg(tmp_path, rows, skip_keys=["_comment"])
    cfg["path"] = str(tmp_path / "artifact.jsonl")

    stats = ingest._process_source(cfg, set(), dry_run=True)
    assert stats["parsed"] == 1  # header skipped before parse count
    assert stats["emitted"] == 1


def test_process_source_missing_artifact_returns_zero_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "REPO", tmp_path)
    cfg = _make_source_cfg(tmp_path, [])
    cfg["path"] = str(tmp_path / "nonexistent.jsonl")

    stats = ingest._process_source(cfg, set(), dry_run=True)
    assert stats["parsed"] == 0
    assert stats["emitted"] == 0
