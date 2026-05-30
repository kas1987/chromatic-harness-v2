#!/usr/bin/env python3
"""Detect duplicated or conflicting instruction patterns across agent instruction files."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

INSTRUCTION_FILES = [
    "AGENT_OPERATIONS.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".cursor/rules/context-hygiene.mdc",
    ".cursor/rules/git-autonomy.mdc",
    ".cursor/rules/harness-audit.mdc",
]

# Duplication across many files is OK for pointers; flag forbidden blocks in thin wrappers.
FORBIDDEN_IN_WRAPPERS = [
    "Work is NOT complete until",
    "MANDATORY WORKFLOW:",
    "Session Completion",
]

PHRASES = {
    "bd_required": ["bd prime", "bd ready", "Use `bd`", "uses **bd"],
    "no_todo": ["Do not use TodoWrite", "do NOT use TodoWrite", "markdown TODO"],
    "session_compact": ["SESSION_COMPACT", "Session Compact", "handoffs/latest.json"],
    "context_boot": ["new_session_bootstrap.py", "BOOT_CONTEXT.md"],
    "git_autonomy": ["GIT_AUTONOMY_POLICY", "workflow_git.py plan"],
}

CONFLICT_PATTERNS = [
    ("todo_allowed", re.compile(r"use\s+(TodoWrite|TaskCreate)", re.I)),
    ("memory_md_allowed", re.compile(r"use\s+MEMORY\.md", re.I)),
]

NEGATION_BEFORE = re.compile(r"(do not|don't|never|not)\s+$", re.I)


def _affirmative_conflict(text: str, pattern: re.Pattern[str]) -> bool:
    """Match only when 'use X' is not negated (avoids 'Do not use TodoWrite' false positives)."""
    for m in pattern.finditer(text):
        before = text[max(0, m.start() - 24) : m.start()]
        if NEGATION_BEFORE.search(before):
            continue
        return True
    return False


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def audit(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    phrase_hits: dict[str, list[str]] = {key: [] for key in PHRASES}

    for rel in INSTRUCTION_FILES:
        path = root / rel
        if not path.exists():
            continue
        text = read_text(path)
        for key, needles in PHRASES.items():
            if any(n in text for n in needles):
                phrase_hits[key].append(rel)
        for code, pattern in CONFLICT_PATTERNS:
            if _affirmative_conflict(text, pattern):
                findings.append({
                    "severity": "P1",
                    "code": code,
                    "file": rel,
                    "message": f"Potential conflicting instruction found in {rel}",
                })
        if rel in ("AGENTS.md", "CLAUDE.md"):
            for block in FORBIDDEN_IN_WRAPPERS:
                if block in text:
                    findings.append({
                        "severity": "P1",
                        "code": "forbidden_wrapper_block",
                        "file": rel,
                        "message": f"Thin wrapper must not contain {block!r}; use AGENT_OPERATIONS.md",
                    })

    drift_exclude = {".cursor/rules/context-hygiene.mdc", ".cursor/rules/harness-audit.mdc"}

    for key, files in phrase_hits.items():
        files = [f for f in files if f not in drift_exclude]
        threshold = 6 if key == "bd_required" else 4
        if len(files) >= threshold:
            findings.append({
                "severity": "P2",
                "code": "duplicated_governance_phrase",
                "topic": key,
                "files": files,
                "message": f"Governance topic appears duplicated across {len(files)} files: {key}",
            })

    return {
        "audit": "instruction_drift",
        "phrase_hits": phrase_hits,
        "findings": findings,
        "status": "fail" if any(f["severity"] in {"P0", "P1"} for f in findings) else "warn" if findings else "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = audit(Path(args.root).resolve())
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
