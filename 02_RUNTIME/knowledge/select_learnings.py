"""Relevance-ranked learning selection for session-start injection.

Bead chromatic-harness-v2-yl2a: capture worked, but fresh sessions started
blind — prior learnings were inert until manually queried. This selects the
top-N most relevant learnings so session_start.py can surface them into a new
session's context (closing the flywheel's apply step).

Ranking = confidence weight + recency + term overlap (with the current branch /
task terms). Dependency-light: parses the simple `key: value` frontmatter block
directly. Pure + fail-open.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_CONFIDENCE_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}
_DEFAULT_DIR = Path(os.path.expanduser("~/.claude/.agents/learnings"))


def _parse_frontmatter(text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    block = text[3:end]
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if key == "tags":
            val = val.strip("[]")
            meta["tags"] = [t.strip() for t in val.split(",") if t.strip()]
        else:
            meta[key] = val
    return meta


def _title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def load_learnings(directory: Path | None = None) -> list[dict[str, Any]]:
    d = directory or _DEFAULT_DIR
    out: list[dict[str, Any]] = []
    if not d.is_dir():
        return out
    for path in sorted(d.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = _parse_frontmatter(text)
        out.append(
            {
                "path": str(path),
                "title": _title(text, path.stem),
                "date": meta.get("date", ""),
                "confidence": (meta.get("confidence") or "medium").lower(),
                "maturity": meta.get("maturity", ""),
                "tags": meta.get("tags", []),
            }
        )
    return out


def score(learning: dict[str, Any], terms: list[str]) -> float:
    s = _CONFIDENCE_WEIGHT.get(learning.get("confidence", "medium"), 2.0)
    # Recency: lexicographic date works for ISO YYYY-MM-DD; newer ranks higher.
    date = learning.get("date", "")
    if date:
        s += min(len(date), 10) * 0.0  # presence only; comparison handled in sort
    # Term overlap with tags + title.
    hay = (" ".join(learning.get("tags", [])) + " " + learning.get("title", "")).lower()
    s += sum(2.0 for t in terms if t and t.lower() in hay)
    return s


def select_top(
    directory: Path | None = None,
    n: int = 3,
    terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return the top-N learnings by (term-relevance + confidence), then recency."""
    terms = terms or []
    learnings = load_learnings(directory)
    learnings.sort(
        key=lambda lc: (score(lc, terms), lc.get("date", "")),
        reverse=True,
    )
    return learnings[:n]


def format_for_injection(learnings: list[dict[str, Any]]) -> str:
    if not learnings:
        return "(no prior learnings found)"
    lines = ["Top prior learnings (apply where relevant):"]
    for lc in learnings:
        tags = ", ".join(lc.get("tags", [])[:4])
        lines.append(
            f"  - {lc['title']} [{lc.get('confidence', '?')}, {lc.get('date', '?')}]"
            + (f" ({tags})" if tags else "")
        )
    return "\n".join(lines)
