#!/usr/bin/env python3
"""AI-reviewer + risk-scoring governance gate (bead gh-59).

Network-free: AI review is modelled as deterministic heuristic findings
over the git diff (no live LLM calls).

Eval requirements:
  1. generate_findings(diff_metrics) -> list[dict]  -- heuristic rule hits
  2. risk_score(diff_metrics, findings) -> int 0-100  -- composite score
  3. Configurable warn/fail thresholds (env: AI_REVIEW_WARN_FILES, AI_REVIEW_FAIL_FILES)
  4. Markdown + JSON artifacts under 07_LOGS_AND_AUDIT/ai_review/
  5. apply_override(result, reason, actor) -- flips fail->override-allow, audited

Exit codes: 0 = ok/warn (or overridden), 1 = fail.

Usage:
    python scripts/ai_review_gate.py
    python scripts/ai_review_gate.py --base main
    python scripts/ai_review_gate.py --json
    python scripts/ai_review_gate.py --override-reason "hotfix approved" --actor alice
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import run_safe  # noqa: E402

ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ai_review"
DEFAULT_BASE = "origin/session/chromatic-harness-v2-initial"

# Eval 3: configurable thresholds (env overrides).
WARN_FILES = int(os.environ.get("AI_REVIEW_WARN_FILES", "30"))
FAIL_FILES = int(os.environ.get("AI_REVIEW_FAIL_FILES", "100"))

# Heuristic rule thresholds.
LARGE_FILE_CHURN_LINES = 500  # single-file line churn threshold
DELETION_RATIO_THRESH = 0.7  # deleted / total > this -> flag
TODO_PATTERN = re.compile(r"\bTODO\b|\bFIXME\b|\bHACK\b|\bXXX\b")

# Risk-score weights.
_W_WARN = 5
_W_ERROR = 15
_W_CRITICAL = 30


# ---------------------------------------------------------------------------
# Git helpers (mirrors pr_size_gate.py)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        r = run_safe(cmd, cwd=REPO, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # defensive; run_safe itself does not raise
        return 1, str(exc)


def _merge_base(base: str) -> str:
    code, out = _run(["git", "merge-base", "HEAD", base])
    return out.strip() if code == 0 and out.strip() else base


def collect_diff_metrics(base: str) -> dict:
    """Collect changed-file and line-count metrics from the live git diff."""
    ref = _merge_base(base)
    code, out = _run(["git", "diff", "--numstat", f"{ref}...HEAD"])
    if code != 0:
        return {
            "status": "error",
            "note": out[-200:],
            "files": [],
            "changed_files": 0,
            "added_lines": 0,
            "deleted_lines": 0,
            "total_lines": 0,
        }
    files: list[dict] = []
    added = deleted = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        ai = int(a) if a.isdigit() else 0
        di = int(d) if d.isdigit() else 0
        added += ai
        deleted += di
        files.append({"path": path, "added": ai, "deleted": di})

    # Scan diff text for TODO/FIXME additions.
    todo_hits: list[str] = []
    code2, diff_text = _run(["git", "diff", f"{ref}...HEAD"])
    if code2 == 0:
        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++") and TODO_PATTERN.search(line):
                todo_hits.append(line[1:].strip())

    # Detect new scripts (added .py files with no corresponding test).
    new_scripts = [
        f["path"] for f in files if f["path"].startswith("scripts/") and f["path"].endswith(".py") and f["added"] > 0
    ]
    test_files = {f["path"] for f in files if "test" in f["path"].lower()}

    return {
        "status": "ok",
        "base": ref,
        "files": files,
        "changed_files": len(files),
        "added_lines": added,
        "deleted_lines": deleted,
        "total_lines": added + deleted,
        "todo_hits": todo_hits,
        "new_scripts": new_scripts,
        "test_files_changed": sorted(test_files),
    }


# ---------------------------------------------------------------------------
# Eval 1: heuristic findings
# ---------------------------------------------------------------------------


def generate_findings(diff_metrics: dict) -> list[dict]:
    """Pure function: produce heuristic findings from diff_metrics.

    Each finding: {rule, severity, message, recommendation}
    Severity levels: info, warn, error, critical
    """
    findings: list[dict] = []
    files: list[dict] = diff_metrics.get("files", [])
    nf = diff_metrics.get("changed_files", 0)
    added = diff_metrics.get("added_lines", 0)
    deleted = diff_metrics.get("deleted_lines", 0)
    total = diff_metrics.get("total_lines", 0)

    # R1: large overall change.
    if nf >= FAIL_FILES:
        findings.append(
            {
                "rule": "large-pr-critical",
                "severity": "critical",
                "message": f"PR touches {nf} files (>= {FAIL_FILES} hard limit).",
                "recommendation": "Split into smaller atomic PRs.",
            }
        )
    elif nf >= WARN_FILES:
        findings.append(
            {
                "rule": "large-pr-warn",
                "severity": "warn",
                "message": f"PR touches {nf} files (>= {WARN_FILES} warn threshold).",
                "recommendation": "Consider breaking into smaller PRs.",
            }
        )

    # R2: individual files with high churn.
    for f in files:
        file_total = f["added"] + f["deleted"]
        if file_total >= LARGE_FILE_CHURN_LINES:
            findings.append(
                {
                    "rule": "large-file-churn",
                    "severity": "warn",
                    "message": f"{f['path']}: {file_total} lines changed in a single file.",
                    "recommendation": "Review for unintended bulk edits or generated content.",
                }
            )

    # R3: high deletion ratio (possible mass removal).
    if total > 0 and deleted / total >= DELETION_RATIO_THRESH:
        findings.append(
            {
                "rule": "high-deletion-ratio",
                "severity": "warn",
                "message": f"Deletion ratio {deleted / total:.0%} ({deleted} deleted / {total} total).",
                "recommendation": "Confirm removals are intentional and nothing critical was dropped.",
            }
        )

    # R4: TODO/FIXME added.
    todo_hits = diff_metrics.get("todo_hits", [])
    if todo_hits:
        findings.append(
            {
                "rule": "todo-fixme-added",
                "severity": "warn",
                "message": f"{len(todo_hits)} TODO/FIXME/HACK comment(s) added.",
                "recommendation": "Resolve or track as separate issues before merging.",
            }
        )

    # R5: new scripts with no test coverage.
    new_scripts = diff_metrics.get("new_scripts", [])
    test_files = set(diff_metrics.get("test_files_changed", []))
    untested = [s for s in new_scripts if not any(Path(s).stem in tf for tf in test_files)]
    if untested:
        findings.append(
            {
                "rule": "missing-tests",
                "severity": "error",
                "message": f"{len(untested)} new script(s) added without corresponding test file: "
                + ", ".join(untested[:5]),
                "recommendation": "Add tests under tests/ for each new script.",
            }
        )

    # R6: only deletions (no additions at all) — possible accident.
    if deleted > 0 and added == 0:
        findings.append(
            {
                "rule": "additions-absent",
                "severity": "error",
                "message": "PR contains only deletions and no additions.",
                "recommendation": "Confirm this is intentional (dead-code removal vs accidental wipe).",
            }
        )

    return findings


# ---------------------------------------------------------------------------
# Eval 2: risk score
# ---------------------------------------------------------------------------


def risk_score(diff_metrics: dict, findings: list[dict]) -> int:
    """Pure function: compute 0-100 risk score.

    Higher = riskier. Combines size contribution + finding severities.
    """
    nf = diff_metrics.get("changed_files", 0)
    total_lines = diff_metrics.get("total_lines", 0)

    # Size component (0-40).
    size_score = min(40, int(nf / max(FAIL_FILES, 1) * 20) + int(total_lines / 3000 * 20))

    # Finding component (0-60).
    severity_points = {"info": 1, "warn": _W_WARN, "error": _W_ERROR, "critical": _W_CRITICAL}
    finding_score = sum(severity_points.get(f.get("severity", "info"), 0) for f in findings)
    finding_score = min(60, finding_score)

    return min(100, size_score + finding_score)


# ---------------------------------------------------------------------------
# Threshold classification
# ---------------------------------------------------------------------------


def classify_level(nf: int, score: int) -> str:
    """Return ok / warn / fail based on file count and risk score."""
    if nf >= FAIL_FILES or score >= 70:
        return "fail"
    if nf >= WARN_FILES or score >= 40:
        return "warn"
    return "ok"


# ---------------------------------------------------------------------------
# Eval 4: artifact writers
# ---------------------------------------------------------------------------


def _finding_md(f: dict) -> str:
    sev = f.get("severity", "info").upper()
    return (
        f"- **[{sev}]** `{f.get('rule', '')}`: {f.get('message', '')}\n"
        f"  - *Recommendation*: {f.get('recommendation', '')}"
    )


def write_report(result: dict, timestamp: str) -> tuple[Path, Path]:
    """Write markdown report and JSON artifact; return (md_path, json_path)."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    score = result.get("risk_score", 0)
    level = result.get("level", "ok")
    findings = result.get("findings", [])
    overridden = result.get("overridden", False)

    lines = [
        "# AI Review Gate Report",
        "",
        f"**Timestamp:** {timestamp}",
        f"**Risk Score:** {score}/100",
        f"**Level:** {level.upper()}{'  *(overridden)*' if overridden else ''}",
        "",
        "## Findings",
        "",
    ]
    if findings:
        lines += [_finding_md(f) for f in findings]
    else:
        lines.append("No findings — diff looks clean.")

    lines += [
        "",
        "## Metrics",
        "",
        f"- Changed files: {result.get('changed_files', 0)}",
        f"- Added lines:   {result.get('added_lines', 0)}",
        f"- Deleted lines: {result.get('deleted_lines', 0)}",
        "",
        "## Thresholds",
        "",
        f"- Warn files: {WARN_FILES}",
        f"- Fail files: {FAIL_FILES}",
        "",
        "---",
        "*Generated by scripts/ai_review_gate.py (network-free heuristic review)*",
    ]

    md_path = ARTIFACT_DIR / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    json_path = ARTIFACT_DIR / "latest.json"
    json_path.write_text(payload, encoding="utf-8")

    return md_path, json_path


# ---------------------------------------------------------------------------
# Eval 5: human override
# ---------------------------------------------------------------------------


def apply_override(result: dict, reason: str, actor: str) -> dict:
    """Flip fail->override-allow; append an auditable record to overrides.jsonl."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    import datetime

    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "actor": actor,
        "reason": reason,
        "original_level": result.get("level"),
        "original_score": result.get("risk_score"),
    }
    overrides_path = ARTIFACT_DIR / "overrides.jsonl"
    with overrides_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")

    result = {**result, "level": "override-allow", "overridden": True, "override": entry}
    return result


# ---------------------------------------------------------------------------
# summarize (fail-open for closeout report)
# ---------------------------------------------------------------------------


def summarize() -> dict:
    """Read latest artifact and return compact summary (fail-open)."""
    try:
        latest = ARTIFACT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "risk_score": None, "level": None, "findings": [], "overridden": False}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "risk_score": data.get("risk_score"),
            "level": data.get("level"),
            "findings": data.get("findings", []),
            "overridden": data.get("overridden", False),
            "timestamp": data.get("timestamp"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "error": str(exc),
            "risk_score": None,
            "level": None,
            "findings": [],
            "overridden": False,
        }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="AI review + risk-scoring governance gate (gh-59)")
    ap.add_argument("--base", default=os.environ.get("AI_REVIEW_BASE", DEFAULT_BASE))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timestamp", default="")
    ap.add_argument("--override-reason", default="")
    ap.add_argument("--actor", default=os.environ.get("USER", "unknown"))
    args = ap.parse_args()

    import datetime

    ts = args.timestamp or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    metrics = collect_diff_metrics(args.base)
    findings = generate_findings(metrics)
    score = risk_score(metrics, findings)
    level = classify_level(metrics.get("changed_files", 0), score)

    result: dict = {
        "status": metrics.get("status", "ok"),
        "risk_score": score,
        "level": level,
        "changed_files": metrics.get("changed_files", 0),
        "added_lines": metrics.get("added_lines", 0),
        "deleted_lines": metrics.get("deleted_lines", 0),
        "total_lines": metrics.get("total_lines", 0),
        "findings": findings,
        "overridden": False,
        "thresholds": {"warn_files": WARN_FILES, "fail_files": FAIL_FILES},
    }

    if args.override_reason and level == "fail":
        result = apply_override(result, args.override_reason, args.actor)

    md_path, json_path = write_report(result, ts)

    print("AI review gate:")
    print(f"  changed files : {result['changed_files']}")
    print(f"  risk score    : {score}/100")
    print(f"  level         : {result['level'].upper()}")
    print(f"  findings      : {len(findings)}")
    for f in findings:
        print(f"    [{f['severity'].upper():8s}] {f['rule']}: {f['message']}")
    print(f"  report        : {md_path}")
    print(f"  artifact      : {json_path}")

    sep = "=" * 60
    final_level = result["level"]
    if final_level == "fail":
        print(f"\n{sep}\nAI review gate: FAIL  (score {score}/100)\n{sep}")
    elif final_level == "override-allow":
        print(f"\n{sep}\nAI review gate: OVERRIDE-ALLOW (was FAIL)\n{sep}")
    elif final_level == "warn":
        print(f"\n{sep}\nAI review gate: WARN  (score {score}/100)\n{sep}")
    else:
        print(f"\n{sep}\nAI review gate: OK    (score {score}/100)\n{sep}")

    if args.json:
        print(json.dumps(result, indent=2))

    return 0 if final_level != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
