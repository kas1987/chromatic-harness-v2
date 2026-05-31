#!/usr/bin/env python3
"""SessionEnd hook: promote high-confidence learnings to pending candidates.

KOS Stage 8 — Feedback Loop
Reads .agents/learnings/*.md with confidence >= 0.8 and creates a pending
candidate in .agents/candidates/ for any learning not already represented
there (checked by name slug).  Appends one telemetry record to
05_REPORTS/telemetry.jsonl and prints a summary line.

Fail-open: any unhandled exception prints a warning and exits 0 so it never
blocks SessionEnd.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEARNINGS_DIR = REPO / ".agents" / "learnings"
CANDIDATES_DIR = REPO / ".agents" / "candidates"
TELEMETRY_FILE = REPO / "05_REPORTS" / "telemetry.jsonl"

MIN_CONFIDENCE = 0.8

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_CATEGORICAL_CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = text[m.end() :]
    return meta, body


def _confidence(meta: dict) -> float:
    raw = meta.get("confidence", "0") or "0"
    key = str(raw).strip().lower()
    if key in _CATEGORICAL_CONFIDENCE:
        return _CATEGORICAL_CONFIDENCE[key]
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if val > 1.0:
        val = val / 100.0
    return max(0.0, min(1.0, val))


def _name_to_slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")[:80] or "candidate"


def _existing_candidate_slugs() -> set[str]:
    if not CANDIDATES_DIR.is_dir():
        return set()
    return {p.stem for p in CANDIDATES_DIR.iterdir() if p.suffix == ".md"}


def _build_candidate_text(name: str, slug: str, confidence: float, body: str) -> str:
    suggested_use = f"Apply {name} guidance"
    # Strip "Learning: " prefix that nightly extracts often add
    first_heading = re.search(r"^#\s+(?:Learning:\s*)?(.+)$", body, re.MULTILINE)
    if first_heading:
        suggested_use = first_heading.group(1).strip()

    source_ids_yaml = f"[{slug}]"
    frontmatter = (
        f"---\n"
        f"name: {name}\n"
        f"source_ids: {source_ids_yaml}\n"
        f"source_type: learning\n"
        f"confidence: {confidence:.2f}\n"
        f"suggested_use: {suggested_use}\n"
        f"canon_map: general\n"
        f"status: pending\n"
        f"tags: []\n"
        f"---\n"
    )
    candidate_body = (
        f"\n## Summary\n\n{suggested_use}\n\n## Evidence\n\n{body.strip()}\n"
    )
    return frontmatter + candidate_body


def main() -> None:
    try:
        CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
        existing_slugs = _existing_candidate_slugs()

        new_candidates = 0

        for path in sorted(LEARNINGS_DIR.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            meta, body = _parse_frontmatter(text)
            conf = _confidence(meta)
            if conf < MIN_CONFIDENCE:
                continue

            # Derive name: prefer frontmatter 'name', fall back to file stem
            raw_name = meta.get("name", "").strip() or path.stem
            slug = _name_to_slug(raw_name)

            if slug in existing_slugs:
                continue

            candidate_text = _build_candidate_text(raw_name, slug, conf, body)
            dest = CANDIDATES_DIR / f"{slug}.md"
            dest.write_text(candidate_text, encoding="utf-8")
            existing_slugs.add(slug)
            new_candidates += 1

        # Append telemetry record
        session_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        record = {
            "event": "knowledge_feedback",
            "new_candidates": new_candidates,
            "session_id": session_id,
            "timestamp": timestamp,
        }
        TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TELEMETRY_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        print(
            f"Knowledge feedback: {new_candidates} new candidates staged from "
            "high-confidence learnings"
        )

    except Exception as exc:  # noqa: BLE001
        print(
            f"[session_knowledge_feedback] WARNING: {exc} — skipping", file=sys.stderr
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
