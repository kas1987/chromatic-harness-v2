#!/usr/bin/env python3
"""Mirror harness docs into Chromatic Wiki per Wiki manifest.yaml.

Usage:
  python scripts/sync_wiki_mirror.py --dry-run
  python scripts/sync_wiki_mirror.py --execute

Reads: CHROMATIC_WIKI_ROOT/manifest.yaml (or default path)
Copies governance, antipatterns, playbooks with MIRRORED header.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_WIKI = Path(r"C:\Users\kas41\chromatic-wiki")
MIRROR_HEADER = (
    "<!-- MIRRORED from chromatic-harness-v2 — edit in harness or re-run sync_wiki_mirror.py --execute -->\n"
    "<!-- synced_at: {ts} source: {src} -->\n\n"
)


def _wiki_root() -> Path:
    raw = os.environ.get("CHROMATIC_WIKI_ROOT", "")
    return Path(raw).resolve() if raw else DEFAULT_WIKI


def _load_manifest(wiki: Path) -> dict:
    path = wiki / "manifest.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"missing manifest: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _iter_sources(harness: Path, spec: str) -> list[Path]:
    src = harness / spec.replace("/", os.sep)
    if not src.exists():
        return []
    if src.is_file():
        return [src]
    return sorted(p for p in src.rglob("*") if p.is_file() and not p.name.startswith("."))


def _normalize_text(text: str) -> str:
    """Normalize text for stable comparison: LF line endings, no trailing whitespace."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines())


def _strip_mirror_header(text: str) -> str:
    """Remove the MIRRORED header from existing wiki files for content comparison."""
    lines = text.splitlines()
    # Skip consecutive header comment lines at the top
    idx = 0
    while idx < len(lines) and lines[idx].strip().startswith("<!--"):
        idx += 1
    # Skip blank lines after header
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    return "\n".join(lines[idx:])


def _mirror_file(src: Path, dest: Path, *, execute: bool) -> dict:
    text = src.read_text(encoding="utf-8", errors="replace")
    ts = datetime.now(timezone.utc).isoformat()
    if dest.suffix in (".md", ".markdown"):
        body = MIRROR_HEADER.format(ts=ts, src=str(src)) + text
    else:
        body = text
    changed = True
    if dest.is_file():
        old_text = dest.read_text(encoding="utf-8", errors="replace")
        # Compare normalized content, stripping volatile header from existing file
        old_content = _normalize_text(_strip_mirror_header(old_text))
        new_content = _normalize_text(text)
        changed = old_content != new_content
    if execute and changed:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
    return {"src": str(src), "dest": str(dest), "changed": changed}


def _mirror_tree(harness: Path, wiki: Path, source: str, target: str, *, execute: bool) -> list[dict]:
    results: list[dict] = []
    src_base = harness / source.replace("/", os.sep)
    tgt_base = wiki / target.replace("/", os.sep)

    for src in _iter_sources(harness, source):
        if src_base.is_file():
            dest = tgt_base
        else:
            rel = src.relative_to(src_base)
            dest = tgt_base / rel
        results.append(_mirror_file(src, dest, execute=execute))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror harness docs to Wiki")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    execute = args.execute
    wiki = _wiki_root()

    try:
        manifest = _load_manifest(wiki)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    mirrors = manifest.get("harness_docs_mirror") or []
    all_results: list[dict] = []
    for entry in mirrors:
        source = entry.get("source", "")
        target = entry.get("target", "")
        if not source or not target:
            continue
        all_results.extend(_mirror_tree(REPO, wiki, source, target, execute=execute))

    changed = sum(1 for r in all_results if r.get("changed"))
    print(
        json.dumps(
            {
                "wiki_root": str(wiki),
                "execute": execute,
                "files": len(all_results),
                "changed": changed,
                "results": all_results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
