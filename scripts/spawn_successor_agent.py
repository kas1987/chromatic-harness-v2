#!/usr/bin/env python3
"""Spawn successor agent when budget packet allows (adapters: cursor_sdk, claude_cli, manual)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget.ledger import load_agent_budget_config  # noqa: E402


def _load_packet(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _prompt_body(repo_root: Path, packet: dict[str, Any]) -> str:
    rel = packet.get("successor", {}).get(
        "prompt_path", ".agents/handoffs/successor_prompt.md"
    )
    p = repo_root / rel
    if p.is_file():
        return p.read_text(encoding="utf-8")[:12000]
    return packet.get("summary", "Continue from handoff.")


def spawn_cursor_sdk(prompt: str) -> tuple[bool, str]:
    if not os.environ.get("CURSOR_API_KEY"):
        return False, "CURSOR_API_KEY not set"
    try:
        import cursor_sdk  # type: ignore[import-untyped]
    except ImportError:
        try:
            from cursor import Agent  # type: ignore[import-untyped]
        except ImportError:
            return False, "cursor SDK not installed (pip install cursor-sdk)"

        try:
            agent = Agent.create()
            agent.prompt(prompt[:8000])
            return True, "cursor Agent.prompt dispatched"
        except Exception as exc:
            return False, f"cursor Agent failed: {exc}"

    try:
        agent = cursor_sdk.Agent.create()
        agent.prompt(prompt[:8000])
        return True, "cursor_sdk Agent.prompt dispatched"
    except Exception as exc:
        return False, f"cursor_sdk failed: {exc}"


def spawn_claude_cli(repo_root: Path, prompt: str) -> tuple[bool, str]:
    tmp = repo_root / ".agents" / "handoffs" / "_successor_prompt_cli.txt"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(prompt, encoding="utf-8")
    for cmd in (
        ["claude", "-p", f"@{tmp}"],
        ["claude", "-p", prompt[:4000]],
    ):
        try:
            r = subprocess.run(
                cmd,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            if r.returncode == 0:
                return True, (r.stdout or "claude cli ok")[:500]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return (
        False,
        f"claude CLI unavailable; prompt saved to {tmp.relative_to(repo_root)}",
    )


def spawn_manual_bead(summary: str) -> tuple[bool, str]:
    title = "Successor handoff ready — read transfer_packet"
    body = summary[:500]
    try:
        r = subprocess.run(
            [
                "bd",
                "create",
                title,
                "--type",
                "task",
                "--priority",
                "2",
                "--description",
                body,
            ],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if r.returncode == 0:
            return True, (r.stdout or r.stderr or "bead created").strip()
        return False, r.stderr or r.stdout or "bd create failed"
    except FileNotFoundError:
        return False, "bd not found"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--packet",
        default=str(_REPO / ".agents" / "handoffs" / "transfer_packet.json"),
    )
    parser.add_argument("--force", action="store_true", help="Ignore budget.decision")
    args = parser.parse_args()

    packet_path = Path(args.packet).resolve()
    if not packet_path.is_file():
        print(json.dumps({"ok": False, "error": "transfer_packet.json missing"}))
        return 1

    packet = _load_packet(packet_path)
    budget = packet.get("budget") or {}
    decision = budget.get("decision", "handoff_only")
    if decision != "spawn" and not args.force:
        ok, msg = spawn_manual_bead(
            f"Spawn blocked (decision={decision}). Read {packet_path.name}"
        )
        print(
            json.dumps(
                {"ok": ok, "adapter": "manual", "message": msg, "decision": decision}
            )
        )
        return 0

    cfg = load_agent_budget_config(_REPO)
    runtime = (
        os.environ.get("CHROMATIC_SUCCESSOR_RUNTIME")
        or (packet.get("successor") or {}).get("runtime")
        or cfg.get("default_successor_runtime", "cursor")
    )
    runtimes = cfg.get("runtimes") or {}
    adapter = (runtimes.get(runtime) or {}).get("spawn_adapter", "manual")
    prompt = _prompt_body(_REPO, packet)

    result: dict[str, Any] = {"runtime": runtime, "adapter": adapter}
    if adapter == "cursor_sdk":
        ok, msg = spawn_cursor_sdk(prompt)
        result.update({"ok": ok, "message": msg})
        if not ok:
            ok2, msg2 = spawn_manual_bead(msg)
            result["fallback"] = {"ok": ok2, "message": msg2}
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if adapter == "claude_cli":
        ok, msg = spawn_claude_cli(_REPO, prompt)
        result.update({"ok": ok, "message": msg})
        if not ok:
            ok2, msg2 = spawn_manual_bead(msg)
            result["fallback"] = {"ok": ok2, "message": msg2}
        print(json.dumps(result, indent=2))
        return 0 if ok else 1

    ok, msg = spawn_manual_bead(
        f"Handoff ready at {packet.get('handoff_path', '')}. Budget: {decision}."
    )
    result.update({"ok": ok, "message": msg})
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
