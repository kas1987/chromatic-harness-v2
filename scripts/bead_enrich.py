#!/usr/bin/env python3
"""bead_enrich.py — make ready beads gate-ready for the long-running task runner.

The runner only takes on a bead whose confidence score clears the dispatch gate
(>=75, or >=60 if reversible+low-risk). Freshly-created beads usually carry only a
title + description, so they score ~50-54 and are correctly skipped. This tool:

  * `report` (default) — for every non-epic ready bead, show the *accurate*
    confidence score, band, dispatch verdict, and the specific weak factors +
    what to add. Read-only.
  * `apply` — write REAL, caller-supplied acceptance criteria (and optional file
    scope / risk) onto one bead via `bd update`. It never fabricates content; you
    pass the criteria.

Scoring reuses go_mode verbatim (estimate_factors -> score_confidence ->
dispatch_allowed), so the report reflects exactly what the runner will decide.

Examples:
  python scripts/bead_enrich.py report
  python scripts/bead_enrich.py report --json
  python scripts/bead_enrich.py apply --bead chromatic-harness-v2-u8uj.1 \
      --acceptance "RoutingContext dataclass defined in router/contracts.py; \
ContextDetector/ComplexityClassifier/ProviderSelector refactored as pure functions; \
unit tests validate pure-function behaviour and pytest is green" \
      --scope 02_RUNTIME/router/contracts.py --risk low
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import go_mode  # noqa: E402
from common_harness import run_safe  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

# A factor is "weak" below the value it would need to help clear the 75 gate.
# Maps factor -> (target, human suggestion).
_FACTOR_ADVICE: dict[str, tuple[float, str]] = {
    "objective_clarity": (80.0, "add a clear description (bd update --description)"),
    "scope_clarity": (85.0, "declare file scope via scope:<path> labels"),
    "evidence_quality": (90.0, "add >=3 acceptance criteria (bd update --acceptance)"),
    "testability": (90.0, "include a 'test ...'/'validate ...' acceptance criterion"),
    "risk_awareness": (85.0, "add stop:<condition> labels for stop-conditions"),
    "reversibility": (85.0, "high risk — split the task or add reversibility safeguards"),
}


def gate_assessment(item: dict) -> dict:
    """Score one bead through the go_mode gate and surface weak factors + fixes."""
    factors = go_mode.estimate_factors(item)
    confidence = go_mode.score_confidence(factors)
    risk = str(item.get("risk_level", "medium")).lower()
    allowed, reason = go_mode.dispatch_allowed(confidence, risk)

    weak: list[str] = []
    suggestions: list[str] = []
    for name, (target, advice) in _FACTOR_ADVICE.items():
        if factors.get(name, 0.0) < target:
            weak.append(name)
            if advice not in suggestions:
                suggestions.append(advice)

    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "score": confidence["score"],
        "band": confidence["band"],
        "dispatch_allowed": allowed,
        "dispatch_reason": reason,
        "weak_factors": weak,
        "suggestions": suggestions,
    }


def report(items: list[dict]) -> dict:
    """Assess every non-epic item; return assessments + a summary."""
    rows = [gate_assessment(it) for it in items if str(it.get("issue_type", it.get("type", ""))).lower() != "epic"]
    ready = [r for r in rows if r["dispatch_allowed"]]
    return {
        "total": len(rows),
        "gate_ready": len(ready),
        "needs_work": len(rows) - len(ready),
        "ready_ids": [r["id"] for r in ready],
        "assessments": rows,
    }


def build_update_args(bead: str, acceptance: str, scope: list[str], risk: str) -> list[str]:
    """Build the `bd update` argv for an enrichment. Pure (no side effects)."""
    args = ["update", bead]
    if acceptance:
        args += ["--acceptance", acceptance]
    for path in scope:
        args += ["--add-label", f"scope:{path}"]
    if risk:
        args += ["--add-label", f"risk:{risk}"]
    return args


def _run_bd(args: list[str]) -> tuple[int, str]:
    import shutil

    bd = shutil.which("bd") or shutil.which("bd.cmd")
    if not bd:
        return 1, "bd CLI not found"
    proc = run_safe([bd, *args], cwd=REPO, timeout=30)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _cmd_report(args: argparse.Namespace) -> int:
    items = go_mode.load_queue_from_bd()
    result = report(items)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"Gate readiness: {result['gate_ready']}/{result['total']} ready ({result['needs_work']} need work)\n")
    for r in sorted(result["assessments"], key=lambda x: -x["score"]):
        flag = "READY" if r["dispatch_allowed"] else "     "
        print(f"[{flag}] {str(r['id'] or '-'):<28} score={r['score']:>5} band={r['band']}")
        if not r["dispatch_allowed"] and r["suggestions"]:
            print(f"          -> {'; '.join(r['suggestions'])}")
    return 0


def _cmd_apply(args: argparse.Namespace) -> int:
    scope = [s.strip() for s in (args.scope.split(",") if args.scope else []) if s.strip()]
    bd_args = build_update_args(args.bead, args.acceptance, scope, args.risk)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "bd_args": bd_args}, indent=2))
        return 0
    code, out = _run_bd(bd_args)
    print(out.strip())
    if code != 0:
        return code
    # Re-score after enrichment so the caller sees the effect immediately.
    items = go_mode.load_queue_from_bd()
    match = next((it for it in items if str(it.get("id")) == args.bead), None)
    if match:
        a = gate_assessment(match)
        print(
            json.dumps(
                {"after": {"score": a["score"], "band": a["band"], "dispatch_allowed": a["dispatch_allowed"]}}, indent=2
            )
        )
    return 0


def main() -> int:
    # bd emits non-cp1252 glyphs (✓); keep the native encoding but never crash on them.
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001 - best-effort; older/replaced stdout
        pass

    ap = argparse.ArgumentParser(description="Bead gate-readiness report + enricher")
    sub = ap.add_subparsers(dest="command")

    rp = sub.add_parser("report", help="Score ready beads against the dispatch gate (read-only)")
    rp.add_argument("--json", action="store_true")
    rp.set_defaults(func=_cmd_report)

    ap2 = sub.add_parser("apply", help="Write real acceptance criteria / scope onto one bead")
    ap2.add_argument("--bead", required=True)
    ap2.add_argument("--acceptance", default="", help="Criteria, ';'-separated (you supply the content)")
    ap2.add_argument("--scope", default="", help="Comma-separated file paths -> scope:<path> labels")
    ap2.add_argument("--risk", default="", choices=["", "low", "medium", "high"])
    ap2.add_argument("--dry-run", action="store_true", help="Print the bd args without writing")
    ap2.set_defaults(func=_cmd_apply)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        args = ap.parse_args(["report", *(["--json"] if "--json" in sys.argv else [])])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
