#!/usr/bin/env python3
"""consensus_workflow.py — Multi-agent review consensus workflow (GH #65).

Implements a lightweight consensus scoring protocol where each reviewer role
independently rates a proposed change as approve / reject / abstain.

Decision rules:
  - Consensus = simple majority among non-abstaining votes.
  - Tie (equal approve/reject) → escalate (exit 2).
  - All abstain → escalate.
  - Quorum = number of non-abstaining reviewers (must be >= 1).

Output (JSON to stdout):
    {
        "verdict":  "approve" | "reject" | "escalate",
        "scores":   {"security": "approve", "correctness": "reject", ...},
        "quorum":   2,
        "approve_count": 2,
        "reject_count":  1,
        "abstain_count": 0,
        "subject":  "PR title",
        "timestamp": "2026-06-01T00:00:00Z"
    }

Artifact written to: .agents/council/latest_consensus.json

Exit codes:
    0 = approve
    1 = reject
    2 = escalate (tie, all-abstain, or error)

CLI:
    python scripts/consensus_workflow.py \\
        --subject "Add policy engine" \\
        --diff-summary "Adds scripts/policy_engine.py and docs" \\
        [--roles security,correctness,completeness]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
COUNCIL_DIR = REPO / ".agents" / "council"
CONSENSUS_FILE = COUNCIL_DIR / "latest_consensus.json"

# Default reviewer roles used when --roles is not specified.
DEFAULT_ROLES = ["security", "correctness", "completeness"]

# Static role heuristics: each role evaluates subject + diff_summary and
# returns approve / reject / abstain based on keyword signals.
# In a live multi-agent environment these would be replaced by LLM calls.
_APPROVE_SIGNALS: dict[str, list[str]] = {
    "security": ["read", "docs", "test", "log", "audit", "allow", "allow-t1", "allow-t2"],
    "correctness": ["fix", "update", "refactor", "test", "docs", "correct", "gate", "engine"],
    "completeness": ["add", "create", "new", "implement", "complete", "init", "workflow"],
}
_REJECT_SIGNALS: dict[str, list[str]] = {
    "security": ["secret", "credential", "pem", "key", "force push", "force-push", "rm -rf"],
    "correctness": ["broken", "regression", "fail", "error", "crash", "invalid"],
    "completeness": ["todo", "stub", "placeholder", "wip", "fixme", "missing"],
}


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _heuristic_vote(role: str, subject: str, diff_summary: str) -> str:
    """
    Heuristic vote for a reviewer role.

    Returns "approve", "reject", or "abstain".
    Checks reject signals first (they take priority over approve signals).
    Falls back to abstain when neither signal fires.
    """
    combined = (subject + " " + diff_summary).lower()
    role_lower = role.lower()

    reject_words = _REJECT_SIGNALS.get(role_lower, _REJECT_SIGNALS.get("correctness", []))
    approve_words = _APPROVE_SIGNALS.get(role_lower, _APPROVE_SIGNALS.get("completeness", []))

    for word in reject_words:
        if word in combined:
            return "reject"
    for word in approve_words:
        if word in combined:
            return "approve"
    return "abstain"


def run_consensus(
    subject: str,
    diff_summary: str,
    roles: list[str],
) -> dict[str, Any]:
    """
    Run consensus scoring for the given roles.

    Each role produces approve / reject / abstain.
    Returns a full consensus record.
    """
    ts = _ts()
    scores: dict[str, str] = {}
    for role in roles:
        scores[role] = _heuristic_vote(role, subject, diff_summary)

    approve_count = sum(1 for v in scores.values() if v == "approve")
    reject_count = sum(1 for v in scores.values() if v == "reject")
    abstain_count = sum(1 for v in scores.values() if v == "abstain")
    quorum = approve_count + reject_count  # non-abstaining

    if quorum == 0:
        verdict = "escalate"
        reason = "All reviewers abstained; no quorum reached."
    elif approve_count > reject_count:
        verdict = "approve"
        reason = f"Majority approve ({approve_count}/{quorum} non-abstaining votes)."
    elif reject_count > approve_count:
        verdict = "reject"
        reason = f"Majority reject ({reject_count}/{quorum} non-abstaining votes)."
    else:
        verdict = "escalate"
        reason = f"Tie vote ({approve_count} approve vs {reject_count} reject); escalating."

    return {
        "verdict": verdict,
        "scores": scores,
        "quorum": quorum,
        "approve_count": approve_count,
        "reject_count": reject_count,
        "abstain_count": abstain_count,
        "subject": subject,
        "diff_summary": diff_summary[:200],
        "roles": roles,
        "reason": reason,
        "timestamp": ts,
    }


def write_consensus_artifact(record: dict) -> Path:
    """Write consensus record to .agents/council/latest_consensus.json."""
    COUNCIL_DIR.mkdir(parents=True, exist_ok=True)
    CONSENSUS_FILE.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return CONSENSUS_FILE


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Multi-agent review consensus workflow (GH #65)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0 = approve
  1 = reject
  2 = escalate (tie, all-abstain, or quorum failure)

Examples:
  python scripts/consensus_workflow.py \\
      --subject "Add policy engine" \\
      --diff-summary "Adds scripts/policy_engine.py with YAML rule loader"

  python scripts/consensus_workflow.py \\
      --subject "Remove secrets vault" \\
      --diff-summary "Deletes credentials.pem" \\
      --roles security,correctness

  python scripts/consensus_workflow.py \\
      --subject "Refactor memory gate" \\
      --diff-summary "Refactors 02_RUNTIME/memory/memory_gate.py" \\
      --roles security,correctness,completeness \\
      --dry-run
""",
    )
    ap.add_argument("--subject", required=True, help="PR title or change subject")
    ap.add_argument(
        "--diff-summary",
        required=True,
        help="Brief summary of the diff / change description",
    )
    ap.add_argument(
        "--roles",
        default=",".join(DEFAULT_ROLES),
        help=f"Comma-separated reviewer roles (default: {','.join(DEFAULT_ROLES)})",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Run consensus but do not write artifact to disk",
    )
    args = ap.parse_args()

    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    if not roles:
        print(json.dumps({"error": "No reviewer roles specified."}), file=sys.stderr)
        return 2

    record = run_consensus(
        subject=args.subject,
        diff_summary=args.diff_summary,
        roles=roles,
    )

    if not args.dry_run:
        try:
            artifact_path = write_consensus_artifact(record)
            record["_artifact_path"] = str(artifact_path.relative_to(REPO))
        except OSError as exc:
            record["_artifact_error"] = str(exc)

    print(json.dumps(record, indent=2))

    verdict = record["verdict"]
    if verdict == "approve":
        return 0
    if verdict == "reject":
        return 1
    return 2  # escalate


if __name__ == "__main__":
    raise SystemExit(main())
