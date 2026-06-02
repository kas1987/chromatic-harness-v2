"""Advisory stage: assemble routing advisory string from overlay + CRG gate."""

from __future__ import annotations

import json
import os
from pathlib import Path

_CONTEXT_MAX_TOKENS = int(os.environ.get("ROUTER_CONTEXT_MAX_TOKENS", "128000"))

_REPO: Path | None = None


def _repo() -> Path:
    global _REPO
    if _REPO is None:
        _REPO = Path(__file__).resolve().parents[3]
    return _REPO


def read_routing_overlay() -> dict | None:
    """Read control-plane routing_policy_overlay.json. Fail-open → None."""
    overlay_path = _repo() / "07_LOGS_AND_AUDIT" / "control_plane" / "routing_policy_overlay.json"
    if not overlay_path.is_file():
        return None
    try:
        data = json.loads(overlay_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def overlay_advisory() -> str:
    """Format control-plane overlay knobs for advisory string (fail-open)."""
    try:
        overlay = read_routing_overlay()
        if not overlay:
            return ""
        thr = overlay.get("c_to_t_threshold")
        spill = overlay.get("allow_paid_spill")
        if overlay.get("staleness_fallback"):
            return f" | overlay STALE-FALLBACK: C->T>={thr} paid_spill={spill}"
        return f" | overlay: C->T>={thr} paid_spill={spill}"
    except Exception:  # noqa: BLE001
        return ""


def context_gate_advisory(description: str, prompt: str, complexity_level: str) -> str:
    """Append CRG resource-filtering note to PreToolUse advisory."""
    try:
        import importlib
        import importlib.util

        router_dir = Path(__file__).resolve().parents[1]

        def _load(name: str, fname: str):
            path = router_dir / fname
            spec = importlib.util.spec_from_file_location(f"router.{name}", path)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod

        _cg = _load("context_gate", "context_gate.py")
        _contracts = _load("contracts", "contracts.py")
        ContextGate = _cg.ContextGate
        RouteRequest = _contracts.RouteRequest
        TaskType = _contracts.TaskType
        RouteConstraints = _contracts.RouteConstraints
        PrivacyClass = _contracts.PrivacyClass

        haystack = f"{description}\n{prompt}".lower()
        if "research" in haystack or "investigate" in haystack:
            task_type = TaskType.RESEARCH
        elif "review" in haystack or "audit" in haystack:
            task_type = TaskType.REVIEW
        else:
            task_type = TaskType.CODING

        req = RouteRequest(
            request_id="pre-agent-hook",
            task_id="pre-agent",
            task_type=task_type,
            objective=description or prompt[:200],
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P1,
                max_tokens=_CONTEXT_MAX_TOKENS,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
            ),
        )
        result = ContextGate().check(req, complexity_level=complexity_level)
        if not result.ok:
            return f" | CRG BLOCKED ({result.estimated_context_tokens} tok budget)"

        handoff_hint = ""
        handoff_path = _repo() / ".agents" / "handoffs" / "latest.json"
        if handoff_path.is_file():
            handoff_hint = " | handoff: .agents/handoffs/latest.json"

        budget_hint = ""
        tp_path = _repo() / ".agents" / "handoffs" / "transfer_packet.json"
        if tp_path.is_file():
            try:
                tp = json.loads(tp_path.read_text(encoding="utf-8"))
                decision = (tp.get("budget") or {}).get("decision", "")
                if decision == "halt_human":
                    budget_hint = " | BUDGET HALT: human lane only"
                elif decision:
                    budget_hint = f" | budget: {decision}"
            except Exception:  # noqa: BLE001
                pass

        overlay_hint = overlay_advisory()
        return (
            f" | CRG {len(result.allowed_resources)} resources"
            f"{handoff_hint}{budget_hint}{overlay_hint} | ops: AGENT_OPERATIONS.md"
        )
    except Exception:  # noqa: BLE001
        return ""
