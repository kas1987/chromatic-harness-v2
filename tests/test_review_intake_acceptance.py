"""Proof harness for the 8 PDR acceptance criteria (REVIEW_INTAKE_PDR.md S13).

Each test maps to a numbered acceptance criterion and proves it against the shipped
JSON schemas and real event fixtures. Everything runs in tmp_path; no tracked repo
state is touched.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
SCHEMAS = REPO_ROOT / "schemas"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "review_intake"

sys.path.insert(0, str(SCRIPTS))

import lock_pr_branch  # noqa: E402

ALL_SOURCES = [
    ("pull_request_review_comment", "sample_pull_request_review_comment_event.json", "github_pr_review_comment"),
    ("pull_request_review", "sample_pull_request_review_event.json", "github_pr_review"),
    ("issue_comment", "sample_issue_comment_event.json", "github_issue_comment"),
    ("check_run", "sample_check_run_event.json", "github_check_run"),
    ("workflow_run", "sample_workflow_run_event.json", "github_workflow_run"),
]


def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text())


def validate(record: dict, schema_name: str) -> None:
    jsonschema.validate(instance=record, schema=load_schema(schema_name))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def run_intake(base: Path, event_name: str, fixture: str) -> dict:
    cmd = [
        sys.executable,
        str(SCRIPTS / "review_intake.py"),
        "--event-name",
        event_name,
        "--event-path",
        str(FIXTURES / fixture),
        "--findings",
        str(base / "findings.jsonl"),
        "--queue",
        str(base / "queue.json"),
        "--state",
        str(base / "state.json"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else {}


@pytest.fixture
def base(tmp_path: Path) -> Path:
    d = tmp_path / "review_intake"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------- AC1
def test_ac1_all_sources_emit_schema_valid_findings(base: Path):
    """AC1: GitHub review events create valid review_finding records (all 5 sources)."""
    seen = set()
    for event_name, fixture, source in ALL_SOURCES:
        run_intake(base, event_name, fixture)
        seen.add(source)
    findings = read_jsonl(base / "findings.jsonl")
    assert {f["source"] for f in findings} == {s for *_, s in ALL_SOURCES}
    for f in findings:
        validate(f, "review_finding.schema.json")
    assert seen == {s for *_, s in ALL_SOURCES}


# ---------------------------------------------------------------- AC2
def test_ac2_duplicate_comments_do_not_duplicate_queue_items(base: Path):
    """AC2: Duplicate comments do not create duplicate queue items."""
    run_intake(base, "pull_request_review_comment", "sample_pull_request_review_comment_event.json")
    out2 = run_intake(base, "pull_request_review_comment", "sample_pull_request_review_comment_event.json")
    assert out2.get("finding_created") is False
    assert len(read_jsonl(base / "findings.jsonl")) == 1
    queue = json.loads((base / "queue.json").read_text())
    assert len(queue["items"]) == 1


def test_ac2_synchronize_invalidates_stale_queue_items(base: Path):
    """AC2/PDR S6: pull_request.synchronize invalidates findings tied to an old commit."""
    run_intake(base, "pull_request_review_comment", "sample_pull_request_review_comment_event.json")
    item = json.loads((base / "queue.json").read_text())["items"][0]
    assert item["commit_sha"] == "abc123" and item["status"] == "ready"
    out = run_intake(base, "pull_request", "sample_pull_request_synchronize_event.json")
    assert out["invalidated_queue_items"] == 1
    item = json.loads((base / "queue.json").read_text())["items"][0]
    assert item["status"] == "blocked" and item["stale"] is True
    assert item["superseded_by_sha"] == "newsha999"


# ---------------------------------------------------------------- AC3
def test_ac3_queue_items_complete_and_schema_valid(base: Path):
    """AC3: Queue items carry owner, priority, risk, confidence, links, acceptance + validate."""
    for event_name, fixture, _ in ALL_SOURCES:
        run_intake(base, event_name, fixture)
    queue = json.loads((base / "queue.json").read_text())
    assert queue["items"]
    for item in queue["items"]:
        validate(item, "next_work_item.schema.json")
        assert item["owner_agent"] and item["acceptance_checks"]
        assert "confidence_score" in item and "risk_level" in item


# ---------------------------------------------------------------- AC4
def test_ac4_dispatcher_generates_mission_packet_and_dispatch_record(base: Path):
    """AC4: Mission packets are generated from queue items; dispatch record is schema-valid."""
    run_intake(base, "pull_request_review_comment", "sample_pull_request_review_comment_event.json")
    cmd = [
        sys.executable,
        str(SCRIPTS / "dispatch_review_work.py"),
        "--queue",
        str(base / "queue.json"),
        "--lock-dir",
        str(base / "locks"),
        "--packet-dir",
        str(base / "mission_packets"),
        "--dispatch-log",
        str(base / "dispatch_log.jsonl"),
        "--limit",
        "1",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["dispatched"] == 1

    dispatches = read_jsonl(base / "dispatch_log.jsonl")
    assert len(dispatches) == 1
    validate({k: v for k, v in dispatches[0].items()}, "agent_dispatch.schema.json")

    packets = list((base / "mission_packets").glob("*.md"))
    assert packets, "no mission packet rendered"
    body = packets[0].read_text()
    assert "{{" not in body, "unrendered template placeholder remains"
    assert "Acceptance Checks" in body and "Stop Conditions" in body

    item = json.loads((base / "queue.json").read_text())["items"][0]
    assert item["status"] == "in-progress"


# ---------------------------------------------------------------- AC5
def test_ac5_branch_lock_blocks_second_acquire(base: Path):
    lock_dir = base / "locks"
    ok1, _ = lock_pr_branch.acquire(lock_dir, "owner/repo", 42, holder="Sentinel", queue_item_id="NW-1")
    assert ok1 is True
    ok2, payload = lock_pr_branch.acquire(lock_dir, "owner/repo", 42, holder="Auditor", queue_item_id="NW-2")
    assert ok2 is False and payload["reason"] == "active_lock"
    assert lock_pr_branch.release(lock_dir, "owner/repo", 42) is True
    ok3, rec = lock_pr_branch.acquire(lock_dir, "owner/repo", 42, holder="Auditor", queue_item_id="NW-2")
    assert ok3 is True
    validate(rec, "pr_branch_lock.schema.json")


def test_ac5_expired_lock_is_reacquirable(base: Path):
    lock_dir = base / "locks"
    lock_pr_branch.acquire(lock_dir, "owner/repo", 7, holder="A", queue_item_id="NW-1")
    # Force expiry into the past.
    path = lock_pr_branch.lock_path(lock_dir, "owner/repo", 7)
    data = json.loads(path.read_text())
    data["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    path.write_text(json.dumps(data))
    ok, _ = lock_pr_branch.acquire(lock_dir, "owner/repo", 7, holder="B", queue_item_id="NW-2")
    assert ok is True


def test_ac5_dispatcher_respects_lock_no_double_patch(base: Path):
    """Two ready items on the same PR → only one is dispatched (one mutating agent)."""
    # Two distinct review comments on PR #42 → two ready queue items, same branch.
    run_intake(base, "pull_request_review_comment", "sample_pull_request_review_comment_event.json")
    # Synthesize a second ready item on the same PR by editing the queue directly.
    queue = json.loads((base / "queue.json").read_text())
    clone = dict(queue["items"][0])
    clone["id"] = "NW-SECOND"
    clone["source_finding_id"] = "RF-SECOND"
    queue["items"].append(clone)
    (base / "queue.json").write_text(json.dumps(queue))

    cmd = [
        sys.executable,
        str(SCRIPTS / "dispatch_review_work.py"),
        "--queue",
        str(base / "queue.json"),
        "--lock-dir",
        str(base / "locks"),
        "--packet-dir",
        str(base / "mission_packets"),
        "--dispatch-log",
        str(base / "dispatch_log.jsonl"),
        "--limit",
        "5",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["dispatched"] == 1
    blocked = [r for r in out["results"] if not r.get("dispatched")]
    assert any(r.get("reason") == "pr_branch_locked" for r in blocked)


# ---------------------------------------------------------------- AC6
def _resolution(base: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(SCRIPTS / "post_review_resolution.py"),
        "--finding",
        "RF-ABC",
        "--task",
        "NW-XYZ",
        "--agent",
        "Sentinel",
        "--log",
        str(base / "resolution_log.jsonl"),
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


def test_ac6_resolution_requires_evidence(base: Path):
    """AC6: a Resolved finding without files+validation is rejected."""
    r = _resolution(base, "--status", "Resolved")
    assert r.returncode == 2
    assert "requires evidence" in r.stderr


def test_ac6_resolution_with_evidence_logs_schema_valid_record(base: Path):
    r = _resolution(base, "--status", "Resolved", "--files", "src/list.py", "--validation", "pytest tests/test_list.py")
    assert r.returncode == 0, r.stderr
    assert "Chromatic Review Resolution" in r.stdout
    records = read_jsonl(base / "resolution_log.jsonl")
    assert len(records) == 1
    validate(records[0], "review_resolution.schema.json")
    assert records[0]["files_changed"] == ["src/list.py"]


# ---------------------------------------------------------------- AC7
def test_ac7_security_and_architecture_are_gated(base: Path):
    """AC7: security/architecture/unclear findings never auto-ready; they need a human."""
    # pull_request_review fixture body mentions a bug → bug_fix; craft security/arch via classifier.
    sys.path.insert(0, str(SCRIPTS))
    from classify_review_finding import enrich_finding, queue_status_for_confidence

    for body, expect_type in [
        ("Please rotate the leaked API secret/token immediately", "security"),
        ("This abstraction couples the architecture boundary; redesign the module", "architecture"),
    ]:
        f = enrich_finding({"body": body, "path": "src/x.py", "dedupe_key": "k"})
        assert f["finding_type"] == expect_type
        status = queue_status_for_confidence(f["confidence_score"], f["finding_type"])
        assert status == "needs-human-decision", f"{expect_type} should be gated, got {status}"


def test_ac7_gated_items_are_not_dispatched(base: Path):
    """A needs-human-decision item must not be picked up by the dispatcher."""
    queue = {
        "items": [
            {
                "id": "NW-SEC",
                "title": "Address review finding RF-SEC on PR #99",
                "status": "needs-human-decision",
                "priority": 80,
                "repo": "owner/repo",
                "pr_number": 99,
                "area": "review-intake",
                "specialties": ["security"],
                "owner_agent": "Sentinel",
                "acceptance_checks": ["x"],
                "links": [],
                "notes": "n",
                "commit_sha": "z",
            }
        ]
    }
    (base / "queue.json").write_text(json.dumps(queue))
    cmd = [
        sys.executable,
        str(SCRIPTS / "dispatch_review_work.py"),
        "--queue",
        str(base / "queue.json"),
        "--lock-dir",
        str(base / "locks"),
        "--packet-dir",
        str(base / "mission_packets"),
        "--dispatch-log",
        str(base / "dispatch_log.jsonl"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    out = json.loads(result.stdout)
    assert out["ready_count"] == 0 and out["dispatched"] == 0


# ---------------------------------------------------------------- AC8
def test_ac8_learning_writer_mines_reviewer_patterns(base: Path):
    """AC8: repeated reviewer feedback becomes a learning artifact; logs are valid JSONL."""
    # Two findings of the same type from the same reviewer → one pattern.
    findings = base / "findings.jsonl"
    rows = [
        {
            "author": "reviewer-x",
            "finding_type": "lint_style",
            "repo": "owner/repo",
            "source": "s",
            "finding_id": "RF1",
            "status": "open",
            "body": "b",
            "dedupe_key": "d1",
            "confidence_score": 80,
            "risk_level": "low",
        },
        {
            "author": "reviewer-x",
            "finding_type": "lint_style",
            "repo": "owner/repo",
            "source": "s",
            "finding_id": "RF2",
            "status": "open",
            "body": "b",
            "dedupe_key": "d2",
            "confidence_score": 80,
            "risk_level": "low",
        },
    ]
    findings.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    cmd = [
        sys.executable,
        str(SCRIPTS / "review_learning.py"),
        "--findings",
        str(findings),
        "--patterns",
        str(base / "reviewer_patterns.jsonl"),
        "--min-count",
        "2",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    patterns = read_jsonl(base / "reviewer_patterns.jsonl")
    assert len(patterns) == 1
    assert patterns[0]["occurrences"] == 2 and patterns[0]["finding_type"] == "lint_style"
