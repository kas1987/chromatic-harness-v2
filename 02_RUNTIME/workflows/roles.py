"""Standard task-graph role presets (scout → build → verify → scribe)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Sonnet plans/verifies; Kimi builds/logs (per PDR-GOV-SONNET-KIMI-001)
ROLE_MODEL: dict[str, str] = {
    "scout": "sonnet",
    "architect": "sonnet",
    "worker": "kimi",
    "verifier": "sonnet",
    "scribe": "kimi",
    "auditor": "sonnet",
    "orchestrator": "gpt",
}

DEFAULT_TOOL_BUDGET: dict[str, int] = {
    "scout": 15,
    "worker": 40,
    "verifier": 12,
    "scribe": 8,
}

DEFAULT_CONFIDENCE: dict[str, int] = {
    "scout": 70,
    "worker": 75,
    "verifier": 80,
    "scribe": 65,
}


def _task(
    task_id: str,
    title: str,
    role: str,
    *,
    depends_on: list[str] | None = None,
    allowed_files: list[str] | None = None,
    status: str = "pending",
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "title": title,
        "assigned_model": ROLE_MODEL[role],
        "role": role,
        "depends_on": depends_on or [],
        "allowed_files": allowed_files or [],
        "forbidden_files": [],
        "tool_budget": DEFAULT_TOOL_BUDGET.get(role, 20),
        "confidence_required": DEFAULT_CONFIDENCE.get(role, 75),
        "risk_level": "low",
        "acceptance_criteria": [],
        "stop_conditions": ["confidence_below_threshold", "scope_unclear"],
        "status": status,
    }


def build_standard_pipeline(
    objective: str,
    *,
    workflow_id: str = "",
    bead_id: str = "",
    allowed_files: list[str] | None = None,
) -> dict[str, Any]:
    """Four-step pipeline aligned with lite /go and /close-issue (no swarm)."""
    wf_id = workflow_id or f"WF-{bead_id or 'pipeline'}"
    prefix = bead_id[:12] if bead_id else "task"
    return {
        "workflow_id": wf_id,
        "objective": objective,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_level": "low",
        "global_stop_conditions": [
            "confidence_below_threshold",
            "scope_unclear",
            "no_unattended_swarm",
        ],
        "tasks": [
            _task(f"{prefix}-scout", f"Scout: {objective[:80]}", "scout", allowed_files=allowed_files),
            _task(
                f"{prefix}-build",
                f"Build: {objective[:80]}",
                "worker",
                depends_on=[f"{prefix}-scout"],
                allowed_files=allowed_files,
            ),
            _task(
                f"{prefix}-verify",
                f"Verify: {objective[:80]}",
                "verifier",
                depends_on=[f"{prefix}-build"],
                allowed_files=allowed_files,
            ),
            _task(
                f"{prefix}-scribe",
                f"Log: {objective[:80]}",
                "scribe",
                depends_on=[f"{prefix}-verify"],
                allowed_files=["docs/", "07_LOGS_AND_AUDIT/", ".agents/handoffs/"],
            ),
        ],
    }


def write_active_graph(
    graph: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> Path:
    import json

    root = repo_root or Path(__file__).resolve().parents[2]
    out = root / ".agents" / "workflows" / "active-graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    return out
