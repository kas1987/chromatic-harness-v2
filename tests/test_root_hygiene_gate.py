"""OMH-7: root-allowlist hygiene gate."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "root_hygiene_gate.py"
_spec = importlib.util.spec_from_file_location("root_hygiene_gate", SCRIPT)
rhg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rhg)  # type: ignore


def test_dotfiles_and_allowlisted_are_clean():
    files = [".gitignore", ".coveragerc", "README.md", "pyproject.toml"]
    assert rhg.find_violations(files) == []


def test_scratch_files_are_flagged():
    files = ["README.md", "INTEGRATION_TEST.ts", "hook_audit.json", "_v3_beads.ps1"]
    assert rhg.find_violations(files) == sorted(["INTEGRATION_TEST.ts", "hook_audit.json", "_v3_beads.ps1"])


def test_live_repo_root_is_clean():
    """The real repo root must pass the gate (bead acceptance: the script runs clean)."""
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"root not clean:\n{r.stdout}\n{r.stderr}"


def test_removed_scratch_no_longer_tracked():
    tracked = rhg._tracked_top_level()
    for scratch in ("INTEGRATION_TEST.ts", "hook_audit.json", "_v3_bead_map.json", "_v3_beads.ps1"):
        assert scratch not in tracked


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
