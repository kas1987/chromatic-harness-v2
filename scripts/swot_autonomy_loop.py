#!/usr/bin/env python3
"""Autonomous SWOT -> PDR -> bead -> drain -> audit loop.

Default behavior is safe (dry-run for bead mutation and close actions).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))
sys.path.insert(0, str(REPO / "scripts"))

from common_harness import run_safe  # noqa: E402
from intake.bd_runner import resolve_bd_argv  # noqa: E402

SWOT_DEFAULT = REPO / "08_PDRS" / "SWOT_CI_CD_2026-06-16.md"
PDR_DIR_DEFAULT = REPO / "08_PDRS" / "SWOT_AUTONOMY"
OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
OUT_PATH = OUT_DIR / "swot_autonomy_latest.json"
CLEANUP_MD_PATH = OUT_DIR / "swot_duplicate_cleanup_latest.md"


@dataclass
class Finding:
    section: str
    index: int
    text: str


SECTION_LABEL = {
    "strengths": "strength",
    "weaknesses": "weakness",
    "opportunities": "opportunity",
    "threats": "threat",
}

LEGACY_SECTION_LABELS = {
    "strength": "strengths",
    "weakness": "weaknesses",
    "weaknesse": "weaknesses",
    "opportunity": "opportunities",
    "opportunitie": "opportunities",
    "threat": "threats",
}


def _parse_timestamp(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _parse_swot_title(title: str) -> tuple[str, int, str] | None:
    match = re.match(
        r"^SWOT\s+(strength|weakness|weaknesse|opportunity|opportunitie|threat)\s+remediation\s+(\d+):",
        title,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    label = match.group(1).lower()
    section = LEGACY_SECTION_LABELS.get(label)
    if not section:
        return None
    return section, int(match.group(2)), label


def _canonical_label_for_section(section: str) -> str:
    return SECTION_LABEL.get(section, section[:-1])


def _bead_preference_key(row: dict[str, Any]) -> tuple[int, datetime, str]:
    parsed = _parse_swot_title(str(row.get("title") or ""))
    label_rank = 1
    if parsed:
        section, _, label = parsed
        label_rank = 0 if label == _canonical_label_for_section(section) else 1
    updated = _parse_timestamp(str(row.get("updated_at") or row.get("created_at") or ""))
    bead_id = str(row.get("id") or "")
    return (label_rank, -int(updated.timestamp()), bead_id)


def _slug(text: str, limit: int = 48) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (raw[:limit]).strip("-") or "finding"


def _parse_findings(swot_path: Path) -> list[Finding]:
    lines = swot_path.read_text(encoding="utf-8").splitlines()
    sections = {"strengths", "weaknesses", "opportunities", "threats"}
    current: str | None = None
    counts: dict[str, int] = {k: 0 for k in sections}
    findings: list[Finding] = []

    for line in lines:
        hdr = re.match(r"^##\s+(.+)$", line.strip())
        if hdr:
            key = hdr.group(1).strip().lower()
            current = key if key in sections else None
            continue
        if not current:
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*\S)\s*$", line)
        if not bullet:
            continue
        counts[current] += 1
        findings.append(Finding(section=current, index=counts[current], text=bullet.group(1).strip()))
    return findings


def _pdr_path(base_dir: Path, finding: Finding) -> Path:
    section = finding.section.upper()
    slug = _slug(finding.text)
    name = f"PDR_SWOT_{section}_{finding.index:02d}_{slug}_{date.today().isoformat()}.md"
    return base_dir / name


def _render_pdr(finding: Finding, rel_swot_path: str) -> str:
    title = f"SWOT {finding.section[:-1].capitalize()} Remediation #{finding.index}"
    track = f"swot-{finding.section}-{finding.index:02d}"
    return (
        "\n".join(
            [
                f"# PDR - {title}",
                "",
                "**Status:** draft",
                f"**Track:** {track}",
                f"**Date:** {date.today().isoformat()}",
                "",
                "---",
                "",
                "## 1. Problem",
                "",
                f'SWOT finding requiring dedicated execution: "{finding.text}".',
                f"Source: {rel_swot_path} ({finding.section} item {finding.index}).",
                "",
                "---",
                "",
                "## 2. Non-Goals",
                "",
                "- Will not widen scope beyond this single SWOT finding.",
                "- Will not close related governance debt without measurable proof.",
                "",
                "---",
                "",
                "## 3. Design",
                "",
                "1. Convert this finding into an executable bead with explicit acceptance criteria.",
                "2. Run a bounded implementation loop using existing self-heal/intake workflow controls.",
                "3. Validate outcome in daily audit and CI governance artifacts before promotion.",
                "",
                "---",
                "",
                "## 4. Integration / Actuation Edge",
                "",
                "Runtime entrypoints:",
                "- scripts/workflow_self_heal_cycle.py",
                "- scripts/daily_harness_audit.py",
                "- .github/workflows/ci.yml",
                "- .github/workflows/ci-governance-weekly.yml",
                "",
                "Live proof:",
                "- SWOT autonomy artifact shows this finding generated and tracked.",
                "- Bead exists and is either in progress or closed with audit evidence.",
                "- Daily/CI audit has no blocking regression caused by the remediation.",
                "",
                "---",
                "",
                "## 5. Tests and Hardening",
                "",
                "- Run scripts/swot_autonomy_loop.py in dry-run, then apply mode.",
                "- Run scripts/daily_harness_audit.py --strict after loop execution.",
                "- Keep close actions gated behind explicit apply flags.",
                "",
                "---",
                "",
                "## 6. Definition of Done",
                "",
                "- [ ] Dedicated PDR exists for this SWOT finding.",
                "- [ ] A linked bead exists with acceptance criteria.",
                "- [ ] Bounded drain loop executed with evidence artifact.",
                "- [ ] Daily/CI audit confirms no P1 regressions from this change.",
            ]
        )
        + "\n"
    )


def _run(cmd: list[str], timeout: int = 180) -> dict[str, Any]:
    proc = run_safe(cmd, cwd=REPO, timeout=timeout)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "")[-6000:],
        "stderr": (proc.stderr or "")[-6000:],
    }


def _extract_bead_id(text: str) -> str | None:
    for pat in [r"(chromatic-harness-v2-[a-z0-9][a-z0-9\.-]*)", r"\b([a-z0-9]+-[a-z0-9\.-]+)\b"]:
        match = re.search(pat, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _create_bead(title: str, description: str, dry_run: bool) -> dict[str, Any]:
    cmd = [
        *resolve_bd_argv(),
        "create",
        title,
        "--type",
        "task",
        "--priority",
        "2",
        "--description",
        description[:1200],
    ]
    if dry_run:
        return {"ok": True, "dry_run": True, "cmd": cmd}
    result = _run(cmd, timeout=45)
    bead_id = _extract_bead_id((result.get("stdout") or "") + "\n" + (result.get("stderr") or ""))
    if bead_id:
        result["bead_id"] = bead_id
    return result


def _bd_list_rows() -> list[dict[str, Any]]:
    proc = run_safe([*resolve_bd_argv(), "list", "--json", "--limit", "0"], cwd=REPO, timeout=120)
    if proc.returncode != 0:
        return []
    text = (proc.stdout or proc.stderr or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return [row for row in items if isinstance(row, dict)]
    return []


def _existing_swot_beads() -> dict[tuple[str, int], dict[str, Any]]:
    rows = _bd_list_rows()
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        title = str(row.get("title") or "")
        parsed = _parse_swot_title(title)
        if not parsed:
            continue
        section, idx, _ = parsed
        grouped.setdefault((section, idx), []).append(row)
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for key, items in grouped.items():
        best = sorted(items, key=_bead_preference_key)[0]
        out[key] = {
            "id": str(best.get("id") or ""),
            "title": str(best.get("title") or ""),
            "status": str(best.get("status") or ""),
        }
    return out


def _duplicate_swot_beads() -> list[dict[str, Any]]:
    rows = _bd_list_rows()
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        parsed = _parse_swot_title(str(row.get("title") or ""))
        if not parsed:
            continue
        section, idx, _ = parsed
        grouped.setdefault((section, idx), []).append(row)

    duplicates: list[dict[str, Any]] = []
    for (section, idx), items in grouped.items():
        if len(items) < 2:
            continue
        ranked = sorted(items, key=_bead_preference_key)
        keep = ranked[0]
        close = ranked[1:]
        duplicates.append(
            {
                "section": section,
                "index": idx,
                "keep": {
                    "id": str(keep.get("id") or ""),
                    "title": str(keep.get("title") or ""),
                    "status": str(keep.get("status") or ""),
                },
                "close": [
                    {
                        "id": str(item.get("id") or ""),
                        "title": str(item.get("title") or ""),
                        "status": str(item.get("status") or ""),
                    }
                    for item in close
                ],
            }
        )
    return sorted(duplicates, key=lambda item: (item["section"], item["index"]))


def _render_cleanup_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SWOT Duplicate Cleanup",
        "",
        f"- Generated: {payload.get('generated_at', '')}",
        f"- Apply mode: {payload.get('cleanup_apply', False)}",
        f"- Duplicate groups: {payload.get('duplicate_group_count', 0)}",
        "",
        "## Groups",
        "",
    ]
    duplicates = payload.get("duplicates") or []
    if not duplicates:
        lines.append("No duplicate SWOT bead groups found.")
    else:
        for group in duplicates:
            keep = group.get("keep") or {}
            lines.append(
                f"- {group.get('section')} #{group.get('index')}: keep {keep.get('id', '')} ({keep.get('title', '')})"
            )
            for item in group.get("close") or []:
                lines.append(f"- close {item.get('id', '')} ({item.get('title', '')})")
    lines += ["", "## Actions", ""]
    actions = payload.get("actions") or []
    if not actions:
        lines.append("No actions emitted.")
    else:
        for action in actions:
            bead_id = action.get("bead_id", "")
            if action.get("dry_run"):
                lines.append(f"- DRY RUN {bead_id}")
            elif action.get("ok"):
                lines.append(f"- CLOSED {bead_id}")
            else:
                lines.append(f"- FAILED {bead_id} {action.get('error', '')}")
    lines.append("")
    return "\n".join(lines)


def _close_bead(bead_id: str, reason: str, dry_run: bool) -> dict[str, Any]:
    cmd = [*resolve_bd_argv(), "close", bead_id, "--reason", reason[:500]]
    if dry_run:
        return {"ok": True, "dry_run": True, "cmd": cmd, "bead_id": bead_id}
    return _run(cmd, timeout=45)


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous SWOT -> PDR -> bead loop")
    parser.add_argument("--swot-file", default=str(SWOT_DEFAULT))
    parser.add_argument("--pdr-dir", default=str(PDR_DIR_DEFAULT))
    parser.add_argument("--drain-limit", type=int, default=12)
    parser.add_argument("--apply", action="store_true", help="Allow bead creation and close mutations")
    parser.add_argument("--drain", action="store_true", help="Run self-heal drain cycle")
    parser.add_argument(
        "--close-generated",
        action="store_true",
        help="Close generated beads after successful strict audit (requires --apply)",
    )
    parser.add_argument("--branch-mode", choices=["off", "local", "subagent", "cloud"], default="local")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--audit-strict",
        action="store_true",
        help="Run daily audit in strict mode before CI/CD promotion checks",
    )
    parser.add_argument(
        "--fail-on-audit",
        action="store_true",
        help="Exit non-zero if daily audit command returns non-zero",
    )
    parser.add_argument(
        "--cleanup-duplicates",
        action="store_true",
        help="Preview or apply redundant SWOT bead cleanup",
    )
    parser.add_argument(
        "--cleanup-apply",
        action="store_true",
        help="Actually close redundant SWOT duplicates (requires --cleanup-duplicates)",
    )
    args = parser.parse_args()

    if args.cleanup_apply and not args.cleanup_duplicates:
        print(json.dumps({"error": "--cleanup-apply requires --cleanup-duplicates"}, indent=2))
        return 2

    if args.cleanup_duplicates:
        duplicates = _duplicate_swot_beads()
        actions: list[dict[str, Any]] = []
        for group in duplicates:
            for item in group.get("close", []):
                bead_id = str(item.get("id") or "")
                if not bead_id:
                    continue
                actions.append(
                    _close_bead(
                        bead_id,
                        f"Closing redundant SWOT duplicate; canonical bead is {group['keep']['id']}",
                        dry_run=not args.cleanup_apply,
                    )
                )
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cleanup_duplicates": True,
            "cleanup_apply": bool(args.cleanup_apply),
            "duplicate_group_count": len(duplicates),
            "duplicates": duplicates,
            "actions": actions,
        }
        if args.write:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            CLEANUP_MD_PATH.write_text(_render_cleanup_markdown(payload), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0 if all(action.get("ok") for action in actions) else 1

    swot_path = Path(args.swot_file).resolve()
    pdr_dir = Path(args.pdr_dir).resolve()
    pdr_dir.mkdir(parents=True, exist_ok=True)

    findings = _parse_findings(swot_path)
    rel_swot = str(swot_path.relative_to(REPO)) if swot_path.is_relative_to(REPO) else str(swot_path)
    existing_beads = _existing_swot_beads()

    pdr_records: list[dict[str, Any]] = []
    bead_records: list[dict[str, Any]] = []

    for finding in findings:
        pdr_path = _pdr_path(pdr_dir, finding)
        content = _render_pdr(finding, rel_swot)
        pdr_path.write_text(content, encoding="utf-8")
        pdr_record = {
            "section": finding.section,
            "index": finding.index,
            "finding": finding.text,
            "pdr": str(pdr_path.relative_to(REPO)) if pdr_path.is_relative_to(REPO) else str(pdr_path),
        }
        pdr_records.append(pdr_record)

        label = SECTION_LABEL.get(finding.section, finding.section[:-1])
        bead_title = f"SWOT {label} remediation {finding.index}: {finding.text[:90]}"
        bead_desc = (
            f"Auto-generated from SWOT finding.\\n"
            f"Section: {finding.section} #{finding.index}\\n"
            f"Finding: {finding.text}\\n"
            f"PDR: {pdr_record['pdr']}"
        )
        existing = existing_beads.get((finding.section, finding.index))
        if existing:
            bead = {
                "ok": True,
                "reused": True,
                "bead_id": existing.get("id"),
                "status": existing.get("status"),
                "title": existing.get("title"),
            }
        else:
            bead = _create_bead(bead_title, bead_desc, dry_run=not args.apply)
        bead_records.append({**pdr_record, "bead": bead})

    drain_result: dict[str, Any] | None = None
    if args.drain:
        drain_cmd = [
            sys.executable,
            str(REPO / "scripts" / "workflow_self_heal_cycle.py"),
            "--limit",
            str(args.drain_limit),
            "--branch-mode",
            args.branch_mode,
        ]
        drain_result = _run(drain_cmd, timeout=420)

    audit_cmd = [sys.executable, str(REPO / "scripts" / "daily_harness_audit.py")]
    if args.audit_strict:
        audit_cmd.append("--strict")
    audit_result = _run(audit_cmd, timeout=300)

    close_results: list[dict[str, Any]] = []
    if args.close_generated:
        if not args.apply:
            close_results.append({"ok": False, "error": "--close-generated requires --apply"})
        elif not audit_result.get("ok"):
            close_results.append({"ok": False, "error": "strict audit failed; skipping close"})
        else:
            for record in bead_records:
                bead_id = (record.get("bead") or {}).get("bead_id")
                if not bead_id:
                    continue
                close_results.append(
                    _close_bead(
                        bead_id,
                        "Auto-closed by swot_autonomy_loop after strict audit passed",
                        dry_run=not args.apply,
                    )
                )

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "swot_file": rel_swot,
        "pdr_dir": str(pdr_dir.relative_to(REPO)) if pdr_dir.is_relative_to(REPO) else str(pdr_dir),
        "apply": bool(args.apply),
        "drain": bool(args.drain),
        "close_generated": bool(args.close_generated),
        "audit_strict": bool(args.audit_strict),
        "fail_on_audit": bool(args.fail_on_audit),
        "finding_count": len(findings),
        "findings_by_section": {
            sec: len([f for f in findings if f.section == sec])
            for sec in ["strengths", "weaknesses", "opportunities", "threats"]
        },
        "pdrs": pdr_records,
        "beads": bead_records,
        "drain_result": drain_result,
        "audit_result": audit_result,
        "close_results": close_results,
    }

    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))

    if args.fail_on_audit and not audit_result.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
