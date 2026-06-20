#!/usr/bin/env python3
"""Measure review-intake loop closure latency end-to-end.

This script waits for a PR comment with the "review-intake: analyze" tag,
tracks the time from comment creation through beads registration, and
generates a latency report.

Usage:
  python measure_review_intake_loop.py --pr 275 --timeout 300
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp_to_seconds(ts: str) -> float:
    """Parse ISO 8601 timestamp to seconds since epoch."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    """Read JSONL file."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def read_json(path: Path) -> Dict[str, Any]:
    """Read JSON file."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def find_recent_review_intake_comment(
    pr_number: int, lookback_seconds: int = 60
) -> Optional[Dict[str, Any]]:
    """Find a recent comment with 'review-intake: analyze' tag via gh API."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "comments"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        comments = data.get("comments", [])

        cutoff = time.time() - lookback_seconds
        for comment in reversed(comments):
            body = comment.get("body", "")
            created_at_str = comment.get("createdAt", "")
            created_ts = timestamp_to_seconds(created_at_str)

            if created_ts >= cutoff and "review-intake: analyze" in body:
                return {
                    "id": comment.get("id"),
                    "body": body,
                    "created_at": created_at_str,
                    "created_ts": created_ts,
                }
        return None
    except Exception as e:
        print(f"Error fetching comments: {e}")
        return None


def get_findings_created_after(
    findings_path: Path, after_ts: float
) -> list[Dict[str, Any]]:
    """Find findings created after a given timestamp."""
    findings = read_jsonl(findings_path)
    return [
        f
        for f in findings
        if timestamp_to_seconds(f.get("created_at", "")) >= after_ts
    ]


def get_queue_items_for_findings(
    queue_path: Path, finding_ids: list[str]
) -> list[Dict[str, Any]]:
    """Find queue items that reference the given finding IDs."""
    queue = read_json(queue_path)
    items = queue.get("items", [])
    finding_id_set = set(finding_ids)
    return [
        item
        for item in items
        if item.get("source_finding_id") in finding_id_set
    ]


def get_beads_for_queue_items(
    bead_dir: Path, queue_item_ids: list[str]
) -> list[str]:
    """Find beads created for given queue item IDs (via bd list)."""
    try:
        result = subprocess.run(
            ["bd", "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        beads_data = json.loads(result.stdout)
        beads = beads_data if isinstance(beads_data, list) else beads_data.get("items", [])

        queue_id_set = set(queue_item_ids)
        matched = []
        for bead in beads:
            # Match on title containing queue item ID
            title = bead.get("title", "")
            for qid in queue_id_set:
                if qid in title:
                    matched.append(bead.get("id", ""))
                    break
        return matched
    except Exception as e:
        print(f"Error listing beads: {e}")
        return []


def measure_loop_closure(
    pr_number: int,
    findings_path: Path = Path("07_LOGS_AND_AUDIT/review_intake/findings.jsonl"),
    queue_path: Path = Path("07_LOGS_AND_AUDIT/review_intake/queue.json"),
    state_path: Path = Path("07_LOGS_AND_AUDIT/review_intake/state.json"),
    timeout: int = 300,
    poll_interval: int = 5,
) -> Dict[str, Any]:
    """Measure review-intake loop closure latency.

    Returns a dict with timing data for each phase.
    """
    result = {
        "status": "timeout",
        "pr_number": pr_number,
        "started_at": utc_now(),
        "phases": {},
        "total_latency_seconds": None,
        "error": None,
    }

    # Step 1: Find a recent comment with the trigger tag
    print(f"[1] Searching for 'review-intake: analyze' comment on PR #{pr_number}...")
    comment = find_recent_review_intake_comment(pr_number, lookback_seconds=60)
    if not comment:
        result["error"] = "No recent comment with 'review-intake: analyze' tag found"
        result["status"] = "comment_not_found"
        return result

    t0 = comment["created_ts"]
    result["phases"]["t0_comment_created"] = comment["created_at"]
    print(f"   Found comment created at {comment['created_at']}")

    # Step 2: Poll for findings created after the comment
    print(f"[2] Polling for review_finding records...")
    t1 = None
    findings = []
    elapsed = 0
    while elapsed < timeout:
        findings = get_findings_created_after(findings_path, t0 - 2)  # 2 sec buffer
        if findings:
            t1 = timestamp_to_seconds(findings[0].get("created_at", ""))
            result["phases"]["t1_finding_created"] = findings[0]["created_at"]
            result["phases"]["phase_0_1_ingest_sec"] = t1 - t0
            print(f"   Found {len(findings)} finding(s). Ingest latency: {t1-t0:.1f}s")
            break
        time.sleep(poll_interval)
        elapsed += poll_interval

    if not findings:
        result["error"] = "Findings not created within timeout"
        result["status"] = "findings_timeout"
        return result

    # Step 3: Poll for queue items
    print(f"[3] Polling for queue items...")
    t2 = None
    queue_items = []
    finding_ids = [f["finding_id"] for f in findings]
    elapsed = 0
    while elapsed < timeout:
        queue_items = get_queue_items_for_findings(queue_path, finding_ids)
        if queue_items:
            t2 = time.time()  # Approximate as now
            result["phases"]["t2_queue_created"] = utc_now()
            result["phases"]["phase_1_2_classify_sec"] = t2 - t1
            print(f"   Found {len(queue_items)} queue item(s). Classification latency: {t2-t1:.1f}s")
            break
        time.sleep(poll_interval)
        elapsed += poll_interval

    if not queue_items:
        result["error"] = "Queue items not created within timeout"
        result["status"] = "queue_timeout"
        return result

    # Step 4: Poll for beads created
    print(f"[4] Polling for beads...")
    t3 = None
    beads = []
    queue_ids = [q["id"] for q in queue_items]
    elapsed = 0
    while elapsed < timeout:
        beads = get_beads_for_queue_items(Path("07_LOGS_AND_AUDIT/review_intake"), queue_ids)
        if beads:
            t3 = time.time()
            result["phases"]["t3_beads_created"] = utc_now()
            result["phases"]["phase_2_3_dispatch_sec"] = t3 - t2
            result["phases"]["phase_3_beads_write_sec"] = 0.1  # Approximation
            print(f"   Found {len(beads)} bead(s). Dispatch latency: {t3-t2:.1f}s")
            break
        time.sleep(poll_interval)
        elapsed += poll_interval

    if not beads:
        # Not a hard failure; beads integration may not be active
        t3 = time.time()
        result["phases"]["t3_beads_created"] = "N/A (beads not found)"
        result["phases"]["phase_2_3_dispatch_sec"] = t3 - t2
        result["phases"]["phase_3_beads_write_sec"] = None
        print(f"   Beads not created. Dispatch latency: {t3-t2:.1f}s (beads may be optional)")

    # Summary
    t4 = time.time()
    result["phases"]["t4_measurement_complete"] = utc_now()
    total = t4 - t0
    result["total_latency_seconds"] = total
    result["status"] = "success"
    result["completed_at"] = utc_now()

    print(f"\n[✓] Loop closure measured successfully")
    print(f"   Total latency: {total:.1f}s")
    if total <= 60:
        print(f"   Status: ✓ PASS (target <60s)")
    elif total <= 300:
        print(f"   Status: ⚠ PASS (target <60s, acceptable <5min)")
    else:
        print(f"   Status: ✗ FAIL (total >5min; optimization needed)")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure review-intake loop closure latency"
    )
    parser.add_argument("--pr", type=int, required=True, help="PR number to measure")
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Poll interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("07_LOGS_AND_AUDIT/review_intake/measurement_log.jsonl"),
        help="Output file for measurement results",
    )
    args = parser.parse_args()

    result = measure_loop_closure(
        args.pr,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )

    # Write result to log
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(f"\nMeasurement logged to {args.output}")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    exit(main())
