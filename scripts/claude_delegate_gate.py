#!/usr/bin/env python3
"""Prepare and gate Claude Code task delegation using Harness routing/governance.

This script is the Claude-facing delegation entrypoint.
It enforces:
1) pre-swarm gate (forced boot + governance checks)
2) T-level safety policy
3) complexity classification (auto or explicit)
4) provider selection via router policies
5) confidence/permission decision for mutation

Usage examples:
  python scripts/claude_delegate_gate.py --task "Implement bpq.1 dashboard view" --bead-id chromatic-harness-v2-bpq.1 --t-level T2
  python scripts/claude_delegate_gate.py --task "Refactor routing policy" --t-level T3 --complexity C3 --spawn-claude-cli
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "02_RUNTIME"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(REPO / "scripts"))

from common_harness import run_safe  # noqa: E402
from router.complexity_classifier import ComplexityClassifier  # noqa: E402
from router.context_detector import ContextDetector  # noqa: E402
from router.provider_selector import ProviderSelector  # noqa: E402
from workflows.confidence import mutation_allowed, score_task  # noqa: E402
from workflows.run_log import append_run_log  # noqa: E402

T_LEVELS = ("T1", "T2", "T3", "T4")
PRIVACY_CLASSES = ("P0", "P1", "P2", "P3", "P4")
COMPLEXITY_LEVELS = ("auto", "C1", "C2", "C3", "C4")
DESTRUCTIVE_PATTERNS = (
    r"rm\s+-rf",
    r"\bdel\s+/f\b",
    r"\bformat\s+[a-z]:",
    r"\bdrop\s+database\b",
    r"\btruncate\s+table\b",
    r"git\s+reset\s+--hard",
    r"git\s+push\s+--force",
    r"\bdisable\s+firewall\b",
)


def _run(cmd: list[str], timeout: int = 900, cwd: Path | None = None) -> tuple[int, str]:
    """Run a command via the harness-safe runner.

    cwd defaults to the main checkout (REPO); pass an isolated worktree path to
    run a spawned worker without moving the shared checkout's HEAD.
    """
    proc = run_safe(cmd, cwd=cwd or REPO, timeout=timeout)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


# ── Worktree isolation ─────────────────────────────────────────────────────────
# The spawned `claude -p` worker gets its own `git worktree` checkout so its
# branch/commits never move the shared checkout's HEAD. Without this, a worker
# switching branches in the shared tree corrupts a concurrent interactive
# session's git state (the documented concurrent-runner branch-churn problem;
# see docs/retros/2026-06-02-worker-spawn-worktree-isolation.md learning #2 and bd memory
# `concurrent-runner-worktree-isolation`). .worktrees/ is gitignored. This
# mirrors task_runner.py's _create_worktree/_remove_worktree/_run(cwd=...).
_WORKTREE_ROOT = REPO / ".worktrees"


def _worktree_path(worker_id: str) -> Path:
    safe = worker_id.replace("/", "_").replace(".", "_") or "delegate"
    return _WORKTREE_ROOT / f"delegate-{safe}"


def _create_worktree(worker_id: str, base: str = "HEAD") -> Path | None:
    """Add an isolated worktree checked out on a fresh `delegate/<id>` branch.

    Returns the worktree path, or None on failure (caller must then refuse to
    spawn rather than fall back to the shared checkout). Cleans up any stale
    worktree/branch left by a prior aborted run first.
    """
    path = _worktree_path(worker_id)
    branch = f"delegate/{worker_id}"
    _run(["git", "worktree", "remove", str(path), "--force"])  # ignore failure (may not exist)
    _run(["git", "worktree", "prune"])
    _run(["git", "branch", "-D", branch])  # ignore failure (branch may not exist)
    code, _ = _run(["git", "worktree", "add", str(path), "-b", branch, base])
    return path if code == 0 else None


def _remove_worktree(path: Path) -> None:
    """Tear down a spawned worker's worktree (best-effort)."""
    _run(["git", "worktree", "remove", str(path), "--force"])
    _run(["git", "worktree", "prune"])


def _run_pre_swarm_gate(invoked_by: str) -> tuple[bool, str]:
    code, out = _run(
        [
            sys.executable,
            str(REPO / "scripts" / "pre_swarm_gate.py"),
            "--invoked-by",
            invoked_by,
        ]
    )
    return code == 0, out[-2000:]


def _complexity(task: str, explicit: str) -> dict:
    if explicit != "auto":
        return {
            "level": explicit,
            "name": "manual_override",
            "confidence": 1.0,
            "matched_keywords": [],
            "reasoning_depth": "manual",
            "source": "manual",
        }

    classifier = ComplexityClassifier()
    result = classifier.classify(description=task)
    out = asdict(result)

    # The classifier defaults unknown tasks to C4 with 0 confidence.
    # For common implementation intents, treat this as C3 to avoid false high-risk blocking.
    lowered = task.lower()
    impl_tokens = ("implement", "build", "fix", "test", "refactor", "add ")
    if out.get("level") == "C4" and float(out.get("confidence", 0.0)) == 0.0:
        if any(tok in lowered for tok in impl_tokens):
            out["level"] = "C3"
            out["name"] = "heuristic_fallback_engineering"
            out["reasoning_depth"] = "deep"

    out["source"] = "classifier"
    return out


def _risk_for_t_level(t_level: str) -> str:
    if t_level in ("T1", "T2"):
        return "low"
    if t_level == "T3":
        return "medium"
    return "high"


def _score_for_delegate(task: str, t_level: str, complexity_level: str) -> dict:
    base = {
        "C1": 88.0,
        "C2": 82.0,
        "C3": 84.0,
        "C4": 74.0,
    }.get(complexity_level, 75.0)

    t_penalty = {"T1": 0.0, "T2": 3.0, "T3": 7.0, "T4": 15.0}[t_level]
    clarity = max(45.0, min(95.0, base - t_penalty))
    evidence = max(45.0, min(95.0, base - (t_penalty / 2.0)))

    record = score_task(
        objective_clarity=clarity,
        scope_clarity=clarity,
        evidence_quality=evidence,
        risk_level=_risk_for_t_level(t_level),
    )
    data = record.to_dict()
    data["mutation_allowed"] = mutation_allowed(record)
    data["task_excerpt"] = task[:140]
    return data


def _provider_choices(complexity_level: str, privacy_class: str) -> list[dict]:
    detector = ContextDetector()
    context = detector.detect()
    classifier = ComplexityClassifier()
    selector = ProviderSelector()

    # Create a synthetic complexity object expected by selector
    synthetic = classifier.classify(description=f"complexity {complexity_level}")
    synthetic = synthetic.__class__(
        level=complexity_level,  # type: ignore[arg-type]
        name=synthetic.name,
        confidence=synthetic.confidence,
        matched_keywords=synthetic.matched_keywords,
        reasoning_depth=synthetic.reasoning_depth,
    )

    selection = selector.select(synthetic, context, privacy_class=privacy_class)
    return [asdict(choice) for choice in selection.ranked_choices[:4]]


def _t_level_guard(t_level: str, complexity_level: str, allow_t4: bool) -> tuple[str, str]:
    if t_level == "T4" and not allow_t4:
        return "halt", "T4 requires explicit --allow-t4 due to high-risk actions"

    if t_level in ("T1", "T2") and complexity_level == "C4":
        return "plan_only", "C4 work with T1/T2 routes to plan-only before delegation"

    return "ok", "within delegation bounds"


def _write_artifacts(packet: dict) -> tuple[Path, Path]:
    handoff_dir = REPO / ".agents" / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    packet_path = handoff_dir / "claude_delegate_packet.json"
    prompt_path = handoff_dir / "claude_delegate_prompt.md"

    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")

    prompt = [
        "# Claude Delegation Packet",
        "",
        f"Timestamp: {packet['generated_at']}",
        f"Bead: {packet.get('bead_id') or 'n/a'}",
        f"T-level: {packet['t_level']}",
        f"Complexity: {packet['complexity']['level']}",
        f"Privacy: {packet['privacy_class']}",
        "",
        "## Objective",
        packet["task"],
        "",
        "## Governance",
        f"- Pre-swarm gate passed: {packet['pre_swarm_gate']['ok']}",
        f"- Confidence decision: {packet['confidence']['decision']}",
        f"- Mutation allowed: {packet['confidence']['mutation_allowed']}",
        "",
        "## Routing Recommendation",
        *[
            f"- {c['provider']} ({c.get('model') or 'default'}) :: {c.get('reason', '')}"
            for c in packet["provider_choices"]
        ],
        "",
        "## Required Guardrails",
        "- Use bd for tracking; no TodoWrite authority.",
        "- Stay within assigned file scope.",
        "- If confidence drops to plan_only/halt, stop mutation and return plan.",
        "",
        "## Packet Reference",
        f"- .agents/handoffs/{packet_path.name}",
    ]
    prompt_path.write_text("\n".join(prompt) + "\n", encoding="utf-8")
    return packet_path, prompt_path


def _spawn_claude(prompt_path: Path, worker_id: str) -> tuple[bool, str]:
    if shutil.which("claude") is None:
        return False, "claude CLI not found; packet created for manual use"

    # Isolate the spawned worker in its own worktree so it never moves the shared
    # checkout's HEAD. If the worktree can't be created, refuse rather than churn
    # the shared tree (which would corrupt concurrent interactive git work).
    worktree = _create_worktree(worker_id)
    if worktree is None:
        return False, "failed to create isolated git worktree; refusing to spawn into the shared checkout"

    try:
        # prompt_path is absolute, so the `@file` reference resolves regardless of cwd.
        cmd = ["claude", "-p", f"@{prompt_path}"]
        code, out = _run(cmd, timeout=120, cwd=worktree)
        if code == 0:
            return True, (out[:1000] or "claude delegation dispatched")
        return False, out[-1000:]
    finally:
        _remove_worktree(worktree)


def _destructive_guard(task: str, allow_destructive: bool) -> tuple[str, str]:
    if allow_destructive:
        return "ok", "destructive_override_enabled"

    lowered = task.lower()
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, lowered):
            return "halt", "destructive_intent_blocked"

    return "ok", "no_destructive_patterns"


def _emit_delegation_log(packet: dict) -> None:
    provider_choices = packet.get("provider_choices")
    top = provider_choices[0] if isinstance(provider_choices, list) and provider_choices else {}
    provider = top.get("provider") if isinstance(top, dict) else "unknown"
    model = top.get("model") if isinstance(top, dict) else ""
    if provider and not model:
        model = f"{provider}:default"

    record = {
        "event_type": "delegation.gate",
        "task_id": packet.get("task_id") or packet.get("bead_id") or "unknown",
        "run_id": packet.get("run_id") or "",
        "bead_id": packet.get("bead_id") or "",
        "provider": provider or "unknown",
        "model": model or "unknown",
        "task_type": "delegation_gate",
        "execution_status": packet.get("decision") or "unknown",
        "decision": packet.get("decision") or "unknown",
        "summary": packet.get("task", "")[:200],
    }
    append_run_log(REPO, record)


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude delegation gate for Harness routing/policy")
    parser.add_argument("--task", required=True, help="Task objective to delegate")
    parser.add_argument("--bead-id", default="", help="Optional bead id")
    parser.add_argument("--t-level", choices=T_LEVELS, default="T2")
    parser.add_argument("--complexity", choices=COMPLEXITY_LEVELS, default="auto")
    parser.add_argument("--privacy-class", choices=PRIVACY_CLASSES, default="P1")
    parser.add_argument("--invoked-by", choices=["claude", "preflight", "automation"], default="claude")
    parser.add_argument("--run-id", default="", help="Optional run correlation id")
    parser.add_argument("--task-id", default="", help="Optional task correlation id")
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Allow tasks containing destructive command patterns",
    )
    parser.add_argument("--allow-t4", action="store_true", help="Allow T4 dispatch")
    parser.add_argument("--spawn-claude-cli", action="store_true", help="Run claude -p with generated prompt")
    parser.add_argument("extras", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Harden accidental placeholder args on Windows operators.
    ignored = [x for x in args.extras if x.strip() in {".", "./", ".\\"}]
    if ignored:
        print(f"INFO ignored placeholder args: {' '.join(ignored)}")

    if args.invoked_by == "automation" and (not args.run_id or not args.task_id):
        print(
            json.dumps(
                {
                    "ok": False,
                    "decision": "halt",
                    "reason": "missing_correlation_ids",
                    "details": "automation invocation requires both --run-id and --task-id",
                },
                indent=2,
            )
        )
        return 1

    destructive_decision, destructive_reason = _destructive_guard(args.task, args.allow_destructive)
    if destructive_decision == "halt":
        print(
            json.dumps(
                {
                    "ok": False,
                    "decision": "halt",
                    "reason": destructive_reason,
                    "details": "task contains destructive command patterns; pass --allow-destructive only after explicit risk acceptance",
                },
                indent=2,
            )
        )
        return 1

    gate_ok, gate_output = _run_pre_swarm_gate(args.invoked_by)
    if not gate_ok:
        print(
            json.dumps(
                {
                    "ok": False,
                    "decision": "halt",
                    "reason": "pre_swarm_gate_failed",
                    "details": gate_output,
                },
                indent=2,
            )
        )
        return 1

    complexity = _complexity(args.task, args.complexity)
    confidence = _score_for_delegate(args.task, args.t_level, complexity["level"])
    provider_choices = _provider_choices(complexity["level"], args.privacy_class)

    guard_decision, guard_reason = _t_level_guard(args.t_level, complexity["level"], args.allow_t4)

    decision = confidence.get("decision", "plan_only")
    if guard_decision == "halt":
        decision = "halt"
    elif guard_decision == "plan_only" and decision == "execute":
        decision = "plan_only"

    packet = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": "claude_code",
        "run_id": args.run_id or None,
        "task_id": args.task_id or args.bead_id or None,
        "task": args.task,
        "bead_id": args.bead_id or None,
        "t_level": args.t_level,
        "privacy_class": args.privacy_class,
        "complexity": complexity,
        "confidence": confidence,
        "provider_choices": provider_choices,
        "pre_swarm_gate": {
            "ok": gate_ok,
            "summary_tail": gate_output[-500:],
        },
        "decision": decision,
        "decision_reason": guard_reason,
        "destructive_guard": {
            "decision": destructive_decision,
            "reason": destructive_reason,
        },
        "next": "delegate" if decision == "execute" else "plan_only_or_escalate",
    }

    packet_path, prompt_path = _write_artifacts(packet)
    packet["artifact_paths"] = {
        "packet": str(packet_path.relative_to(REPO)).replace("\\", "/"),
        "prompt": str(prompt_path.relative_to(REPO)).replace("\\", "/"),
    }

    if args.spawn_claude_cli and decision == "execute":
        worker_id = args.bead_id or args.task_id or args.run_id or "delegate"
        ok, msg = _spawn_claude(prompt_path, worker_id)
        packet["spawn"] = {"ok": ok, "message": msg}

    _emit_delegation_log(packet)

    print(json.dumps(packet, indent=2))
    return 0 if decision != "halt" else 1


if __name__ == "__main__":
    raise SystemExit(main())
