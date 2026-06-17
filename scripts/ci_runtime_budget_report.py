#!/usr/bin/env python3
"""Collect CI runtime data and compare against budget targets."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from log_retention import prune_dir  # noqa: E402

TARGETS_PATH = REPO / "config" / "ci" / "runtime_budget_targets.json"
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
LATEST_PATH = ARTIFACT_DIR / "runtime_budget_latest.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_jobs(token: str, repo: str, run_id: str) -> list[dict[str, Any]]:  # pragma: allowlist secret
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    jobs = payload.get("jobs") or []
    return jobs if isinstance(jobs, list) else []


def _duration_minutes(job: dict[str, Any]) -> float | None:
    started = job.get("started_at")
    completed = job.get("completed_at")
    if not isinstance(started, str) or not isinstance(completed, str):
        return None
    try:
        s = datetime.fromisoformat(started.replace("Z", "+00:00"))
        c = datetime.fromisoformat(completed.replace("Z", "+00:00"))
    except ValueError:
        return None
    seconds = max(0.0, (c - s).total_seconds())
    return round(seconds / 60.0, 3)


def _lane_for_job(name: str) -> str:
    lower = name.lower()
    if "concurrency suite" in lower or "windows" in lower or "matrix" in lower:
        return "deep_lane"
    return "fast_lane"


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, math.ceil(p * len(ordered)) - 1)
    return round(ordered[idx], 3)


def _aggregate(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    by_lane: dict[str, list[float]] = {"fast_lane": [], "deep_lane": []}
    by_lane_jobs: dict[str, list[dict[str, Any]]] = {"fast_lane": [], "deep_lane": []}

    for job in jobs:
        name = str(job.get("name") or "")
        if not name:
            continue
        duration = _duration_minutes(job)
        if duration is None:
            continue
        lane = _lane_for_job(name)
        by_lane[lane].append(duration)
        by_lane_jobs[lane].append(
            {
                "name": name,
                "duration_minutes": duration,
                "conclusion": job.get("conclusion"),
            }
        )

    out: dict[str, Any] = {"lanes": {}, "sample_count": sum(len(v) for v in by_lane.values())}
    for lane, values in by_lane.items():
        median = _percentile(values, 0.5)
        p95 = _percentile(values, 0.95)
        out["lanes"][lane] = {
            "job_count": len(values),
            "median_minutes": median,
            "p95_minutes": p95,
            "jobs": by_lane_jobs[lane],
        }
    return out


def _evaluate(agg: dict[str, Any], targets: dict[str, Any]) -> dict[str, Any]:
    lanes = targets.get("targets") or {}
    verdicts: dict[str, Any] = {}
    over_budget = False

    for lane, lane_targets in lanes.items():
        actual = (agg.get("lanes") or {}).get(lane) or {}
        median_actual = float(actual.get("median_minutes") or 0.0)
        p95_actual = float(actual.get("p95_minutes") or 0.0)
        median_target = float((lane_targets or {}).get("median_minutes") or 0.0)
        p95_target = float((lane_targets or {}).get("p95_minutes") or 0.0)

        lane_over = median_actual > median_target or p95_actual > p95_target
        over_budget = over_budget or lane_over
        verdicts[lane] = {
            "median_target": median_target,
            "p95_target": p95_target,
            "median_actual": median_actual,
            "p95_actual": p95_actual,
            "over_budget": lane_over,
        }

    return {
        "lanes": verdicts,
        "over_budget": over_budget,
    }


def _write_report(report: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["timestamp"] = ts

    LATEST_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ARTIFACT_DIR / f"runtime_budget_{ts}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    prune_dir(ARTIFACT_DIR, keep=50, apply=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate CI runtime budget report")
    ap.add_argument("--jobs-file", default="", help="Optional path to jobs JSON payload")
    ap.add_argument("--enforce", action="store_true", help="Exit 1 when over budget")
    args = ap.parse_args()

    targets = _load_json(TARGETS_PATH)

    jobs: list[dict[str, Any]] = []
    source = "none"
    if args.jobs_file:
        payload = _load_json(Path(args.jobs_file))
        jobs = payload.get("jobs") if isinstance(payload, dict) else payload
        jobs = jobs if isinstance(jobs, list) else []
        source = "file"
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")  # pragma: allowlist secret
        repo = os.environ.get("GITHUB_REPOSITORY")
        run_id = os.environ.get("GITHUB_RUN_ID")
        if token and repo and run_id:
            try:
                jobs = _fetch_jobs(token, repo, run_id)
                source = "github_api"
            except Exception as exc:  # noqa: BLE001
                source = f"github_api_error:{exc}"

    agg = _aggregate(jobs)
    eval_report = _evaluate(agg, targets)
    report = {
        "ok": True,
        "source": source,
        "targets_path": str(TARGETS_PATH.relative_to(REPO)).replace("\\", "/"),
        "sample_count": agg.get("sample_count", 0),
        "runtime": agg,
        "budget": eval_report,
    }

    if agg.get("sample_count", 0) == 0:
        report["ok"] = False
        report["note"] = "No CI job samples available in current context"

    _write_report(report)
    print(json.dumps(report, indent=2))

    if args.enforce and eval_report.get("over_budget"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
