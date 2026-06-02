#!/usr/bin/env python3
"""Ingest GitHub review-related events into Chromatic findings and Next Work."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from classify_review_finding import enrich_finding, queue_status_for_confidence, specialties_for_type


DEFAULT_BASE = "07_LOGS_AND_AUDIT/review_intake"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12].upper()}"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.read_text().strip():
        return {}
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_jsonl_once(path: Path, record: Dict[str, Any], key: str = "dedupe_key") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {row.get(key) for row in read_jsonl(path)}
    if record.get(key) in existing:
        return False
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return True


def normalize_pull_request_review_comment(event: Dict[str, Any], repo: str) -> Dict[str, Any]:
    comment = event.get("comment", {})
    pr = event.get("pull_request", {})
    body = comment.get("body") or ""
    path = comment.get("path")
    line = comment.get("line") or comment.get("original_line")
    comment_id = comment.get("id")
    pr_number = pr.get("number")
    dedupe_key = f"{repo}#{pr_number}:{path}:{line}:{comment_id}"
    return {
        "finding_id": stable_id("RF", repo, pr_number, path, line, comment_id),
        "source": "github_pr_review_comment",
        "repo": repo,
        "pr_number": pr_number,
        "review_id": comment.get("pull_request_review_id"),
        "comment_id": comment_id,
        "thread_id": None,
        "author": (comment.get("user") or {}).get("login"),
        "created_at": comment.get("created_at") or utc_now(),
        "commit_sha": comment.get("commit_id") or pr.get("head", {}).get("sha"),
        "path": path,
        "line": line,
        "side": comment.get("side"),
        "body": body,
        "status": "open",
        "dedupe_key": dedupe_key,
        "links": {
            "pr": pr.get("html_url"),
            "comment": comment.get("html_url"),
        },
    }


def normalize_pull_request_review(event: Dict[str, Any], repo: str) -> Dict[str, Any]:
    review = event.get("review", {})
    pr = event.get("pull_request", {})
    body = review.get("body") or f"Review state: {review.get('state')}"
    pr_number = pr.get("number")
    review_id = review.get("id")
    dedupe_key = f"{repo}#{pr_number}:review:{review_id}:{review.get('state')}"
    return {
        "finding_id": stable_id("RF", repo, pr_number, review_id, review.get("state")),
        "source": "github_pr_review",
        "repo": repo,
        "pr_number": pr_number,
        "review_id": review_id,
        "comment_id": None,
        "thread_id": None,
        "author": (review.get("user") or {}).get("login"),
        "created_at": review.get("submitted_at") or utc_now(),
        "commit_sha": review.get("commit_id") or pr.get("head", {}).get("sha"),
        "path": None,
        "line": None,
        "side": None,
        "body": body,
        "status": "open" if review.get("state") == "changes_requested" else "informational",
        "dedupe_key": dedupe_key,
        "links": {"pr": pr.get("html_url"), "review": review.get("html_url")},
    }


def normalize_issue_comment(event: Dict[str, Any], repo: str) -> Dict[str, Any]:
    comment = event.get("comment", {})
    issue = event.get("issue", {})
    pr_number = issue.get("number")
    comment_id = comment.get("id")
    body = comment.get("body") or ""
    dedupe_key = f"{repo}#{pr_number}:issue-comment:{comment_id}"
    return {
        "finding_id": stable_id("RF", repo, pr_number, comment_id),
        "source": "github_issue_comment",
        "repo": repo,
        "pr_number": pr_number,
        "review_id": None,
        "comment_id": comment_id,
        "thread_id": None,
        "author": (comment.get("user") or {}).get("login"),
        "created_at": comment.get("created_at") or utc_now(),
        "commit_sha": None,
        "path": None,
        "line": None,
        "side": None,
        "body": body,
        "status": "open",
        "dedupe_key": dedupe_key,
        "links": {"pr": issue.get("html_url"), "comment": comment.get("html_url")},
    }


def normalize_check_run(event: Dict[str, Any], repo: str) -> Dict[str, Any]:
    check = event.get("check_run", {})
    conclusion = check.get("conclusion")
    name = check.get("name") or "check_run"
    body = f"Check run {name} completed with conclusion: {conclusion}."
    pr_number = None
    prs = check.get("pull_requests") or []
    if prs:
        pr_number = prs[0].get("number")
    dedupe_key = f"{repo}#{pr_number}:check-run:{check.get('id')}:{conclusion}"
    return {
        "finding_id": stable_id("RF", repo, pr_number, check.get("id"), conclusion),
        "source": "github_check_run",
        "repo": repo,
        "pr_number": pr_number,
        "review_id": None,
        "comment_id": check.get("id"),
        "thread_id": None,
        "author": "github-checks",
        "created_at": check.get("completed_at") or utc_now(),
        "commit_sha": (check.get("head_sha") or None),
        "path": None,
        "line": None,
        "side": None,
        "body": body,
        "status": "open" if conclusion not in {"success", "neutral", "skipped"} else "informational",
        "dedupe_key": dedupe_key,
        "links": {"check": check.get("html_url")},
    }


def normalize_workflow_run(event: Dict[str, Any], repo: str) -> Dict[str, Any]:
    run = event.get("workflow_run", {})
    conclusion = run.get("conclusion")
    name = run.get("name") or "workflow_run"
    body = f"Workflow {name} completed with conclusion: {conclusion}."
    pr_number = None
    prs = run.get("pull_requests") or []
    if prs:
        pr_number = prs[0].get("number")
    dedupe_key = f"{repo}#{pr_number}:workflow-run:{run.get('id')}:{conclusion}"
    return {
        "finding_id": stable_id("RF", repo, pr_number, run.get("id"), conclusion),
        "source": "github_workflow_run",
        "repo": repo,
        "pr_number": pr_number,
        "review_id": None,
        "comment_id": run.get("id"),
        "thread_id": None,
        "author": "github-actions",
        "created_at": run.get("updated_at") or utc_now(),
        "commit_sha": run.get("head_sha"),
        "path": None,
        "line": None,
        "side": None,
        "body": body,
        "status": "open" if conclusion not in {"success", "neutral", "skipped"} else "informational",
        "dedupe_key": dedupe_key,
        "links": {"workflow": run.get("html_url")},
    }


def normalize_event(event_name: str, event: Dict[str, Any], repo: str) -> Dict[str, Any] | None:
    action = event.get("action")
    if event_name == "pull_request_review_comment" and action != "deleted":
        return normalize_pull_request_review_comment(event, repo)
    if event_name == "pull_request_review":
        finding = normalize_pull_request_review(event, repo)
        if finding["status"] == "informational":
            return None
        return finding
    if event_name == "issue_comment" and action != "deleted":
        return normalize_issue_comment(event, repo)
    if event_name == "check_run":
        finding = normalize_check_run(event, repo)
        if finding["status"] == "informational":
            return None
        return finding
    if event_name == "workflow_run":
        finding = normalize_workflow_run(event, repo)
        if finding["status"] == "informational":
            return None
        return finding
    return None


def load_queue(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.read_text().strip():
        return {"items": []}
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return {"items": data}
    data.setdefault("items", [])
    return data


def finding_to_queue_item(finding: Dict[str, Any]) -> Dict[str, Any]:
    finding_type = finding.get("finding_type", "unclear")
    score = int(finding.get("confidence_score", 0))
    status = queue_status_for_confidence(score, finding_type)
    pr = finding.get("pr_number")
    path = finding.get("path") or "PR-level feedback"
    task_id = stable_id("NW", finding.get("repo"), pr, finding.get("finding_id"))
    links = [v for v in (finding.get("links") or {}).values() if v]
    return {
        "id": task_id,
        "title": f"Address review finding {finding.get('finding_id')} on PR #{pr}",
        "status": status,
        "priority": min(100, max(1, score)),
        "repo": finding.get("repo"),
        "pr_number": pr,
        "area": "review-intake",
        "specialties": specialties_for_type(finding_type),
        "owner_agent": finding.get("suggested_agent", "Auditor"),
        "depends_on": [],
        "blocked_by": [] if status == "ready" else ["confidence gate or human decision required"],
        "risk_level": finding.get("risk_level", "medium"),
        "confidence_score": score,
        "acceptance_checks": finding.get("acceptance_checks") or ["Review manually"],
        "links": links,
        "source_finding_id": finding.get("finding_id"),
        "commit_sha": finding.get("commit_sha"),
        "allowed_files": [finding.get("path")] if finding.get("path") else [],
        "notes": f"Review finding from {finding.get('source')} at {path}. Body: {finding.get('body', '')[:500]}",
    }


def invalidate_stale_queue_items(queue_path: Path, repo: str, pr_number: Any, after_sha: str | None) -> int:
    """Mark queue items stale when their source commit no longer matches the PR head.

    Triggered by ``pull_request.synchronize``. Items tied to a concrete commit that
    differs from the new head SHA are blocked so dispatch never patches stale feedback.
    Items with no commit (issue-level instructions) are left untouched. Findings.jsonl
    stays append-only; the queue is the mutable, dispatchable surface (PDR S15 decision).
    """
    if not queue_path.exists():
        return 0
    queue = load_queue(queue_path)
    invalidated = 0
    for item in queue.get("items", []):
        if str(item.get("repo")) != str(repo):
            continue
        if pr_number is not None and item.get("pr_number") != pr_number:
            continue
        item_sha = item.get("commit_sha")
        if not item_sha or item_sha == after_sha:
            continue
        if item.get("status") in {"done", "in-progress"}:
            continue
        if item.get("stale") and item.get("superseded_by_sha") == after_sha:
            continue
        item["status"] = "blocked"
        item["stale"] = True
        item["superseded_by_sha"] = after_sha
        reasons = set(item.get("blocked_by") or [])
        reasons.add(f"stale: PR synchronized to {after_sha}")
        item["blocked_by"] = sorted(reasons)
        item["updated_at"] = utc_now()
        invalidated += 1
    if invalidated:
        queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n")
    return invalidated


def upsert_queue_item(queue_path: Path, item: Dict[str, Any]) -> bool:
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue = load_queue(queue_path)
    items = queue.setdefault("items", [])
    for idx, existing in enumerate(items):
        if existing.get("id") == item.get("id") or existing.get("source_finding_id") == item.get("source_finding_id"):
            merged = {**existing, **item, "updated_at": utc_now()}
            items[idx] = merged
            queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n")
            return False
    item["created_at"] = utc_now()
    items.append(item)
    queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n")
    return True


def update_state(
    path: Path, event_name: str, finding: Dict[str, Any] | None, queue_item: Dict[str, Any] | None
) -> None:
    state = load_json(path) if path.exists() else {}
    state.update(
        {
            "last_event_name": event_name,
            "last_processed_at": utc_now(),
            "last_finding_id": finding.get("finding_id") if finding else None,
            "last_queue_item_id": queue_item.get("id") if queue_item else None,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", required=True)
    parser.add_argument("--findings", default=f"{DEFAULT_BASE}/findings.jsonl")
    parser.add_argument("--queue", default=f"{DEFAULT_BASE}/queue.json")
    parser.add_argument("--state", default=f"{DEFAULT_BASE}/state.json")
    args = parser.parse_args()

    event = load_json(Path(args.event_path))
    repo = event.get("repository", {}).get("full_name") or event.get("repository") or "unknown/repo"

    if args.event_name == "pull_request" and event.get("action") == "synchronize":
        pr = event.get("pull_request", {})
        after_sha = event.get("after") or pr.get("head", {}).get("sha")
        invalidated = invalidate_stale_queue_items(Path(args.queue), repo, pr.get("number"), after_sha)
        update_state(Path(args.state), args.event_name, None, None)
        print(
            json.dumps({"synchronize": True, "invalidated_queue_items": invalidated, "after_sha": after_sha}, indent=2)
        )
        return 0

    finding = normalize_event(args.event_name, event, repo)
    if not finding:
        update_state(Path(args.state), args.event_name, None, None)
        print("No actionable finding created.")
        return 0

    enriched = enrich_finding(finding)
    created = append_jsonl_once(Path(args.findings), enriched)
    queue_item = finding_to_queue_item(enriched)
    upsert_queue_item(Path(args.queue), queue_item)
    update_state(Path(args.state), args.event_name, enriched, queue_item)
    print(
        json.dumps(
            {"finding_created": created, "finding_id": enriched["finding_id"], "queue_item_id": queue_item["id"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
