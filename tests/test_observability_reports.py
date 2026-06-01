"""OBS-010: observability report + learning-candidate generation.

Hermetic, subprocess-based against a throwaway repo root.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
REPORTER = SCRIPTS / "generate_observability_report.py"
LEARNER = SCRIPTS / "propose_learnings.py"


def _seed(root: Path, events: list[dict]) -> None:
    log = root / "00_META" / "observability" / "ERROR_LOG.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _ev(eid, sev="high", cat="test_failure", status="open", sig="boom", files=None) -> dict:
    return {
        "event_id": eid,
        "timestamp": f"2026-06-01T0{eid[-1]}:00:00Z",
        "severity": sev,
        "category": cat,
        "status": status,
        "error_signature": sig,
        "files_touched": files or [],
        "source": {"surface": "ci"},
    }


def _run(script: Path, root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), "--repo-root", str(root), *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )


# ---- report ---------------------------------------------------------------


def test_report_writes_dated_markdown(tmp_path):
    _seed(tmp_path, [_ev("evt-1"), _ev("evt-2")])
    r = _run(REPORTER, tmp_path)
    assert r.returncode == 0
    out = Path(r.stdout.strip())
    assert out.is_file()
    assert out.suffix == ".md"
    assert "2026-06-01" in out.name or "OBSERVABILITY_REPORT" in out.name


def test_report_includes_required_sections(tmp_path):
    _seed(
        tmp_path,
        [
            _ev("evt-1", sev="critical", sig="sig_a", files=["a.py"]),
            _ev("evt-2", sev="high", sig="sig_a", files=["a.py"]),
        ],
    )
    r = _run(REPORTER, tmp_path)
    text = Path(r.stdout.strip()).read_text(encoding="utf-8")
    assert "Unresolved High / Critical Events" in text
    assert "Repeated Error Signatures" in text
    assert "Files Most Often Touched" in text
    assert "Recommended Next Work" in text
    # Content checks: the repeated signature and noisy file appear.
    assert "sig_a" in text
    assert "a.py" in text


# ---- learning candidates --------------------------------------------------


def test_learner_identifies_repeated_signatures_and_stages(tmp_path):
    _seed(tmp_path, [_ev(f"evt-{i}", sig="recurring") for i in range(4)])
    r = _run(LEARNER, tmp_path, "--threshold", "3")
    assert r.returncode == 0
    staged = Path(r.stdout.strip())
    assert staged.is_file()
    assert "staging" in str(staged)
    assert "recurring" in staged.read_text(encoding="utf-8")
    # Governance: canonical log must NOT be mutated by default.
    assert not (tmp_path / "00_META/observability/LEARNINGS_LOG.md").exists()


def test_learner_below_threshold_emits_nothing(tmp_path):
    _seed(tmp_path, [_ev("evt-1", sig="rare")])
    r = _run(LEARNER, tmp_path, "--threshold", "3")
    assert r.returncode == 0
    assert "No learning candidates" in r.stdout


def test_learner_commit_flag_appends_to_canonical(tmp_path):
    _seed(tmp_path, [_ev(f"evt-{i}", sig="recurring") for i in range(4)])
    r = _run(LEARNER, tmp_path, "--threshold", "3", "--commit")
    assert r.returncode == 0
    canonical = tmp_path / "00_META/observability/LEARNINGS_LOG.md"
    assert canonical.is_file()
    assert "recurring" in canonical.read_text(encoding="utf-8")


def test_learner_tolerates_malformed_jsonl(tmp_path):
    log = tmp_path / "00_META" / "observability" / "ERROR_LOG.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    good = "\n".join(json.dumps(_ev(f"evt-{i}", sig="recurring")) for i in range(3))
    log.write_text("{ broken json\n" + good + "\n", encoding="utf-8")
    r = _run(LEARNER, tmp_path, "--threshold", "3")
    assert r.returncode == 0, r.stderr
    assert "recurring" in Path(r.stdout.strip()).read_text(encoding="utf-8")


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
