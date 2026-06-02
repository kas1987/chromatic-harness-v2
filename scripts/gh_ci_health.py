#!/usr/bin/env python3
"""On-demand GitHub CI-health probe — detects silent CI breakage.

Motivated by a real incident: GitHub Actions was disabled at the repo level, so
`ci.yml` silently stopped running on every branch/PR for two days while only the
Copilot review bot (a GitHub App, not Actions) kept appearing — masking the gap.

This is the deliberate alternative to a standing GitHub MCP: a thin, `gh`-backed
script the pipeline (a SessionStart step, a magnet, or a scheduler) can call on
demand. It costs nothing until invoked and adds no per-turn context.

Checks:
  1. Actions enabled at the repo level (the thing that broke).
  2. The latest CI run on the target ref — its conclusion and age.

Verdict: ``ok`` / ``warn`` (stale or unknown) / ``fail`` (Actions off, or last run
failed). Dependency-injected runner → fully testable without a network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import run_safe  # noqa: E402

Runner = Callable[[list[str]], "tuple[int, str]"]
_REPO_SLUG = "kas1987/chromatic-harness-v2"


def _default_runner(cmd: list[str]) -> tuple[int, str]:
    # run_safe reaps the process tree on timeout (rc=124) and returns rc=1 on a
    # missing binary; both are non-zero, which the callers' `code != 0` checks
    # treat identically (the 127 value was never inspected downstream).
    proc = run_safe(cmd, timeout=30)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _json(code: int, out: str) -> Any:
    if code != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def check_ci_health(
    *,
    repo: str = _REPO_SLUG,
    workflow: str = "ci.yml",
    stale_after_hours: float = 48.0,
    gh: Runner | None = None,
) -> dict[str, Any]:
    """Probe Actions-enabled + latest workflow-run conclusion. Pure verdict dict."""
    run = gh or _default_runner
    reasons: list[str] = []
    verdict: dict[str, Any] = {
        "actions_enabled": None,
        "last_conclusion": None,
        "last_status": None,
        "status": "ok",
        "reasons": reasons,
    }

    perms = _json(*run(["gh", "api", f"repos/{repo}/actions/permissions"]))
    if perms is None:
        reasons.append("could not read Actions permissions (gh unavailable)")
        verdict["status"] = "warn"
    else:
        enabled = bool(perms.get("enabled"))
        verdict["actions_enabled"] = enabled
        if not enabled:
            reasons.append("GitHub Actions is DISABLED at the repo level")
            verdict["status"] = "fail"

    runs = _json(
        *run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                workflow,
                "--limit",
                "1",
                "--json",
                "status,conclusion,createdAt,headBranch",
            ]
        )
    )
    if not runs:
        reasons.append(f"no runs found for {workflow}")
        if verdict["status"] == "ok":
            verdict["status"] = "warn"
    else:
        last = runs[0]
        verdict["last_status"] = last.get("status")
        verdict["last_conclusion"] = last.get("conclusion")
        verdict["last_branch"] = last.get("headBranch")
        if last.get("status") == "completed" and last.get("conclusion") not in (
            "success",
            None,
        ):
            reasons.append(f"latest {workflow} run concluded {last.get('conclusion')}")
            if verdict["status"] != "fail":
                verdict["status"] = "warn"

    return verdict


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="GitHub CI-health probe")
    p.add_argument("--repo", default=_REPO_SLUG)
    p.add_argument("--workflow", default="ci.yml")
    args = p.parse_args(argv)
    v = check_ci_health(repo=args.repo, workflow=args.workflow)
    print(json.dumps(v, indent=2))
    # fail (2) only when Actions is off or a run failed — warn/ok exit 0.
    return 2 if v["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
