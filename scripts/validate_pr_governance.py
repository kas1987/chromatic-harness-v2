#!/usr/bin/env python3
"""Validate stacked PR governance metadata and banned artifact changes."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

STACKED_PR_PREFIX = "pr/"
REQUIRED_SECTIONS = (
    "Stack",
    "Summary",
    "Validation",
    "Files Intentionally Excluded",
    "Risk",
    "Governance Overrides",
)
REQUIRED_STACK_FIELDS = (
    "Stack position",
    "Base branch",
    "Merge after",
    "Tracking",
)
DEFAULT_MAX_CHANGED_FILES = 25
DEFAULT_MAX_INSERTIONS = 800
DEFAULT_MAX_DELETIONS = 400
BLOCKED_GENERATED_PREFIXES = (
    ".agents/",
    ".beads/",
    "07_LOGS_AND_AUDIT/",
)
BLOCKED_GENERATED_FILES = {
    "12_HANDOFFS/PRE_SESSION_INVENTORY.md",
    "config/pre_session/inventory.snapshot.json",
    "docs/PRE_SESSION_AND_TOOLS.md",
    "docs/workflows/WORKFLOW_RUN_LOG.jsonl",
}
PLACEHOLDER_VALUES = {
    "",
    "tbd",
    "todo",
    "n/a",
    "fill me",
    "<fill me>",
    "<required>",
}


def _sanitize_argv(argv: list[str]) -> list[str]:
    return [arg for arg in argv if arg != "."]


def _parse_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line.strip())
        if match:
            current = match.group(1).strip().lower()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _find_field(section: str, field_name: str) -> str:
    pattern = re.compile(rf"^-\s*{re.escape(field_name)}\s*:\s*(.+)$", re.IGNORECASE)
    for line in section.splitlines():
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    return ""


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _has_meaningful_list_content(section: str) -> bool:
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        value = stripped.lstrip("-").strip()
        if _normalized(value) not in PLACEHOLDER_VALUES:
            return True
    return False


def _is_placeholder(value: str) -> bool:
    return _normalized(value) in PLACEHOLDER_VALUES


def _is_generated_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized in BLOCKED_GENERATED_FILES:
        return True
    return any(normalized.startswith(prefix) for prefix in BLOCKED_GENERATED_PREFIXES)


def validate_pr(
    *,
    title: str,
    body: str,
    head_ref: str,
    base_ref: str,
    changed_files: list[str],
    changed_files_count: int | None = None,
    insertions: int | None = None,
    deletions: int | None = None,
    max_changed_files: int = DEFAULT_MAX_CHANGED_FILES,
    max_insertions: int = DEFAULT_MAX_INSERTIONS,
    max_deletions: int = DEFAULT_MAX_DELETIONS,
) -> list[str]:
    if not head_ref.startswith(STACKED_PR_PREFIX):
        return []

    errors: list[str] = []
    sections = _parse_sections(body)

    for section_name in REQUIRED_SECTIONS:
        if section_name.lower() not in sections:
            errors.append(f"Missing required PR section: {section_name}")

    if errors:
        return errors

    stack_section = sections["stack"]
    for field_name in REQUIRED_STACK_FIELDS:
        value = _find_field(stack_section, field_name)
        if not value or _is_placeholder(value):
            errors.append(f"Stack section missing field: {field_name}")

    declared_base = _find_field(stack_section, "Base branch")
    if declared_base and declared_base != base_ref:
        errors.append(
            f"Stack base branch {declared_base!r} does not match actual base ref {base_ref!r}"
        )

    summary_section = sections["summary"]
    if not _has_meaningful_list_content(summary_section):
        errors.append("Summary section must contain at least one non-placeholder bullet")

    validation_section = sections["validation"]
    if not _has_meaningful_list_content(validation_section):
        errors.append(
            "Validation section must contain at least one concrete command or result bullet"
        )

    excluded_section = sections["files intentionally excluded"]
    if not _has_meaningful_list_content(excluded_section):
        errors.append(
            "Files Intentionally Excluded section must list excluded paths or 'none'"
        )

    risk_section = sections["risk"]
    risk_level = _find_field(risk_section, "Risk level")
    if risk_level.lower() not in {"low", "medium", "high"}:
        errors.append("Risk section must declare '- Risk level: low|medium|high'")

    overrides_section = sections["governance overrides"]
    artifact_override = _find_field(overrides_section, "Artifact override")
    if not artifact_override:
        errors.append(
            "Governance Overrides section must declare '- Artifact override: none|approved'"
        )
    elif artifact_override.lower() not in {"none", "approved"}:
        errors.append("Artifact override must be either 'none' or 'approved'")

    size_override = _find_field(overrides_section, "Size override")
    if not size_override:
        errors.append(
            "Governance Overrides section must declare '- Size override: none|approved'"
        )
    elif size_override.lower() not in {"none", "approved"}:
        errors.append("Size override must be either 'none' or 'approved'")

    blocked_changed = [path for path in changed_files if _is_generated_path(path)]
    if blocked_changed and artifact_override.lower() != "approved":
        joined = ", ".join(blocked_changed[:5])
        errors.append(
            "Generated/runtime artifact paths changed without approved override: " + joined
        )

    effective_changed_files = (
        changed_files_count if changed_files_count is not None else len(changed_files)
    )
    effective_insertions = 0 if insertions is None else insertions
    effective_deletions = 0 if deletions is None else deletions
    size_violations: list[str] = []
    if effective_changed_files > max_changed_files:
        size_violations.append(
            f"files={effective_changed_files}>{max_changed_files}"
        )
    if effective_insertions > max_insertions:
        size_violations.append(
            f"insertions={effective_insertions}>{max_insertions}"
        )
    if effective_deletions > max_deletions:
        size_violations.append(f"deletions={effective_deletions}>{max_deletions}")
    if size_violations and size_override.lower() != "approved":
        errors.append(
            "PR size thresholds exceeded without approved size override: "
            + ", ".join(size_violations)
        )

    if not title.strip():
        errors.append("PR title must not be empty")

    return errors


def _read_event(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _pr_context_from_event(event: dict[str, object]) -> tuple[str, str, str, str]:
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        return "", "", "", ""
    title = str(pr.get("title") or "")
    body = str(pr.get("body") or "")
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    head_ref = str((head or {}).get("ref") or "")
    base_ref = str((base or {}).get("ref") or "")
    return title, body, head_ref, base_ref


def _git_changed_files(repo: Path, event: dict[str, object]) -> list[str]:
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        return []
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    base_sha = str((base or {}).get("sha") or "")
    head_sha = str((head or {}).get("sha") or "")
    if not base_sha or not head_sha:
        return []
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _git_diff_stats(repo: Path, event: dict[str, object]) -> tuple[int, int, int]:
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        return 0, 0, 0
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    base_sha = str((base or {}).get("sha") or "")
    head_sha = str((head or {}).get("sha") or "")
    if not base_sha or not head_sha:
        return 0, 0, 0
    proc = subprocess.run(
        ["git", "diff", "--numstat", f"{base_sha}...{head_sha}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return 0, 0, 0
    files = 0
    insertions = 0
    deletions = 0
    for line in proc.stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        files += 1
        add_raw, del_raw = parts[0], parts[1]
        if add_raw.isdigit():
            insertions += int(add_raw)
        if del_raw.isdigit():
            deletions += int(del_raw)
    return files, insertions, deletions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate stacked PR governance metadata")
    parser.add_argument("--repo", default=str(REPO))
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH", ""))
    parser.add_argument("--title", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--head-ref", default=os.environ.get("GITHUB_HEAD_REF", ""))
    parser.add_argument("--base-ref", default=os.environ.get("GITHUB_BASE_REF", ""))
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--changed-files-count", type=int, default=None)
    parser.add_argument("--insertions", type=int, default=None)
    parser.add_argument("--deletions", type=int, default=None)
    parser.add_argument(
        "--max-changed-files",
        type=int,
        default=int(os.environ.get("CHROMATIC_PR_MAX_CHANGED_FILES", str(DEFAULT_MAX_CHANGED_FILES))),
    )
    parser.add_argument(
        "--max-insertions",
        type=int,
        default=int(os.environ.get("CHROMATIC_PR_MAX_INSERTIONS", str(DEFAULT_MAX_INSERTIONS))),
    )
    parser.add_argument(
        "--max-deletions",
        type=int,
        default=int(os.environ.get("CHROMATIC_PR_MAX_DELETIONS", str(DEFAULT_MAX_DELETIONS))),
    )
    args = parser.parse_args(_sanitize_argv(argv or sys.argv[1:]))

    event = _read_event(Path(args.event_path)) if args.event_path else {}
    event_title, event_body, event_head_ref, event_base_ref = _pr_context_from_event(event)

    title = args.title or event_title
    body = args.body or event_body
    head_ref = args.head_ref or event_head_ref
    base_ref = args.base_ref or event_base_ref

    if not head_ref:
        print("PR governance check skipped: no pull request context")
        return 0

    changed_files = list(args.changed_file) or _git_changed_files(Path(args.repo), event)
    files_count = args.changed_files_count
    insertions = args.insertions
    deletions = args.deletions
    if files_count is None or insertions is None or deletions is None:
        auto_files_count, auto_insertions, auto_deletions = _git_diff_stats(
            Path(args.repo), event
        )
        if files_count is None:
            files_count = auto_files_count
        if insertions is None:
            insertions = auto_insertions
        if deletions is None:
            deletions = auto_deletions
    errors = validate_pr(
        title=title,
        body=body,
        head_ref=head_ref,
        base_ref=base_ref,
        changed_files=changed_files,
        changed_files_count=files_count,
        insertions=insertions,
        deletions=deletions,
        max_changed_files=args.max_changed_files,
        max_insertions=args.max_insertions,
        max_deletions=args.max_deletions,
    )
    if errors:
        print("PR GOVERNANCE FAILED", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("PR governance OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())