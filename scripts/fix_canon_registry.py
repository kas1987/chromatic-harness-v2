#!/usr/bin/env python3
"""Deduplicate canon_registry.yaml: for entries sharing the same base slug
(i.e., same id minus the -vN suffix), keep only the first occurrence (lowest
version). Also strips excess blank lines (>1 consecutive blank line -> 1).

Usage:
    python scripts/fix_canon_registry.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CANON = Path(__file__).resolve().parents[1] / "00_SOURCE_OF_TRUTH" / "canon_registry.yaml"


def base_slug(entry_id: str) -> str:
    """Return the slug without trailing -vN version suffix."""
    return re.sub(r"-v\d+$", "", entry_id)


def parse_yaml_raw(text: str) -> tuple[str, list[str]]:
    """Split file into header (before first '  - id:') and raw entry blocks."""
    lines = text.splitlines(keepends=True)
    header_lines: list[str] = []
    entry_blocks: list[str] = []
    current_block: list[str] = []
    in_entries = False

    for line in lines:
        if not in_entries:
            if re.match(r"^  - id:", line):
                in_entries = True
                current_block = [line]
            else:
                header_lines.append(line)
        else:
            if re.match(r"^  - id:", line):
                # Start of a new entry
                entry_blocks.append("".join(current_block))
                current_block = [line]
            else:
                current_block.append(line)

    if current_block:
        entry_blocks.append("".join(current_block))

    return "".join(header_lines), entry_blocks


def extract_id(block: str) -> str | None:
    m = re.search(r"^  - id:\s*(.+)$", block, re.MULTILINE)
    return m.group(1).strip() if m else None


def deduplicate(blocks: list[str]) -> list[str]:
    """Keep only the first occurrence of each base slug."""
    seen_bases: dict[str, int] = {}  # base_slug -> first index
    kept: list[str] = []
    skipped = 0

    for block in blocks:
        eid = extract_id(block)
        if eid is None:
            kept.append(block)
            continue
        slug = base_slug(eid)
        if slug in seen_bases:
            skipped += 1
        else:
            seen_bases[slug] = len(kept)
            kept.append(block)

    print(f"  Kept {len(kept)} entries, removed {skipped} duplicate-version entries", file=sys.stderr)
    return kept


def collapse_blanks(text: str) -> str:
    """Replace runs of >1 blank line with a single blank line."""
    return re.sub(r"\n{3,}", "\n\n", text)


def main() -> None:
    raw = CANON.read_text(encoding="utf-8")
    header, blocks = parse_yaml_raw(raw)
    print(f"  Found {len(blocks)} entries in {CANON.name}", file=sys.stderr)

    deduped = deduplicate(blocks)

    # Reconstruct: header + entries
    body = "".join(deduped)
    combined = header + body

    # Collapse excess blank lines
    combined = collapse_blanks(combined)

    # Ensure single trailing newline
    combined = combined.rstrip("\n") + "\n"

    CANON.write_text(combined, encoding="utf-8")
    print(f"  Written {len(combined.splitlines())} lines to {CANON}", file=sys.stderr)


if __name__ == "__main__":
    main()
