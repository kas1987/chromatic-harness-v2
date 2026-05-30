"""Safety guard tests for claude_delegate_gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "claude_delegate_gate.py"


def test_automation_requires_run_and_task_ids() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--task",
            "Continue malformed bead-id remediation",
            "--bead-id",
            "chromatic-harness-v2-4n4",
            "--invoked-by",
            "automation",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload.get("reason") == "missing_correlation_ids"


def test_destructive_intent_is_blocked_pre_gate() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--task",
            "Please run rm -rf /tmp/build-cache and continue",
            "--bead-id",
            "chromatic-harness-v2-4n4",
            "--invoked-by",
            "preflight",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload.get("reason") == "destructive_intent_blocked"
