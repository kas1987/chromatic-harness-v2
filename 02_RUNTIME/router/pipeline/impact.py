"""Classify stage: codegraph blast-radius fan-out fed to the complexity classifier.

Env-gated OFF by default (ROUTER_CODEGRAPH_IMPACT=false) to protect the
PreToolUse hot path. Always fail-open — any error returns None, letting the
classifier fall back to its keyword path unchanged.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

IMPACT_ENABLED = os.environ.get("ROUTER_CODEGRAPH_IMPACT", "false").lower() == "true"
IMPACT_TIMEOUT = float(os.environ.get("ROUTER_CODEGRAPH_IMPACT_TIMEOUT", "3"))
_FILE_REF = r"[\w./\\-]+\.(?:py|ts|tsx|js|jsx|yaml|yml|json|md|sh|ps1)"

# Resolved lazily so this module can be imported without a git context.
_REPO: Path | None = None


def _repo() -> Path:
    global _REPO
    if _REPO is None:
        _REPO = Path(__file__).resolve().parents[3]
    return _REPO


def extract_file_refs(text: str) -> list[str]:
    """Return repo-relative file references that exist on disk."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(_FILE_REF, text or ""):
        ref = raw.strip("`\"'()[],")
        norm = ref.replace("\\", "/")
        if norm in seen:
            continue
        if (_repo() / norm).is_file():
            seen.add(norm)
            out.append(norm)
    return out


def count_impacted(stdout: str) -> int:
    """Count distinct path-like lines in codegraph impact output."""
    paths = {ln.strip() for ln in (stdout or "").splitlines() if ln.strip() and ("/" in ln or "\\" in ln or "." in ln)}
    return len(paths)


def _default_runner(files: list[str]) -> str:
    proc = subprocess.run(
        ["codegraph", "impact", "--stdin"],
        cwd=str(_repo()),
        input="\n".join(files),
        capture_output=True,
        text=True,
        timeout=IMPACT_TIMEOUT,
        check=False,
    )
    return proc.stdout or ""


def impact_fan_out(description: str, prompt: str, runner=None) -> int | None:
    """Real codegraph blast radius for files the task references, else None.

    None → no evidence; classifier uses keyword path unchanged.
    """
    if not IMPACT_ENABLED:
        return None
    try:
        refs = extract_file_refs(f"{description}\n{prompt}")
        if not refs:
            return None
        run = runner or _default_runner
        count = count_impacted(run(refs))
        return max(count, len(refs))
    except Exception:
        return None
