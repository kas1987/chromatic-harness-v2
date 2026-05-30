#!/usr/bin/env python3
"""Promote high-confidence harness learnings to the Chromatic Wiki repo.

Usage:
  python scripts/promote_to_wiki.py --dry-run
  python scripts/promote_to_wiki.py --execute
  python scripts/promote_to_wiki.py --execute --min-confidence 0.8

Requires CHROMATIC_WIKI_ROOT or default C:\\Users\\kas41\\-Chromatic_Wiki
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_WIKI = Path(r"C:\Users\kas41\-Chromatic_Wiki")
LEARNINGS = REPO / ".agents" / "learnings"
WIKI_LEARNINGS = "02_LEARNINGS"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _wiki_root() -> Path:
    raw = os.environ.get("CHROMATIC_WIKI_ROOT", "")
    return Path(raw).resolve() if raw else DEFAULT_WIKI


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = text[m.end() :]
    return meta, body


def _confidence(meta: dict[str, str]) -> float:
    try:
        return float(meta.get("confidence", "0"))
    except ValueError:
        return 0.0


def _slug(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return base[:80] or "learning"


def _discover_candidates(min_conf: float) -> list[dict]:
    if not LEARNINGS.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(LEARNINGS.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, _ = _parse_frontmatter(text)
        conf = _confidence(meta)
        if conf < min_conf:
            continue
        out.append(
            {
                "path": str(path.relative_to(REPO)),
                "name": meta.get("name", path.stem),
                "confidence": conf,
                "sha": hashlib.sha256(text.encode()).hexdigest()[:12],
            }
        )
    return out


def _promote_one(src: Path, wiki_root: Path, *, execute: bool) -> str | None:
    text = src.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_frontmatter(text)
    slug = _slug(meta.get("name", src.stem))
    dest = wiki_root / WIKI_LEARNINGS / f"{slug}.md"
    if dest.is_file():
        existing = dest.read_text(encoding="utf-8", errors="replace")
        if hashlib.sha256(existing.encode()).hexdigest() == hashlib.sha256(text.encode()).hexdigest():
            return None

    header = meta.copy()
    header.setdefault("promoted_from", str(src.relative_to(REPO)))
    header.setdefault("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    header.setdefault("status", "candidate")
    lines = ["---"]
    for k, v in header.items():
        lines.append(f"{k}: {v}")
    lines.append("---\n")
    out_text = "\n".join(lines) + "\n" + body.lstrip()

    if execute:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out_text, encoding="utf-8")
    return str(dest.relative_to(wiki_root))


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote learnings to Chromatic Wiki")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true", help="Copy files to Wiki")
    parser.add_argument("--min-confidence", type=float, default=0.75)
    args = parser.parse_args()
    execute = args.execute
    wiki = _wiki_root()

    if not wiki.is_dir():
        print(
            json.dumps(
                {
                    "error": f"Wiki root not found: {wiki}",
                    "hint": "git clone https://github.com/kas1987/-Chromatic_Wiki.git",
                },
                indent=2,
            )
        )
        return 1

    candidates = _discover_candidates(args.min_confidence)
    promoted: list[str] = []
    for item in candidates:
        src = REPO / item["path"]
        rel = _promote_one(src, wiki, execute=execute)
        if rel:
            promoted.append(rel)
        item["wiki_dest"] = rel or "(unchanged)"

    report = {
        "wiki_root": str(wiki),
        "execute": execute,
        "min_confidence": args.min_confidence,
        "candidates": len(candidates),
        "promoted": len(promoted),
        "items": candidates,
        "paths_written": promoted,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
