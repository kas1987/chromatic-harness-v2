#!/usr/bin/env python3
"""error_log_to_learning.py — auto-feed the learning flywheel from CI/harness errors.

Bridges ``00_META/observability/ERROR_LOG.jsonl`` failures into ``bd remember``-ready
learning candidates so the flywheel accumulates **without a manual harvest pass**
(OMH-5, ``chromatic-harness-v2-w1bf.5``).

GOVERNANCE — read-only analysis. This tool NEVER runs ``bd remember`` / ``ao`` itself.
It stages proposals (a human-readable ``.md`` and a machine ``.jsonl`` of candidates,
each carrying the exact ``bd remember`` command) under
``00_META/observability/staging/``. Promotion into the knowledge base stays an
explicit, human/gated step. ``--dry-run`` writes nothing and prints a JSON summary.

Distinct from ``propose_learnings.py`` (which stages generic repeated-signature
markdown): this script filters to **failures** (CI / harness errors), synthesises a
richer candidate (cause, fix-taken, surfaces, sample events), and emits records
shaped for direct knowledge-base ingestion.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from common_harness import priority_for, repo_root, utc_now

# An event counts as a failure worth learning from when any of these hold.
FAILURE_SEVERITIES = {"critical", "high", "error"}
OPEN_STATUSES = {"open", "unresolved", "in-progress", "investigating"}
# Categories that are operational noise, never a learning candidate.
SKIP_CATEGORIES = {"manual_note"}


def load_events(log: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not log.exists():
        return events
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)  # log may be partially written; guard parse
        except (ValueError, TypeError):
            continue
        if isinstance(e, dict):
            events.append(e)
    return events


def is_failure(e: Dict[str, Any]) -> bool:
    if e.get("category") in SKIP_CATEGORIES:
        return False
    if e.get("severity") in FAILURE_SEVERITIES:
        return True
    if e.get("event_type") == "failure":
        return True
    if e.get("status") in OPEN_STATUSES:
        return True
    exit_code = e.get("exit_code")
    return isinstance(exit_code, int) and exit_code != 0


def signature(e: Dict[str, Any]) -> str:
    return (e.get("error_signature") or e.get("category") or (e.get("raw_excerpt", "")[:60]) or "unknown").strip()


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return ("err-" + s)[:48] or "err-unknown"


_SEV_RANK = {"critical": 4, "high": 3, "error": 3, "medium": 2, "low": 1, "info": 0}


def _first_nonempty(events: List[Dict[str, Any]], key: str) -> str:
    for e in events:
        v = (e.get(key) or "").strip() if isinstance(e.get(key), str) else ""
        if v:
            return v
    return ""


def known_signatures(root: Path) -> set[str]:
    """Signatures already promoted into the canonical learnings log — skip re-proposing."""
    canonical = root / "00_META/observability/LEARNINGS_LOG.md"
    if not canonical.exists():
        return set()
    text = canonical.read_text(encoding="utf-8")
    return {line for line in text.splitlines()}  # cheap membership source; matched by substring below


def build_candidate(sig: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    severities = Counter(e.get("severity", "unknown") for e in events)
    categories = Counter(e.get("category", "unknown") for e in events)
    surfaces = Counter((e.get("source") or {}).get("surface", "unknown") for e in events)
    top_severity = max(severities, key=lambda s: _SEV_RANK.get(s, 0))
    top_category = categories.most_common(1)[0][0]
    cause = _first_nonempty(events, "suspected_cause")
    fix = _first_nonempty(events, "linked_fix") or _first_nonempty(events, "action_taken")
    files = Counter(f for e in events for f in (e.get("files_touched") or []))
    sample_ids = [e.get("event_id") for e in events if e.get("event_id")][:3]

    parts = [
        f"CI/harness failure `{sig}` recurred {len(events)}x",
        f"across {', '.join(sorted(surfaces))}",
        f"(category: {top_category}, peak severity: {top_severity}).",
    ]
    if cause:
        parts.append(f"Suspected cause: {cause}.")
    if fix:
        parts.append(f"Fix applied previously: {fix}.")
    if files:
        parts.append("Hot files: " + ", ".join(f for f, _ in files.most_common(3)) + ".")
    insight = " ".join(parts)

    key = slug(sig)
    return {
        "key": key,
        "signature": sig,
        "occurrences": len(events),
        "peak_severity": top_severity,
        "top_category": top_category,
        "suggested_priority": priority_for(top_severity, top_category),
        "surfaces": dict(surfaces),
        "suspected_cause": cause,
        "fix_applied": fix,
        "hot_files": [f for f, _ in files.most_common(5)],
        "sample_event_ids": sample_ids,
        "insight": insight,
        "bd_remember_command": ["bd", "remember", insight, "--key", key],
    }


def render_markdown(candidates: List[Dict[str, Any]]) -> str:
    lines = [
        "# Learning Candidates from Errors (PROPOSED — review before promoting)",
        "",
        f"Generated: {utc_now()}",
        "",
        "> Auto-extracted from ERROR_LOG.jsonl failures (OMH-5). These are PROPOSALS.",
        "> This tool never runs `bd remember`; a human/gated step promotes them.",
        "",
    ]
    for c in candidates:
        lines += [
            f"## `{c['signature']}` — {c['occurrences']}x ({c['peak_severity']}, {c['suggested_priority']})",
            "",
            c["insight"],
            "",
            f"- Proposed key: `{c['key']}`",
            f"- Surfaces: {', '.join(f'{k}:{v}' for k, v in c['surfaces'].items())}",
            f"- Sample events: {', '.join(c['sample_event_ids']) or '(none)'}",
            "- Promote with:",
            "",
            "  ```bash",
            f"  bd remember {json.dumps(c['insight'])} --key {c['key']}",
            "  ```",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage bd-remember learning candidates from CI/harness errors.")
    ap.add_argument("--repo-root")
    ap.add_argument("--log", help="Override path to ERROR_LOG.jsonl")
    ap.add_argument("--threshold", type=int, default=2, help="Min occurrences of a failure signature to propose")
    ap.add_argument(
        "--dry-run", action="store_true", help="Print a JSON summary of candidates; write nothing to staging"
    )
    args = ap.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    log = Path(args.log) if args.log else root / "00_META/observability/ERROR_LOG.jsonl"

    events = [e for e in load_events(log) if is_failure(e)]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        grouped.setdefault(signature(e), []).append(e)

    known = "\n".join(known_signatures(root))
    candidates = [
        build_candidate(sig, evs)
        for sig, evs in grouped.items()
        if len(evs) >= args.threshold and sig not in known  # skip already-promoted signatures
    ]
    candidates.sort(key=lambda c: c["occurrences"], reverse=True)

    if args.dry_run:
        print(json.dumps({"candidate_count": len(candidates), "candidates": candidates}, indent=2))
        return 0

    if not candidates:
        print("No learning candidates from errors above threshold.")
        return 0

    staging = root / "00_META/observability/staging"
    staging.mkdir(parents=True, exist_ok=True)
    date = utc_now()[:10]
    md_path = staging / f"LEARNING_FROM_ERRORS_{date}.md"
    jsonl_path = staging / f"learning_candidates_{date}.jsonl"
    md_path.write_text(render_markdown(candidates), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, sort_keys=True) + "\n")
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
