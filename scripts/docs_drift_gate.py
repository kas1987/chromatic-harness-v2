#!/usr/bin/env python3
"""Documentation drift gate (bead gh-58 / chromatic-harness-v2).

Covers the eval requirement:
  1. Detect API/interface changes without docs updates.

Behavior:
- From the git diff (vs merge-base), identify changed Python files under
  scripts/ and src/ that ADD or MODIFY public interface lines (def, class,
  async def for non-underscore names).
- Determine whether docs were updated: any changed file under docs/, any
  *.md file, or a changed docstring in the diff.
- Interface changes with NO doc/markdown changes => risk "warn" (exit 0)
  or "fail" with --strict (exit 1).

Exit codes: 0 = ok/warn, 1 = fail (only when --strict and drift detected).

Usage:
    python scripts/docs_drift_gate.py
    python scripts/docs_drift_gate.py --base main
    python scripts/docs_drift_gate.py --strict
    python scripts/docs_drift_gate.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "docs_drift"
DEFAULT_BASE = os.environ.get("DOCS_GATE_BASE", "origin/session/chromatic-harness-v2-initial")

# Python source directories to watch for interface changes.
INTERFACE_DIRS = ("scripts/", "src/")

# Regex for public interface lines in unified diff output.
# Matches added or removed lines (+ or -) with def/class/async def for public names.
_INTERFACE_RE = re.compile(r"^[+-][ \t]*(async def |def |class )([A-Za-z][A-Za-z0-9_]*)\b")

# Docstring change indicator in diff (added/removed triple-quote lines).
_DOCSTRING_RE = re.compile(r'^[+-]\s*"""')


def _run(cmd: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def _merge_base(base: str) -> str:
    code, out = _run(["git", "merge-base", "HEAD", base])
    return out.strip() if code == 0 and out.strip() else base


def extract_interface_changes(diff_text: str) -> list[dict]:
    """Pure function: parse unified diff text, return public interface changes.

    Returns a list of dicts with keys: file, kind (def/class/async def), name,
    change (added/removed).

    Rules:
    - Only processes files under INTERFACE_DIRS (scripts/, src/).
    - Only matches public names (no leading underscore).
    - Ignores context lines (lines starting with space) and diff headers.
    """
    results: list[dict] = []
    current_file: str | None = None

    for line in diff_text.splitlines():
        # Detect file header: +++ b/path or --- a/path
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            path = line[6:]
            if any(path.startswith(d) for d in INTERFACE_DIRS) and path.endswith(".py"):
                current_file = path
            else:
                current_file = None
            continue

        if current_file is None:
            continue

        # Skip context lines and diff chunk headers.
        if not line or line[0] not in ("+", "-") or line.startswith("+++") or line.startswith("---"):
            continue

        m = _INTERFACE_RE.match(line)
        if not m:
            continue

        keyword = m.group(1).strip()  # "def", "class", or "async def"
        name = m.group(2)

        # Skip private/dunder names.
        if name.startswith("_"):
            continue

        change = "added" if line[0] == "+" else "removed"
        results.append({"file": current_file, "kind": keyword, "name": name, "change": change})

    return results


def _get_full_diff(ref: str) -> str:
    """Return the full unified diff from merge-base to HEAD."""
    code, out = _run(["git", "diff", f"{ref}...HEAD"], timeout=60)
    return out if code == 0 else ""


def _get_numstat(ref: str) -> list[str]:
    """Return list of changed file paths (numstat)."""
    code, out = _run(["git", "diff", "--numstat", f"{ref}...HEAD"], timeout=30)
    paths: list[str] = []
    if code != 0:
        return paths
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            paths.append(parts[2])
    return paths


def _docs_updated(changed_paths: list[str], diff_text: str) -> bool:
    """Return True if docs were changed: docs/ dir, any .md file, or docstring delta."""
    for path in changed_paths:
        if path.startswith("docs/") or path.endswith(".md"):
            return True
    # Check for docstring changes in the diff.
    if _DOCSTRING_RE.search(diff_text):
        return True
    return False


def collect_and_assess(base: str, *, strict: bool) -> dict:
    ref = _merge_base(base)
    changed_paths = _get_numstat(ref)
    diff_text = _get_full_diff(ref)

    interface_changes = extract_interface_changes(diff_text)
    docs_changed = _docs_updated(changed_paths, diff_text)

    has_drift = len(interface_changes) > 0 and not docs_changed

    if has_drift and strict:
        risk_level = "fail"
    elif has_drift:
        risk_level = "warn"
    else:
        risk_level = "ok"

    passed = risk_level != "fail"

    return {
        "base": ref,
        "interface_changes": interface_changes,
        "interface_change_count": len(interface_changes),
        "docs_updated": docs_changed,
        "has_drift": has_drift,
        "risk_level": risk_level,
        "passed": passed,
        "strict": strict,
    }


def write_artifact(result: dict, timestamp: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    latest = ARTIFACT_DIR / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


def summarize() -> dict:
    """For the closeout report -- reads the latest artifact (fail-open)."""
    try:
        latest = ARTIFACT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "passed": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "passed": data.get("passed"),
            "interface_changes": data.get("interface_change_count", 0),
            "docs_updated": data.get("docs_updated"),
            "risk_level": data.get("risk_level"),
            "timestamp": data.get("timestamp"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "passed": None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Documentation drift gate (gh-58)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="Base ref for diff")
    ap.add_argument("--strict", action="store_true", help="Exit 1 on drift (default: warn only)")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default="", help="ISO timestamp override")
    args = ap.parse_args()

    ts = args.timestamp
    if not ts:
        import datetime

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = collect_and_assess(args.base, strict=args.strict)
    artifact = write_artifact(result, ts)

    print("docs drift gate:")
    print(f"  interface changes: {result['interface_change_count']}")
    print(f"  docs updated:      {result['docs_updated']}")
    print(f"  risk level:        {result['risk_level'].upper()}")
    if result["interface_changes"]:
        for ic in result["interface_changes"][:20]:
            print(f"    [{ic['change']}] {ic['kind']} {ic['name']} @ {ic['file']}")
    print(f"  artifact:          {artifact}")

    sep = "=" * 60
    if result["risk_level"] == "fail":
        print(f"\n{sep}\ndocs drift gate: FAIL -- interface changed, no docs update\n{sep}")
    elif result["risk_level"] == "warn":
        print(f"\n{sep}\ndocs drift gate: WARN -- interface changed, no docs update (use --strict to fail)\n{sep}")
    else:
        print(f"\n{sep}\ndocs drift gate: OK\n{sep}")

    if args.json:
        print(json.dumps(result, indent=2))

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
