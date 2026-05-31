#!/usr/bin/env python3
"""Stage high-confidence patterns as candidates for Wiki promotion.

KOS Stage 5: Candidate Staging Registry

Usage:
  python scripts/stage_candidates.py --dry-run
  python scripts/stage_candidates.py
  python scripts/stage_candidates.py --min-confidence 0.8
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PATTERNS_DIR = REPO / ".agents" / "patterns"
CANDIDATES_DIR = REPO / ".agents" / "candidates"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_CATEGORICAL_CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}

# Tag-to-canon_map mapping rules (first match wins)
_TAG_CANON_MAP: list[tuple[set[str], str]] = [
    ({"routing", "ollama", "ol-layer", "subagents", "model-routing"}, "routing"),
    ({"security", "secrets", "auth", "permissions"}, "security"),
    ({"knowledge", "wiki", "learnings", "kos", "canon"}, "knowledge"),
    ({"operations", "hooks", "session", "governance", "audit", "ci"}, "operations"),
]

# Type-to-canon_map fallbacks when no tags match
_TYPE_CANON_MAP: dict[str, str] = {
    "anti-pattern": "operations",
    "pattern": "general",
    "principle": "knowledge",
}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter, returning (meta_dict, body)."""
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


def _parse_list_field(raw: str) -> list[str]:
    """Parse a YAML inline list like '[a, b, c]' or bare comma-separated."""
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


def _infer_canon_map(tags: list[str], source_type: str) -> str:
    tag_set = {t.lower() for t in tags}
    for rule_tags, canon in _TAG_CANON_MAP:
        if tag_set & rule_tags:
            return canon
    return _TYPE_CANON_MAP.get(source_type, "general")


def _build_candidate_text(
    meta: dict,
    source_name: str,
    source_type: str,
    confidence: float,
    tags: list[str],
    body: str,
) -> str:
    """Build the full candidate .md file text."""
    name = meta.get("name", source_name)
    source_ids_raw = meta.get("source_learnings", "")
    source_ids = _parse_list_field(source_ids_raw) if source_ids_raw else [source_name]
    suggested_use = meta.get("description", "").strip() or f"Apply {name} guidance"
    # Strip "Learning: " prefix that nightly extracts often add
    if suggested_use.lower().startswith("learning:"):
        suggested_use = suggested_use[9:].strip()
    canon_map = _infer_canon_map(tags, source_type)

    source_ids_yaml = "[" + ", ".join(source_ids) + "]"
    tags_yaml = "[" + ", ".join(tags) + "]"

    frontmatter = (
        f"---\n"
        f"name: {name}\n"
        f"source_ids: {source_ids_yaml}\n"
        f"source_type: {source_type}\n"
        f"confidence: {confidence:.2f}\n"
        f"suggested_use: {suggested_use}\n"
        f"canon_map: {canon_map}\n"
        f"status: pending\n"
        f"tags: {tags_yaml}\n"
        f"---\n"
    )

    # Build a clean body summary
    candidate_body = (
        f"\n## Summary\n\n{suggested_use}\n\n## Evidence\n\n{body.strip()}\n"
    )
    return frontmatter + candidate_body


def _discover_patterns(min_conf: float) -> list[dict]:
    """Scan .agents/patterns/ and return items meeting confidence threshold."""
    items = []
    for path in sorted(PATTERNS_DIR.rglob("*.md")):
        if path.name in ("SCHEMA.md",) or path.name.startswith("_"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        conf = _confidence(meta)
        if conf < min_conf:
            continue
        source_type = meta.get("type", "pattern").strip()
        tags_raw = meta.get("tags", "")
        tags = _parse_list_field(tags_raw) if tags_raw else []
        items.append(
            {
                "path": path,
                "name": meta.get("name", path.stem),
                "source_type": source_type,
                "confidence": conf,
                "tags": tags,
                "meta": meta,
                "body": body,
            }
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage high-confidence patterns as KOS candidates"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold (default: 0.7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be staged without writing files",
    )
    args = parser.parse_args()

    if not PATTERNS_DIR.is_dir():
        print(f"ERROR: patterns directory not found: {PATTERNS_DIR}", file=sys.stderr)
        return 1

    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    patterns = _discover_patterns(
        args.min_conf if hasattr(args, "min_conf") else args.min_confidence
    )

    staged = 0
    skipped_existing = 0
    below_threshold_total = 0

    # Count below-threshold for the summary (scan all, not filtered)
    all_patterns = list(PATTERNS_DIR.rglob("*.md"))
    valid_pattern_count = sum(
        1
        for p in all_patterns
        if p.name not in ("SCHEMA.md",) and not p.name.startswith("_")
    )
    below_threshold_total = valid_pattern_count - len(patterns)

    print(
        f"Scanning {PATTERNS_DIR.relative_to(REPO)} — "
        f"{len(patterns)} items >= {args.min_confidence} confidence "
        f"({below_threshold_total} below threshold)"
    )
    print()

    for item in patterns:
        name = item["name"]
        # Candidate filename: sanitize name to kebab slug
        slug = (
            re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")[:80] or "candidate"
        )
        dest = CANDIDATES_DIR / f"{slug}.md"

        if dest.exists():
            skipped_existing += 1
            if args.dry_run:
                print(f"  [skip]  {dest.name}  (already exists)")
            continue

        candidate_text = _build_candidate_text(
            meta=item["meta"],
            source_name=name,
            source_type=item["source_type"],
            confidence=item["confidence"],
            tags=item["tags"],
            body=item["body"],
        )

        if args.dry_run:
            print(
                f"  [stage] {dest.name}  (confidence={item['confidence']:.2f}, "
                f"type={item['source_type']}, canon_map="
                f"{_infer_canon_map(item['tags'], item['source_type'])})"
            )
        else:
            dest.write_text(candidate_text, encoding="utf-8")
            staged += 1
            print(f"  [wrote] {dest.name}")

    print()
    if args.dry_run:
        print(
            f"DRY RUN — {len(patterns) - skipped_existing} would be staged, "
            f"{skipped_existing} skipped (already exist), "
            f"{below_threshold_total} below threshold"
        )
    else:
        print(
            f"DONE — {staged} candidates staged, "
            f"{skipped_existing} skipped (already exist), "
            f"{below_threshold_total} below threshold"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
