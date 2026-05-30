#!/usr/bin/env python3
"""Generate review-only bead remediation command sets from hygiene plan artifacts.

This script never mutates tracker state. It only emits commands and a markdown plan
for manual review and operator execution.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO / ".agents" / "audits" / "bead_hygiene"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_reason(text: str) -> str:
    cleaned = (text or "").replace("\n", " ").replace("\r", " ").strip()
    cleaned = " ".join(cleaned.split())
    return cleaned[:160] if cleaned else "duplicate consolidation"


def _cmd_close(bead_id: str, canonical_id: str, title: str) -> str:
    reason = _safe_reason(f"duplicate of {canonical_id}: {title}")
    return f'bd close {bead_id} --reason "{reason}"'


def _cmd_comment(bead_id: str, canonical_id: str) -> str:
    note = _safe_reason(f"duplicate-triage: merged into {canonical_id}")
    return f'bd update {bead_id} --notes "{note}"'


def _cmd_malformed_review(bead_id: str) -> str:
    note = _safe_reason("id-hygiene-review: non-canonical bead id; migrate to canonical id")
    return f'bd update {bead_id} --notes "{note}"'


def build_command_plan(remediation_plan: list[dict[str, Any]]) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    commands: list[dict[str, str]] = []

    for group in remediation_plan:
        title = str(group.get("title") or "")
        plan_type = str(group.get("plan_type") or "")
        canonical_id = str(group.get("canonical_id") or "")
        actions = group.get("actions") or []
        if not isinstance(actions, list):
            continue

        for action in actions:
            if not isinstance(action, dict):
                continue
            bead_id = str(action.get("id") or "")
            action_name = str(action.get("action") or "")
            if not bead_id:
                continue

            if action_name == "manual_review_duplicate" and canonical_id:
                commands.append(
                    {
                        "action_type": "duplicate_close",
                        "plan_type": plan_type or "duplicate_group",
                        "title": title,
                        "canonical_id": canonical_id,
                        "target_id": bead_id,
                        "close_cmd": _cmd_close(bead_id, canonical_id, title),
                        "comment_cmd": _cmd_comment(bead_id, canonical_id),
                        "review_note": "Run only after verifying duplicate relationship manually.",
                    }
                )
            elif action_name == "manual_review_malformed_id":
                commands.append(
                    {
                        "action_type": "malformed_review",
                        "plan_type": plan_type or "malformed_id",
                        "title": title,
                        "canonical_id": canonical_id,
                        "target_id": bead_id,
                        "comment_cmd": _cmd_malformed_review(bead_id),
                        "review_note": "Annotate for migration planning; do not auto-close without canonical replacement.",
                    }
                )

    return {
        "audit": "bead_hygiene_remediation_commands",
        "generated_at": generated_at,
        "mode": "review_only",
        "command_count": len(commands),
        "commands": commands,
    }


def write_artifacts(plan: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)

    latest_json = out_dir / "latest_remediation_commands.json"
    latest_md = out_dir / "latest_remediation_commands.md"
    latest_ps1 = out_dir / "latest_remediation_commands.ps1"

    latest_json.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    md_lines = [
        "# Bead Hygiene Remediation Commands (Review Only)",
        "",
        f"Generated: {plan.get('generated_at','')}",
        f"Total commands: {plan.get('command_count', 0)}",
        "",
        "## Safety",
        "",
        "- Review each candidate manually before running any command.",
        "- Commands are generated from duplicate-title heuristics and may include false positives.",
        "",
        "## Candidates",
        "",
    ]

    if not plan.get("commands"):
        md_lines.append("- none")
    else:
        for item in plan["commands"]:
            action_type = item.get("action_type", "")
            md_lines.append(
                f"- action={action_type} target={item.get('target_id','')} canonical={item.get('canonical_id','')} title={item.get('title','')}"
            )
            if item.get("comment_cmd"):
                md_lines.append(f"  - {item.get('comment_cmd','')}")
            if item.get("close_cmd"):
                md_lines.append(f"  - {item.get('close_cmd','')}")

    latest_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    ps1_lines = [
        "# Review-only candidate commands generated by bead_hygiene_remediation_commands.py",
        "# Remove leading '#' to execute after manual verification.",
        "",
    ]
    for item in plan.get("commands", []):
        if item.get("comment_cmd"):
            ps1_lines.append(f"# {item.get('comment_cmd','')}")
        if item.get("close_cmd"):
            ps1_lines.append(f"# {item.get('close_cmd','')}")
    if not plan.get("commands"):
        ps1_lines.append("# no remediation commands generated")

    latest_ps1.write_text("\n".join(ps1_lines) + "\n", encoding="utf-8")

    return {
        "latest_json": str(latest_json.relative_to(REPO)).replace("\\", "/"),
        "latest_md": str(latest_md.relative_to(REPO)).replace("\\", "/"),
        "latest_ps1": str(latest_ps1.relative_to(REPO)).replace("\\", "/"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate review-only remediation commands")
    parser.add_argument(
        "--plan",
        default=str(AUDIT_DIR / "latest_remediation_plan.json"),
        help="Path to remediation plan JSON generated by bead_hygiene_audit.py",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write remediation command artifacts into .agents/audits/bead_hygiene",
    )
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = (REPO / plan_path).resolve()

    if not plan_path.is_file():
        raise SystemExit(f"missing remediation plan: {plan_path}")

    raw_plan = _load_json(plan_path)
    if not isinstance(raw_plan, list):
        raise SystemExit("remediation plan must be a JSON array")

    output = build_command_plan(raw_plan)
    if args.write:
        output["artifacts"] = write_artifacts(output, AUDIT_DIR)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
