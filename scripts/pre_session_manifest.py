#!/usr/bin/env python3
"""Write compact pre-session manifest per PRE_SESSION_CONTEXT_POLICY.md.

Usage:
    python scripts/pre_session_manifest.py
    python scripts/pre_session_manifest.py --write
    python scripts/pre_session_manifest.py --write --json
    python scripts/pre_session_manifest.py --mcps-path tests/fixtures/mcp_minimal
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from common_harness import run_safe  # noqa: E402
from pre_session_common import (  # noqa: E402
    REPO,
    load_profile,
    resolve_mcps_path,
    scan_mcps,
    tok,
)

PACK_VERSION_FILES = [
    "AGENT_OPERATIONS.md",
    "00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md",
    "docs/governance/PRE_SESSION_CONTEXT_POLICY.md",
    "docs/governance/OPENROUTER_BROKER_POLICY.md",
    "docs/BEADS_OBJECT_MODEL.md",
]

BLOCKED_BULK_SOURCES = [
    "old_logs",
    "bulk_jsonl",
    "archive",
    "~/.claude/projects/**/*.jsonl",
]

P0_LOADED_DOCS = [
    "AGENT_OPERATIONS.md",
    "00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md",
]


def _repo_root() -> Path:
    override = os.environ.get("CHROMATIC_REPO")
    return Path(override).resolve() if override else REPO


def _output_dir(repo: Path) -> Path:
    override = os.environ.get("CHROMATIC_PRE_SESSION_DIR")
    if override:
        return Path(override).resolve()
    return repo / "07_LOGS_AND_AUDIT" / "pre_session"


def _git_branch(repo: Path) -> str:
    r = run_safe(["git", "branch", "--show-current"], cwd=repo, timeout=10)
    if r.returncode == 0:
        return (r.stdout or "").strip() or "unknown"
    return "unknown"


def _git_status_summary(repo: Path) -> dict:
    r = run_safe(["git", "status", "--short"], cwd=repo, timeout=10)
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    return {
        "dirty": len(lines) > 0,
        "changed_file_count": len(lines),
    }


def _pack_version(repo: Path) -> str:
    h = hashlib.sha256()
    for rel in PACK_VERSION_FILES:
        path = repo / rel
        if path.is_file():
            h.update(rel.encode())
            h.update(str(path.stat().st_mtime_ns).encode())
    return h.hexdigest()[:16]


def _active_beads(repo: Path) -> list[dict]:
    for cmd in (
        ["bd", "ready", "--json"],
        ["bd", "ready", "-json"],
    ):
        r = run_safe(cmd, cwd=repo, timeout=15)
        if r.returncode != 0 or not (r.stdout or "").strip():
            continue
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "issues" in data:
            return data["issues"]
        if isinstance(data, dict):
            return [data]
    return []


def _mcp_audit_summary(mcps_path: Path, profile_name: str) -> dict:
    profile_doc = load_profile()
    disable_daily = set(profile_doc.get("disable_for_daily_dev", []))
    tool_count, total_chars, per_server = scan_mcps(mcps_path)
    per_server_tok = {k: tok(v) for k, v in per_server.items()}
    total_tok = tok(total_chars)
    warn_tok = int(profile_doc.get("warn_total_tokens", 12000))
    heavy = [s for s in per_server_tok if s in disable_daily]
    return {
        "mcps_path": str(mcps_path),
        "profile": profile_name,
        "tool_count": tool_count,
        "estimated_tokens_if_enabled": total_tok,
        "warn_threshold": warn_tok,
        "over_warn_threshold": total_tok > warn_tok,
        "heavy_servers_on_disk": heavy,
        "heavy_tokens_on_disk": sum(per_server_tok.get(s, 0) for s in heavy),
    }


def _routing_context() -> dict:
    """Runtime routing signals from ContextDetector (best-effort, no network in CI)."""
    try:
        runtime_dir = _repo_root() / "02_RUNTIME"
        if str(runtime_dir) not in sys.path:
            sys.path.insert(0, str(runtime_dir))
        from router.context_detector import ContextDetector  # noqa: E402

        ctx = ContextDetector().detect()
        return {
            "device_type": ctx.device_type,
            "gpu_available": ctx.gpu_available,
            "ollama_local_reachable": ctx.ollama_local_reachable,
            "internet_reachable": ctx.internet_reachable,
            "connectivity": ctx.connectivity,
            "is_battery": ctx.is_battery,
            "speed_mode": os.environ.get("CHROMATIC_SPEED_MODE", "balance"),
        }
    except Exception:
        return {
            "device_type": os.environ.get("CHROMATIC_DEVICE", "unknown"),
            "connectivity": os.environ.get("CHROMATIC_CONNECTIVITY", "unknown"),
            "speed_mode": os.environ.get("CHROMATIC_SPEED_MODE", "balance"),
        }


def _read_handoff(repo: Path) -> dict:
    latest = repo / ".agents" / "handoffs" / "latest.json"
    if not latest.is_file():
        return {"present": False, "path": str(latest.relative_to(repo))}
    data = json.loads(latest.read_text(encoding="utf-8"))
    return {
        "present": True,
        "path": str(latest.relative_to(repo)),
        "data": data,
    }


def build_manifest(
    *,
    repo: Path,
    mcps_path: Path,
    profile_name: str = "harness_dev",
    invoked_by: str = "preflight",
) -> dict:
    handoff = _read_handoff(repo)
    handoff_pointer = handoff.get("path", ".agents/handoffs/latest.json")
    loaded_docs = list(P0_LOADED_DOCS)
    if handoff.get("present"):
        hp = handoff.get("data", {}).get("handoff_path")
        if hp:
            loaded_docs.append(str(hp))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "invoked_by": invoked_by,
        "repo": repo.name,
        "repo_path": str(repo),
        "branch": _git_branch(repo),
        "git_status": _git_status_summary(repo),
        "active_beads": _active_beads(repo),
        "handoff_pointer": handoff_pointer,
        "handoff_present": handoff.get("present", False),
        "mcp_profile": profile_name,
        "context_tier": "P0",
        "loaded_docs": loaded_docs,
        "blocked_bulk_sources": list(BLOCKED_BULK_SOURCES),
        "routing_context": _routing_context(),
        "mcp_audit": _mcp_audit_summary(mcps_path, profile_name),
        "pack_version": _pack_version(repo),
        "governance": _governance_snapshot(repo),
    }


def _governance_snapshot(repo: Path) -> dict:
    """ROUTE-007 extended manifest fields for session boot audits."""
    snap: dict = {
        "context_trim_risk": "unknown",
        "instruction_drift_status": "unknown",
    }
    trim_path = repo / ".agents" / "context" / "context_trim_audit.json"
    if trim_path.is_file():
        try:
            data = json.loads(trim_path.read_text(encoding="utf-8"))
            snap["context_trim_risk"] = data.get("risk_level", "unknown")
        except (json.JSONDecodeError, OSError):
            pass
    return snap


def write_manifest(manifest: dict, out_dir: Path) -> tuple[Path, Path | None]:
    out_dir.mkdir(parents=True, exist_ok=True)
    latest = out_dir / "latest.json"
    latest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    append_path: Path | None = None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    append_path = out_dir / f"manifest_{stamp}.jsonl"
    with open(append_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest, ensure_ascii=False) + "\n")
    return latest, append_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-session boot manifest")
    parser.add_argument("--mcps-path", help="Cursor project mcps folder")
    parser.add_argument("--profile", default="harness_dev")
    parser.add_argument(
        "--invoked-by",
        default=os.environ.get("CHROMATIC_RUNTIME", "preflight"),
    )
    parser.add_argument("--write", action="store_true", help="Write latest.json + append jsonl")
    parser.add_argument("--json", action="store_true", help="Print manifest JSON to stdout")
    args = parser.parse_args()

    repo = _repo_root()
    mcps_path = resolve_mcps_path(args.mcps_path)
    if not mcps_path.is_dir():
        print(f"ERROR: mcps path not found: {mcps_path}", file=sys.stderr)
        return 1

    manifest = build_manifest(
        repo=repo,
        mcps_path=mcps_path,
        profile_name=args.profile,
        invoked_by=args.invoked_by,
    )

    if args.json:
        print(json.dumps(manifest, indent=2))

    if args.write:
        latest, appended = write_manifest(manifest, _output_dir(repo))

        def _rel(p: Path) -> str:
            try:
                return str(p.relative_to(repo))
            except ValueError:
                return str(p)

        print(f"Wrote {_rel(latest)}", file=sys.stderr)
        if appended:
            print(f"Appended {_rel(appended)}", file=sys.stderr)
    elif not args.json:
        print(json.dumps(manifest, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
