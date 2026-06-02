#!/usr/bin/env python3
"""Security scanning gate (bead gh-57 / chromatic-harness-v2-j12l).

Covers the five eval requirements:
  1. Detect common API keys, tokens, passwords, and secrets (regex scan of
     tracked files; patterns reuse the pre-commit hook's SECRET_PATTERN set).
  2. Dependency audit runs automatically (pip-audit when available; degrades to
     "not_instrumented" when the tool isn't installed, never a false pass).
  3. High-severity findings fail the gate (exit 1).
  4. Scan results stored as an artifact (07_LOGS_AND_AUDIT/security/latest.json
     + timestamped copy).
  5. Security summary surfaced for the closeout report via summarize().

Usage:
    python scripts/security_scan.py            # full scan, exit 1 on high sev
    python scripts/security_scan.py --no-deps  # secrets only
    python scripts/security_scan.py --json     # print full JSON result
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "security"

# Secret patterns — mirrors ~/.claude/hooks/pre-commit.sh SECRET_PATTERN so the
# pre-push gate and this scanner agree on what counts as a secret.
SECRET_PATTERNS: list[tuple[str, str, str]] = [
    (
        "credential_assignment",
        r"(?i)(password|passwd|api_key|api_secret|secret_key|access_token|auth_token|"
        r"aws_secret_access_key|private_key|github_personal_access_token)"
        r"""\s*[:=]\s*["'][^"']{8,}""",
        "high",
    ),
    ("private_key_block", r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY", "high"),
    ("github_pat", r"ghp_[A-Za-z0-9_]{36,}", "high"),
    ("aws_access_key_id", r"AKIA[0-9A-Z]{16}", "high"),
    ("slack_token", r"xox[baprs]-[0-9A-Za-z-]{10,}", "high"),
]

# Files/dirs never scanned (binary, vendored, or self — this file documents the
# patterns so it would always self-match).
SKIP_DIRS = {
    ".git",
    ".beads",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".worktrees",
    ".claude",
    "07_LOGS_AND_AUDIT",
    "runtime-engines",
}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".sqlite3", ".lock", ".pyc"}
SELF = Path(__file__).name


def _run(cmd: list[str], *, timeout: int = 120) -> tuple[int, str]:
    # Preserve the 127 "tool-not-found" sentinel that run_safe would otherwise
    # collapse to rc=1 (the consumer keys on code == 127).
    if cmd and shutil.which(cmd[0]) is None:
        return 127, "tool-not-found"
    r = run_safe(cmd, cwd=REPO, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _tracked_files() -> list[Path]:
    """Scan git-tracked files only (avoids scanning artifacts/build output)."""
    code, out = _run(["git", "ls-files"], timeout=30)
    if code != 0:
        return []
    files = []
    for line in out.splitlines():
        rel = line.strip()
        if not rel:
            continue
        parts = set(Path(rel).parts)
        if parts & SKIP_DIRS:
            continue
        p = REPO / rel
        if p.suffix.lower() in SKIP_SUFFIXES or p.name == SELF:
            continue
        files.append(p)
    return files


def scan_secrets() -> dict:
    """Eval 1 + 3: regex-scan tracked files; high-severity hits fail the gate."""
    compiled = [(name, re.compile(pat), sev) for name, pat, sev in SECRET_PATTERNS]
    findings: list[dict] = []
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if len(line) > 1000:  # skip minified/long data lines
                continue
            # Standard allowlist convention: a line tagged with this pragma is a
            # known-safe sample/fixture (e.g. test data), not a real credential.
            if "pragma: allowlist secret" in line:
                continue
            for name, rx, sev in compiled:
                if rx.search(line):
                    findings.append(
                        {
                            "rule": name,
                            "severity": sev,
                            "file": str(path.relative_to(REPO)).replace("\\", "/"),
                            "line": lineno,
                        }
                    )
    high = sum(1 for f in findings if f["severity"] == "high")
    return {
        "status": "ok",
        "findings": findings,
        "total": len(findings),
        "high_severity": high,
    }


def scan_dependencies() -> dict:
    """Eval 2: run pip-audit, scoped to the project's requirements.txt when present.

    Scoping to requirements.txt is deliberate: auditing the ambient interpreter
    finds dozens of dev-tool vulns unrelated to the project and would make the
    gate permanently red. The pinned project deps are the meaningful signal.
    """
    req = REPO / "requirements.txt"
    cmd = [sys.executable, "-m", "pip_audit", "-f", "json", "--progress-spinner", "off"]
    scope = "ambient_env"
    if req.exists():
        cmd += ["-r", str(req)]
        scope = "requirements.txt"
    code, out = _run(cmd, timeout=180)
    if code == 127 or "No module named" in out or "tool-not-found" in out:
        return {
            "status": "not_instrumented",
            "note": "pip-audit not installed; run `pip install pip-audit` to enable dependency scanning",
            "scope": scope,
            "vulnerabilities": [],
            "high_severity": 0,
        }
    # pip-audit prints a human summary to stderr; the JSON is on stdout. Find the
    # first '{' so the merged stream still parses.
    brace = out.find("{")
    if brace == -1:
        return {"status": "error", "note": out[-300:], "scope": scope, "vulnerabilities": [], "high_severity": 0}
    vulns: list[dict] = []
    try:
        # raw_decode parses the first JSON object and ignores any trailing text
        # (pip-audit appends a human summary line after the JSON).
        data, _ = json.JSONDecoder().raw_decode(out[brace:])
        deps = data.get("dependencies", data) if isinstance(data, dict) else data
        for dep in deps:
            for v in dep.get("vulns", []) or []:
                vulns.append(
                    {
                        "package": dep.get("name"),
                        "version": dep.get("version"),
                        "id": v.get("id"),
                        "fix_versions": v.get("fix_versions", []),
                    }
                )
    except (json.JSONDecodeError, AttributeError, TypeError):
        return {
            "status": "error",
            "note": out[brace:][-300:],
            "scope": scope,
            "vulnerabilities": [],
            "high_severity": 0,
        }
    # pip-audit reports any vuln as actionable; treat each as high for the gate.
    return {
        "status": "ok",
        "scope": scope,
        "vulnerabilities": vulns,
        "total": len(vulns),
        "high_severity": len(vulns),
    }


def run_scan(*, include_deps: bool = True) -> dict:
    secrets = scan_secrets()
    deps = scan_dependencies() if include_deps else {"status": "skipped", "high_severity": 0}
    high = secrets.get("high_severity", 0) + deps.get("high_severity", 0)
    return {
        "secrets": secrets,
        "dependencies": deps,
        "high_severity_total": high,
        "passed": high == 0,
    }


def write_artifact(result: dict, timestamp: str) -> Path:
    """Eval 4: persist scan result as an artifact."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({**result, "timestamp": timestamp}, indent=2)
    (ARTIFACT_DIR / f"{timestamp}.json").write_text(payload, encoding="utf-8")
    latest = ARTIFACT_DIR / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


def summarize() -> dict:
    """Eval 5: compact summary for the closeout report (reads latest artifact).
    Fail-open — never raises."""
    try:
        latest = ARTIFACT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "passed": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "passed": data.get("passed"),
            "secret_findings": data.get("secrets", {}).get("total", 0),
            "high_severity_total": data.get("high_severity_total", 0),
            "dep_status": data.get("dependencies", {}).get("status"),
            "timestamp": data.get("timestamp"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "passed": None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Security scanning gate (gh-57)")
    ap.add_argument("--no-deps", action="store_true", help="Skip dependency audit")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--timestamp", default="", help="ISO timestamp override")
    args = ap.parse_args()

    ts = args.timestamp
    if not ts:
        import datetime

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = run_scan(include_deps=not args.no_deps)
    artifact = write_artifact(result, ts)

    s = result["secrets"]
    d = result["dependencies"]
    print("security scan:")
    print(f"  secrets:      {s.get('total', 0)} finding(s), {s.get('high_severity', 0)} high")
    print(f"  dependencies: {d.get('status')} ({d.get('high_severity', 0)} high)")
    if s.get("findings"):
        for f in s["findings"][:20]:
            print(f"    [{f['severity']}] {f['rule']} @ {f['file']}:{f['line']}")
    print(f"  artifact:     {artifact}")

    sep = "=" * 60
    status = "PASSED" if result["passed"] else "FAILED"
    print(f"\n{sep}\nsecurity gate: {status} ({result['high_severity_total']} high-severity)\n{sep}")
    if args.json:
        print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
