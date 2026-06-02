#!/usr/bin/env python3
"""harness_health_check.py — runtime services & integrity cockpit (issue #79, NW-RG-079).

One command that reports the live health of every runtime dependency the harness
relies on, each as pass / warn / fail:

  Services (best-effort TCP probe, no credentials, never mutating):
    - Rudalo            (RUDALO_URL            | default 127.0.0.1:8800)
    - Ollama            (OLLAMA_URL            | default 127.0.0.1:11434)
    - Neo4j             (NEO4J_URL             | default 127.0.0.1:7687)
    - ChromaDB          (CHROMADB_URL          | default 127.0.0.1:8000)
    - ComfyUI           (COMFYUI_URL           | default 127.0.0.1:8188)

  Local integrity (read-only file inspection):
    - hooks              — .claude/settings*.json configured hook count
    - routing_log        — latest 07_LOGS_AND_AUDIT/routing/routes_*.jsonl parses + fresh
    - skill_inventory    — discoverable SKILL.md count
    - last_go_artifact   — freshness of 07_LOGS_AND_AUDIT/decisions/decision_log.jsonl
    - active_queue       — `bd ready` count (best-effort; warn if bd unavailable)

Design rules (mission stop-conditions):
  * Read-only by DEFAULT. Nothing is written unless --write is passed (which only
    emits a report artifact under 05_REPORTS/harness_health/, never harness state).
  * No credentials are ever required or used — service checks are bare TCP connects,
    so an unreachable/optional local service WARNs, it does not FAIL the cockpit.

Output: JSON to stdout by default; --markdown for the dashboard table; --write to
persist 05_REPORTS/harness_health/latest.{json,md}.

Exit code: 0 unless a hard-fail check fails (integrity checks only — services warn).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import run_safe  # noqa: E402

LOGS = REPO / "07_LOGS_AND_AUDIT"
ROUTING_DIR = LOGS / "routing"
DECISION_LOG = LOGS / "decisions" / "decision_log.jsonl"
OUT_DIR = REPO / "05_REPORTS" / "harness_health"

# Service registry: name -> (env var, default host:port). TCP-only, no auth.
SERVICES: list[tuple[str, str, str]] = [
    ("rudalo", "RUDALO_URL", "127.0.0.1:8800"),
    ("ollama", "OLLAMA_URL", "127.0.0.1:11434"),
    ("neo4j", "NEO4J_URL", "127.0.0.1:7687"),
    ("chromadb", "CHROMADB_URL", "127.0.0.1:8000"),
    ("comfyui", "COMFYUI_URL", "127.0.0.1:8188"),
]

# Optional services: warn when unreachable, but do NOT contribute to the
# overall_status turning yellow. These are supplementary integrations that
# may not be running in a typical dev session.
OPTIONAL_SERVICES: frozenset[str] = frozenset({"rudalo", "neo4j", "chromadb", "comfyui"})

# Integrity checks are authoritative — a failure means the harness cannot be
# trusted, so the cockpit exits non-zero. Service probes only ever warn.
HARD_FAIL_CHECKS = {"hooks", "routing_log", "skill_inventory"}


@dataclass
class Check:
    name: str
    status: str  # pass | warn | fail
    message: str
    value: Any = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_hostport(raw: str) -> tuple[str, int] | None:
    """Accept host:port or scheme://host:port[/path]; return (host, port) or None."""
    s = raw.strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    s = s.split("/", 1)[0]  # strip any path
    if ":" not in s:
        return None
    host, _, port = s.rpartition(":")
    try:
        return host or "127.0.0.1", int(port)
    except ValueError:
        return None


def probe_tcp(host: str, port: int, timeout: float = 0.6) -> bool:
    """Return True if a TCP connection to host:port succeeds. No data sent."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_service(name: str, env_var: str, default: str, timeout: float = 0.6) -> Check:
    raw = os.environ.get(env_var, default)
    hp = _parse_hostport(raw)
    if hp is None:
        return Check(name, "warn", f"unparseable endpoint {raw!r} (set {env_var})", value=raw)
    host, port = hp
    if probe_tcp(host, port, timeout):
        return Check(name, "pass", f"reachable at {host}:{port}", value={"host": host, "port": port})
    # Unreachable: a local optional service being down is a warning, not a failure.
    return Check(
        name,
        "warn",
        f"unreachable at {host}:{port} (service down or not configured)",
        value={"host": host, "port": port},
    )


# ── Local integrity (read-only) ──────────────────────────────────────────────


def check_hooks() -> Check:
    total = 0
    for fname in ("settings.json", "settings.local.json"):
        p = REPO / ".claude" / fname
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return Check("hooks", "fail", f"{fname} is not valid JSON", value=fname)
        hooks = data.get("hooks") or {}
        for _event, entries in hooks.items() if isinstance(hooks, dict) else []:
            if isinstance(entries, list):
                total += len(entries)
    if total == 0:
        return Check("hooks", "fail", "no hooks configured in .claude/settings*.json", value=0)
    return Check("hooks", "pass", f"{total} hook group(s) configured", value=total)


def _latest_routing_log() -> Path | None:
    if not ROUTING_DIR.is_dir():
        return None
    logs = sorted(ROUTING_DIR.glob("routes_*.jsonl"))
    return logs[-1] if logs else None


def check_routing_log(max_age_hours: float = 72.0) -> Check:
    latest = _latest_routing_log()
    if latest is None:
        return Check("routing_log", "fail", "no routes_*.jsonl found in 07_LOGS_AND_AUDIT/routing", value=None)
    # Integrity: every non-empty line must be valid JSON.
    bad = 0
    count = 0
    try:
        for line in latest.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            count += 1
            try:
                json.loads(line)
            except json.JSONDecodeError:
                bad += 1
    except OSError as exc:
        return Check("routing_log", "fail", f"cannot read {latest.name}: {exc}", value=None)
    if bad:
        return Check(
            "routing_log",
            "fail",
            f"{bad}/{count} corrupt line(s) in {latest.name}",
            value={"corrupt": bad, "lines": count},
        )
    age_h = round(
        (_utc_now() - datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)).total_seconds() / 3600, 1
    )
    if age_h > max_age_hours:
        return Check(
            "routing_log",
            "warn",
            f"{latest.name} stale ({age_h}h old, {count} routes)",
            value={"age_hours": age_h, "lines": count},
        )
    return Check(
        "routing_log",
        "pass",
        f"{latest.name} intact, {count} routes, {age_h}h old",
        value={"age_hours": age_h, "lines": count},
    )


def _iter_skill_files() -> list[Path]:
    found: list[Path] = []
    for base in (REPO / ".agents" / "skills", REPO / ".claude" / "skills", REPO / "skills"):
        if base.is_dir():
            found.extend(base.glob("**/SKILL.md"))
    return found


def check_skill_inventory(min_skills: int = 1) -> Check:
    skills = _iter_skill_files()
    n = len(skills)
    if n < min_skills:
        return Check("skill_inventory", "fail", f"only {n} SKILL.md found (expected >= {min_skills})", value=n)
    return Check("skill_inventory", "pass", f"{n} skill(s) discoverable", value=n)


def check_last_go_artifact(max_age_hours: float = 168.0) -> Check:
    if not DECISION_LOG.is_file():
        return Check("last_go_artifact", "warn", "decision_log.jsonl missing (no GO runs recorded yet)", value=None)
    lines = [ln for ln in DECISION_LOG.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not lines:
        return Check("last_go_artifact", "warn", "decision_log.jsonl empty", value=0)
    age_h = round(
        (_utc_now() - datetime.fromtimestamp(DECISION_LOG.stat().st_mtime, tz=timezone.utc)).total_seconds() / 3600, 1
    )
    status = "pass" if age_h <= max_age_hours else "warn"
    return Check(
        "last_go_artifact",
        status,
        f"{len(lines)} decision(s), last {age_h}h ago",
        value={"count": len(lines), "age_hours": age_h},
    )


def check_active_queue() -> Check:
    """Best-effort `bd ready` count. bd unavailable -> warn (not fail)."""
    import shutil

    bd = shutil.which("bd") or shutil.which("bd.cmd")
    if not bd:
        return Check("active_queue", "warn", "bd not on PATH; queue status unknown", value=None)
    try:
        r = run_safe([bd, "ready", "--json"], cwd=REPO, timeout=20)
        if r.returncode != 0:
            return Check("active_queue", "warn", "bd ready returned non-zero", value=None)
        data = json.loads(r.stdout) if r.stdout.strip() else []
        items = data if isinstance(data, list) else data.get("issues", [])
        return Check("active_queue", "pass", f"{len(items)} ready item(s) in queue", value=len(items))
    except json.JSONDecodeError as exc:
        # run_safe absorbs timeout/OSError (rc handled above); malformed bd JSON
        # is the only remaining raisable error.
        return Check("active_queue", "warn", f"queue probe failed: {exc}", value=None)


def check_leases() -> Check:
    """Report active/stale lease counts + live conflicts (collision-control FR-8)."""
    import importlib.util

    lm_path = REPO / "scripts" / "lease_manager.py"
    if not lm_path.is_file():
        return Check("leases", "warn", "lease_manager.py not present", value=None)
    try:
        spec = importlib.util.spec_from_file_location("lease_manager", lm_path)
        lm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lm)
        s = lm.summarize()
        if s.get("status") != "ok":
            return Check("leases", "warn", f"lease summary error: {s.get('error')}", value=s)
        conflicts = s.get("conflicts", 0)
        stale = s.get("stale_leases", 0)
        msg = f"{s.get('active_leases', 0)} active, {stale} stale, {conflicts} conflict(s)"
        if conflicts:
            return Check("leases", "fail", msg, value=s)  # a live overlap is a real collision
        if stale:
            return Check("leases", "warn", msg, value=s)
        return Check("leases", "pass", msg, value=s)
    except Exception as exc:  # noqa: BLE001
        return Check("leases", "warn", f"lease probe failed: {exc}", value=None)


# ── Aggregation ──────────────────────────────────────────────────────────────


def run_all(service_timeout: float = 0.6) -> dict:
    checks: list[Check] = [check_service(n, e, d, service_timeout) for n, e, d in SERVICES]
    checks += [
        check_hooks(),
        check_routing_log(),
        check_skill_inventory(),
        check_last_go_artifact(),
        check_active_queue(),
        check_leases(),
    ]

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for c in checks:
        counts[c.status] = counts.get(c.status, 0) + 1

    # For the overall traffic-light, optional-service warns are informational
    # only (shown in the report but excluded from the green/yellow/red decision).
    blocking_warns = sum(1 for c in checks if c.status == "warn" and c.name not in OPTIONAL_SERVICES)
    blocking_fails = sum(1 for c in checks if c.status == "fail")

    hard_fail = any(c.status == "fail" and c.name in HARD_FAIL_CHECKS for c in checks)
    overall = "red" if hard_fail else ("yellow" if blocking_warns or blocking_fails else "green")
    score = max(0, 100 - blocking_fails * 20 - blocking_warns * 6)

    return {
        "generated_at_utc": _ts(),
        "overall_status": overall,
        "readiness_score": score,
        "counts": counts,
        "checks": [asdict(c) for c in checks],
    }


def to_markdown(result: dict) -> str:
    lines = [
        "# Harness Health Dashboard Cockpit",
        "",
        f"- generated_at_utc: {result.get('generated_at_utc', '')}",
        f"- overall_status: **{result.get('overall_status', 'unknown').upper()}**",
        f"- readiness_score: {result.get('readiness_score', 0)}/100",
        f"- pass/warn/fail: {result['counts']['pass']}/{result['counts']['warn']}/{result['counts']['fail']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Message |",
        "|---|---|---|",
    ]
    icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
    for c in result.get("checks", []):
        lines.append(f"| {c['name']} | {icon.get(c['status'], c['status'])} | {c['message']} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "- **PASS** — dependency reachable / artifact intact and fresh.",
        "- **WARN** — optional service down, stale artifact, or probe inconclusive. Non-blocking.",
        "- **FAIL** — integrity check failed (hooks / routing-log / skill inventory). Investigate before GO-mode.",
        "",
        "Services are bare TCP probes (no credentials, no mutation). A local service that is",
        "simply not running shows WARN, not FAIL — the cockpit never blocks on optional services.",
        "",
        "*Generated by scripts/harness_health_check.py (read-only).*",
    ]
    return "\n".join(lines) + "\n"


def summarize() -> dict:
    """Fail-open compact summary for the closeout report / meta-gate (gate contract)."""
    try:
        latest = OUT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "overall_status": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "overall_status": data.get("overall_status"),
            "readiness_score": data.get("readiness_score"),
            "counts": data.get("counts"),
            "generated_at_utc": data.get("generated_at_utc"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "overall_status": None}


def write_artifact(result: dict) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "latest.json"
    md_path = OUT_DIR / "latest.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(result), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Harness runtime health cockpit (issue #79)")
    ap.add_argument("--markdown", action="store_true", help="print the Markdown dashboard instead of JSON")
    ap.add_argument("--write", action="store_true", help="persist 05_REPORTS/harness_health/latest.{json,md}")
    ap.add_argument("--service-timeout", type=float, default=0.6, help="per-service TCP probe timeout (seconds)")
    args = ap.parse_args()

    result = run_all(service_timeout=args.service_timeout)

    if args.write:
        json_path, md_path = write_artifact(result)
        result["_written"] = {"json": str(json_path.relative_to(REPO)), "md": str(md_path.relative_to(REPO))}

    if args.markdown:
        print(to_markdown(result))
    else:
        print(json.dumps(result, indent=2))

    # Exit non-zero only on a hard integrity failure (services never block).
    return 1 if result["overall_status"] == "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
