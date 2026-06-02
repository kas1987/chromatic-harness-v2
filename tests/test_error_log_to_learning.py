"""OMH-5: error-log -> learning-flywheel auto-feed.

Hermetic, subprocess-based against a throwaway repo root. Verifies failure
filtering, bd-remember-ready staging, governance (read-only / dry-run), and
that already-promoted signatures are not re-proposed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "error_log_to_learning.py"


def _seed(root: Path, events: list[dict]) -> None:
    log = root / "00_META" / "observability" / "ERROR_LOG.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _ev(eid, sev="high", cat="test_failure", status="open", sig="boom", surface="ci", exit_code=1, **extra) -> dict:
    rec = {
        "event_id": eid,
        "timestamp": f"2026-06-01T00:00:0{eid[-1]}Z",
        "severity": sev,
        "category": cat,
        "status": status,
        "error_signature": sig,
        "exit_code": exit_code,
        "files_touched": extra.pop("files", []),
        "source": {"surface": surface},
    }
    rec.update(extra)
    return rec


def _run(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(root), *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_dry_run_writes_nothing_and_reports_candidates(tmp_path):
    _seed(tmp_path, [_ev(f"evt-{i}", sig="ci_timeout") for i in range(3)])
    r = _run(tmp_path, "--dry-run", "--threshold", "2")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["candidate_count"] == 1
    cand = payload["candidates"][0]
    assert cand["signature"] == "ci_timeout" and cand["occurrences"] == 3
    assert cand["bd_remember_command"][:2] == ["bd", "remember"]
    assert cand["bd_remember_command"][-2:] == ["--key", cand["key"]]
    # Governance: dry-run stages nothing.
    assert not (tmp_path / "00_META/observability/staging").exists()


def test_stages_md_and_jsonl_with_bd_remember_command(tmp_path):
    _seed(
        tmp_path,
        [
            _ev(f"evt-{i}", sig="lock_toctou", cat="file_collision", suspected_cause="race", linked_fix="add flock")
            for i in range(2)
        ],
    )
    r = _run(tmp_path, "--threshold", "2")
    assert r.returncode == 0, r.stderr
    md = Path(r.stdout.strip())
    assert md.is_file() and "staging" in str(md)
    body = md.read_text(encoding="utf-8")
    assert "lock_toctou" in body and "bd remember" in body and "race" in body
    jsonl = md.parent / md.name.replace("LEARNING_FROM_ERRORS_", "learning_candidates_").replace(".md", ".jsonl")
    assert jsonl.is_file()
    rec = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])
    assert rec["fix_applied"] == "add flock" and rec["suggested_priority"] == "P1"


def test_filters_out_resolved_info_events(tmp_path):
    _seed(
        tmp_path,
        [
            _ev("evt-1", sev="info", cat="manual_note", status="resolved", sig="bootstrap", exit_code=0),
            _ev("evt-2", sev="info", cat="manual_note", status="resolved", sig="bootstrap", exit_code=0),
        ],
    )
    r = _run(tmp_path, "--dry-run", "--threshold", "2")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["candidate_count"] == 0


def test_below_threshold_emits_nothing(tmp_path):
    _seed(tmp_path, [_ev("evt-1", sig="rare")])
    r = _run(tmp_path, "--threshold", "2")
    assert r.returncode == 0
    assert "No learning candidates" in r.stdout


def test_skips_already_promoted_signatures(tmp_path):
    _seed(tmp_path, [_ev(f"evt-{i}", sig="known_flake") for i in range(3)])
    canonical = tmp_path / "00_META/observability/LEARNINGS_LOG.md"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("- Pattern `known_flake` already captured.\n", encoding="utf-8")
    r = _run(tmp_path, "--dry-run", "--threshold", "2")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["candidate_count"] == 0


def test_tolerates_malformed_jsonl(tmp_path):
    log = tmp_path / "00_META" / "observability" / "ERROR_LOG.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    good = "\n".join(json.dumps(_ev(f"evt-{i}", sig="recurring")) for i in range(2))
    log.write_text("{ broken json\n" + good + "\n", encoding="utf-8")
    r = _run(tmp_path, "--dry-run", "--threshold", "2")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["candidate_count"] == 1


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
