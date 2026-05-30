"""Append-only workflow run log (JSONL)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def runtime_log_path(repo_root: Path) -> Path:
    """Local append target (gitignored at repo root)."""
    return repo_root / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"


def seed_log_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "workflows" / "WORKFLOW_RUN_LOG.seed.jsonl"


def default_log_path(repo_root: Path) -> Path:
    """Write path: always runtime log."""
    return runtime_log_path(repo_root)


def read_log_path(repo_root: Path) -> Path:
    """Read path: runtime if present, else tracked seed."""
    runtime = runtime_log_path(repo_root)
    if runtime.is_file():
        return runtime
    seed = seed_log_path(repo_root)
    if seed.is_file():
        return seed
    return runtime


def _pick(entry: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in entry and entry[key] not in (None, ""):
            return entry[key]
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _canonicalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    confidence_obj = entry.get("confidence") if isinstance(entry.get("confidence"), dict) else {}
    confidence_score = _pick(entry, "confidence_score")
    if confidence_score is None and confidence_obj:
        confidence_score = _pick(confidence_obj, "score", "confidence_score")

    canonical: dict[str, Any] = {
        "task_id": _pick(entry, "task_id", "bead_id", "workflow_id", "request_id") or "unknown",
        "provider": _pick(entry, "provider", "selected_provider") or "unknown",
        "model": _pick(entry, "model", "selected_model", "assigned_model") or "unknown",
        "task_type": _pick(entry, "task_type", "mode", "event_type") or "unknown",
        "execution_status": _pick(
            entry,
            "execution_status",
            "result_status",
            "status",
            "result",
            "decision",
            "validation",
        )
        or "unknown",
        "confidence_score": _to_float(confidence_score),
        "cost_usd": _to_float(
            _pick(entry, "cost_usd", "actual_cost", "estimated_cost", "cost_estimate_usd")
        ),
        "latency_ms": _to_float(_pick(entry, "latency_ms", "duration_ms", "elapsed_ms")),
    }

    return canonical


def append_run_log(repo_root: Path, entry: dict[str, Any]) -> Path:
    path = default_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = _canonicalize_entry(entry)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **canonical,
        **entry,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    _mirror_two_log(repo_root, record)
    return path


def _mirror_two_log(repo_root: Path, record: dict[str, Any]) -> None:
    """Best-effort dual audit; never blocks workflow logging."""
    try:
        import sys

        runtime = Path(__file__).resolve().parents[1]
        if str(runtime) not in sys.path:
            sys.path.insert(0, str(runtime))
        from audit.two_log import record_workflow_event

        record_workflow_event(repo_root, record)
    except OSError:
        pass


def read_last_entry(repo_root: Path) -> dict[str, Any] | None:
    path = default_log_path(repo_root)
    if not path.is_file():
        path = read_log_path(repo_root)
    if not path.is_file():
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])
