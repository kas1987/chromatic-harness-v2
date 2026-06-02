#!/usr/bin/env python3
"""Convert drift findings into beads tasks.

Sources:
- .agents/evolve/drift-findings-latest.jsonl
- .agents/evolve/drift-findings-*.jsonl
- .agents/evolve/drift-report/*.md

Default mode is dry-run; use --write to create beads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

DEFAULT_STATE = ".agents/evolve/drift-triage-state.json"


@dataclass
class DriftItem:
    source: str
    category: str
    file: str
    line: int | None
    detail: str


@dataclass
class TriageAction:
    fingerprint: str
    title: str
    description: str
    created: bool
    bead_id: str


def _run(cmd: list[str], *, cwd: Path, timeout: int = 60) -> tuple[int, str]:
    r = run_safe(cmd, cwd=cwd, timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out.strip()


def _run_bd(args: list[str], *, cwd: Path) -> tuple[int, str]:
    code, out = _run(["bd", *args], cwd=cwd)
    if code == 0:
        return code, out
    lowered = out.lower()
    if "not found" in lowered or "winerror 2" in lowered or "no such file" in lowered:
        return _run(["cmd", "/c", "bd", *args], cwd=cwd)
    return code, out


def _extract_issue_id(text: str) -> str:
    match = re.search(r"Created issue:\s*([^\s]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _fingerprint(item: DriftItem) -> str:
    raw = "|".join(
        [
            item.source,
            item.category,
            item.file,
            str(item.line or ""),
            item.detail,
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_jsonl(path: Path) -> list[DriftItem]:
    items: list[DriftItem] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        detail = _safe_text(row.get("detail") or row.get("message") or row.get("summary"))
        if not detail:
            continue
        file_path = _safe_text(row.get("file") or row.get("path") or "unknown")
        line_value = row.get("line")
        line_no = int(line_value) if isinstance(line_value, int) else None
        category = _safe_text(row.get("category") or row.get("code") or "drift")
        items.append(
            DriftItem(
                source=str(path.relative_to(REPO)).replace("\\", "/"),
                category=category,
                file=file_path,
                line=line_no,
                detail=detail,
            )
        )
    return items


def _read_markdown(path: Path) -> list[DriftItem]:
    items: list[DriftItem] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        detail = line[2:].strip()
        if not detail:
            continue
        items.append(
            DriftItem(
                source=str(path.relative_to(REPO)).replace("\\", "/"),
                category="drift_report",
                file="unknown",
                line=None,
                detail=detail,
            )
        )
    return items


def load_drift_items(root: Path) -> list[DriftItem]:
    evolve = root / ".agents" / "evolve"
    if not evolve.exists():
        return []

    jsonl_paths = sorted(evolve.glob("drift-findings-*.jsonl"))
    latest = evolve / "drift-findings-latest.jsonl"
    if latest.is_file():
        jsonl_paths.insert(0, latest)

    report_dir = evolve / "drift-report"
    md_paths = sorted(report_dir.glob("*.md")) if report_dir.is_dir() else []

    items: list[DriftItem] = []
    seen: set[str] = set()

    for path in jsonl_paths:
        for item in _read_jsonl(path):
            fp = _fingerprint(item)
            if fp in seen:
                continue
            seen.add(fp)
            items.append(item)

    for path in md_paths:
        for item in _read_markdown(path):
            fp = _fingerprint(item)
            if fp in seen:
                continue
            seen.add(fp)
            items.append(item)

    return items


def _priority_for(item: DriftItem) -> str:
    text = f"{item.category} {item.detail}".lower()
    if "critical" in text or "security" in text:
        return "1"
    if "broken" in text or "error" in text or "missing" in text:
        return "2"
    return "3"


def _title_for(item: DriftItem) -> str:
    base = f"Drift triage: {item.category}"
    if item.file and item.file != "unknown":
        base += f" ({item.file})"
    return base[:120]


def _description_for(item: DriftItem) -> str:
    location = item.file
    if item.line:
        location += f":{item.line}"
    return "\n".join(
        [
            "Auto-triaged from drift findings.",
            f"Source: {item.source}",
            f"Category: {item.category}",
            f"Location: {location}",
            f"Detail: {item.detail}",
        ]
    )


def _load_state(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    entries = payload.get("created_fingerprints") if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return set()
    return {str(x) for x in entries if str(x).strip()}


def _save_state(path: Path, fingerprints: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_fingerprints": sorted(fingerprints),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def triage(
    *,
    root: Path,
    write: bool,
    max_items: int,
    state_path: Path,
) -> dict[str, Any]:
    items = load_drift_items(root)
    known = _load_state(state_path)

    actions: list[TriageAction] = []
    created_fingerprints: set[str] = set(known)

    pending: list[tuple[str, DriftItem]] = []
    for item in items:
        fp = _fingerprint(item)
        if fp in created_fingerprints:
            continue
        pending.append((fp, item))

    for fp, item in pending[: max(0, max_items)]:
        title = _title_for(item)
        desc = _description_for(item)
        action = TriageAction(
            fingerprint=fp,
            title=title,
            description=desc,
            created=False,
            bead_id="",
        )

        if write:
            args = [
                "create",
                "--title",
                title,
                "--description",
                desc,
                "--type",
                "task",
                "--priority",
                _priority_for(item),
            ]
            code, out = _run_bd(args, cwd=root)
            if code == 0:
                action.created = True
                action.bead_id = _extract_issue_id(out)
                created_fingerprints.add(fp)

        actions.append(action)

    if write:
        _save_state(state_path, created_fingerprints)

    return {
        "audit": "drift_triage_to_beads",
        "write": write,
        "input_count": len(items),
        "pending_count": len(pending),
        "planned_count": len(actions),
        "created_count": sum(1 for a in actions if a.created),
        "state_path": str(state_path.relative_to(root)).replace("\\", "/"),
        "actions": [asdict(a) for a in actions],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--state", default=DEFAULT_STATE)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    state_path = (root / args.state).resolve()
    result = triage(
        root=root,
        write=args.write,
        max_items=args.max_items,
        state_path=state_path,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
