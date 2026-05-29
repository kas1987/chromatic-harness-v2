"""Python drop-in replacement for the PreToolUse hook `model-router.sh`.

Reads the standard PreToolUse JSON blob from stdin, writes a
hookSpecificOutput decision JSON to stdout, and appends a log entry
to the router jsonl stream.

Usage (in settings.json / PreToolUse):
    cd <repo>/02_RUNTIME && python -m router.gate
    # or:
    python <repo>/02_RUNTIME/router/gate.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Self-contained loader: works when run as a script or module ───────────
_ROUTER_DIR = Path(__file__).resolve().parent
_REPO = _ROUTER_DIR.parent.parent

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _load_submodule(name: str, fname: str):
    path = _ROUTER_DIR / fname
    spec = importlib.util.spec_from_file_location(f"router.{name}", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules.setdefault(f"router.{name}", mod)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_context = _load_submodule("context_detector", "context_detector.py")
_complexity = _load_submodule("complexity_classifier", "complexity_classifier.py")
_selector = _load_submodule("provider_selector", "provider_selector.py")

ContextDetector = _context.ContextDetector
RuntimeContext = _context.RuntimeContext
ComplexityClassifier = _complexity.ComplexityClassifier
ProviderSelector = _selector.ProviderSelector
ProviderChoice = _selector.ProviderChoice


LOG_DIR = Path(
    os.environ.get("ROUTER_LOG_DIR", Path.home() / ".claude" / ".agents" / "router")
)
LOG_FILE = LOG_DIR / "log.jsonl"
BLOCK_ENABLED = os.environ.get("ROUTER_BLOCK_ENABLED", "true").lower() == "true"
# CRG token budget uses max_tokens * context_budget_pct; 8k default caused false BLOCKED.
CONTEXT_MAX_TOKENS = int(os.environ.get("ROUTER_CONTEXT_MAX_TOKENS", "128000"))
MAX_LOG_LINES = int(os.environ.get("ROUTER_MAX_LOG_LINES", "2000"))
TOOL_USE_PATTERN = os.environ.get(
    "TOOL_USE_PATTERN",
    "bash|glob|grep|install|execute|curl|npm |pip |webfetch|websearch",
)


def _read_stdin() -> dict[str, Any]:
    data = sys.stdin.read()
    if not data:
        return {}
    try:
        return json.loads(data)  # type: ignore[return-value]
    except Exception:
        return {}


def _log_entry(entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Lazy rotation: if file > MAX_LOG_LINES, trim to 80%
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > MAX_LOG_LINES:
            keep = int(MAX_LOG_LINES * 0.8)
            with open(LOG_FILE, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-keep:])
    except Exception:
        pass


def _has_tool_use(haystack: str) -> bool:
    import re

    return bool(re.search(TOOL_USE_PATTERN, haystack, re.IGNORECASE))


def _context_gate_advisory(description: str, prompt: str, complexity_level: str) -> str:
    """Append CRG resource-filtering note to PreToolUse advisory."""
    try:
        _cg = _load_submodule("context_gate", "context_gate.py")
        _contracts = _load_submodule("contracts", "contracts.py")
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
                max_tokens=CONTEXT_MAX_TOKENS,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
            ),
        )
        result = ContextGate().check(req, complexity_level=complexity_level)
        if not result.ok:
            return (
                f" | CRG BLOCKED ({result.estimated_context_tokens} tok budget)"
            )
        handoff_hint = ""
        handoff_path = _REPO / ".agents" / "handoffs" / "latest.json"
        if handoff_path.is_file():
            handoff_hint = " | handoff: .agents/handoffs/latest.json"
        return (
            f" | CRG {len(result.allowed_resources)} resources"
            f"{handoff_hint} | ops: AGENT_OPERATIONS.md"
        )
    except Exception:
        return ""


def main() -> None:
    data = _read_stdin()
    tool_name = data.get("tool_name", "")
    if tool_name != "Agent":
        # Not an Agent tool - noop (fail-open, same as old bash hook)
        _emit_advisory("ROUTER: non-Agent tool, passing through")
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    description = tool_input.get("description", "")
    prompt = tool_input.get("prompt", "")
    sub_type = tool_input.get("subagent_type", "general-purpose")
    model_requested = tool_input.get("model", "")

    # ── Classification + selection ──────────────────────────────────────
    classifier = ComplexityClassifier()
    context = ContextDetector().detect()
    selector = ProviderSelector()

    complexity = classifier.classify(description, prompt)
    selection = selector.select(complexity, context)

    ranked: list[Any] = selection.ranked_choices
    chosen = (
        ranked[0]
        if ranked
        else ProviderChoice(
            provider="native_claude",
            model=None,
            tier=4,
            reason="no providers available",
        )
    )

    # ── Blocking logic (speed-mode-aware) ──────────────────────────────
    # Philosophy: block based on cost discipline, not capability.
    # Speed mode = never block (advisory only). Low mode = block non-local.
    haystack = f"{description}\n{prompt}".lower()
    speed_mode = selection.speed_mode

    if speed_mode == "speed":
        should_block = False  # Advisory only; user wants speed
    elif speed_mode == "low":
        # In low mode, only allow local providers (ollama, lmstudio, native_claude)
        should_block = chosen.provider not in (
            "ollama_local",
            "ollama_remote_desktop",
            "lmstudio",
            "native_claude",
        )
    else:
        # balance mode: block non-tier-4 pure-LLM calls (cost discipline)
        should_block = (
            BLOCK_ENABLED
            and chosen.tier < 4
            and sub_type == "general-purpose"
            and not _has_tool_use(haystack)
        )

    # Model overrides (mirror old bash hook)
    override_note = ""
    if model_requested.lower() == "haiku" and chosen.tier > 1:
        should_block = True
        override_note = " | caller specified haiku - cap at tier-1"
    if model_requested.lower() == "opus":
        chosen = ProviderChoice(
            provider="native_claude",
            model="opus",
            tier=4,
            reason="caller specified opus - tier-4 (native)",
        )
        should_block = False
        override_note = ""

    # ── Format advisory (after all overrides) ───────────────────────────
    ctx_note = _context_gate_advisory(description, prompt, complexity.level)
    advisory = (
        f"ROUTER C={complexity.level} speed={selection.speed_mode} "
        f"provider={chosen.provider} model={chosen.model} — "
        f"{chosen.reason}{override_note}{ctx_note}"
    )

    # ── Output to stdout ────────────────────────────────────────────────
    if should_block:
        _emit_deny(advisory)
    else:
        _emit_advisory(advisory)

    # ── Log ─────────────────────────────────────────────────────────────
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "description": description[:200],
        "subagent_type": sub_type,
        "model_requested": model_requested,
        "c_level": complexity.level,
        "c_confidence": complexity.confidence,
        "speed_mode": selection.speed_mode,
        "context": selection.context_key,
        "provider": chosen.provider,
        "target_model": chosen.model,
        "tier": chosen.tier,
        "reason": chosen.reason,
        "blocked": should_block,
    }
    _log_entry(entry)
    sys.exit(0)


def _emit_advisory(advisory: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "additionalContext": advisory,
                }
            },
            ensure_ascii=False,
        )
    )


def _emit_deny(advisory: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "permissionDecision": "deny",
                    "denyReason": f"Use cheaper tier instead. {advisory}",
                    "additionalContext": advisory,
                }
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
