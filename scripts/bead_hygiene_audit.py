#!/usr/bin/env python3
"""Audit bead hygiene to detect and prevent tracker pollution.

Reactive control: detect duplicate titles and malformed IDs across live bead data.
Produces machine-readable artifacts for governance loops.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".agents" / "audits" / "bead_hygiene"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    if cmd and cmd[0] == "bd":
        for name in ("bd.cmd", "bd.exe", "bd"):
            path = shutil.which(name)
            if path:
                cmd = [path, *cmd[1:]]
                break
    return subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


def _load_rows() -> list[dict[str, Any]]:
    proc = _run(["bd", "list", "--limit", "0", "--json"])
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "bd list failed").strip())
    text = (proc.stdout or proc.stderr or "").strip()
    data = json.loads(text)
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("items", "results", "issues", "data"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
    return []


def _pick(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = row.get(key)
        if val not in (None, ""):
            return str(val)
    return ""


def _norm_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def _id_malformed(issue_id: str) -> bool:
    # Canonical IDs look like "prefix-abc" or "prefix-abc.N" for hierarchical children.
    # bd generates dot-notation child IDs automatically (e.g. prefix-ar7.5); these are valid.
    if "." in issue_id:
        # Allow hierarchical child pattern: base-id.digits
        if re.match(r"^[a-z0-9][a-z0-9-]*-[a-z0-9]{2,}\.\d+$", issue_id.lower()):
            return False
        return True
    return not bool(re.match(r"^[a-z0-9][a-z0-9-]*-[a-z0-9]{2,}$", issue_id.lower()))


def _status_rank(status: str) -> int:
    order = {
        "OPEN": 0,
        "READY": 1,
        "IN_PROGRESS": 2,
        "BLOCKED": 3,
        "DEFERRED": 4,
        "DONE": 5,
        "CLOSED": 5,
    }
    return order.get((status or "").upper(), 9)


def _build_remediation_plan(
    duplicate_groups: list[dict[str, Any]], malformed_ids: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for group in duplicate_groups:
        rows = [r for r in group.get("items", []) if isinstance(r, dict)]
        if len(rows) <= 1:
            continue

        ranked = sorted(
            rows,
            key=lambda r: (
                _status_rank(r.get("status", "")),
                -len(r.get("id", "")),
            ),
        )
        canonical = ranked[0]
        others = ranked[1:]
        active_others = [
            r for r in others if r.get("status") in {"OPEN", "READY", "IN_PROGRESS"}
        ]

        actions = [
            {
                "action": "keep_canonical",
                "id": canonical.get("id", ""),
                "status": canonical.get("status", ""),
                "title": canonical.get("title", ""),
            }
        ]
        for item in others:
            actions.append(
                {
                    "action": "manual_review_duplicate",
                    "id": item.get("id", ""),
                    "status": item.get("status", ""),
                    "title": item.get("title", ""),
                    "note": f"consider closing/merging into {canonical.get('id', '')}",
                }
            )

        plan.append(
            {
                "plan_type": "duplicate_group",
                "title": group.get("title", ""),
                "canonical_id": canonical.get("id", ""),
                "duplicate_count": len(others),
                "active_duplicate_count": len(active_others),
                "actions": actions,
            }
        )

    for item in malformed_ids:
        issue_id = str(item.get("id") or "")
        if not issue_id:
            continue
        plan.append(
            {
                "plan_type": "malformed_id",
                "title": str(item.get("title") or ""),
                "canonical_id": "",
                "duplicate_count": 0,
                "active_duplicate_count": 0,
                "actions": [
                    {
                        "action": "manual_review_malformed_id",
                        "id": issue_id,
                        "status": str(item.get("status") or ""),
                        "title": str(item.get("title") or ""),
                        "note": "verify intent, then migrate to canonical bead id and close source",
                    }
                ],
            }
        )

    plan.sort(
        key=lambda p: (
            1 if p.get("plan_type") == "malformed_id" else 0,
            -int(p.get("active_duplicate_count", 0) or 0),
        )
    )
    return plan


def build_report() -> dict[str, Any]:
    rows = _load_rows()
    now = datetime.now(timezone.utc).isoformat()

    status_counts: Counter[str] = Counter()
    title_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    malformed_ids: list[dict[str, Any]] = []

    for row in rows:
        issue_id = _pick(row, "id", "issue_id", "key", "ticket_id")
        title = _pick(row, "title", "name", "summary", "subject")
        status = _pick(row, "status", "state", "workflow_status").upper() or "UNKNOWN"

        status_counts[status] += 1
        key = _norm_title(title)
        if key:
            title_groups[key].append(row)
        if issue_id and _id_malformed(issue_id):
            malformed_ids.append({"id": issue_id, "title": title, "status": status})

    duplicate_groups = []
    for title_key, group in title_groups.items():
        if len(group) <= 1:
            continue
        per_status = Counter(
            _pick(r, "status", "state", "workflow_status").upper() or "UNKNOWN"
            for r in group
        )
        items = []
        for row in group:
            items.append(
                {
                    "id": _pick(row, "id", "issue_id", "key", "ticket_id"),
                    "title": _pick(row, "title", "name", "summary", "subject"),
                    "status": _pick(row, "status", "state", "workflow_status").upper()
                    or "UNKNOWN",
                }
            )
        duplicate_groups.append(
            {
                "title": title_key,
                "count": len(group),
                "status_counts": dict(per_status),
                "items": items,
                "sample_ids": [
                    _pick(r, "id", "issue_id", "key", "ticket_id") for r in group[:8]
                ],
            }
        )

    duplicate_groups.sort(key=lambda x: x["count"], reverse=True)

    findings: list[dict[str, Any]] = []
    if malformed_ids:
        findings.append(
            {
                "severity": "P2",
                "code": "bead_id_hygiene_warning",
                "message": f"Found {len(malformed_ids)} non-canonical bead IDs",
                "count": len(malformed_ids),
            }
        )
    hot_duplicates = [
        g
        for g in duplicate_groups
        if any(s in g["status_counts"] for s in ("OPEN", "READY", "IN_PROGRESS"))
    ]
    if hot_duplicates:
        findings.append(
            {
                "severity": "P1",
                "code": "duplicate_active_titles",
                "message": f"Found {len(hot_duplicates)} duplicate title groups in active statuses",
                "count": len(hot_duplicates),
            }
        )

    status = "green"
    if any(f["severity"] == "P1" for f in findings):
        status = "red"
    elif findings:
        status = "yellow"

    remediation_plan = _build_remediation_plan(duplicate_groups, malformed_ids)

    return {
        "audit": "bead_hygiene_audit",
        "timestamp": now,
        "status": status,
        "counts": {
            "total_items": len(rows),
            "status": dict(status_counts),
            "duplicate_groups": len(duplicate_groups),
            "malformed_ids": len(malformed_ids),
        },
        "findings": findings,
        "duplicates": duplicate_groups[:25],
        "remediation_plan": remediation_plan[:25],
        "malformed_id_examples": malformed_ids[:50],
        "controls": {
            "preventive": [
                "intake duplicate-title prevention enabled in auto_intake",
                "canonical field enforcement in workflow logs",
            ],
            "reactive": [
                "bead_hygiene_audit detects duplicate active titles",
                "daily_harness_audit can surface findings",
            ],
        },
    }


def write_reports(
    report: dict[str, Any], *, write_remediation_plan: bool = False
) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_json = OUT_DIR / f"bead_hygiene_{ts}.json"
    latest_json = OUT_DIR / "latest.json"
    latest_md = OUT_DIR / "latest.md"
    latest_remediation_json = OUT_DIR / "latest_remediation_plan.json"

    run_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Bead Hygiene Audit",
        "",
        f"Timestamp: {report.get('timestamp', '')}",
        f"Status: {report.get('status', '')}",
        "",
        "## Counts",
        "",
        f"- Total items: {report['counts'].get('total_items', 0)}",
        f"- Duplicate groups: {report['counts'].get('duplicate_groups', 0)}",
        f"- Malformed IDs: {report['counts'].get('malformed_ids', 0)}",
        "",
        "## Findings",
        "",
    ]
    if report.get("findings"):
        for finding in report["findings"]:
            lines.append(
                f"- {finding.get('severity')} {finding.get('code')}: {finding.get('message')}"
            )
    else:
        lines.append("- none")

    latest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if write_remediation_plan:
        latest_remediation_json.write_text(
            json.dumps(report.get("remediation_plan", []), indent=2), encoding="utf-8"
        )

    artifacts = {
        "run_json": str(run_json.relative_to(REPO)).replace("\\", "/"),
        "latest_json": str(latest_json.relative_to(REPO)).replace("\\", "/"),
        "latest_md": str(latest_md.relative_to(REPO)).replace("\\", "/"),
    }
    if write_remediation_plan:
        artifacts["latest_remediation_plan_json"] = str(
            latest_remediation_json.relative_to(REPO)
        ).replace("\\", "/")
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit bead hygiene pollution risks")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write .agents/audits/bead_hygiene artifacts",
    )
    parser.add_argument(
        "--write-remediation-plan",
        action="store_true",
        help="Write remediation plan artifact (dry-run recommendations only)",
    )
    args = parser.parse_args()

    report = build_report()
    if args.write:
        report["artifacts"] = write_reports(
            report, write_remediation_plan=args.write_remediation_plan
        )

    print(json.dumps(report, indent=2))
    return 1 if report.get("status") == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
