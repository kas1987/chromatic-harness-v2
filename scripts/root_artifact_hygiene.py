#!/usr/bin/env python3
"""Root artifact hygiene for Chromatic Harness v2.

This script keeps repository root tidy by applying a narrow, explicit policy:
- Move known tracked temp artifacts into 07_LOGS_AND_AUDIT/root_artifacts
- Delete known disposable ignored artifacts from root
- Remove malformed one-off root clutter names

Default mode is dry-run. Use --write to apply changes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = REPO_ROOT / "07_LOGS_AND_AUDIT" / "root_artifacts"

MOVE_PREFIXES = (".tmp_",)
MOVE_EXACT = {
    "server_stderr.txt",
    "server_stdout.txt",
    "__bh_autoloop_ec.txt",
    "__bh_autoloop_out.txt",
}

DELETE_EXACT = {
    ".coverage",
    "check_files.log",
    "prepush2.log",
    "prepush_sim.log",
    "__bh_run.log",
    "0)",
    "0))",
    ",m.get(wiki_dest)) for m in matches[",
}

DELETE_DIR_EXACT = {
    ".tmp_ingest",
    ".tmp_pre_session_pack",
}


@dataclass
class Action:
    action: str
    path: str
    destination: str | None
    existed: bool
    applied: bool
    reason: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode, output


def _is_tracked(path: Path) -> bool:
    rel_path = str(path.relative_to(REPO_ROOT))
    code, _ = _run_git("ls-files", "--error-unmatch", "--", rel_path)
    return code == 0


def _is_ignored(path: Path) -> bool:
    code, _ = _run_git("check-ignore", str(path.relative_to(REPO_ROOT)))
    return code == 0


def _target_for_move(src: Path) -> Path:
    """Create a collision-safe target path in ARTIFACT_DIR."""
    dest = ARTIFACT_DIR / src.name
    if not dest.exists():
        return dest

    stem = dest.stem
    suffix = dest.suffix
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return ARTIFACT_DIR / f"{stem}.{stamp}{suffix}"


def _iter_root_entries() -> list[Path]:
    return sorted(REPO_ROOT.iterdir(), key=lambda p: p.name.lower())


def _should_move(name: str) -> bool:
    return name.startswith(MOVE_PREFIXES) or name in MOVE_EXACT


def _should_delete_file(name: str) -> bool:
    return name in DELETE_EXACT


def _should_delete_dir(name: str) -> bool:
    return name in DELETE_DIR_EXACT


def plan_actions() -> list[Action]:
    actions: list[Action] = []

    for entry in _iter_root_entries():
        name = entry.name

        if entry.is_file() and _should_move(name):
            tracked = _is_tracked(entry)
            ignored = _is_ignored(entry)
            # Preserve tracked or non-ignored artifacts by moving them.
            if tracked or not ignored:
                dest = _target_for_move(entry)
                actions.append(
                    Action(
                        action="move",
                        path=str(entry.relative_to(REPO_ROOT)),
                        destination=str(dest.relative_to(REPO_ROOT)),
                        existed=True,
                        applied=False,
                        reason="tracked-or-preserved-artifact",
                    )
                )
                continue

        if entry.is_file() and _should_delete_file(name):
            actions.append(
                Action(
                    action="delete",
                    path=str(entry.relative_to(REPO_ROOT)),
                    destination=None,
                    existed=True,
                    applied=False,
                    reason="disposable-root-artifact",
                )
            )
            continue

        if entry.is_dir() and _should_delete_dir(name):
            actions.append(
                Action(
                    action="delete_dir",
                    path=str(entry.relative_to(REPO_ROOT)),
                    destination=None,
                    existed=True,
                    applied=False,
                    reason="disposable-root-artifact-dir",
                )
            )
            continue

    return actions


def apply_actions(actions: list[Action], write: bool) -> None:
    if write:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    for action in actions:
        src = REPO_ROOT / action.path
        if not src.exists():
            action.existed = False
            continue

        if action.action == "move":
            assert action.destination is not None
            if write:
                dest = REPO_ROOT / action.destination
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                action.applied = True
            continue

        if action.action in {"delete", "delete_dir"}:
            if write:
                if src.is_dir():
                    shutil.rmtree(src)
                else:
                    src.unlink()
                action.applied = True


def write_report(
    report_path: Path, actions: list[Action], write: bool
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "mode": "write" if write else "dry-run",
        "counts": {
            "planned": len(actions),
            "applied": sum(1 for a in actions if a.applied),
            "missing": sum(1 for a in actions if not a.existed),
            "moves": sum(1 for a in actions if a.action == "move"),
            "deletes": sum(
                1 for a in actions if a.action in {"delete", "delete_dir"}
            ),
        },
        "actions": [asdict(a) for a in actions],
    }
    report_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Root artifact hygiene")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply changes. Without this flag, script runs in dry-run mode.",
    )
    parser.add_argument(
        "--report",
        default=(
            "07_LOGS_AND_AUDIT/root_artifacts/"
            "latest_root_artifact_hygiene.json"
        ),
        help="JSON report path relative to repo root.",
    )
    args = parser.parse_args()

    actions = plan_actions()
    apply_actions(actions, write=args.write)

    report_path = (REPO_ROOT / args.report).resolve()
    write_report(report_path, actions, write=args.write)

    mode = "WRITE" if args.write else "DRY_RUN"
    print(f"ROOT_ARTIFACT_HYGIENE: mode={mode}")
    print(f"ROOT_ARTIFACT_HYGIENE: planned={len(actions)}")
    applied = sum(1 for a in actions if a.applied)
    print(f"ROOT_ARTIFACT_HYGIENE: applied={applied}")
    print(f"ROOT_ARTIFACT_HYGIENE: report={report_path}")

    for action in actions:
        if action.action == "move":
            print(
                "ROOT_ARTIFACT_HYGIENE_ITEM: "
                "move "
                f"{action.path} -> {action.destination} "
                f"reason={action.reason}"
            )
        else:
            print(
                "ROOT_ARTIFACT_HYGIENE_ITEM: "
                f"{action.action} {action.path} reason={action.reason}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
