#!/usr/bin/env python3
"""
Chromatic Harness v2: Context Trim Audit

Read-only audit for files that may bloat or contaminate pre-session context.
Uses Python standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_SCAN_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "AGENT_OPERATIONS.md",
    "GOVERNANCE_AND_ROUTING_ARCHITECTURE.md",
    "DEPLOYMENT_GUIDE.md",
]

RISKY_DIRS = [
    "07_LOGS_AND_AUDIT",
    "traces",
    "archive",
    "12_HANDOFFS/sessions",
    ".claude/projects",
]

DUPLICATE_PATTERNS = [
    "Beads Issue Tracker",
    "Session Completion",
    "Session Compact",
    "PRE_SESSION_AND_TOOLS",
    "CURSOR_CONTEXT_HYGIENE",
    "AGENT_ANTIPATTERNS",
    "Work is NOT complete until",
]

# Link-only mentions in thin wrappers are intentional pointers, not duplicate blocks.
LINK_ONLY_ALLOWED = {
    "AGENT_ANTIPATTERNS": {"CLAUDE.md", "AGENTS.md"},
}


@dataclass
class FileFinding:
    path: str
    kind: str
    severity: str
    message: str
    size_bytes: int | None = None
    line_count: int | None = None


@dataclass
class AuditReport:
    generated_at: str
    repo_root: str
    risk_level: str
    findings: list[FileFinding]
    summary: dict[str, int]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def audit_large_files(root: Path, paths: Iterable[str]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    for rel in paths:
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        size = path.stat().st_size
        lines = count_lines(path)
        if size > 80_000 or lines > 900:
            severity = "high" if size > 150_000 or lines > 1600 else "medium"
            findings.append(FileFinding(
                path=rel,
                kind="large_instruction_file",
                severity=severity,
                message="File may be too large for default pre-session loading; convert to wrapper or load only by relevance.",
                size_bytes=size,
                line_count=lines,
            ))
        elif size > 35_000 or lines > 400:
            findings.append(FileFinding(
                path=rel,
                kind="watch_instruction_file",
                severity="low",
                message="File is moderately large; avoid loading with duplicate wrappers.",
                size_bytes=size,
                line_count=lines,
            ))
    return findings


def audit_duplicate_patterns(root: Path, paths: Iterable[str]) -> list[FileFinding]:
    occurrences: dict[str, list[str]] = {pat: [] for pat in DUPLICATE_PATTERNS}
    for rel in paths:
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        text = read_text(path)
        for pattern in DUPLICATE_PATTERNS:
            if pattern in text:
                occurrences[pattern].append(rel)

    findings: list[FileFinding] = []
    for pattern, files in occurrences.items():
        if len(files) < 2:
            continue
        allowed = LINK_ONLY_ALLOWED.get(pattern, set())
        substantive = [f for f in files if f not in allowed]
        if len(substantive) < 2:
            continue
        findings.append(FileFinding(
            path=", ".join(substantive),
            kind="duplicate_governance_pattern",
            severity="medium" if len(substantive) == 2 else "high",
            message=f"Pattern appears in multiple files: {pattern!r}. Prefer one canonical source plus wrappers.",
        ))
    return findings


def audit_risky_dirs(root: Path) -> list[FileFinding]:
    findings: list[FileFinding] = []
    for rel in RISKY_DIRS:
        path = root / rel
        if not path.exists():
            continue
        file_count = 0
        total_size = 0
        jsonl_count = 0
        for dirpath, _, filenames in os.walk(path):
            for name in filenames:
                file_count += 1
                p = Path(dirpath) / name
                try:
                    total_size += p.stat().st_size
                except OSError:
                    pass
                if name.endswith(".jsonl"):
                    jsonl_count += 1
        if file_count:
            # Known ops dirs are informational (listed in RISKY_DIRS); not duplicate-governance.
            severity = "low"
            findings.append(FileFinding(
                path=rel,
                kind="risky_auto_load_directory",
                severity=severity,
                message=f"Directory contains {file_count} files ({jsonl_count} jsonl). Should never be auto-loaded; use targeted retrieval only.",
                size_bytes=total_size,
            ))
    return findings


def determine_risk(findings: list[FileFinding]) -> str:
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    dup = sum(1 for f in findings if f.kind == "duplicate_governance_pattern")
    if high >= 3 or (high >= 1 and medium >= 3):
        return "red"
    if high >= 1 or medium >= 3 or dup >= 1:
        return "orange"
    if medium >= 1:
        return "yellow"
    return "green"


def build_report(root: Path) -> AuditReport:
    scan_files = DEFAULT_SCAN_FILES
    findings: list[FileFinding] = []
    findings.extend(audit_large_files(root, scan_files))
    findings.extend(audit_duplicate_patterns(root, scan_files))
    findings.extend(audit_risky_dirs(root))
    risk = determine_risk(findings)
    summary = {
        "total_findings": len(findings),
        "high": sum(1 for f in findings if f.severity == "high"),
        "medium": sum(1 for f in findings if f.severity == "medium"),
        "low": sum(1 for f in findings if f.severity == "low"),
    }
    return AuditReport(
        generated_at=utc_now(),
        repo_root=str(root),
        risk_level=risk,
        findings=findings,
        summary=summary,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit context bloat risks for Chromatic Harness v2.")
    parser.add_argument("--root", default=".", help="Repository root. Default: current directory.")
    parser.add_argument("--out", default=".agents/context/context_trim_audit.json", help="Output JSON path relative to root.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = build_report(root)
    data = asdict(report)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(f"Context trim audit written: {out_path}")
    print(f"Risk level: {report.risk_level}")
    print(json.dumps(report.summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
