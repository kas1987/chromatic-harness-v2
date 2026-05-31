#!/usr/bin/env python3
"""Promote high-confidence harness learnings to the Chromatic Wiki repo.

Usage:
  python scripts/promote_to_wiki.py --dry-run
  python scripts/promote_to_wiki.py --execute
  python scripts/promote_to_wiki.py --execute --min-confidence 0.8

Requires CHROMATIC_WIKI_ROOT or default C:\\Users\\kas41\\chromatic-wiki
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
DEFAULT_WIKI = Path(r"C:\Users\kas41\chromatic-wiki")
LEARNINGS = REPO / ".agents" / "learnings"
AUTO_TURN_REPORTS = REPO / "07_LOGS_AND_AUDIT" / "auto_turn_thresholds"
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


_CATEGORICAL_CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}


def _confidence(meta: dict[str, str]) -> float:
    raw = meta.get("confidence", "0")
    if raw is None:
        return 0.0
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


def _slug(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return base[:80] or "learning"


def _discover_candidates(min_conf: float) -> list[dict]:
    out: list[dict] = []
    # Learnings plus the auto-turn threshold calibration reports (also promotable).
    for base in (LEARNINGS, AUTO_TURN_REPORTS):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
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
        if (
            hashlib.sha256(existing.encode()).hexdigest()
            == hashlib.sha256(text.encode()).hexdigest()
        ):
            return None

    header = meta.copy()
    header.setdefault("promoted_from", src.relative_to(REPO).as_posix())
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
                    "hint": "git clone https://github.com/kas1987/chromatic-wiki.git",
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
