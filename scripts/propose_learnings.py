#!/usr/bin/env python3
"""propose_learnings.py — identify repeated error signatures as learning candidates.

GOVERNANCE: this is a read-only *analysis* tool. By default it STAGES proposals
to ``00_META/observability/staging/LEARNING_CANDIDATES_<date>.md`` for human
review and never mutates the canonical ``LEARNINGS_LOG.md``. Promotion to the
canonical log is an explicit, gated action via ``--commit``.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from common_harness import repo_root, utc_now


def load_signatures(log: Path) -> list[str]:
    sigs = []
    if not log.exists():
        return sigs
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)  # file may be partially written; guard parse
        except (ValueError, TypeError):
            continue
        if not isinstance(e, dict):
            continue
        sigs.append(e.get("error_signature") or e.get("category", "unknown"))
    return sigs


def render(candidates) -> str:
    lines = [
        "# Learning Candidates (PROPOSED — review before promoting)",
        "",
        f"Generated: {utc_now()}",
        "",
        "> Staged proposals. Promote to LEARNINGS_LOG.md only after review",
        "> (re-run with --commit, or copy entries manually).",
        "",
    ]
    for sig, c in candidates:
        lines.append(f"- Pattern `{sig}` appeared {c} times. Review for playbook or fix-pattern update.")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Propose learning candidates from repeated error signatures.")
    ap.add_argument("--repo-root")
    ap.add_argument("--threshold", type=int, default=3)
    ap.add_argument(
        "--commit",
        action="store_true",
        help="Gated promotion: append candidates to the canonical LEARNINGS_LOG.md.",
    )
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    log = root / "00_META/observability/ERROR_LOG.jsonl"

    sigs = load_signatures(log)
    candidates = [(s, c) for s, c in Counter(sigs).most_common() if s and c >= args.threshold]
    if not candidates:
        print("No learning candidates above threshold.")
        return 0

    if args.commit:
        # Explicit, gated promotion to the canonical learnings log.
        canonical = root / "00_META/observability/LEARNINGS_LOG.md"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        with canonical.open("a", encoding="utf-8") as f:
            f.write(f"\n## Learning Candidates - {utc_now()}\n")
            for sig, c in candidates:
                f.write(f"\n- Pattern `{sig}` appeared {c} times. Review for playbook or fix-pattern update.\n")
        print(f"Promoted {len(candidates)} candidate(s) to {canonical}")
        return 0

    # Default: stage proposals for review (never mutate the canonical log).
    staging = root / "00_META/observability/staging" / ("LEARNING_CANDIDATES_" + utc_now()[:10] + ".md")
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(render(candidates), encoding="utf-8")
    print(staging)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
