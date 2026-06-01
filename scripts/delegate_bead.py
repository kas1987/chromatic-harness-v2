#!/usr/bin/env python3
"""Delegate a bead to a local/cheaper model via the Chromatic router.

This is the concrete "dispatch lower-complexity beads to other LLMs" path:

    bead id -> classify C-level -> if C1/C2 route to a local model
    (Ollama) via ChromaticRouter -> capture the result -> attach it to the bead.

C3/C4 work stays on the orchestrator model (Claude) — those need the
reasoning. Only mechanical C1/C2 work is delegated, which is where the
cost/quota savings are.

Usage:
  python scripts/delegate_bead.py <bead-id>                 # delegate if C1/C2
  python scripts/delegate_bead.py <bead-id> --dry-run       # classify only
  python scripts/delegate_bead.py --sweep                   # all `bd ready` C1/C2
  python scripts/delegate_bead.py --sweep --dry-run
  python scripts/delegate_bead.py <bead-id> --max-level C3  # widen delegation
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "02_RUNTIME"))

from intake.bd_runner import resolve_bd_argv  # noqa: E402
from router.router import ChromaticRouter  # noqa: E402
from router.contracts import (  # noqa: E402
    RouteRequest,
    RouteInput,
    RouteConstraints,
    RouteConfidence,
    TaskType,
    PrivacyClass,
    ConfidenceBand,
    OutputType,
)

_LEVEL_ORDER = {"C1": 1, "C2": 2, "C3": 3, "C4": 4}


def _run_bd(args: list[str], *, timeout: int = 60) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [*resolve_bd_argv(), *args],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # bd missing / timeout
        return 1, str(exc)


def _bead_text(bead_id: str) -> tuple[str, str]:
    """Return (title, description) for a bead via `bd show --json`, best-effort."""
    code, out = _run_bd(["show", bead_id, "--json"])
    if code == 0:
        try:
            data = json.loads(out)
            rec = data[0] if isinstance(data, list) and data else data
            if isinstance(rec, dict):
                return str(rec.get("title", "")), str(rec.get("description", ""))
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
    # Fallback: plain `bd show` — first line as title.
    code, out = _run_bd(["show", bead_id])
    if code != 0:
        raise ValueError(f"Failed to retrieve bead '{bead_id}': {out.strip()}")
    first = out.strip().splitlines()[0] if out.strip() else ""
    return first, out


def _ready_bead_ids() -> list[str]:
    code, out = _run_bd(["ready"])
    if code != 0:
        raise RuntimeError(f"Failed to list ready beads: {out.strip()}")
    ids: list[str] = []
    for line in out.splitlines():
        m = re.search(r"(chromatic-harness-v2-[a-z0-9]+)", line)
        if m:
            ids.append(m.group(1))
    return ids


async def delegate(
    bead_id: str,
    *,
    max_level: str = "C2",
    dry_run: bool = False,
    router: ChromaticRouter | None = None,
) -> dict:
    """Classify a bead and, if within max_level, run it on a local model."""
    router = router or ChromaticRouter()
    title, description = _bead_text(bead_id)
    objective = f"{title}\n\n{description}".strip() or bead_id

    complexity = router.complexity_classifier.classify(objective)
    level = getattr(complexity, "level", "C4")
    threshold = _LEVEL_ORDER.get(max_level, 2)

    result: dict = {
        "bead_id": bead_id,
        "c_level": level,
        "c_confidence": round(getattr(complexity, "confidence", 0.0), 3),
        "delegated": False,
        "max_level": max_level,
    }

    if _LEVEL_ORDER.get(level, 4) > threshold:
        result["reason"] = f"{level} exceeds max_level {max_level}; keep on orchestrator"
        return result

    if dry_run:
        result["reason"] = f"{level} <= {max_level}: would delegate to local model"
        result["would_delegate"] = True
        return result

    # Route to a local model. P0 + prefer ollama so the local adapter is chosen;
    # the router's fallback chain still protects us if the local model is down.
    req = RouteRequest(
        request_id=f"delegate-{bead_id}",
        task_id=bead_id,
        task_type=TaskType.CODING,
        objective=objective,
        input=RouteInput(messages=[{"role": "user", "content": objective}]),
        constraints=RouteConstraints(privacy_class=PrivacyClass.P0, allow_cloud=True),
        confidence=RouteConfidence(score=90.0, band=ConfidenceBand.HIGH),
        preferred_provider="ollama",
    )
    resp = await router.route(req)
    provider = getattr(resp, "selected_provider", "")
    out = getattr(resp, "output", None)
    is_error = out is not None and out.type == OutputType.ERROR
    content = getattr(out, "content", "") if out is not None else ""

    # A `mock` provider means the real local/cheaper adapters were all
    # unavailable and the router fell back to the always-succeeds mock. That is
    # NOT real delegation — don't count it or write a bead note as if a local
    # model did the work.
    is_mock = provider == "mock"
    delegated = not is_error and not is_mock

    result["delegated"] = delegated
    result["provider"] = provider
    result["error"] = is_error
    result["output_preview"] = str(content)[:500]
    result["cost_estimate_usd"] = getattr(resp, "cost_estimate_usd", None)
    if is_mock:
        result["reason"] = "router fell back to mock; no local model available"

    if delegated:
        note = f"[delegated to {provider}] C-level={level}. Model output:\n\n{content}"
        nc, err_out = _run_bd(["update", bead_id, "--notes", note[:4000]])
        result["bead_note_written"] = nc == 0
        if nc != 0:
            result["bead_note_error"] = err_out.strip()

    return result


async def _main_async(args: argparse.Namespace) -> int:
    router = ChromaticRouter()
    if args.sweep:
        try:
            ids = _ready_bead_ids()
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not ids:
            print("No ready beads found.", file=sys.stderr)
            return 0
        results = []
        for bid in ids:
            # One bad bead (transient error, corrupt record) must not abort the
            # whole sweep — log it and keep going.
            try:
                r = await delegate(bid, max_level=args.max_level, dry_run=args.dry_run, router=router)
            except Exception as exc:
                print(f"  {bid}: failed to delegate: {exc}", file=sys.stderr)
                continue
            results.append(r)
            verb = "would delegate" if args.dry_run else ("delegated" if r["delegated"] else "kept")
            prov = f" ({r.get('provider', '')})" if r.get("provider") else ""
            print(f"  {bid}: {r['c_level']} -> {verb}{prov}")
        if not results:
            print("\nNo beads were successfully processed.", file=sys.stderr)
            return 1
        n_deleg = sum(1 for r in results if r.get("delegated") or r.get("would_delegate"))
        print(f"\n{n_deleg}/{len(results)} beads delegated to local/cheaper models")
        if args.json:
            print(json.dumps(results, indent=2))
        return 0

    if not args.bead_id:
        print("error: provide a bead id or --sweep", file=sys.stderr)
        return 2
    result = await delegate(args.bead_id, max_level=args.max_level, dry_run=args.dry_run, router=router)
    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Delegate beads to local/cheaper models")
    parser.add_argument("bead_id", nargs="?", help="Bead id to delegate")
    parser.add_argument("--sweep", action="store_true", help="Delegate all ready C1/C2 beads")
    parser.add_argument(
        "--max-level",
        default="C2",
        choices=["C1", "C2", "C3", "C4"],
        help="Highest C-level to delegate (default C2)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Classify only; do not route")
    parser.add_argument("--json", action="store_true", help="Emit full JSON in sweep mode")
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
