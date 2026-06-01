#!/usr/bin/env python3
"""PR size & change-risk gate (bead gh-60 / chromatic-harness-v2-0f37).

Covers the five eval requirements:
  1. Capture changed-file and line-count metrics (from the live git diff).
  2. Detect protected-path touches (settings, hooks, CI, secrets, governance).
  3. Configurable warn/fail thresholds (constants + env overrides).
  4. Surface a large-PR warning before push/PR creation.
  5. Save the risk result to audit output (07_LOGS_AND_AUDIT/pr_risk/latest.json).

Exit codes: 0 = ok/warn, 1 = fail (over hard threshold or protected-path touch
when --strict). Warnings never block unless --strict-protected / over fail size.

Usage:
    python scripts/pr_size_gate.py                 # diff vs merge-base with origin base
    python scripts/pr_size_gate.py --base main     # explicit base ref
    python scripts/pr_size_gate.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "pr_risk"
DEFAULT_BASE = "origin/session/chromatic-harness-v2-initial"

# Eval 3: configurable thresholds (env overrides).
WARN_FILES = int(os.environ.get("PR_GATE_WARN_FILES", "30"))
FAIL_FILES = int(os.environ.get("PR_GATE_FAIL_FILES", "100"))
WARN_LINES = int(os.environ.get("PR_GATE_WARN_LINES", "800"))
FAIL_LINES = int(os.environ.get("PR_GATE_FAIL_LINES", "3000"))

# Eval 2: protected paths — touching these raises change-risk.
PROTECTED_PATTERNS = [
    r"\.github/",
    r"\.claude/settings(\.local)?\.json$",
    r"scripts/hooks/",
    r"02_RUNTIME/router/gate\.py$",
    r"00_SOURCE_OF_TRUTH/",
    r"\.agents/governance/",
    r"pre-?push|pre-?commit",
    r"requirements.*\.txt$",
    r"pyproject\.toml$",
]

# Paths that are generated/vendored — counted but down-weighted for risk.
GENERATED_PATTERNS = [r"\.lock$", r"package-lock\.json$", r"\.min\.", r"/dist/", r"/build/"]


def _run(cmd: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def _merge_base(base: str) -> str:
    code, out = _run(["git", "merge-base", "HEAD", base])
    return out.strip() if code == 0 and out.strip() else base


def collect_diff_metrics(base: str) -> dict:
    """Eval 1: changed-file and line-count metrics from the live git diff."""
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
        }
    files: list[dict] = []
    added = deleted = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        # binary files report "-"; treat as 0 lines but still a changed file.
        ai = int(a) if a.isdigit() else 0
        di = int(d) if d.isdigit() else 0
        added += ai
        deleted += di
        files.append({"path": path, "added": ai, "deleted": di})
    return {
        "status": "ok",
        "base": ref,
        "files": files,
        "changed_files": len(files),
        "added_lines": added,
        "deleted_lines": deleted,
        "total_lines": added + deleted,
    }


def _matches(path: str, patterns: list[str]) -> bool:
    return any(re.search(p, path) for p in patterns)


def assess_risk(metrics: dict, *, strict_protected: bool) -> dict:
    """Evals 2-4: protected-path detection, threshold classification, warning."""
    files = metrics.get("files", [])
    protected = [f["path"] for f in files if _matches(f["path"], PROTECTED_PATTERNS)]
    generated = [f["path"] for f in files if _matches(f["path"], GENERATED_PATTERNS)]

    nf = metrics.get("changed_files", 0)
    nl = metrics.get("total_lines", 0)
    reasons: list[str] = []
    level = "low"

    if nf >= FAIL_FILES or nl >= FAIL_LINES:
        level = "fail"
        reasons.append(f"size over hard limit ({nf} files / {nl} lines)")
    elif nf >= WARN_FILES or nl >= WARN_LINES:
        level = "warn"
        reasons.append(f"large change ({nf} files / {nl} lines)")

    if protected:
        reasons.append(f"{len(protected)} protected-path touch(es)")
        if strict_protected and level != "fail":
            level = "fail"
        elif level == "low":
            level = "warn"

    return {
        "risk_level": level,
        "reasons": reasons,
        "protected_paths": protected,
        "generated_paths": generated,
        "thresholds": {
            "warn_files": WARN_FILES,
            "fail_files": FAIL_FILES,
            "warn_lines": WARN_LINES,
            "fail_lines": FAIL_LINES,
        },
    }


def write_artifact(result: dict, timestamp: str) -> Path:
    """Eval 5: persist the risk result."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    latest = ARTIFACT_DIR / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


def run_gate(base: str, *, strict_protected: bool = False) -> dict:
    metrics = collect_diff_metrics(base)
    risk = assess_risk(metrics, strict_protected=strict_protected)
    return {
        "metrics": {k: v for k, v in metrics.items() if k != "files"},
        "risk": risk,
        "changed_files": metrics.get("changed_files", 0),
        "total_lines": metrics.get("total_lines", 0),
        "risk_level": risk["risk_level"],
        "passed": risk["risk_level"] != "fail",
    }


def summarize() -> dict:
    """For the closeout report — reads the latest artifact (fail-open)."""
    try:
        latest = ARTIFACT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "risk_level": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "risk_level": data.get("risk_level"),
            "changed_files": data.get("changed_files"),
            "total_lines": data.get("total_lines"),
            "protected_touches": len(data.get("risk", {}).get("protected_paths", [])),
            "timestamp": data.get("timestamp"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "risk_level": None}


def main() -> int:
    ap = argparse.ArgumentParser(description="PR size & change-risk gate (gh-60)")
    ap.add_argument("--base", default=os.environ.get("PR_GATE_BASE", DEFAULT_BASE))
    ap.add_argument("--strict-protected", action="store_true", help="Fail (not warn) when a protected path is touched")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timestamp", default="")
    args = ap.parse_args()

    ts = args.timestamp
    if not ts:
        import datetime

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = run_gate(args.base, strict_protected=args.strict_protected)
    artifact = write_artifact(result, ts)
    r = result["risk"]

    print("PR size & change-risk gate:")
    print(f"  changed files: {result['changed_files']} | lines: {result['total_lines']}")
    print(f"  risk level:    {result['risk_level'].upper()}")
    if r["protected_paths"]:
        print(f"  protected:     {', '.join(r['protected_paths'][:10])}")
    for reason in r["reasons"]:
        print(f"  - {reason}")
    print(f"  artifact:      {artifact}")

    sep = "=" * 60
    if result["risk_level"] == "fail":
        print(f"\n{sep}\nPR gate: FAIL — change set over threshold / protected\n{sep}")
    elif result["risk_level"] == "warn":
        print(f"\n{sep}\nPR gate: WARN — large or risky change (review before push)\n{sep}")
    else:
        print(f"\n{sep}\nPR gate: OK\n{sep}")
    if args.json:
        print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
