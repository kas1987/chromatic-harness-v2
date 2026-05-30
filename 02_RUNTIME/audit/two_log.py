"""Two-log audit: execution JSONL (recovery) + OTel GenAI trace stub (diagnostics)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "00_SOURCE_OF_TRUTH").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


def _hash_payload(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class TwoLogAudit:
    """Zylos-style dual logging: execution (never sampled) + trace stub (diagnostic)."""

    def __init__(self, repo_root: Path | None = None):
        root = _repo_root(repo_root)
        audit = root / "07_LOGS_AND_AUDIT"
        self.execution_path = audit / "execution" / "execution.jsonl"
        self.trace_path = audit / "traces" / "traces.jsonl"
        self.decision_path = audit / "decisions" / "decision_log.jsonl"

    def append_execution(self, entry: dict[str, Any]) -> Path:
        record = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
        _append_jsonl(self.execution_path, record)
        return self.execution_path

    def append_trace_span(self, span: dict[str, Any]) -> Path:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": span.get("trace_id") or uuid.uuid4().hex,
            "span_id": span.get("span_id") or uuid.uuid4().hex[:16],
            **span,
        }
        _append_jsonl(self.trace_path, record)
        return self.trace_path

    def append_decision(self, entry: dict[str, Any]) -> Path:
        record = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
        _append_jsonl(self.decision_path, record)
        return self.decision_path

    def record_workflow_run(self, workflow_entry: dict[str, Any]) -> dict[str, str]:
        """Mirror a workflow run log row into execution + trace + decision logs."""
        mode = workflow_entry.get("mode", "WORKFLOW")
        raw_event = workflow_entry.get("event_type", "")
        bead_id = workflow_entry.get("bead_id") or workflow_entry.get("task_id", "")
        handoff = workflow_entry.get("handoff") or {}
        mission_id = handoff.get("mission_id") or workflow_entry.get("mission_id", "")
        decision = workflow_entry.get("decision", "")
        confidence_raw = workflow_entry.get("confidence")
        confidence = confidence_raw if isinstance(confidence_raw, dict) else {}
        score = confidence.get("confidence_score", workflow_entry.get("confidence_score"))
        if score in (None, "") and confidence_raw not in (None, "") and not isinstance(confidence_raw, dict):
            score = confidence_raw
        cmp_decision = confidence.get("cmp_decision", "")

        idem = _hash_payload(
            {
                "mode": mode,
                "bead_id": bead_id,
                "decision": decision,
                "ts": workflow_entry.get("timestamp"),
            }
        )

        self.append_execution(
            {
                "mission_id": mission_id,
                "task_id": bead_id or "unknown",
                "agent_role": workflow_entry.get("agent_role", "orchestrator"),
                "event_type": (
                    raw_event
                    if raw_event.startswith(("activity.", "workflow."))
                    else (f"activity.{raw_event}" if raw_event else f"workflow.{mode.replace(' ', '_').lower()}")
                ),
                "idempotency_key": idem,
                "model": workflow_entry.get("model", ""),
                "input_hash": _hash_payload({"mode": mode, "bead_id": bead_id}),
                "output_hash": _hash_payload(decision or workflow_entry.get("error", "")),
                "tool_name": mode,
                "tool_args_hash": _hash_payload(workflow_entry.get("git_pipeline", {})),
                "side_effect_receipt": decision in ("execute", "shipped"),
                "prompt_version": "workflow_go_v1",
                "model_version": "harness_v2",
                "workflow_decision": decision,
            }
        )

        self.append_trace_span(
            {
                "name": f"workflow.{mode.replace(' ', '.').lower()}",
                "kind": "INTERNAL",
                "status": "ERROR" if workflow_entry.get("error") else "OK",
                "duration_ms": 0,
                "attributes": {
                    "gen_ai.operation.name": "workflow",
                    "gen_ai.request.model": workflow_entry.get("model", "harness"),
                    "gen_ai.usage.input_tokens": 0,
                    "gen_ai.usage.output_tokens": 0,
                    "gen_ai.response.finish_reason": decision or "unknown",
                    "workflow.mode": mode,
                    "workflow.bead_id": bead_id,
                    "workflow.mission_id": mission_id,
                    "workflow.decision": decision,
                    "harness.confidence_score": score,
                },
            }
        )

        if score or cmp_decision or decision:
            band = "high" if float(score or 0) >= 75 else "medium" if float(score or 0) >= 50 else "low"
            self.append_decision(
                {
                    "mission_id": mission_id,
                    "task_id": bead_id,
                    "gate": "confidence",
                    "input_score": score,
                    "band": band,
                    "action": decision or cmp_decision or mode,
                    "reason": workflow_entry.get("error") or workflow_entry.get("next", ""),
                    "lesson": "",
                }
            )

        return {
            "execution": str(self.execution_path),
            "trace": str(self.trace_path),
            "decision": str(self.decision_path),
        }


def record_workflow_event(repo_root: Path, workflow_entry: dict[str, Any]) -> dict[str, str]:
    """Convenience wrapper used by workflow run_log."""
    return TwoLogAudit(repo_root).record_workflow_run(workflow_entry)
