"""Self-healing repo format hygiene tests.

These tests guard against configuration regressions that cause CI format
failures which are hard to diagnose in a PR loop:

1. .gitattributes must pin *.py to LF so Windows autocrlf cannot inject CRLF
   into Python files (black/ruff reformat CRLF files, causing spurious CI failures).
2. The CI format-check step must use ``ruff format``, not ``black``.
   The two formatters produce subtly different output; using black locally
   while CI runs ruff leads to repeated format failures.
3. Hook directories that contain bash scripts must also be pinned to LF so
   the shebang line isn't corrupted on Windows checkout.
4. All Python files in src/ and tests/ must be ruff-formatted. This test
   self-heals on local runs: it applies ruff format + LF-normalises in place
   then passes, so the push continues and the fixes land as unstaged changes.
   On CI it fails with the file list and the fix command.

Root cause of 2026-06-03 PR #259 format failures: ran ``python -m black``
locally, but CI runs ``ruff format --check``.  Two pushes wasted on format
commits before diagnosing the mismatch.  The whack-a-mole recurred on P2/P3/P4
additions to test_usage_calibration.py that were not ruff-formatted before push.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GITATTRIBUTES = REPO / ".gitattributes"
CI_WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


# ---------------------------------------------------------------------------
# .gitattributes LF pins
# ---------------------------------------------------------------------------


def test_gitattributes_pins_python_to_lf():
    """*.py must be pinned to eol=lf so Windows autocrlf never injects CRLF."""
    text = GITATTRIBUTES.read_text(encoding="utf-8")
    assert "*.py text eol=lf" in text, (
        ".gitattributes is missing '*.py text eol=lf'. "
        "Without this, Windows autocrlf injects CRLF into Python files, "
        "which ruff format on the Linux CI runner will then reformat, "
        "causing spurious format-check CI failures."
    )


def test_gitattributes_pins_git_hooks_to_lf():
    """Bash hook scripts must be LF — CRLF breaks the shebang on Git Bash."""
    text = GITATTRIBUTES.read_text(encoding="utf-8")
    assert "git_hooks/**" in text and "eol=lf" in text, (
        ".gitattributes should pin git_hooks/** to eol=lf to prevent CRLF shebang corruption on Windows checkout."
    )


# ---------------------------------------------------------------------------
# CI format step uses ruff, not black
# ---------------------------------------------------------------------------


def test_ci_format_check_uses_ruff_format():
    """The CI format-check step must run 'ruff format --check', not black.

    black and ruff format produce subtly different output.  Running black
    locally then pushing will fail CI because the CI runner uses ruff.
    Always run 'python -m ruff format <files>' before committing.
    """
    assert CI_WORKFLOW.exists(), f"CI workflow not found: {CI_WORKFLOW}"
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "ruff format --check" in text, (
        "CI workflow does not contain 'ruff format --check'. "
        "If the format step changed, update tests and the bd memory "
        "'ruff-format-not-black-ci-uses-ruff' accordingly."
    )
    # Ensure black isn't the format gate (it's fine as an optional dep but
    # must not be the authoritative format check).
    lines_with_black = [
        line.strip()
        for line in text.splitlines()
        if "black" in line and "--check" in line and not line.strip().startswith("#")
    ]
    assert not lines_with_black, (
        "CI workflow contains a 'black --check' step; "
        "the authoritative format gate should be 'ruff format --check'. "
        f"Offending lines: {lines_with_black}"
    )


def test_ci_uses_ruff_check_for_lint():
    """Sanity-check: CI also runs ruff check (linting) — keep them paired."""
    assert CI_WORKFLOW.exists(), f"CI workflow not found: {CI_WORKFLOW}"
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "ruff check" in text, "CI workflow does not contain 'ruff check'. Lint gate may have regressed."


# ---------------------------------------------------------------------------
# Actual format compliance — self-heals locally, fails on CI
# ---------------------------------------------------------------------------


def test_all_python_files_are_ruff_formatted():
    """src/ and tests/ Python files must be ruff-formatted.

    Self-heal behaviour (local runs, CI env var not set):
      Applies ``ruff format`` + LF-normalises on Windows, then passes.
      The fixed files appear as unstaged changes — stage and commit them.

    CI behaviour (CI=true):
      Fails with the list of unformatted files and the command to fix them.

    This prevents the whack-a-mole pattern where feature commits add new
    Python code that isn't ruff-formatted before push (PR #259 hit this
    three times across the P2/P3/P4 usage-calibration additions).
    """
    check = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "src/", "tests/"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return  # all files already formatted

    bad_files = [
        line.split("Would reformat: ", 1)[-1].strip() for line in check.stdout.splitlines() if "Would reformat" in line
    ]

    on_ci = os.environ.get("CI", "").lower() in ("true", "1")

    if not on_ci:
        # Auto-heal: reformat in place.
        subprocess.run(
            [sys.executable, "-m", "ruff", "format"] + bad_files,
            cwd=REPO,
            check=False,
        )
        # LF-normalise on Windows so git doesn't stage CRLF.
        if platform.system() == "Windows":
            for rel in bad_files:
                p = REPO / rel.replace("\\", "/")
                if p.exists():
                    p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
        # Pass — the files are now fixed; the developer's push continues.
        # Fixed files will appear as unstaged changes in `git status`.
        return

    # On CI we cannot commit, so fail with an actionable message.
    import pytest

    pytest.fail(
        f"ruff format found {len(bad_files)} unformatted file(s):\n"
        + "\n".join(f"  {f}" for f in bad_files)
        + "\nFix locally:\n"
        + "  python -m ruff format src/ tests/\n"
        + "  # on Windows also LF-normalise, then:\n"
        + "  git add <files> && git commit -m 'style: ruff format'"
    )
