"""OBS-005: harness_run.py wraps commands, preserves exit codes, logs failures.

Hermetic, subprocess-based against a throwaway repo root so the wrapper's own
observability writes never touch the real tree.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WRAPPER = REPO / "scripts" / "harness_run.py"
ERROR_LOG = "00_META/observability/ERROR_LOG.jsonl"


def _run(root: Path, *wrapper_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WRAPPER), "--repo-root", str(root), *wrapper_args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _events(root: Path) -> list[dict]:
    p = root / ERROR_LOG
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def test_successful_command_logs_nothing_and_exits_zero(tmp_path):
    r = _run(tmp_path, "--", sys.executable, "-c", "print('ok')")
    assert r.returncode == 0
    assert "ok" in r.stdout
    assert _events(tmp_path) == []


def test_failed_command_creates_error_log_entry(tmp_path):
    r = _run(tmp_path, "--", sys.executable, "-c", "import sys; sys.exit(3)")
    assert r.returncode == 3  # original exit code preserved
    evs = _events(tmp_path)
    assert len(evs) == 1
    assert evs[0]["event_type"] == "command_result"
    assert evs[0]["exit_code"] == 3
    assert evs[0]["error_signature"] == "command_failed_exit_3"


def test_wrapper_preserves_arbitrary_exit_code(tmp_path):
    r = _run(tmp_path, "--", sys.executable, "-c", "import sys; sys.exit(42)")
    assert r.returncode == 42
    assert _events(tmp_path)[0]["exit_code"] == 42


def test_excerpt_is_redacted_before_logging(tmp_path):
    # Emit a token-shaped secret to stderr then fail.
    prog = "import sys; sys.stderr.write('ghp_' + 'A' * 36 + '\\n'); sys.exit(1)"
    r = _run(tmp_path, "--", sys.executable, "-c", prog)
    assert r.returncode == 1
    ev = _events(tmp_path)[0]
    assert ev["redacted"] is True
    assert "ghp_" + "A" * 36 not in ev["raw_excerpt"]


def test_no_command_returns_2(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 2
    assert "No command provided" in r.stderr


def test_empty_command_after_separator_returns_2(tmp_path):
    r = _run(tmp_path, "--")
    assert r.returncode == 2
    assert "No command provided" in r.stderr


def test_missing_binary_returns_127_and_logs(tmp_path):
    r = _run(tmp_path, "--", "definitely-not-a-real-binary-xyz")
    assert r.returncode == 127
    ev = _events(tmp_path)[0]
    assert ev["exit_code"] == 127
    assert ev["error_signature"] == "command_not_found"


def test_route_flag_invokes_router_for_failure(tmp_path):
    (tmp_path / "00_META" / "queues").mkdir(parents=True, exist_ok=True)
    r = _run(
        tmp_path,
        "--severity-on-fail",
        "high",
        "--category-on-fail",
        "test_failure",
        "--route",
        "--",
        sys.executable,
        "-c",
        "import sys; sys.exit(1)",
    )
    assert r.returncode == 1
    ev = _events(tmp_path)[0]
    q = tmp_path / "00_META/queues/ERROR_REMEDIATION_QUEUE.md"
    assert q.is_file()
    assert ev["event_id"] in q.read_text(encoding="utf-8")


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
