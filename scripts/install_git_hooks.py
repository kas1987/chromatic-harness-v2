#!/usr/bin/env python3
"""Install repo-tracked git hooks (hooks/) into .git/hooks, idempotently.

Wires the local CI gates (scripts/ci_local.py) into pre-commit (fast) and pre-push
(full). Any pre-existing pre-push hook — e.g. the global E2E delegate — is preserved
as `pre-push.prior` and chained, so nothing is lost.

Usage:
  python scripts/install_git_hooks.py            # install
  python scripts/install_git_hooks.py --check    # report status, change nothing
"""

from __future__ import annotations

import argparse
import shutil
import stat
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "hooks"


def _git_hooks_dir() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    p = Path(out)
    return p if p.is_absolute() else _REPO / p


def _make_exec(p: Path) -> None:
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _is_managed_dir(hooks_dir: Path) -> bool:
    """True if the hooks dir is git-tracked or beads-managed (do not clobber it)."""
    try:
        tracked = (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(hooks_dir / "pre-commit")],
                cwd=_REPO,
                capture_output=True,
                text=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        tracked = False
    pc = hooks_dir / "pre-commit"
    beads = pc.is_file() and "BEADS INTEGRATION" in pc.read_text(
        encoding="utf-8", errors="ignore"
    )
    return tracked or beads


def install(check: bool = False) -> dict[str, str]:
    hooks_dir = _git_hooks_dir()
    hooks_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, str] = {}

    # Safety: never overwrite a git-tracked / beads-managed hooks dir (e.g. when
    # core.hooksPath points at .beads/hooks). Doing so would shadow the secrets
    # scrub. Advise manual wiring instead.
    if _is_managed_dir(hooks_dir):
        report["status"] = (
            f"refused: {hooks_dir} is git-tracked/beads-managed. Run gates manually "
            "(python scripts/ci_local.py --stage pre-commit) or append a ci_local call "
            "after the beads-managed block."
        )
        return report

    for name in ("pre-commit", "pre-push"):
        src = _SRC / name
        if not src.is_file():
            report[name] = "source-missing"
            continue
        dst = hooks_dir / name
        # Preserve a foreign pre-push (e.g. the global E2E delegate) for chaining.
        if (
            name == "pre-push"
            and dst.exists()
            and "ci_local.py" not in dst.read_text(encoding="utf-8", errors="ignore")
        ):
            prior = hooks_dir / "pre-push.prior"
            if check:
                report["pre-push.prior"] = "would-preserve"
            else:
                shutil.copy2(dst, prior)
                _make_exec(prior)
                report["pre-push.prior"] = "preserved"
        if check:
            cur = (
                dst.read_text(encoding="utf-8", errors="ignore") if dst.exists() else ""
            )
            report[name] = (
                "up-to-date"
                if cur == src.read_text(encoding="utf-8")
                else "would-install"
            )
            continue
        shutil.copy2(src, dst)
        _make_exec(dst)
        report[name] = "installed"
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="Install repo git hooks")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    report = install(check=args.check)
    width = max((len(k) for k in report), default=0)
    for k, v in report.items():
        print(f"  {k.ljust(width)} : {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
