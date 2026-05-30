#!/usr/bin/env python3
"""Run the CI gate suite locally — the single source of truth for both git hooks
and (optionally) the GitHub workflow, so local and remote never drift.

Why: GitHub Actions is free for *public* repos but costs minutes on private ones,
and local gates give faster feedback regardless. This runner lets you enforce the
same checks at commit / push time as CI would, with no cloud cost.

Presets:
  --stage pre-commit   fast gates only (ruff check + format) — keep commits snappy
  --stage pre-push     fast + guards + mypy + pytest (default) — full local CI
  --stage merge        same as pre-push (authoritative pre-merge gate)

Flags: --skip mypy,pytest to drop slow gates; --list to print the gate plan.
Exit 0 only when every selected gate passes; non-zero (count of failures) otherwise.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

Runner = Callable[[list[str]], int]


@dataclass(frozen=True)
class Gate:
    name: str
    cmd: list[str]
    fast: bool  # runs in the pre-commit (fast) tier


def gate_plan() -> list[Gate]:
    """The canonical gate list, mirroring .github/workflows/ci.yml (Linux job)."""
    return [
        Gate("ruff-check", [PY, "-m", "ruff", "check", "src/", "tests/"], fast=True),
        Gate(
            "ruff-format",
            [PY, "-m", "ruff", "format", "--check", "src/", "tests/"],
            fast=True,
        ),
        Gate("agent-ops-guard", [PY, "scripts/check_agent_operations.py"], fast=False),
        Gate("intake-loop", [PY, "scripts/validate_intake_loop.py"], fast=False),
        Gate(
            "mypy", [PY, "-m", "mypy", "src/", "--config-file", "mypy.ini"], fast=False
        ),
        Gate("pytest", [PY, "-m", "pytest", "tests/", "-q"], fast=False),
    ]


def _default_runner(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=_REPO, check=False).returncode


def select_gates(stage: str, skip: set[str]) -> list[Gate]:
    gates = gate_plan()
    if stage == "pre-commit":
        gates = [g for g in gates if g.fast]
    return [g for g in gates if g.name not in skip]


def run_gates(gates: list[Gate], *, runner: Runner | None = None) -> dict[str, int]:
    """Run each gate; return {name: returncode}. 0 == pass."""
    run = runner or _default_runner
    results: dict[str, int] = {}
    for g in gates:
        print(f"== ci-local: {g.name} ==", flush=True)
        rc = run(g.cmd)
        results[g.name] = rc
        print(f"   {'PASS' if rc == 0 else 'FAIL'} ({g.name})", flush=True)
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run CI gates locally")
    p.add_argument(
        "--stage", choices=["pre-commit", "pre-push", "merge"], default="pre-push"
    )
    p.add_argument("--skip", default="", help="comma-separated gate names to skip")
    p.add_argument("--list", action="store_true", help="print the gate plan and exit")
    args = p.parse_args(argv)

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    gates = select_gates(args.stage, skip)

    if args.list:
        for g in gates:
            print(f"{g.name}: {' '.join(g.cmd)}")
        return 0

    results = run_gates(gates)
    failed = [n for n, rc in results.items() if rc != 0]
    print(
        f"\nci-local [{args.stage}]: {len(results) - len(failed)}/{len(results)} passed"
        + (f" — FAILED: {', '.join(failed)}" if failed else "")
    )
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(main())
