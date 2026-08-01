#!/usr/bin/env python3
r"""
Intake bridge: Harness V2 → CAT BEAD conversion.

Reads new entries from the repo-relative intake queue (07_LOGS_AND_AUDIT/intake_queue.jsonl)
and converts them to CAT BEAD YAML in E:\chromatic-atomic-tower\beads\active\
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from uuid import uuid4


def read_intake_queue(path=None):
    """Read new intake entries since last bridge run.

    Defaults to the repo-relative intake queue (07_LOGS_AND_AUDIT/intake_queue.jsonl)
    and skips entries whose ids have already been bridged.
    """
    if not path:
        repo_root = Path(__file__).resolve().parents[1]
        path = repo_root / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"

    entries = []
    if not path.exists():
        return entries

    processed = _load_processed_ids(path)

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[cat-intake-bridge] WARNING skipping malformed queue row", file=sys.stderr)
                    continue
                entry_id = entry.get("id")
                if not entry_id:
                    continue
                if entry_id in processed:
                    continue
                processed.add(entry_id)
                entries.append(entry)
    except Exception as e:
        print(f"[cat-intake-bridge] ERROR reading intake queue: {e}", file=sys.stderr)
        return []

    _save_processed_ids(path, processed)
    return entries


def _processed_ids_path(queue_path: Path) -> Path:
    return queue_path.parent / (queue_path.name + ".bridged-ids.json")


def _load_processed_ids(queue_path: Path) -> set[str]:
    pid_path = _processed_ids_path(queue_path)
    if not pid_path.exists():
        return set()
    try:
        data = json.loads(pid_path.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()


def _save_processed_ids(queue_path: Path, processed: set[str]) -> None:
    pid_path = _processed_ids_path(queue_path)
    pid_path.write_text(json.dumps(sorted(processed), indent=2), encoding="utf-8")


def entry_to_bead(entry):
    """Convert IntakeEntry to CAT BEAD YAML structure."""
    bead_id = f"BEAD-CAT-{entry.get('id', str(uuid4())[:8]).upper()}"

    bead = {
        "id": bead_id,
        "status": "pending",  # CAT will transition from pending → active → validating → done
        "source": "harness-bridge",  # Loop-guard: identifies entries from harness
        "title": entry.get("title", "Harness intake entry"),
        "description": f"Converted from harness intake: {entry.get('kind', 'unknown')}",
        "priority": entry.get("priority", 5),
        "tier": entry.get("tier", "T1"),
        "type": entry.get("type", "task"),
        "queued_at": entry.get("queued_at", datetime.utcnow().isoformat()),
        "owner": "harness-bridge",
        "tags": ["harness-intake", entry.get("kind", "")],
    }
    return bead


def write_bead_yaml(bead, cat_root=None):
    """Write BEAD to CAT beads/active/ directory."""
    if not cat_root:
        cat_root = Path("E:/chromatic-atomic-tower")

    beads_dir = cat_root / "beads" / "active"
    beads_dir.mkdir(parents=True, exist_ok=True)

    bead_file = beads_dir / f"{bead['id']}.yaml"

    # Convert to YAML format (simple key: value dump)
    yaml_content = f"""id: {bead["id"]}
status: {bead["status"]}
source: {bead["source"]}
title: {bead["title"]}
priority: {bead["priority"]}
tier: {bead["tier"]}
type: {bead["type"]}
queued_at: {bead["queued_at"]}
owner: {bead["owner"]}
tags: {bead["tags"]}
"""

    try:
        with open(bead_file, "w") as f:
            f.write(yaml_content)
        return str(bead_file), True
    except Exception as e:
        print(f"[cat-intake-bridge] ERROR writing {bead_file}: {e}", file=sys.stderr)
        return str(bead_file), False


def validate_bead(bead_id, cat_root=None):
    """Run CAT validator on the new BEAD."""
    if not cat_root:
        cat_root = Path("E:/chromatic-atomic-tower")

    try:
        result = subprocess.run(
            ["python", str(cat_root / "scripts" / "cat_validate.py"), "--bead", bead_id],
            capture_output=True,
            text=True,
            cwd=str(cat_root),
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        print(f"[cat-intake-bridge] ERROR validating {bead_id}: {e}", file=sys.stderr)
        return False, str(e)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bridge Harness intake to CAT BEADs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be written without writing")
    args = parser.parse_args()

    entries = read_intake_queue()
    if not entries:
        print("[cat-intake-bridge] No new intake entries", file=sys.stderr)
        return 0

    beads_written = 0
    for entry in entries:
        bead = entry_to_bead(entry)
        bead_file, success = write_bead_yaml(bead) if not args.dry_run else (f"(dry-run) {bead['id']}.yaml", True)

        if success:
            beads_written += 1
            print(f"[cat-intake-bridge] BEAD written: {bead['id']}", file=sys.stderr)

            if not args.dry_run:
                valid, msg = validate_bead(bead["id"])
                if not valid:
                    print(
                        f"[cat-intake-bridge] WARNING: BEAD validation failed for {bead['id']}: {msg}", file=sys.stderr
                    )
        else:
            print(f"[cat-intake-bridge] FAILED to write BEAD: {bead_file}", file=sys.stderr)

    print(f"[cat-intake-bridge] Bridged {beads_written}/{len(entries)} entries", file=sys.stderr)
    return 0 if beads_written > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
