"""Pytest suite for review_intake.py and classify_review_finding.py."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "review_intake"
BASE = REPO_ROOT / "07_LOGS_AND_AUDIT" / "review_intake"

sys.path.insert(0, str(SCRIPTS))

from classify_review_finding import (  # noqa: E402
    AGENT_BY_TYPE,
    ACCEPTANCE_BY_TYPE,
    classify_body,
    enrich_finding,
    queue_status_for_confidence,
    score_finding,
    specialties_for_type,
)


def _clear_test_artifacts():
    for name in ["findings.jsonl", "queue.json", "state.json"]:
        path = BASE / name
        if path.exists():
            path.unlink()
    locks = BASE / "locks"
    if locks.exists():
        shutil.rmtree(locks)


@pytest.fixture(autouse=True)
def clean_artifacts():
    _clear_test_artifacts()
    BASE.mkdir(parents=True, exist_ok=True)
    yield
    _clear_test_artifacts()


class TestClassifyReviewFinding:
    def test_classify_body_security(self):
        assert classify_body("Please rotate the API secret") == "security"

    def test_classify_body_test_failure(self):
        assert classify_body("The integration test is failing") == "test_failure"

    def test_classify_body_lint(self):
        assert classify_body("Run ruff on this file") == "lint_style"

    def test_classify_body_docs(self):
        assert classify_body("Update the README") == "docs"

    def test_classify_body_architecture(self):
        assert classify_body("This couples the boundary too tightly") == "architecture"

    def test_classify_body_bug(self):
        assert classify_body("This is a bug in the handler") == "bug_fix"

    def test_classify_body_vague(self):
        assert classify_body("Maybe consider refactoring?") == "unclear"

    def test_classify_body_unclear_fallback(self):
        assert classify_body("Looks good to me") == "unclear"

    def test_score_finding_high_confidence(self):
        finding = {
            "body": "Fix the off-by-one error in src/list.py line 42",
            "path": "src/list.py",
            "dedupe_key": "repo#1:src/list.py:42:123",
        }
        score = score_finding(finding)
        assert 60 <= score <= 100

    def test_score_finding_low_confidence_vague(self):
        finding = {
            "body": "Maybe think about this?",
            "path": None,
            "dedupe_key": None,
        }
        score = score_finding(finding)
        assert 0 <= score < 75

    def test_enrich_finding_sets_fields(self):
        finding = {"body": "Add a docstring here", "path": "src/foo.py", "dedupe_key": "k1"}
        enriched = enrich_finding(finding)
        assert enriched["finding_type"] == "docs"
        assert enriched["suggested_agent"] == "Archivist"
        assert "confidence_score" in enriched
        assert "risk_level" in enriched
        assert "severity" in enriched

    def test_queue_status_for_confidence_ready(self):
        assert queue_status_for_confidence(80, "bug_fix") == "ready"

    def test_queue_status_for_confidence_blocked(self):
        assert queue_status_for_confidence(30, "unclear") == "blocked"

    def test_queue_status_for_confidence_security_human_gate(self):
        assert queue_status_for_confidence(80, "security") == "needs-human-decision"

    def test_specialties_mapping(self):
        assert "security" in specialties_for_type("security")
        assert "triage" in specialties_for_type("unclear")

    def test_agent_by_type_completeness(self):
        for ft in ACCEPTANCE_BY_TYPE:
            assert ft in AGENT_BY_TYPE


class TestReviewIntakeScript:
    def _run_intake(self, event_name: str, event_file: str) -> dict:
        cmd = [
            sys.executable,
            str(SCRIPTS / "review_intake.py"),
            "--event-name", event_name,
            "--event-path", str(FIXTURES / event_file),
            "--findings", str(BASE / "findings.jsonl"),
            "--queue", str(BASE / "queue.json"),
            "--state", str(BASE / "state.json"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def test_pull_request_review_comment(self):
        out = self._run_intake("pull_request_review_comment", "sample_pull_request_review_comment_event.json")
        assert out.get("finding_created") is True
        assert out.get("finding_id", "").startswith("RF-")
        assert out.get("queue_item_id", "").startswith("NW-")

        findings = [json.loads(line) for line in (BASE / "findings.jsonl").read_text().splitlines() if line.strip()]
        assert len(findings) == 1
        assert findings[0]["source"] == "github_pr_review_comment"
        assert findings[0]["finding_type"] == "test_failure"

        queue = json.loads((BASE / "queue.json").read_text())
        assert len(queue["items"]) == 1
        assert queue["items"][0]["source_finding_id"] == findings[0]["finding_id"]

    def test_dedupe_same_event_twice(self):
        self._run_intake("pull_request_review_comment", "sample_pull_request_review_comment_event.json")
        out2 = self._run_intake("pull_request_review_comment", "sample_pull_request_review_comment_event.json")
        assert out2.get("finding_created") is False

        findings = [json.loads(line) for line in (BASE / "findings.jsonl").read_text().splitlines() if line.strip()]
        assert len(findings) == 1

    def test_check_run_event(self):
        out = self._run_intake("check_run", "sample_check_run_event.json")
        assert out.get("finding_created") is True
        findings = [json.loads(line) for line in (BASE / "findings.jsonl").read_text().splitlines() if line.strip()]
        assert any(f["source"] == "github_check_run" for f in findings)


class TestLockPrBranch:
    def _run_lock(self, *args) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPTS / "lock_pr_branch.py"), *args, "--lock-dir", str(BASE / "locks")]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)

    def test_acquire_and_release(self):
        r1 = self._run_lock("acquire", "--repo", "owner/repo", "--pr-number", "42", "--holder", "Sentinel", "--queue-item-id", "NW-1")
        assert r1.returncode == 0
        data = json.loads(r1.stdout)
        assert data["acquired"] is True

        r2 = self._run_lock("status", "--repo", "owner/repo", "--pr-number", "42")
        assert r2.returncode == 0
        assert "lock_id" in r2.stdout

        r3 = self._run_lock("acquire", "--repo", "owner/repo", "--pr-number", "42", "--holder", "Auditor", "--queue-item-id", "NW-2")
        assert r3.returncode == 2
        data3 = json.loads(r3.stdout)
        assert data3["acquired"] is False

        r4 = self._run_lock("release", "--repo", "owner/repo", "--pr-number", "42")
        assert r4.returncode == 0

        r5 = self._run_lock("acquire", "--repo", "owner/repo", "--pr-number", "42", "--holder", "Auditor", "--queue-item-id", "NW-2")
        assert r5.returncode == 0
        data5 = json.loads(r5.stdout)
        assert data5["acquired"] is True


class TestPostReviewResolution:
    def test_generates_comment(self):
        cmd = [
            sys.executable,
            str(SCRIPTS / "post_review_resolution.py"),
            "--finding", "RF-ABC123",
            "--task", "NW-XYZ789",
            "--agent", "Sentinel",
            "--status", "Resolved",
            "--confidence", "92",
            "--change", "Fixed off-by-one error.",
            "--files", "src/list.py",
            "--validation", "pytest tests/test_list.py",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode == 0
        assert "Chromatic Review Resolution" in result.stdout
        assert "RF-ABC123" in result.stdout
        assert "src/list.py" in result.stdout
        assert "pytest tests/test_list.py" in result.stdout
