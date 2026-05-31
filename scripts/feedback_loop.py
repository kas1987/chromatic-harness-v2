#!/usr/bin/env python3
"""Close the KOS feedback loop — surface session learnings as canon candidates.

KOS Stage 8: Teach & Apply (feedback direction).

The knowledge flywheel is one-way until agent-generated learnings flow back into
the candidate queue. This script scans ``.agents/learnings/`` for high-confidence
entries and stages any not already represented in ``.agents/candidates/`` as
``status: pending`` candidates — the same record shape Stage 5 produces from
patterns, so Stage 6 (review) and Stage 7 (promotion) consume them unchanged.

Invoked at session end (see session_closeout) and runnable manually:

  python scripts/feedback_loop.py --dry-run
  python scripts/feedback_loop.py
  python scripts/feedback_loop.py --min-confidence 0.8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEARNINGS_DIR = REPO / ".agents" / "learnings"
CANDIDATES_DIR = REPO / ".agents" / "candidates"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_CATEGORICAL_CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}

# Tag-to-canon_map mapping (shared rules with stage_candidates Stage 5).
_TAG_CANON_MAP: list[tuple[set[str], str]] = [
    ({"routing", "ollama", "ol-layer", "subagents", "model-routing"}, "routing"),
    ({"security", "secrets", "auth", "permissions"}, "security"),
    ({"knowledge", "wiki", "learnings", "kos", "canon"}, "knowledge"),
    ({"operations", "hooks", "session", "governance", "audit", "ci"}, "operations"),
]
_CATEGORY_CANON_MAP: dict[str, str] = {
    "process": "operations",
    "technical": "general",
    "architecture": "general",
}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end() :]


def _parse_list_field(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [s.strip() for s in raw.split(",") if s.strip()]


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


def _infer_canon_map(tags: list[str], category: str) -> str:
    tag_set = {t.lower() for t in tags}
    for rule_tags, canon in _TAG_CANON_MAP:
        if tag_set & rule_tags:
            return canon
    return _CATEGORY_CANON_MAP.get(category.lower(), "general")


def _existing_candidate_sources() -> set[str]:
    """Return the set of source_ids already represented in candidates/."""
    sources: set[str] = set()
    if not CANDIDATES_DIR.is_dir():
        return sources
    for path in CANDIDATES_DIR.iterdir():
        if (
            path.suffix != ".md"
            or path.name in ("SCHEMA.md",)
            or path.name.startswith("_")
        ):
            continue
        try:
            meta, _ = _parse_frontmatter(
                path.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            continue
        sources.update(_parse_list_field(meta.get("source_ids", "")))
        # The candidate slug itself often matches the source learning slug.
        sources.add(path.stem)
        if meta.get("name"):
            sources.add(meta["name"])
    return sources


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title.lower().startswith("learning:"):
                title = title[9:].strip()
            return title or fallback
    return fallback


def _build_candidate_text(
    *,
    name: str,
    source_id: str,
    confidence: float,
    tags: list[str],
    canon_map: str,
    suggested_use: str,
    body: str,
) -> str:
    source_ids_yaml = "[" + source_id + "]"
    tags_yaml = "[" + ", ".join(tags) + "]"
    frontmatter = (
        f"---\n"
        f"name: {name}\n"
        f"source_ids: {source_ids_yaml}\n"
        f"source_type: learning\n"
        f"confidence: {confidence:.2f}\n"
        f"suggested_use: {suggested_use}\n"
        f"canon_map: {canon_map}\n"
        f"status: pending\n"
        f"tags: {tags_yaml}\n"
        f"---\n"
    )
    return (
        frontmatter
        + f"\n## Summary\n\n{suggested_use}\n\n## Evidence\n\n{body.strip()}\n"
    )


def _discover_learnings(min_conf: float, seen: set[str]) -> tuple[list[dict], int, int]:
    """Return (stageable items, below_threshold count, already_staged count)."""
    items: list[dict] = []
    below = 0
    already = 0
    for path in sorted(LEARNINGS_DIR.glob("*.md")):
        if path.name in ("SCHEMA.md",) or path.name.startswith("_"):
            continue
        try:
            meta, body = _parse_frontmatter(
                path.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            continue
        conf = _confidence(meta)
        if conf < min_conf:
            below += 1
            continue
        slug = path.stem
        source_id = meta.get("id", slug)
        if slug in seen or source_id in seen or meta.get("name", slug) in seen:
            already += 1
            continue
        tags = _parse_list_field(meta.get("tags", ""))
        category = meta.get("category", "")
        title = _title_from_body(body, slug.replace("-", " "))
        items.append(
            {
                "slug": slug,
                "source_id": source_id,
                "confidence": conf,
                "tags": tags,
                "canon_map": _infer_canon_map(tags, category),
                "suggested_use": title,
                "body": body,
            }
        )
    return items, below, already


def run_feedback_loop(*, min_confidence: float = 0.8, dry_run: bool = False) -> dict:
    """Stage high-confidence learnings as pending candidates. Returns a summary dict."""
    if not LEARNINGS_DIR.is_dir():
        return {"status": "skipped", "reason": "learnings dir not found", "staged": 0}

    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    seen = _existing_candidate_sources()
    items, below, already = _discover_learnings(min_confidence, seen)

    staged = 0
    staged_names: list[str] = []
    for item in items:
        slug = (
            re.sub(r"[^a-zA-Z0-9]+", "-", item["slug"].lower()).strip("-")[:80]
            or "candidate"
        )
        dest = CANDIDATES_DIR / f"{slug}.md"
        if dest.exists():
            already += 1
            continue
        if not dry_run:
            dest.write_text(
                _build_candidate_text(
                    name=slug,
                    source_id=item["source_id"],
                    confidence=item["confidence"],
                    tags=item["tags"],
                    canon_map=item["canon_map"],
                    suggested_use=item["suggested_use"],
                    body=item["body"],
                ),
                encoding="utf-8",
            )
        staged += 1
        staged_names.append(slug)

    return {
        "status": "ok",
        "staged": staged,
        "staged_names": staged_names,
        "already_staged": already,
        "below_threshold": below,
        "min_confidence": min_confidence,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Surface high-confidence learnings as KOS candidates (Stage 8)"
    )
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit summary as JSON")
    args = parser.parse_args()

    summary = run_feedback_loop(
        min_confidence=args.min_confidence, dry_run=args.dry_run
    )

    if args.json:
        print(json.dumps(summary))
        return 0 if summary["status"] in ("ok", "skipped") else 1

    if summary["status"] == "skipped":
        print(f"feedback-loop: skipped ({summary['reason']})", file=sys.stderr)
        return 0

    verb = "would stage" if args.dry_run else "staged"
    print(
        f"feedback-loop: {verb} {summary['staged']} learning(s) as pending candidates "
        f"(>= {summary['min_confidence']} confidence; "
        f"{summary['already_staged']} already staged, "
        f"{summary['below_threshold']} below threshold)"
    )
    for name in summary["staged_names"]:
        print(f"  [{verb.split()[-1]}] {name}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
