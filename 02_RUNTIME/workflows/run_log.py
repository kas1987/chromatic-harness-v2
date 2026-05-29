"""Append-only workflow run log (JSONL)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_log_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"


def append_run_log(repo_root: Path, entry: dict[str, Any]) -> Path:
    path = default_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])
