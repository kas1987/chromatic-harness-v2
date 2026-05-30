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

import json
import os
import re
from pathlib import Path
from typing import Any

_CONFIDENCE_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}
_DEFAULT_DIR = Path(os.path.expanduser("~/.claude/.agents/learnings"))
_MIN_EVIDENCE = 2  # applied_success events needed before evidence overrides frontmatter


def load_usage_evidence(usage_log: Path) -> dict[str, dict[str, int]]:
    """Read learning_usage.jsonl and return per-learning success/failure counts.

    Returns {learning_stem: {"success": n, "failure": n}}.
    Fail-open: returns {} on any read/parse error.
    """
    counts: dict[str, dict[str, int]] = {}
    try:
        for line in usage_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            etype = str(row.get("event_type", ""))
            name = str(row.get("learning_name", ""))
            if not name:
                continue
            stem = Path(name).stem
            if stem not in counts:
                counts[stem] = {"success": 0, "failure": 0}
            if etype == "applied_success":
                counts[stem]["success"] += 1
            elif etype == "applied_failure":
                counts[stem]["failure"] += 1
    except Exception:
        pass
    return counts


def _evidence_multiplier(stem: str, evidence: dict[str, dict[str, int]]) -> float:
    """Return a score multiplier based on evidence (1.0 = no adjustment)."""
    rec = evidence.get(stem)
    if not rec:
        return 1.0
    s, f = rec.get("success", 0), rec.get("failure", 0)
    total = s + f
    if total == 0 or s < _MIN_EVIDENCE:
        return 1.0
    ratio = s / total
    if ratio >= 0.8:
        # 4.0 > max frontmatter weight (high=3.0) so proven learnings always float above unproven
        return 4.0
    if ratio < 0.5:
        return 0.5  # more failures than successes → deprioritise
    return 1.0


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


def score(
    learning: dict[str, Any],
    terms: list[str],
    evidence: dict[str, dict[str, int]] | None = None,
) -> float:
    base = _CONFIDENCE_WEIGHT.get(learning.get("confidence", "medium"), 2.0)
    stem = Path(learning.get("path", "")).stem
    multiplier = _evidence_multiplier(stem, evidence or {})
    s = base * multiplier
    # Term overlap with tags + title.
    hay = (" ".join(learning.get("tags", [])) + " " + learning.get("title", "")).lower()
    s += sum(2.0 for t in terms if t and t.lower() in hay)
    return s


def select_top(
    directory: Path | None = None,
    n: int = 3,
    terms: list[str] | None = None,
    usage_log: Path | None = None,
) -> list[dict[str, Any]]:
    """Return the top-N learnings by (term-relevance + evidence-adjusted confidence), then recency."""
    terms = terms or []
    evidence = (
        load_usage_evidence(usage_log) if usage_log and usage_log.exists() else {}
    )
    learnings = load_learnings(directory)
    learnings.sort(
        key=lambda lc: (score(lc, terms, evidence), lc.get("date", "")),
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
