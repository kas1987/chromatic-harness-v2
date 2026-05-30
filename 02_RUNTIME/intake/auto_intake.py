"""Drain intake queue into beads (bd create / claim)."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from activity.lanes import apply_lane_to_bead_fields, normalize_lane
from intake.bd_runner import resolve_bd_argv
from intake.queue import (
    IntakeEntry,
    default_queue_path,
    list_queued,
    record_status,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_SKIP_ID_PREFIXES = ("example-",)


def _normalize_title(title: str) -> str:
    # Ignore telemetry timestamp token so duplicate detection remains stable.
    cleaned = re.sub(r"\[\d{8}T\d{6}Z\]", "", title or "")
    return " ".join(cleaned.strip().lower().split())


def _epic_telemetry_fields(title: str, description: str) -> tuple[str, str, str, str]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if re.search(r"\[\d{8}T\d{6}Z\]", title or ""):
        title_out = title
    else:
        title_out = f"{(title or '').strip()} [{ts}]".strip()
    key = f"EPIC-AUTO-{ts}"
    desc = (description or "").strip()
    if "telemetry_key:" not in desc.lower():
        desc = f"{desc}\n\ntelemetry_key: {key}\ntimestamp_utc: {ts}".strip()
    return title_out, desc, key, ts


def _extract_rows(payload: str) -> list[dict]:
    text = (payload or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "issues", "data"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _existing_open_titles(
    *,
    cwd: Path,
    runner: Callable[[list[str], Path], subprocess.CompletedProcess[str]] | None = None,
) -> set[str]:
    """Read existing OPEN beads and return a normalized title index.

    Best effort only: if bd list fails, return empty set and continue processing.
    """
    titles: set[str] = set()
    proc = _run_bd(
        ["list", "--status", "open", "--limit", "0", "--json"], cwd=cwd, runner=runner
    )
    if proc.returncode != 0:
        return titles
    rows = _extract_rows(proc.stdout or "")
    for row in rows:
        raw = str(row.get("title") or row.get("name") or row.get("summary") or "")
        norm = _normalize_title(raw)
        if norm:
            titles.add(norm)
    return titles


@dataclass
class ProcessResult:
    entry_id: str
    kind: str
    status: str
    bead_id: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "status": self.status,
            "bead_id": self.bead_id,
            "message": self.message,
        }


@dataclass
class DrainReport:
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[ProcessResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "processed": self.processed,
            "failed": self.failed,
            "skipped": self.skipped,
            "results": [r.to_dict() for r in self.results],
        }


def _should_skip(entry: IntakeEntry) -> bool:
    if any(entry.id.startswith(p) for p in _SKIP_ID_PREFIXES):
        return True
    if entry.status != "queued":
        return True
    return False


def simple_decompose(goal: str) -> list[dict[str, str]]:
    """Split bullet goals into tasks; otherwise one atomic task (no LLM in P0)."""
    lines = [ln.strip() for ln in goal.splitlines() if ln.strip()]
    bullets = [ln for ln in lines if re.match(r"^[-*•]\s+|\d+[.)]\s+", ln)]
    if len(bullets) >= 2:
        tasks: list[dict[str, str]] = []
        for bullet in bullets:
            title = re.sub(r"^[-*•]\s+|\d+[.)]\s+", "", bullet).strip()[:200]
            if title:
                tasks.append({"title": title, "description": bullet})
        return tasks or [{"title": goal[:120], "description": goal}]
    return [{"title": (goal[:120] or "Intake goal"), "description": goal}]


def _run_bd(
    args: list[str],
    *,
    cwd: Path,
    runner: Callable[[list[str], Path], subprocess.CompletedProcess[str]] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [*resolve_bd_argv(), *args]
    if runner:
        return runner(cmd, cwd)
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )


def _parse_bead_id(output: str) -> str:
    m = re.search(r"chromatic-harness-v2-[a-z0-9]+", output)
    if m:
        return m.group(0)
    m = re.search(r"\b[a-z]{2}-[a-zA-Z0-9]{3,5}\b", output)
    return m.group(0) if m else ""


def _resolve_lane(entry: IntakeEntry) -> str:
    return normalize_lane(entry.lane or entry.context.get("lane"))


def _bd_create(
    title: str,
    *,
    description: str = "",
    priority: str = "P2",
    issue_type: str = "task",
    lane: str = "",
    cwd: Path,
    runner=None,
    dry_run: bool = False,
) -> tuple[bool, str, str]:
    if dry_run:
        return True, "dry-run-bead", "dry-run"
    if issue_type == "epic":
        title, description, _telemetry_key, _timestamp_utc = _epic_telemetry_fields(
            title, description
        )
    title, description = apply_lane_to_bead_fields(title, description, lane=lane)
    args = ["create", title, "--type", issue_type, "--priority", priority]
    if description:
        args.extend(["--description", description[:4000]])
    proc = _run_bd(args, cwd=cwd, runner=runner)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, "", out.strip()[:500]
    bead_id = _parse_bead_id(out)
    return bool(bead_id), bead_id, out.strip()[:200]


def _bd_claim(
    bead_id: str, *, cwd: Path, runner=None, dry_run: bool = False
) -> tuple[bool, str]:
    if dry_run:
        return True, "dry-run-claim"
    proc = _run_bd(["update", bead_id, "--claim"], cwd=cwd, runner=runner)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out.strip()[:300]


def process_entry(
    entry: IntakeEntry,
    *,
    repo_root: Path | None = None,
    queue_path: Path | None = None,
    runner=None,
    dry_run: bool = False,
    claim: bool = True,
    existing_open_titles: set[str] | None = None,
) -> ProcessResult:
    """Process one intake entry into beads."""
    repo = repo_root or REPO_ROOT
    qpath = queue_path or default_queue_path(repo)

    if _should_skip(entry):
        if not dry_run:
            record_status(
                entry, "skipped", path=qpath, repo_root=repo, error="skip rule"
            )
        return ProcessResult(entry.id, entry.kind, "skipped", message="skip rule")

    if not dry_run:
        record_status(entry, "processing", path=qpath, repo_root=repo)

    try:
        if entry.kind == "bead_dispatch":
            bead_id = entry.bead_id or entry.id
            if claim:
                ok, msg = _bd_claim(bead_id, cwd=repo, runner=runner, dry_run=dry_run)
                if not ok:
                    if not dry_run:
                        record_status(
                            entry, "failed", path=qpath, repo_root=repo, error=msg
                        )
                    return ProcessResult(
                        entry.id, entry.kind, "failed", bead_id=bead_id, message=msg
                    )
            if not dry_run:
                record_status(
                    entry, "processed", path=qpath, repo_root=repo, bead_id=bead_id
                )
            return ProcessResult(
                entry.id,
                entry.kind,
                "processed",
                bead_id=bead_id,
                message="dispatch claimed",
            )

        tasks = (
            simple_decompose(entry.goal or entry.title)
            if entry.kind == "goal"
            else [
                {"title": entry.title[:200], "description": entry.goal or entry.title}
            ]
        )

        if existing_open_titles is not None:
            for task in tasks:
                title_norm = _normalize_title(task["title"])
                if title_norm and title_norm in existing_open_titles:
                    message = f"prevented duplicate open-title: {task['title'][:120]}"
                    if not dry_run:
                        record_status(
                            entry, "skipped", path=qpath, repo_root=repo, error=message
                        )
                    return ProcessResult(
                        entry.id, entry.kind, "skipped", message=message
                    )

        entry_lane = _resolve_lane(entry)
        created: list[str] = []
        for task in tasks:
            title_norm = _normalize_title(task["title"])
            ok, bead_id, msg = _bd_create(
                task["title"],
                description=task.get("description", ""),
                priority=entry.priority,
                issue_type=entry.type,
                lane=entry_lane,
                cwd=repo,
                runner=runner,
                dry_run=dry_run,
            )
            if not ok:
                if not dry_run:
                    record_status(
                        entry, "failed", path=qpath, repo_root=repo, error=msg
                    )
                return ProcessResult(entry.id, entry.kind, "failed", message=msg)
            if claim and bead_id:
                _bd_claim(bead_id, cwd=repo, runner=runner, dry_run=dry_run)
            created.append(bead_id)
            if title_norm and existing_open_titles is not None:
                existing_open_titles.add(title_norm)

        primary = created[0] if created else ""
        if not dry_run:
            record_status(
                entry,
                "processed",
                path=qpath,
                repo_root=repo,
                bead_id=primary,
            )
        return ProcessResult(
            entry.id,
            entry.kind,
            "processed",
            bead_id=primary,
            message=f"created {len(created)} bead(s)",
        )
    except Exception as exc:
        if not dry_run:
            record_status(entry, "failed", path=qpath, repo_root=repo, error=str(exc))
        return ProcessResult(entry.id, entry.kind, "failed", message=str(exc))


def drain_queue(
    *,
    repo_root: Path | None = None,
    queue_path: Path | None = None,
    limit: int | None = None,
    runner=None,
    dry_run: bool = False,
    claim: bool = True,
) -> DrainReport:
    """Process all queued intake entries (newest deduped state per id)."""
    repo = repo_root or REPO_ROOT
    qpath = queue_path or default_queue_path(repo)
    report = DrainReport()
    queued = list_queued(path=qpath, repo_root=repo)
    existing_titles = _existing_open_titles(cwd=repo, runner=runner)
    if limit is not None:
        queued = queued[:limit]

    for entry in queued:
        result = process_entry(
            entry,
            repo_root=repo,
            queue_path=qpath,
            runner=runner,
            dry_run=dry_run,
            claim=claim,
            existing_open_titles=existing_titles,
        )
        report.results.append(result)
        if result.status == "processed":
            report.processed += 1
        elif result.status == "skipped":
            report.skipped += 1
        else:
            report.failed += 1
    return report
