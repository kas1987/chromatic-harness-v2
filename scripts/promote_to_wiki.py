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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_WIKI = Path(r"C:\Users\kas41\chromatic-wiki")
LEARNINGS = REPO / ".agents" / "learnings"
AUTO_TURN_REPORTS = REPO / "07_LOGS_AND_AUDIT" / "auto_turn_thresholds"
CANDIDATES_DIR = REPO / ".agents" / "candidates"
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


def _approved_candidates() -> set[str] | None:
    """Return set of approved candidate names, or None if no candidates dir / it's empty.

    Returns None  → no staging guard in effect (backward compatible).
    Returns set() → candidates dir exists but is empty or has no approved items.
    Returns {name, ...} → approved names that may be promoted.
    """
    if not CANDIDATES_DIR.is_dir():
        return None
    # Collect all non-schema .md files
    candidate_files = [
        p
        for p in CANDIDATES_DIR.iterdir()
        if p.suffix == ".md"
        and p.name not in ("SCHEMA.md",)
        and not p.name.startswith("_")
    ]
    if not candidate_files:
        return None  # Dir exists but empty — treat as backward-compatible
    approved: set[str] = set()
    for path in candidate_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, _ = _parse_frontmatter(text)
        if meta.get("status", "").strip().lower() == "approved":
            name = meta.get("name", path.stem).strip()
            approved.add(name)
    return approved


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
            hashlib.sha256(existing.replace("\r\n", "\n").encode("utf-8")).hexdigest()
            == hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
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

    # Candidate staging guard: if .agents/candidates/ is non-empty, only promote
    # items that have an approved candidate record. Backward-compatible: if the
    # directory doesn't exist or is empty, behave as before.
    approved_names = _approved_candidates()
    if approved_names is not None:
        print(
            json.dumps(
                {
                    "info": "Candidate staging guard active",
                    "approved_count": len(approved_names),
                    "hint": (
                        "Edit .agents/candidates/<slug>.md and set status: approved "
                        "to allow promotion, or delete .agents/candidates/ to disable guard."
                    ),
                }
            )
        )

    candidates = _discover_candidates(args.min_confidence)

    # Apply candidate guard filter
    if approved_names is not None:
        guarded_out: list[dict] = []
        blocked: list[str] = []
        for item in candidates:
            if item["name"] in approved_names:
                guarded_out.append(item)
            else:
                blocked.append(item["name"])
        candidates = guarded_out
        if blocked:
            print(
                json.dumps(
                    {
                        "guard": "blocked",
                        "count": len(blocked),
                        "names": blocked[:20],
                        "hint": "Set status: approved in .agents/candidates/<slug>.md to promote",
                    }
                )
            )

    promoted: list[str] = []
    for item in candidates:
        src = REPO / item["path"]
        rel = _promote_one(src, wiki, execute=execute)
        if rel:
            promoted.append(rel)
            if execute:
                # Register the promoted candidate in the canon registry for traceability
                candidate_name = Path(item["path"]).stem
                try:
                    subprocess.run(
                        [
                            sys.executable,
                            str(REPO / "scripts" / "register_canon.py"),
                            "--add",
                            candidate_name,
                        ],
                        check=False,
                        capture_output=True,
                    )
                except Exception:
                    pass  # Registry update is best-effort; do not fail promotion
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
