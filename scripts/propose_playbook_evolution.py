#!/usr/bin/env python3
"""Playbook evolution feedback loop (chromatic-harness-v2-7d2.5).

Closes the loop from the Decision Log + Agent Lead lessons back into the static
playbooks under ``04_PLAYBOOKS/``. This is the missing P3 "Playbook Evolution /
Feedback Loop" from CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md.

Design constraints (global policy — background learning systems are READ-ONLY):
  * This script NEVER edits a playbook. It only *proposes*.
  * Proposals are appended to a staging file under 00_META/observability/.
  * A human gate (review + manual edit) is required before any playbook changes.

It reads ``07_LOGS_AND_AUDIT/decisions/decision_log.jsonl`` (written by
``02_RUNTIME/audit/two_log.py::append_decision``) whose entries are shaped::

    {ts, mission_id, task_id, gate, input_score, band, action, reason, lesson}

and surfaces three families of recurring signal, each routed to the most
relevant playbook:

  1. Recurring non-empty ``lesson`` strings  -> codify the lesson.
  2. Recurring low/medium-band escalations    -> tune the gate / routing.
  3. Recurring failure ``reason`` clusters     -> add a fix-pattern.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from common_harness import repo_root, utc_now

# Bands that indicate the harness was *not* confident — these are the
# interesting cases for playbook evolution (a confident "proceed" needs no fix).
_ESCALATION_ACTIONS = {"escalate", "replan", "self_heal", "halt", "error"}
_LOW_BANDS = {"low", "medium"}

# Keyword -> playbook routing table. The first playbook whose keyword set
# overlaps the signal text wins; otherwise we fall back to the orchestrator
# playbook (the catch-all coordination doc).
_ROUTES: list[tuple[str, tuple[str, ...]]] = [
    ("MODEL_ROUTING_PLAYBOOK.md", ("model", "route", "routing", "token", "budget")),
    ("BEADS_PLAYBOOK.md", ("bead", "bd ", "dolt", "intake")),
    ("MAGNETS_PLAYBOOK.md", ("magnet", "inflection", "observ")),
    ("GO_MODE_PLAYBOOK.md", ("go mode", "go_mode", "swarm", "crank", "merge")),
    ("SESSION_COMPACT_PLAYBOOK.md", ("compact", "context", "handoff")),
    ("AGENT_ONBOARDING_PLAYBOOK.md", ("onboard", "agent setup")),
    ("SANDBOX_LAB_PLAYBOOK.md", ("sandbox", "experiment", "lab")),
]
_DEFAULT_PLAYBOOK = "ORCHESTRATOR_PLAYBOOK.md"

# The decision-log ``reason`` is sourced from ``error or next`` by the two-log
# writer, so on a non-error step it holds a routine navigation command (e.g.
# ``bd show <id>``) rather than a real failure. Those are noise for fix-pattern
# mining — drop reasons that are bare inspection commands.
_NOISE_REASON_PREFIXES = ("bd show", "bd ready", "bd list", "git ", "gh ")

_STAGING_MD = "00_META/observability/PLAYBOOK_EVOLUTION_PROPOSALS.md"
_STAGING_JSONL = "00_META/observability/playbook_evolution_proposals.jsonl"


def is_noise_reason(reason: str) -> bool:
    """True if ``reason`` is a routine command, not a genuine failure signal."""
    low = (reason or "").strip().lower()
    return any(low.startswith(p) for p in _NOISE_REASON_PREFIXES)


def route_playbook(text: str) -> str:
    """Pick the most relevant playbook for a signal string (keyword overlap)."""
    low = (text or "").lower()
    for playbook, keywords in _ROUTES:
        if any(kw in low for kw in keywords):
            return playbook
    return _DEFAULT_PLAYBOOK


def _load_decisions(log_path: Path, window: int) -> list[dict]:
    """Read the tail ``window`` decision-log entries; tolerate partial lines."""
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if window > 0:
        lines = lines[-window:]
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            # File may be mid-write or contain a torn final line — skip it.
            continue
    return out


def detect_signals(entries: list[dict], threshold: int) -> list[dict]:
    """Aggregate decision-log entries into recurring-pattern proposals."""
    lessons: Counter[str] = Counter()
    escalations: Counter[tuple[str, str]] = Counter()
    reasons: Counter[str] = Counter()

    for e in entries:
        lesson = (e.get("lesson") or "").strip()
        if lesson:
            lessons[lesson] += 1

        action = (e.get("action") or "").strip().lower()
        band = (e.get("band") or "").strip().lower()
        if action in _ESCALATION_ACTIONS and band in _LOW_BANDS:
            escalations[(band, action)] += 1

        reason = (e.get("reason") or "").strip()
        if reason and action in _ESCALATION_ACTIONS and not is_noise_reason(reason):
            reasons[reason] += 1

    proposals: list[dict] = []

    for lesson, count in lessons.items():
        if count >= threshold:
            proposals.append(
                {
                    "kind": "codify_lesson",
                    "signal": lesson,
                    "count": count,
                    "playbook": route_playbook(lesson),
                    "suggestion": (f"Lesson recurred {count}x — codify it as guidance in the playbook."),
                }
            )

    for (band, action), count in escalations.items():
        if count >= threshold:
            proposals.append(
                {
                    "kind": "tune_gate",
                    "signal": f"{band}-band {action}",
                    "count": count,
                    "playbook": _DEFAULT_PLAYBOOK,
                    "suggestion": (
                        f"{count} decisions landed in {band} band with "
                        f"action={action}; review gate thresholds / add a "
                        f"recovery step to the playbook."
                    ),
                }
            )

    for reason, count in reasons.items():
        if count >= threshold:
            proposals.append(
                {
                    "kind": "add_fix_pattern",
                    "signal": reason,
                    "count": count,
                    "playbook": route_playbook(reason),
                    "suggestion": (
                        f"Failure reason recurred {count}x — add a fix-pattern / preflight check to the playbook."
                    ),
                }
            )

    # Highest-impact (most frequent) proposals first.
    proposals.sort(key=lambda p: p["count"], reverse=True)
    return proposals


def render_markdown(proposals: list[dict], scanned: int, generated_at: str) -> str:
    lines = [
        f"\n## Playbook Evolution Proposals — {generated_at}",
        f"\n_Scanned {scanned} decision-log entries; {len(proposals)} proposal(s) above threshold._\n",
        "_READ-ONLY proposal. No playbook is edited automatically; a human must review and apply._\n",
    ]
    for p in proposals:
        lines.append(
            f"- **[{p['kind']}]** `{p['playbook']}` (seen {p['count']}x): "
            f"{p['suggestion']}\n  - signal: `{p['signal']}`"
        )
    if not proposals:
        lines.append("- _No recurring patterns above threshold._")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root")
    ap.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Minimum recurrences before a pattern becomes a proposal.",
    )
    ap.add_argument(
        "--window",
        type=int,
        default=5000,
        help="Scan only the most recent N decision-log entries (0 = all).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposals to stdout; do not write the staging files.",
    )
    args = ap.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    log_path = root / "07_LOGS_AND_AUDIT" / "decisions" / "decision_log.jsonl"

    entries = _load_decisions(log_path, args.window)
    proposals = detect_signals(entries, args.threshold)
    generated_at = utc_now()
    markdown = render_markdown(proposals, len(entries), generated_at)

    if args.dry_run:
        print(markdown)
        return

    md_path = root / _STAGING_MD
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with md_path.open("a", encoding="utf-8") as f:
        f.write(markdown)

    if proposals:
        jsonl_path = root / _STAGING_JSONL
        with jsonl_path.open("a", encoding="utf-8") as f:
            for p in proposals:
                f.write(json.dumps({"generated_at": generated_at, **p}, sort_keys=True) + "\n")

    print(f"{md_path}  ({len(proposals)} proposal(s) from {len(entries)} entries)")


if __name__ == "__main__":
    main()
