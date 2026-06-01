#!/usr/bin/env python3
"""KOS Stage 4 — extract structured patterns, anti-patterns, and principles
from raw learnings in .agents/learnings/ and write them to .agents/patterns/.

Usage:
  python scripts/extract_patterns.py            # write new patterns
  python scripts/extract_patterns.py --dry-run  # print without writing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEARNINGS_DIR = REPO / ".agents" / "learnings"
PATTERNS_DIR = REPO / ".agents" / "patterns"

# Keyword sets for classification (checked against lowercased body + description)
ANTI_PATTERN_KEYWORDS = {
    "avoid",
    "don't",
    "never",
    "bad",
    "harmful",
    "wrong",
    "mistake",
}
PRINCIPLE_KEYWORDS = {"always", "rule:", "principle:", "invariant", "must"}


# ---------------------------------------------------------------------------
# Frontmatter parsing (stdlib only)
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) from a markdown file with YAML frontmatter.

    Only handles simple scalar and inline list values — no nested YAML.
    Returns ({}, text) if no frontmatter fence found.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4 :].strip()
    fm: dict = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        key, _, raw_val = line.partition(":")
        key = key.strip()
        raw_val = raw_val.strip()
        # Inline list: [a, b, c]
        if raw_val.startswith("[") and raw_val.endswith("]"):
            inner = raw_val[1:-1]
            fm[key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
        else:
            fm[key] = raw_val.strip("'\"")
    return fm, body


def _confidence_to_float(value: object) -> float:
    """Normalise confidence to 0.0–1.0 float (handles 'high'/'medium'/'low' strings)."""
    if isinstance(value, float):
        return value
    s = str(value).lower().strip()
    mapping = {"high": 0.9, "medium": 0.7, "low": 0.4, "very_high": 0.95}
    if s in mapping:
        return mapping[s]
    try:
        return float(s)
    except ValueError:
        return 0.5


def _classify(description: str, body: str) -> str:
    """Return 'anti-pattern', 'principle', or 'pattern'."""
    haystack = (description + " " + body).lower()
    if any(kw in haystack for kw in ANTI_PATTERN_KEYWORDS):
        return "anti-pattern"
    if any(kw in haystack for kw in PRINCIPLE_KEYWORDS):
        return "principle"
    return "pattern"


def _slugify(text: str) -> str:
    """Convert arbitrary text to a kebab-case slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _infer_name(fm: dict, stem: str) -> str:
    """Get a slug name from frontmatter or fall back to filename stem."""
    raw = fm.get("name") or fm.get("id") or stem
    # Strip common prefixes like "learning-2026-04-26-"
    raw = re.sub(r"^learning[-_]?\d{4}-\d{2}-\d{2}[-_]?", "", raw)
    return _slugify(raw) or _slugify(stem)


def _yaml_scalar(value: str) -> str:
    """Quote a YAML scalar when it contains characters that break frontmatter.

    A bare scalar like ``Research: Most-Used Skills`` is parsed as a mapping by
    standard YAML loaders. Double-quote (and escape) when the value contains a
    colon-space, leading indicator chars, or quotes so generated frontmatter
    round-trips through any YAML/frontmatter consumer, not just our tolerant
    custom parser.
    """
    text = str(value)
    needs_quote = (
        ": " in text
        or text.endswith(":")
        or text.startswith(
            (
                "#",
                "!",
                "&",
                "*",
                "?",
                "|",
                ">",
                "%",
                "@",
                "`",
                '"',
                "'",
                "[",
                "{",
                "-",
                " ",
            )
        )
        or text.endswith(" ")
        or any(c in text for c in ("\n", "\t"))
        or text == ""
    )
    if not needs_quote:
        return text
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _render_pattern(
    name: str,
    ptype: str,
    confidence: float,
    source_learnings: list[str],
    description: str,
    tags: list[str],
    body: str,
) -> str:
    tags_str = "[" + ", ".join(tags) + "]" if tags else "[]"
    sources_str = "[" + ", ".join(source_learnings) + "]" if source_learnings else "[]"
    return (
        f"---\n"
        f"name: {_yaml_scalar(name)}\n"
        f"type: {ptype}\n"
        f"confidence: {confidence:.2f}\n"
        f"source_learnings: {sources_str}\n"
        f"description: {_yaml_scalar(description)}\n"
        f"tags: {tags_str}\n"
        f"---\n\n"
        f"{body}\n"
    )


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------


def extract_patterns(dry_run: bool = False) -> dict[str, int]:
    """Extract patterns from learnings and write to .agents/patterns/.

    Returns counts: {"pattern": N, "anti-pattern": N, "principle": N, "skipped": N}
    """
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {
        "pattern": 0,
        "anti-pattern": 0,
        "principle": 0,
        "skipped": 0,
    }

    md_files = sorted(LEARNINGS_DIR.glob("*.md"))
    if not md_files:
        print(
            f"[extract_patterns] No .md files found in {LEARNINGS_DIR}", file=sys.stderr
        )
        return counts

    for md_path in md_files:
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"[WARN] Could not read {md_path.name}: {exc}", file=sys.stderr)
            continue

        fm, body = _parse_frontmatter(text)

        description = fm.get("description") or fm.get("summary") or ""
        if not description:
            # Try to extract the first H1/H2 heading as description
            for line in body.splitlines():
                line = line.strip()
                if line.startswith("#"):
                    description = line.lstrip("#").strip()
                    break
        description = description[:200]  # cap length

        ptype = _classify(description, body)
        name = _infer_name(fm, md_path.stem)
        confidence = _confidence_to_float(fm.get("confidence", 0.5))

        raw_tags = fm.get("tags", [])
        if isinstance(raw_tags, str):
            raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        tags = list(dict.fromkeys(raw_tags))  # deduplicate, preserve order

        source_slug = md_path.stem
        dest_name = f"{ptype.replace('-', '_')}-{name}.md"
        dest_path = PATTERNS_DIR / dest_name

        if dest_path.exists():
            counts["skipped"] += 1
            continue

        content = _render_pattern(
            name=name,
            ptype=ptype,
            confidence=confidence,
            source_learnings=[source_slug],
            description=description,
            tags=tags,
            body=body,
        )

        if dry_run:
            print(f"[DRY-RUN] Would write: {dest_name}")
            print(f"  type={ptype}, confidence={confidence:.2f}, tags={tags[:3]}")
        else:
            dest_path.write_text(content, encoding="utf-8")

        counts[ptype] += 1

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KOS Stage 4 — extract patterns from learnings"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print without writing files"
    )
    args = parser.parse_args(argv)

    counts = extract_patterns(dry_run=args.dry_run)

    mode = "DRY-RUN" if args.dry_run else "WRITTEN"
    print(
        f"\n[extract_patterns] {mode} summary:\n"
        f"  patterns:      {counts['pattern']}\n"
        f"  anti-patterns: {counts['anti-pattern']}\n"
        f"  principles:    {counts['principle']}\n"
        f"  skipped (already exist): {counts['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
