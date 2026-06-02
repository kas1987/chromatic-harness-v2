"""Tests for claude_delegate_gate spawn hardening (follow-up to bead d3ti).

Verifies the headless-spawn argv passes the prompt CONTENT (never an `@file`
reference, which `claude -p` would take literally), that full autonomy is opt-in,
and that a prompt carrying a destructive directive is refused before spawn.
Network-free: claude is never invoked.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    # The gate self-bootstraps scripts/ and 02_RUNTIME/ onto sys.path at import.
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("claude_delegate_gate", REPO / "scripts" / "claude_delegate_gate.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["claude_delegate_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


G = _load()


def test_spawn_cmd_passes_prompt_content_not_at_file():
    cmd = G._build_spawn_cmd("Implement bead X.\nDo the work.", autonomous=False)
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[2] == "Implement bead X.\nDo the work."  # the CONTENT, verbatim
    assert "--output-format" in cmd and "text" in cmd
    # No argument is an @file reference (the original bug).
    assert not any(str(a).startswith("@") for a in cmd)
    # Autonomy is NOT granted unless asked.
    assert "--dangerously-skip-permissions" not in cmd


def test_spawn_cmd_autonomy_is_opt_in():
    cmd = G._build_spawn_cmd("prompt", autonomous=True)
    assert "--dangerously-skip-permissions" in cmd


def test_destructive_prompt_is_detected():
    assert G._prompt_has_destructive("Please run rm -rf /tmp/build-cache and continue")
    assert G._prompt_has_destructive("then git push --force to main")
    assert G._prompt_has_destructive("git reset --hard HEAD~5")
    assert not G._prompt_has_destructive("Refactor the router into pure functions and add tests")
