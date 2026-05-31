#!/usr/bin/env python3
"""Budget-aware session closeout: handoff, transfer packet, optional successor spawn.

Usage:
  python scripts/session_closeout.py --invoked-by cursor
  python scripts/session_closeout.py --invoked-by claude --harvest --spawn-successor
  python scripts/session_closeout.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget.ledger import BudgetLedger  # noqa: E402
from budget.transfer_packet import (  # noqa: E402
    build_transfer_packet,
    write_transfer_artifacts,
)
from orchestrator.session_compact import write_handoff  # noqa: E402

_INJECTED_LEARNINGS = _REPO / ".agents" / "context" / "injected_learnings.json"
_EXECUTION_LOG = _REPO / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"


def _emit_injected_learning_outcomes() -> dict[str, Any]:
    """Emit applied_success or applied_failure for learnings injected at session start.

    Heuristic: scan execution.jsonl for error events after the injection timestamp.
    Any error → applied_failure for all injected learnings; clean close → applied_success.
    Fail-open: never raises, returns a summary dict.
    """
    result: dict[str, Any] = {"ok": False, "emitted": [], "skipped": []}
    try:
        if not _INJECTED_LEARNINGS.exists():
            result["skip_reason"] = "no injected_learnings.json"
            return result
        rec = json.loads(_INJECTED_LEARNINGS.read_text(encoding="utf-8"))
        learnings = rec.get("learnings") or []
        if not learnings:
            result["skip_reason"] = "empty learnings list"
            return result
        injected_at = rec.get("injected_at", "")

        # Detect errors in execution.jsonl after the injection timestamp
        had_error = False
        if _EXECUTION_LOG.exists() and injected_at:
            for line in _EXECUTION_LOG.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                ts = str(row.get("ts", ""))
                if ts < injected_at:
                    continue
                etype = str(row.get("event_type", ""))
                decision = str(row.get("workflow_decision", ""))
                if (
                    "error" in etype.lower()
                    or "error" in decision.lower()
                    or "fail" in decision.lower()
                ):
                    had_error = True
                    break

        outcome = "applied_failure" if had_error else "applied_success"
        from activity.log import emit_learning_outcome  # type: ignore[import]

        for lc in learnings:
            name = str(lc.get("name", "")).strip()
            if not name:
                result["skipped"].append(lc)
                continue
            emitted = emit_learning_outcome(
                _REPO,
                learning_name=name,
                outcome=outcome,
                rig_id="session_closeout",
                error_category="session_error" if had_error else "",
            )
            if emitted:
                result["emitted"].append({"name": name, "outcome": outcome})
            else:
                result["skipped"].append(
                    {"name": name, "reason": "duplicate or invalid"}
                )

        result["ok"] = True
        result["outcome"] = outcome
        result["had_error"] = had_error
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result


def _default_epic_swot_policy_config() -> dict[str, Any]:
    return {
        "confidence_threshold": 0.55,
        "block_penalty": 0.8,
        "halt_human_penalty": 0.5,
        "history_windows": {
            "recent_open_hours": 8,
            "rolling_days": 7,
        },
        "history_limits": {
            "open_swot_total_cap": 1,
            "created_swot_today_cap": 1,
            "recent_open_swot_cap": 1,
        },
        "session_tokens": {
            "high": {
                "min": 120000,
                "score": 0.24,
                "reason": "high estimated token load",
            },
            "medium": {
                "min": 60000,
                "score": 0.16,
                "reason": "moderate-high estimated token load",
            },
            "low": {"min": 30000, "score": 0.08, "reason": "estimated token load"},
        },
        "open_tasks": {
            "high": {"min": 8, "score": 0.22, "reason": "high open-task pressure"},
            "medium": {"min": 4, "score": 0.14, "reason": "open-task pressure"},
            "low": {"min": 2, "score": 0.07, "reason": "open-task pressure"},
        },
        "changed_files": {
            "high": {"min": 25, "score": 0.2, "reason": "large session change surface"},
            "medium": {"min": 12, "score": 0.12, "reason": "session change surface"},
            "low": {"min": 6, "score": 0.06, "reason": "session change surface"},
        },
        "event_count": {
            "high": {
                "min": 500,
                "score": 0.16,
                "reason": "high governance event volume",
            },
            "medium": {"min": 200, "score": 0.09, "reason": "governance event volume"},
        },
        "coverage": {
            "min_field_coverage": 0.85,
            "field_weight": 0.04,
            "max_bonus": 0.14,
            "fields": ["provider", "model", "execution_status", "task_id"],
            "reason": "telemetry coverage gaps present",
        },
    }


def _coerce_float(
    value: Any,
    default: float,
    *,
    minimum: float = 0.0,
    maximum: float | None = 1.0,
) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result < minimum:
        return default
    if maximum is not None and result > maximum:
        return default
    return result


def _coerce_int(value: Any, default: int, *, minimum: int = 0) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if result < minimum:
        return default
    return result


def _sanitize_epic_swot_policy_config(
    config: dict[str, Any], defaults: dict[str, Any]
) -> dict[str, Any]:
    sanitized = dict(config)
    sanitized["confidence_threshold"] = _coerce_float(
        config.get("confidence_threshold"),
        float(defaults["confidence_threshold"]),
    )
    sanitized["block_penalty"] = _coerce_float(
        config.get("block_penalty"), float(defaults["block_penalty"])
    )
    sanitized["halt_human_penalty"] = _coerce_float(
        config.get("halt_human_penalty"), float(defaults["halt_human_penalty"])
    )

    history_windows = dict(defaults.get("history_windows") or {})
    history_windows.update(config.get("history_windows") or {})
    history_windows["recent_open_hours"] = _coerce_int(
        history_windows.get("recent_open_hours"),
        int((defaults.get("history_windows") or {}).get("recent_open_hours") or 8),
        minimum=1,
    )
    history_windows["rolling_days"] = _coerce_int(
        history_windows.get("rolling_days"),
        int((defaults.get("history_windows") or {}).get("rolling_days") or 7),
        minimum=1,
    )
    sanitized["history_windows"] = history_windows

    history_limits = dict(defaults.get("history_limits") or {})
    history_limits.update(config.get("history_limits") or {})
    for key, default_value in (defaults.get("history_limits") or {}).items():
        history_limits[key] = _coerce_int(
            history_limits.get(key), int(default_value), minimum=1
        )
    sanitized["history_limits"] = history_limits

    for section_name in (
        "session_tokens",
        "open_tasks",
        "changed_files",
        "event_count",
    ):
        section_defaults = defaults.get(section_name) or {}
        section = dict(section_defaults)
        section.update(config.get(section_name) or {})
        sanitized_section: dict[str, Any] = {}
        for bucket_name, bucket_defaults in section_defaults.items():
            bucket = dict(bucket_defaults)
            bucket.update((section.get(bucket_name) or {}))
            sanitized_section[bucket_name] = {
                "min": _coerce_int(
                    bucket.get("min"), int(bucket_defaults.get("min") or 0), minimum=0
                ),
                "score": _coerce_float(
                    bucket.get("score"), float(bucket_defaults.get("score") or 0.0)
                ),
                "reason": str(
                    bucket.get("reason") or bucket_defaults.get("reason") or ""
                ),
            }
        sanitized[section_name] = sanitized_section

    coverage_defaults = defaults.get("coverage") or {}
    coverage = dict(coverage_defaults)
    coverage.update(config.get("coverage") or {})
    fields = coverage.get("fields")
    if not isinstance(fields, list) or not all(
        isinstance(field, str) and field for field in fields
    ):
        fields = list(coverage_defaults.get("fields") or [])
    sanitized["coverage"] = {
        "min_field_coverage": _coerce_float(
            coverage.get("min_field_coverage"),
            float(coverage_defaults.get("min_field_coverage") or 0.85),
        ),
        "field_weight": _coerce_float(
            coverage.get("field_weight"),
            float(coverage_defaults.get("field_weight") or 0.04),
        ),
        "max_bonus": _coerce_float(
            coverage.get("max_bonus"),
            float(coverage_defaults.get("max_bonus") or 0.14),
        ),
        "fields": fields,
        "reason": str(coverage.get("reason") or coverage_defaults.get("reason") or ""),
    }

    return sanitized


def _load_epic_swot_policy_config(path: Path | None = None) -> dict[str, Any]:
    defaults = _default_epic_swot_policy_config()
    config = defaults
    cfg_path = path or (_REPO / "config" / "epic_swot_policy.json")
    if not cfg_path.is_file():
        return config
    try:
        user = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return config
    if not isinstance(user, dict):
        return config

    def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        out = dict(base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = merge(out[k], v)
            else:
                out[k] = v
        return out

    return _sanitize_epic_swot_policy_config(merge(config, user), defaults)


def _default_auto_turn_policy_config() -> dict[str, Any]:
    return {
        "required_signal_hits": 2,
        "signals": {
            "loc_delta_total": {"enabled": True, "min": 400},
            "policy_event_count": {"enabled": True, "min": 200},
            "open_tasks": {"enabled": True, "min": 4},
            "changed_files": {"enabled": True, "min": 12},
        },
    }


def _sanitize_auto_turn_policy_config(
    config: dict[str, Any], defaults: dict[str, Any]
) -> dict[str, Any]:
    sanitized = dict(defaults)
    sanitized["required_signal_hits"] = _coerce_int(
        config.get("required_signal_hits"),
        int(defaults.get("required_signal_hits") or 2),
        minimum=1,
    )
    default_signals = defaults.get("signals") or {}
    user_signals = config.get("signals") or {}
    signals: dict[str, Any] = {}
    for key, bucket_defaults in default_signals.items():
        bucket = dict(bucket_defaults)
        bucket.update(user_signals.get(key) or {})
        signals[key] = {
            "enabled": bool(bucket.get("enabled", True)),
            "min": _coerce_int(
                bucket.get("min"), int(bucket_defaults.get("min") or 0), minimum=0
            ),
        }
    sanitized["signals"] = signals
    return sanitized


def _load_auto_turn_policy_config(path: Path | None = None) -> dict[str, Any]:
    defaults = _default_auto_turn_policy_config()
    cfg_path = path or (_REPO / "config" / "auto_turn_policy.json")
    if not cfg_path.is_file():
        return defaults
    try:
        user = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaults
    if not isinstance(user, dict):
        return defaults
    return _sanitize_auto_turn_policy_config(user, defaults)


def _evaluate_auto_turn_trigger(
    *,
    auto_turn_index: int,
    auto_turn_threshold: int,
    beads_ready_count: int,
    git_changed_files: int,
    policy_signals: dict[str, Any],
    policy_config: dict[str, Any],
) -> dict[str, Any]:
    loc_delta = _git_loc_delta()
    loc_total = int(loc_delta.get("insertions") or 0) + int(
        loc_delta.get("deletions") or 0
    )
    signal_cfg = policy_config.get("signals") or {}

    def cfg(key: str) -> dict[str, Any]:
        bucket = signal_cfg.get(key) or {}
        return {
            "enabled": bool(bucket.get("enabled", True)),
            "min": int(bucket.get("min") or 0),
        }

    evaluations: dict[str, Any] = {
        "turn_threshold": {
            "enabled": True,
            "min": auto_turn_threshold,
            "value": auto_turn_index,
            "hit": auto_turn_index >= auto_turn_threshold,
        }
    }
    metric_values = {
        "loc_delta_total": loc_total,
        "policy_event_count": int(policy_signals.get("event_count") or 0),
        "open_tasks": max(
            beads_ready_count, int(policy_signals.get("open_tasks") or 0)
        ),
        "changed_files": max(
            git_changed_files, int(policy_signals.get("changed_files") or 0)
        ),
    }
    hit_count = 0
    hit_signals: list[str] = []
    for key, value in metric_values.items():
        bucket = cfg(key)
        hit = bool(bucket["enabled"] and value >= bucket["min"])
        evaluations[key] = {
            "enabled": bucket["enabled"],
            "min": bucket["min"],
            "value": value,
            "hit": hit,
        }
        if hit:
            hit_count += 1
            hit_signals.append(key)

    required_hits = _coerce_int(
        policy_config.get("required_signal_hits"),
        2,
        minimum=1,
    )
    turn_hit = bool(evaluations["turn_threshold"]["hit"])
    multi_signal_hit = hit_count >= required_hits
    return {
        "triggered": turn_hit or multi_signal_hit,
        "turn_threshold_hit": turn_hit,
        "multi_signal_hit": multi_signal_hit,
        "required_signal_hits": required_hits,
        "signal_hit_count": hit_count,
        "hit_signals": hit_signals,
        "signals": evaluations,
        "loc_delta": loc_delta,
    }


def _run(
    cmd: list[str], *, timeout: int = 120, cwd: Path | None = None
) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd or _REPO,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, str(exc)


def _run_harness_health_snapshot() -> dict[str, Any]:
    code, out = _run(
        [
            sys.executable,
            str(_REPO / "scripts" / "harness_health_snapshot.py"),
            "--write",
        ],
        timeout=180,
    )
    status = "unknown"
    score = None
    counts: dict[str, int] = {}
    if out.strip():
        try:
            payload = json.loads(out)
            status = str(payload.get("overall_status") or "unknown")
            score = payload.get("readiness_score")
            raw_counts = payload.get("counts") or {}
            if isinstance(raw_counts, dict):
                counts = {
                    "pass": int(raw_counts.get("pass") or 0),
                    "warn": int(raw_counts.get("warn") or 0),
                    "fail": int(raw_counts.get("fail") or 0),
                }
        except Exception:
            pass

    return {
        "exit": code,
        "ok": code == 0,
        "overall_status": status,
        "readiness_score": score,
        "counts": counts,
        "path": "07_LOGS_AND_AUDIT/harness_health/latest.json",
        "output": out[:2000],
    }


def _run_bd(args: list[str], *, timeout: int = 60) -> tuple[int, str]:
    """Run bd with a Windows-safe fallback when PATH resolution is inconsistent."""
    code, out = _run(["bd", *args], timeout=timeout)
    if code == 0:
        return code, out
    if "WinError 2" in out or "No such file" in out or "not found" in out.lower():
        return _run(["cmd", "/c", "bd", *args], timeout=timeout)
    return code, out


def _extract_issue_id(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"Created issue:\s*([^\s]+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b([a-z0-9][a-z0-9._-]*-[a-z0-9]+)\b", text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _parse_utc(ts: str) -> datetime | None:
    s = (ts or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def _fetch_swot_rows_live() -> list[dict] | None:
    """Query live bd DB for EPIC-SWOT epics. Returns None on any failure (triggers JSONL fallback)."""
    try:
        code, out = _run_bd(
            ["list", "--type", "epic", "--limit", "0", "--json"], timeout=15
        )
        if code != 0 or not out.strip():
            return None
        rows = json.loads(out)
        if not isinstance(rows, list):
            return None
        return [
            r
            for r in rows
            if isinstance(r, dict) and "epic-swot" in str(r.get("title") or "").lower()
        ]
    except Exception:
        return None


def _fetch_swot_rows_jsonl(issues_path: Path) -> list[dict]:
    """Fall back: read .beads/issues.jsonl for EPIC-SWOT rows (may be stale)."""
    result = []
    for row in _load_issue_rows_jsonl(issues_path):
        title = str(row.get("title") or "")
        issue_type = str(row.get("issue_type") or "").lower()
        if "epic-swot" in title.lower() and issue_type == "epic":
            result.append(row)
    return result


def _load_issue_rows_jsonl(issues_path: Path) -> list[dict]:
    if not issues_path.is_file():
        return []
    result = []
    for raw in issues_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            result.append(row)
    return result


def _fetch_pending_swot_tasks_live() -> list[dict] | None:
    """Query open 'Generate next EPIC-SWOT' task beads. Returns None on failure."""
    try:
        code, out = _run_bd(
            ["list", "--type", "task", "--limit", "0", "--json"], timeout=15
        )
        if code != 0 or not out.strip():
            return None
        rows = json.loads(out)
        if not isinstance(rows, list):
            return None
        return [
            r
            for r in rows
            if isinstance(r, dict)
            and "generate next epic-swot" in str(r.get("title") or "").lower()
            and str(r.get("status") or "").lower() in ("open", "in_progress")
        ]
    except Exception:
        return None


def _load_swot_epic_history(
    *,
    issues_path: Path,
    now_utc: datetime,
    recent_open_hours: int = 8,
    rolling_days: int = 7,
) -> dict:
    stats: dict = {
        "open_swot_total": 0,
        "open_swot_recent_window": 0,
        "created_swot_today": 0,
        "created_swot_rolling_window": 0,
        "open_pending_task": 0,
        "live_query_failed": False,
        "newest_open_epic_age_hours": None,
    }
    # Live query first; fail-closed when bd is unavailable (stale JSONL caused duplicate spam)
    rows = _fetch_swot_rows_live()
    if rows is None:
        stats["live_query_failed"] = True
        rows = _fetch_swot_rows_jsonl(issues_path)

    # Also count open "Generate next EPIC-SWOT" task beads — if any exist, block creation
    pending_tasks = _fetch_pending_swot_tasks_live()
    stats["open_pending_task"] = len(pending_tasks) if pending_tasks is not None else 0
    start_recent = now_utc.timestamp() - max(1, int(recent_open_hours)) * 3600
    start_rolling = now_utc.timestamp() - max(1, int(rolling_days)) * 24 * 3600
    newest_open_ts: datetime | None = None
    for row in rows:
        status = str(row.get("status") or "").lower()
        created = _parse_utc(str(row.get("created_at") or ""))
        # Count open and in_progress beads as "active" (bd transitions open→in_progress on claim)
        if status in ("open", "in_progress"):
            stats["open_swot_total"] += 1
            if created and created.timestamp() >= start_recent:
                stats["open_swot_recent_window"] += 1
            # Track the most recently created open epic for staleness detection
            if created and (newest_open_ts is None or created > newest_open_ts):
                newest_open_ts = created
        if created:
            if created.date() == now_utc.date():
                stats["created_swot_today"] += 1
            if created.timestamp() >= start_rolling:
                stats["created_swot_rolling_window"] += 1
    if newest_open_ts is not None:
        stats["newest_open_epic_age_hours"] = round(
            (now_utc - newest_open_ts).total_seconds() / 3600, 2
        )
    return stats


def find_latest_open_swot_epic(issues_path: Path | None = None) -> dict[str, str]:
    rows = _fetch_swot_rows_live()
    if rows is None:
        issues_file = issues_path or (_REPO / ".beads" / "issues.jsonl")
        rows = _fetch_swot_rows_jsonl(issues_file)
    best: tuple[datetime, dict[str, str]] | None = None
    for row in rows:
        status = str(row.get("status") or "").lower()
        issue_type = str(row.get("issue_type") or "").lower()
        if status not in ("open", "in_progress") or issue_type != "epic":
            continue
        title = str(row.get("title") or "")
        created = _parse_utc(
            str(row.get("created_at") or "")
        ) or datetime.fromtimestamp(0, tz=timezone.utc)
        candidate = {
            "epic_id": str(row.get("id") or ""),
            "epic_title": title,
            "timestamp_utc": (re.search(r"\[(\d{8}T\d{6}Z)\]", title) or [None, ""])[1],
            "telemetry_key": "",
        }
        if candidate["timestamp_utc"]:
            candidate["telemetry_key"] = f"EPIC-SWOT-NEXT-{candidate['timestamp_utc']}"
        if best is None or created > best[0]:
            best = (created, candidate)
    return best[1] if best else {}


def find_open_swot_task_for_epic(
    epic_id: str, issues_path: Path | None = None
) -> dict[str, str]:
    if not epic_id:
        return {}
    # Live query first (all issues, not just SWOT-filtered), fall back to JSONL
    try:
        code, out = _run_bd(["list", "--limit", "0", "--json"], timeout=15)
        if code == 0 and out.strip():
            all_rows: list[dict] = json.loads(out)
        else:
            raise ValueError("bd list failed")
    except Exception:
        issues_file = issues_path or (_REPO / ".beads" / "issues.jsonl")
        all_rows = _load_issue_rows_jsonl(issues_file)
    best: tuple[datetime, dict[str, str]] | None = None
    for row in all_rows:
        if not isinstance(row, dict):
            continue
        issue_type = str(row.get("issue_type") or "").lower()
        status = str(row.get("status") or "").lower()
        title = str(row.get("title") or "")
        if status not in ("open", "in_progress") or issue_type not in {
            "task",
            "chore",
            "feature",
        }:
            continue
        if "epic-swot" not in title.lower():
            continue
        deps = row.get("dependencies") or []
        parent_match = False
        if isinstance(deps, list):
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                if (
                    str(dep.get("type") or "") == "parent-child"
                    and str(dep.get("depends_on_id") or "") == epic_id
                ):
                    parent_match = True
                    break
        if not parent_match:
            continue
        created = _parse_utc(
            str(row.get("created_at") or "")
        ) or datetime.fromtimestamp(0, tz=timezone.utc)
        candidate = {
            "task_id": str(row.get("id") or ""),
            "task_title": title,
        }
        if best is None or created > best[0]:
            best = (created, candidate)
    return best[1] if best else {}


def _load_governance_signals(governance_path: Path) -> dict[str, Any]:
    if not governance_path.is_file():
        return {"event_count": 0, "canonical_coverage": {}}
    try:
        data = json.loads(governance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"event_count": 0, "canonical_coverage": {}}
    return {
        "event_count": int(data.get("event_count") or 0),
        "canonical_coverage": dict(data.get("canonical_coverage") or {}),
    }


def _coverage_as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("coverage", "value", "pct", "ratio"):
            v = value.get(key)
            if isinstance(v, (int, float)):
                return float(v)
        return 0.0
    return 0.0


def evaluate_epic_swot_policy(
    *,
    snapshot: Any,
    beads_ready: list[str],
    git: dict[str, Any],
    issues_path: Path | None = None,
    governance_path: Path | None = None,
    policy_config_path: Path | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    issues_file = issues_path or (_REPO / ".beads" / "issues.jsonl")
    gov_file = governance_path or (
        _REPO / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json"
    )
    cfg = _load_epic_swot_policy_config(policy_config_path)

    recent_hours = int((cfg.get("history_windows") or {}).get("recent_open_hours") or 8)
    rolling_days = int((cfg.get("history_windows") or {}).get("rolling_days") or 7)

    history = _load_swot_epic_history(
        issues_path=issues_file,
        now_utc=now,
        recent_open_hours=recent_hours,
        rolling_days=rolling_days,
    )
    gov = _load_governance_signals(gov_file)

    session_est_tokens = int(getattr(snapshot, "session_est_tokens", 0) or 0)
    budget_decision = str(getattr(snapshot, "decision", "") or "")
    open_tasks = len(beads_ready or [])
    changed_files = len((git.get("status_short") or []))
    event_count = int(gov.get("event_count") or 0)
    cov = gov.get("canonical_coverage") or {}

    score = 0.0
    reasons: list[str] = []

    def apply_bucket(metric_value: int, key: str) -> None:
        nonlocal score
        section = cfg.get(key) or {}
        for level in ("high", "medium", "low"):
            rule = section.get(level) or {}
            threshold = int(rule.get("min") or 0)
            if metric_value >= threshold > 0:
                score += float(rule.get("score") or 0.0)
                reason = str(rule.get("reason") or "").strip()
                if reason and reason not in reasons:
                    reasons.append(reason)
                break

    apply_bucket(session_est_tokens, "session_tokens")
    apply_bucket(open_tasks, "open_tasks")
    apply_bucket(changed_files, "changed_files")
    apply_bucket(event_count, "event_count")

    coverage_cfg = cfg.get("coverage") or {}
    coverage_min = float(coverage_cfg.get("min_field_coverage") or 0.85)
    coverage_fields = list(
        coverage_cfg.get("fields")
        or ["provider", "model", "execution_status", "task_id"]
    )
    coverage_weight = float(coverage_cfg.get("field_weight") or 0.04)
    coverage_max = float(coverage_cfg.get("max_bonus") or 0.14)

    low_cov_fields = [
        k for k in coverage_fields if _coverage_as_float(cov.get(k)) < coverage_min
    ]
    if low_cov_fields:
        score += min(coverage_max, coverage_weight * len(low_cov_fields))
        cov_reason = str(
            coverage_cfg.get("reason") or "telemetry coverage gaps present"
        ).strip()
        if cov_reason and cov_reason not in reasons:
            reasons.append(cov_reason)

    block_reasons: list[str] = []
    limits = cfg.get("history_limits") or {}
    recent_open_cap = int(limits.get("recent_open_swot_cap") or 1)
    open_total_cap = int(limits.get("open_swot_total_cap") or 3)
    created_today_cap = int(limits.get("created_swot_today_cap") or 3)

    staleness_override_hours = float(cfg.get("staleness_override_hours") or 48)
    newest_age = history.get("newest_open_epic_age_hours")
    epic_is_stale = newest_age is not None and newest_age >= staleness_override_hours

    stale_override_fired = False
    if history["open_swot_recent_window"] >= recent_open_cap and not epic_is_stale:
        block_reasons.append(f"recent open EPIC-SWOT exists ({recent_hours}h window)")
    elif epic_is_stale and history["open_swot_recent_window"] >= recent_open_cap:
        stale_override_fired = True
    if history["open_swot_total"] >= open_total_cap and not epic_is_stale:
        block_reasons.append("too many open EPIC-SWOT items")
    elif epic_is_stale and history["open_swot_total"] >= open_total_cap:
        stale_override_fired = True
    if stale_override_fired:
        reasons.append(
            f"open EPIC-SWOT is stale ({newest_age:.1f}h old"
            f" ≥ {staleness_override_hours:.0f}h override); allowing new creation"
        )
    if history["created_swot_today"] >= created_today_cap:
        block_reasons.append("daily EPIC-SWOT cap reached")
    if history.get("open_pending_task", 0) >= 1:
        block_reasons.append("open 'Generate next EPIC-SWOT' task already exists")
    if history.get("live_query_failed"):
        block_reasons.append(
            "bd live query failed — blocking to prevent duplicate creation"
        )

    if block_reasons:
        score -= float(cfg.get("block_penalty") or 0.8)
    if budget_decision == "halt_human":
        score -= float(cfg.get("halt_human_penalty") or 0.5)
        block_reasons.append("budget decision is halt_human")

    confidence = max(0.0, min(1.0, score))
    threshold = float(cfg.get("confidence_threshold") or 0.55)
    allow = confidence >= threshold and not block_reasons
    decision_reason = (
        "allow"
        if allow
        else (
            ", ".join(block_reasons) if block_reasons else "confidence below threshold"
        )
    )
    return {
        "allow_create": allow,
        "confidence_score": round(confidence, 3),
        "threshold": threshold,
        "decision_reason": decision_reason,
        "policy_config": {
            "recent_open_hours": recent_hours,
            "rolling_days": rolling_days,
            "history_limits": limits,
        },
        "signals": {
            "session_est_tokens": session_est_tokens,
            "open_tasks": open_tasks,
            "changed_files": changed_files,
            "event_count": event_count,
            "low_coverage_fields": low_cov_fields,
            "budget_decision": budget_decision,
        },
        "history": history,
        "reasons": reasons,
    }


def ensure_epic_swot_chain() -> dict[str, Any]:
    """Create a next-cycle EPIC-SWOT and child task for closeout continuity."""
    now_utc = datetime.now(timezone.utc)
    stamp_date = now_utc.date().isoformat()
    stamp_ts = now_utc.strftime("%Y%m%dT%H%M%SZ")
    telemetry_key = f"EPIC-SWOT-NEXT-{stamp_ts}"
    epic_title = f"EPIC-SWOT NEXT [{stamp_ts}]: Post-Closeout SWOT Seed ({stamp_date})"
    epic_desc = (
        "Created automatically during session closeout. Ensure next session begins with fresh "
        "SWOT from governance/token/routing/pre-session telemetry and spawns a new EPIC-SWOT "
        "execution plan for the following cycle."
    )
    task_title = f"Generate next EPIC-SWOT [{stamp_ts}] before final closeout"
    task_desc = (
        "At end of long session, aggregate latest governance_intelligence/token_governance/"
        "unified_guard/routing/pre_session metrics, publish SWOT, create next-cycle EPIC-SWOT, "
        "and link it as successor continuity."
    )

    code_epic, out_epic = _run_bd(
        [
            "create",
            "--type",
            "epic",
            "--priority",
            "2",
            "--title",
            epic_title,
            "--description",
            epic_desc,
        ],
        timeout=60,
    )
    epic_id = _extract_issue_id(out_epic)

    code_task, out_task = _run_bd(
        [
            "create",
            "--type",
            "task",
            "--priority",
            "2",
            "--title",
            task_title,
            "--description",
            task_desc,
        ],
        timeout=60,
    )
    task_id = _extract_issue_id(out_task)

    parent_update: dict[str, Any] = {"exit": None, "output": "", "ok": False}
    if epic_id and task_id:
        upd_code, upd_out = _run_bd(
            ["update", task_id, "--parent", epic_id], timeout=30
        )
        parent_update = {
            "exit": upd_code,
            "output": upd_out[:1200],
            "ok": upd_code == 0,
        }

    return {
        "ok": code_epic == 0 and code_task == 0,
        "telemetry_key": telemetry_key,
        "timestamp_utc": stamp_ts,
        "epic_title": epic_title,
        "task_title": task_title,
        "epic_id": epic_id,
        "task_id": task_id,
        "epic_create_exit": code_epic,
        "task_create_exit": code_task,
        "epic_create_output": out_epic[:1200],
        "task_create_output": out_task[:1200],
        "parent_update": parent_update,
    }


def promote_learnings_to_wiki(*, execute: bool, runner=None) -> dict[str, Any]:
    """Run promote_to_wiki.py and return a verdict dict.

    Args:
        execute: if True, pass --execute; else dry-run (no files written).
        runner: injectable callable(cmd) -> (returncode, output) for testing.
                Defaults to _run.
    Returns:
        {"ok": bool, "promoted": int, "skipped_reason": str}
    Fail-open: never raises.
    """
    result: dict[str, Any] = {"ok": False, "promoted": 0, "skipped_reason": ""}
    try:
        cmd = [sys.executable, str(_REPO / "scripts" / "promote_to_wiki.py")]
        if execute:
            cmd.append("--execute")
        else:
            cmd.append("--dry-run")
        _runner = runner if runner is not None else _run
        code, out = _runner(cmd)
        if code != 0:
            result["skipped_reason"] = f"promote_to_wiki exited {code}"
            return result
        try:
            payload = json.loads(out)
            result["promoted"] = int(payload.get("promoted") or 0)
            result["ok"] = True
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            result["skipped_reason"] = f"malformed JSON: {exc}"
    except Exception as exc:  # noqa: BLE001
        result["skipped_reason"] = f"unexpected error: {exc}"
    return result


def wiki_git_push(wiki_root: Path, *, runner=None) -> dict[str, Any]:
    """Commit promoted learnings in wiki_root, push a branch, open a PR.

    Wiki main is hook-protected so we must use a feature branch + PR.
    Fail-open: never raises; returns {ok, branch, pr_url, skipped_reason}.
    """
    result: dict[str, Any] = {
        "ok": False,
        "branch": "",
        "pr_url": "",
        "skipped_reason": "",
    }
    try:
        import datetime as _dt
        import shutil

        if not wiki_root.is_dir():
            result["skipped_reason"] = f"wiki root not found: {wiki_root}"
            return result
        if not shutil.which("git"):
            result["skipped_reason"] = "git not on PATH"
            return result

        _r = runner if runner is not None else _run

        # Only proceed if there are staged/unstaged changes in the wiki
        _, status_out = _r(["git", "-C", str(wiki_root), "status", "--porcelain"])
        if not status_out.strip():
            result["ok"] = True
            result["skipped_reason"] = "no changes to commit"
            return result

        stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        branch = f"learnings/auto-promote-{stamp}"

        for cmd in [
            ["git", "-C", str(wiki_root), "checkout", "-b", branch],
            ["git", "-C", str(wiki_root), "add", "02_LEARNINGS/"],
            [
                "git",
                "-C",
                str(wiki_root),
                "commit",
                "-m",
                f"chore: auto-promote harness learnings {stamp}",
            ],
            ["git", "-C", str(wiki_root), "push", "-u", "origin", branch],
        ]:
            code, out = _r(cmd)
            if code != 0:
                result["skipped_reason"] = (
                    f"{' '.join(cmd[2:4])} failed ({code}): {out[:200]}"
                )
                return result

        result["branch"] = branch

        if shutil.which("gh"):
            pr_body = (
                "Auto-promoted harness learnings from `session_closeout.py --promote-wiki`.\n\n"
                "Review for accuracy before merging — content is generated from `.agents/learnings/` "
                "and `07_LOGS_AND_AUDIT/auto_turn_thresholds/`."
            )
            pr_cmd = [
                "gh",
                "pr",
                "create",
                "--repo",
                "kas1987/chromatic-wiki",
                "--base",
                "main",
                "--head",
                branch,
                "--title",
                f"chore: auto-promote learnings {stamp}",
                "--body",
                pr_body,
            ]
            pr_code, pr_out = _r(pr_cmd)
            if pr_code == 0:
                result["pr_url"] = pr_out.strip()
            else:
                result["skipped_reason"] = f"gh pr create failed: {pr_out[:200]}"

        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["skipped_reason"] = f"unexpected error: {exc}"
    return result


def _build_epic_swot_summary(epic: dict[str, Any] | None) -> dict[str, Any]:
    e = epic or {}
    return {
        "ok": bool(e.get("ok")),
        "telemetry_key": e.get("telemetry_key") or "",
        "timestamp_utc": e.get("timestamp_utc") or "",
        "epic_title": e.get("epic_title") or "",
        "epic_id": e.get("epic_id") or "",
        "task_id": e.get("task_id") or "",
        "parent_linked": bool((e.get("parent_update") or {}).get("ok")),
    }


def _apply_epic_swot_aliases(
    result: dict[str, Any], epic: dict[str, Any] | None
) -> None:
    summary = _build_epic_swot_summary(epic)
    result["epic_timestamp_utc"] = summary["timestamp_utc"]
    result["epic_title"] = summary["epic_title"]
    result["epic_swot_telemetry_key"] = summary["telemetry_key"]
    result["epic_swot_summary"] = summary


def _build_closeout_telemetry_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("epic_swot_summary") or {}
    policy = result.get("epic_swot_policy") or {}
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "invoked_by": result.get("invoked_by") or "",
        "budget_decision": (result.get("budget") or {}).get("decision") or "",
        "epic_swot_telemetry_key": result.get("epic_swot_telemetry_key") or "",
        "epic_timestamp_utc": result.get("epic_timestamp_utc") or "",
        "epic_title": result.get("epic_title") or "",
        "epic_id": summary.get("epic_id") or "",
        "task_id": summary.get("task_id") or "",
        "parent_linked": bool(summary.get("parent_linked")),
        "epic_policy_allow": bool(policy.get("allow_create", False)),
        "epic_policy_confidence": float(policy.get("confidence_score") or 0.0),
        "epic_policy_reason": str(policy.get("decision_reason") or ""),
        "auto_start_ok": bool(result.get("auto_start_ok", False)),
    }


def _closeout_telemetry_timestamp(snapshot: dict[str, Any]) -> str:
    generated_at = str(snapshot.get("generated_at_utc") or "").strip()
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _write_closeout_telemetry_snapshot(result: dict[str, Any]) -> dict[str, str]:
    snapshot = _build_closeout_telemetry_snapshot(result)
    rel_dir = Path(".agents") / "handoffs"
    latest_rel = rel_dir / "closeout_telemetry_latest.json"
    history_rel = (
        rel_dir / f"closeout_telemetry_{_closeout_telemetry_timestamp(snapshot)}.json"
    )
    payload = json.dumps(snapshot, indent=2)

    for rel in (latest_rel, history_rel):
        out = _REPO / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")

    return {
        "latest": latest_rel.as_posix(),
        "history": history_rel.as_posix(),
    }


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value


def _sanitize_argv(argv: list[str]) -> list[str]:
    # Guard against accidental placeholder args passed by wrappers.
    return [arg for arg in argv if arg != "."]


def _post_mortem_stamp(now: datetime | None = None) -> tuple[str, str]:
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return ts.strftime("%Y-%m-%d"), ts.strftime("%Y%m%dT%H%M%SZ")


def _git_loc_delta() -> dict[str, int]:
    code, out = _run(["git", "diff", "--numstat", "HEAD"], timeout=30)
    if code != 0 or not out:
        return {"insertions": 0, "deletions": 0, "changed_files": 0}
    insertions = 0
    deletions = 0
    changed_files = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_raw, del_raw = parts[0], parts[1]
        if add_raw.isdigit():
            insertions += int(add_raw)
        if del_raw.isdigit():
            deletions += int(del_raw)
        changed_files += 1
    return {
        "insertions": insertions,
        "deletions": deletions,
        "changed_files": changed_files,
    }


_CODE_SUFFIXES = (".py", ".go", ".ts", ".tsx", ".js", ".rs", ".sh")


def _changed_code_files() -> list[str]:
    """Code files changed vs HEAD (staged+unstaged+untracked)."""
    code, out = _run(["git", "status", "--porcelain"], timeout=30)
    if code != 0 or not out:
        return []
    files: list[str] = []
    for line in out.splitlines():
        path = line[3:].strip() if len(line) > 3 else ""
        if path and path.endswith(_CODE_SUFFIXES):
            files.append(path)
    return files


def run_change_gated_quality(*, run_pytest: bool) -> dict[str, Any]:
    """Default-on quality gates when code changed (-477a): ruff (fast) always,
    pytest when ``run_pytest``. Fail-open; returns a structured summary."""
    changed = _changed_code_files()
    summary: dict[str, Any] = {
        "code_changed": bool(changed),
        "changed_count": len(changed),
        "ruff": None,
        "pytest": None,
    }
    if not changed:
        return summary
    py_changed = [f for f in changed if f.endswith(".py")]
    if py_changed:
        code, out = _run(
            [sys.executable, "-m", "ruff", "check", *py_changed], timeout=120
        )
        summary["ruff"] = {"exit": code, "ok": code == 0, "output": out[:1500]}
    if run_pytest:
        code, out = _run([sys.executable, "-m", "pytest", "tests/", "-q"], timeout=600)
        summary["pytest"] = {"exit": code, "ok": code == 0, "output": out[:1500]}
    return summary


def _select_auto_turn_artifact_kind(result: dict[str, Any]) -> str:
    # Open beads imply in-flight work, so emit a learning checkpoint rather than a full post-mortem.
    if result.get("beads_ready"):
        return "checkpoint"
    return "post_mortem"


def _write_auto_turn_post_mortem(
    result: dict[str, Any],
    *,
    auto_turn_index: int,
    auto_turn_threshold: int,
    artifact_kind: str = "post_mortem",
) -> str:
    date_part, ts_part = _post_mortem_stamp()
    safe_kind = "checkpoint" if artifact_kind == "checkpoint" else "post_mortem"
    rel = (
        Path(".agents")
        / "council"
        / f"{date_part}-{safe_kind.replace('_', '-')}-auto-turn-{auto_turn_index:02d}.md"
    )
    out = _REPO / rel
    out.parent.mkdir(parents=True, exist_ok=True)

    budget = result.get("budget") or {}
    policy = result.get("epic_swot_policy") or {}
    auto_turn = result.get("auto_turn") or {}
    title = (
        "# Learning Checkpoint Report - Auto Turn Closeout"
        if safe_kind == "checkpoint"
        else "# Post-Mortem Council Report - Auto Turn Closeout"
    )
    notes = (
        "- Generated automatically to capture learnings mid-stream because auto-turn threshold was reached.",
        "- Continue active tasks, then run a final post-mortem at completion/session boundary.",
    )
    if safe_kind == "post_mortem":
        notes = (
            "- Generated automatically because auto-turn threshold was reached.",
            "- Run harvest/session compaction and review governance recommendations next cycle.",
        )

    content = "\n".join(
        [
            title,
            "",
            f"- generated_at_utc: {ts_part}",
            f"- auto_turn_index: {auto_turn_index}",
            f"- auto_turn_threshold: {auto_turn_threshold}",
            f"- artifact_kind: {safe_kind}",
            f"- invoked_by: {result.get('invoked_by', '')}",
            "",
            "## Outcome",
            f"- budget_decision: {budget.get('decision', '')}",
            f"- epic_policy_allow_create: {policy.get('allow_create', False)}",
            f"- epic_policy_confidence: {policy.get('confidence_score', 0.0)}",
            f"- epic_policy_reason: {policy.get('decision_reason', '')}",
            f"- harvest_mode: {auto_turn.get('harvest_mode', 'none')}",
            f"- auto_start_ok: {result.get('auto_start_ok', False)}",
            "",
            "## Artifacts",
            f"- closeout_telemetry_latest: {result.get('closeout_telemetry_path', '')}",
            f"- closeout_telemetry_history: {result.get('closeout_telemetry_history_path', '')}",
            "",
            "## Notes",
            notes[0],
            notes[1],
            "",
        ]
    )
    out.write_text(content, encoding="utf-8")
    return rel.as_posix()


def _append_auto_turn_observation(result: dict[str, Any]) -> str:
    rel = Path(".agents") / "handoffs" / "auto_turn_observations.jsonl"
    out = _REPO / rel
    out.parent.mkdir(parents=True, exist_ok=True)

    auto_turn = result.get("auto_turn") or {}
    policy = result.get("epic_swot_policy") or {}
    policy_signals = policy.get("signals") or {}
    loc_delta = (auto_turn.get("trigger_eval") or {}).get(
        "loc_delta"
    ) or _git_loc_delta()
    observation = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "invoked_by": result.get("invoked_by") or "",
        "auto_turn_index": int(auto_turn.get("index") or 0),
        "auto_turn_threshold": int(auto_turn.get("threshold") or 0),
        "triggered_closeout": bool(auto_turn.get("triggered_closeout")),
        "turn_threshold_hit": bool(
            (auto_turn.get("trigger_eval") or {}).get("turn_threshold_hit")
        ),
        "multi_signal_hit": bool(
            (auto_turn.get("trigger_eval") or {}).get("multi_signal_hit")
        ),
        "required_signal_hits": int(
            (auto_turn.get("trigger_eval") or {}).get("required_signal_hits") or 0
        ),
        "signal_hit_count": int(
            (auto_turn.get("trigger_eval") or {}).get("signal_hit_count") or 0
        ),
        "hit_signals": list(
            (auto_turn.get("trigger_eval") or {}).get("hit_signals") or []
        ),
        "artifact_kind": auto_turn.get("artifact_kind") or "none",
        "harvest_mode": auto_turn.get("harvest_mode") or "none",
        "beads_ready_count": len(result.get("beads_ready") or []),
        "git_changed_files": len((result.get("git") or {}).get("status_short") or []),
        "loc_insertions": int(loc_delta.get("insertions") or 0),
        "loc_deletions": int(loc_delta.get("deletions") or 0),
        "policy_confidence": float(policy.get("confidence_score") or 0.0),
        "policy_threshold": float(policy.get("threshold") or 0.0),
        "policy_allow_create": bool(policy.get("allow_create", False)),
        "policy_open_tasks": int(policy_signals.get("open_tasks") or 0),
        "policy_changed_files": int(policy_signals.get("changed_files") or 0),
        "policy_event_count": int(policy_signals.get("event_count") or 0),
        "policy_budget_decision": str(policy_signals.get("budget_decision") or ""),
    }
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(observation) + "\n")
    return rel.as_posix()


_SHIP_EVIDENCE = _REPO / ".agents" / "handoffs" / "ship_evidence.json"


def evaluate_ship_completion(
    beads_ready: list[str], *, evidence_path: Path | None = None
) -> dict[str, Any]:
    """Run the ClosureMagnet ship-completion check (ship-idea S8+S10+DoD) over the
    session's beads (Gap C closeout wiring).

    Evidence source: ``.agents/handoffs/ship_evidence.json`` — either a flat dict of
    ship fields (applies to all beads) or ``{bead_id: {lean_ok, live_ok, dod_ok | ship_log}}``.
    Returns per-bead verdicts and the beads that must NOT be closed
    (recommended_action == "replan"). Fail-open: no evidence ⇒ nothing blocked.
    """
    result: dict[str, Any] = {
        "ok": True,
        "evaluated": [],
        "block_close": [],
        "applicable": False,
    }
    path = evidence_path or _SHIP_EVIDENCE
    if not path.is_file():
        result["skip_reason"] = "no ship_evidence.json"
        return result
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result["ok"] = False
        result["error"] = str(exc)
        return result
    if not isinstance(evidence, dict) or not evidence:
        result["skip_reason"] = "evidence not a non-empty dict"
        return result

    try:
        from magnets.closure_magnet import ClosureMagnet  # type: ignore
    except Exception as exc:  # noqa: BLE001
        result["ok"] = False
        result["error"] = f"closure magnet import failed: {exc}"
        return result

    magnet = ClosureMagnet()
    per_bead_keyed = all(isinstance(v, dict) for v in evidence.values())
    for bead in beads_ready:
        bead_signal = (
            dict(evidence.get(bead) or {}) if per_bead_keyed else dict(evidence)
        )
        if not bead_signal:
            continue
        result["applicable"] = True
        bead_signal.setdefault("validation_passed", True)
        # Note: do NOT inject bead_id here — evidence is already per-bead scoped, and
        # forcing a bead_id would scope-filter unscoped [S8]/[S10] log lines to nothing.
        event = magnet.observe(bead, "closure", bead_signal)
        ship = (event.observed_signal or {}).get("ship_completion") or {}
        verdict = {
            "bead_id": bead,
            "recommended_action": event.recommended_action,
            "missing": ship.get("missing", []),
        }
        result["evaluated"].append(verdict)
        if event.recommended_action == "replan":
            result["block_close"].append(verdict)
    return result


def git_snapshot() -> dict[str, Any]:
    snap: dict[str, Any] = {}
    for key, args in [
        ("branch", ["git", "branch", "--show-current"]),
        ("last_commit", ["git", "log", "-1", "--oneline"]),
        ("status_short", ["git", "status", "--short"]),
    ]:
        code, out = _run(args, timeout=30)
        if key == "status_short":
            snap[key] = out.splitlines() if out else []
        else:
            snap[key] = out if code == 0 else "unknown"
    return snap


def beads_ready_ids() -> list[str]:
    code, out = _run(["bd", "ready"], timeout=30)
    if code != 0 or not out:
        return []
    ids: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # bd ready often prints "id: title" or just id
        token = line.split()[0] if line else ""
        if token and not token.startswith("#"):
            ids.append(token.rstrip(":"))
    return ids[:10]


def log_activity(summary: str, *, bead_id: str = "", decision: str = "ok") -> None:
    lock_owner = os.environ.get("CHROMATIC_SESSION_ID", "").strip()
    _run(
        [
            sys.executable,
            str(_REPO / "scripts" / "log_agent_activity.py"),
            "log",
            "--event",
            "phase.complete",
            "--lane",
            "agent",
            "--summary",
            summary[:500],
            "--decision",
            decision,
            "--lock-owner",
            lock_owner,
        ],
        timeout=60,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Harness session closeout")
    parser.add_argument(
        "--invoked-by",
        choices=[
            "cursor",
            "claude",
            "claude_code",
            "vscode",
            "cli",
            "codex",
            "scheduler",
        ],
        default="cli",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--harvest", action="store_true", help="Run harvest_rigs --execute"
    )
    parser.add_argument("--wiki-dry-run", action="store_true")
    parser.add_argument(
        "--promote-wiki",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Promote high-confidence learnings to the Chromatic Wiki after harvest",
    )
    parser.add_argument("--git-triage", action="store_true")
    parser.add_argument(
        "--with-api", action="store_true", help="Phase C: optional API budget ingest"
    )
    parser.add_argument(
        "--spawn-successor",
        action="store_true",
        help="Spawn when budget allows (also needs CHROMATIC_AUTO_SPAWN=1)",
    )
    parser.add_argument("--no-spawn", action="store_true", help="Never spawn successor")
    parser.add_argument("--summary", default="", help="Override closeout summary")
    parser.add_argument(
        "--pytest",
        action="store_true",
        help="Force pytest tests/ -q even if no code changed",
    )
    parser.add_argument(
        "--no-pytest",
        action="store_true",
        help="Skip pytest in the change-gated quality step (ruff still runs on changed .py)",
    )
    parser.add_argument(
        "--epic-policy-config",
        default="",
        help="Optional path to an alternate epic SWOT policy config JSON file",
    )
    parser.add_argument(
        "--epic-swot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Create a next-session EPIC-SWOT chain during closeout",
    )
    parser.add_argument(
        "--auto-start-next-agent",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After closeout, trigger successor spawn attempt and pre-session boot",
    )
    parser.add_argument(
        "--auto-turn-index",
        type=int,
        default=_env_int("CHROMATIC_AUTO_TURN_INDEX", 0),
        help="Current autonomous turn count in the active cycle",
    )
    parser.add_argument(
        "--auto-turn-threshold",
        type=int,
        default=_env_int("CHROMATIC_AUTO_TURN_THRESHOLD", 5),
        help="Turn threshold that triggers auto post-mortem + session-end harvest",
    )
    args = parser.parse_args(_sanitize_argv(sys.argv[1:]))

    source = args.invoked_by
    if source == "claude":
        source = "claude_code"

    git = git_snapshot()
    beads = beads_ready_ids()
    ledger = BudgetLedger(_REPO)
    snapshot = ledger.snapshot()

    # Gap C: enforce /ship-idea S8+S10+DoD before a bead is considered closeable.
    ship_completion = evaluate_ship_completion(beads)
    ship_risks: list[str] = []
    ship_goals: list[str] = []
    for v in ship_completion.get("block_close", []):
        miss = ",".join(v.get("missing", [])) or "ship-idea gates"
        ship_risks.append(
            f"ship incomplete — bead {v['bead_id']} missing {miss}; do NOT close"
        )
        ship_goals.append(f"Finish ship-idea {miss} for {v['bead_id']}")

    handoff_prep: dict[str, Any] = {
        "directive_summary": args.summary
        or f"Session closeout ({source}). Budget decision: {snapshot.decision}.",
        "decision": "review" if snapshot.decision != "halt_human" else "halt",
        "next_session_goals": ship_goals
        + [
            beads[0] if beads else "bd ready",
            "Read .agents/handoffs/transfer_packet.json",
            "Run new_session_bootstrap.py",
        ],
        "context_snapshot": {"objective": "Continue harness mission from handoff"},
        "risks": list(snapshot.reasons) + ship_risks,
    }

    result: dict[str, Any] = {
        "invoked_by": source,
        "dry_run": args.dry_run,
        "git": git,
        "beads_ready": beads,
        "ship_completion": ship_completion,
        "budget": snapshot.to_budget_dict(),
        "closeout_telemetry_path": "",
        "closeout_telemetry_history_path": "",
        "epic_timestamp_utc": "",
        "epic_title": "",
        "epic_swot_telemetry_key": "",
        "epic_swot_summary": {
            "ok": False,
            "telemetry_key": "",
            "timestamp_utc": "",
            "epic_title": "",
            "epic_id": "",
            "task_id": "",
            "parent_linked": False,
        },
        "epic_swot_policy": {
            "allow_create": False,
            "confidence_score": 0.0,
            "threshold": 0.55,
            "decision_reason": "not evaluated",
        },
        "harness_health": {
            "exit": None,
            "ok": False,
            "overall_status": "unknown",
            "readiness_score": None,
            "counts": {},
            "path": "07_LOGS_AND_AUDIT/harness_health/latest.json",
        },
        "auto_start_ok": False,
        "auto_turn": {
            "index": max(0, args.auto_turn_index),
            "threshold": max(1, args.auto_turn_threshold),
            "triggered_closeout": False,
            "harvest_mode": "none",
            "artifact_kind": "none",
            "post_mortem_path": "",
            "observation_log_path": "",
            "trigger_eval": {
                "triggered": False,
                "turn_threshold_hit": False,
                "multi_signal_hit": False,
                "required_signal_hits": 0,
                "signal_hit_count": 0,
                "hit_signals": [],
                "signals": {},
                "loc_delta": {"insertions": 0, "deletions": 0, "changed_files": 0},
            },
        },
    }

    auto_turn_index = max(0, args.auto_turn_index)
    auto_turn_threshold = max(1, args.auto_turn_threshold)

    if args.dry_run:
        packet = build_transfer_packet(
            _REPO,
            source_runtime=source,
            snapshot=snapshot,
            handoff_prep=handoff_prep,
            handoff_path="12_HANDOFFS/sessions/DRY_RUN.md",
            beads_ready=beads,
            git_snapshot=git,
        )
        result["transfer_packet"] = packet
        print(json.dumps(result, indent=2))
        return 0

    handoff_path = write_handoff(
        handoff_prep,
        agent=source,
        beads_ready=beads,
        next_command="bd ready",
    )
    rel_handoff = handoff_path.relative_to(_REPO).as_posix()

    packet = build_transfer_packet(
        _REPO,
        source_runtime=source,
        snapshot=snapshot,
        handoff_prep=handoff_prep,
        handoff_path=rel_handoff,
        beads_ready=beads,
        git_snapshot=git,
    )
    write_transfer_artifacts(_REPO, packet)
    result["handoff_path"] = rel_handoff
    result["transfer_packet_path"] = ".agents/handoffs/transfer_packet.json"

    if args.epic_swot:
        policy_config_path = (
            Path(args.epic_policy_config) if args.epic_policy_config else None
        )
        policy = evaluate_epic_swot_policy(
            snapshot=snapshot,
            beads_ready=beads,
            git=git,
            policy_config_path=policy_config_path,
        )
        result["epic_swot_policy"] = policy
        if policy.get("allow_create"):
            result["epic_swot"] = ensure_epic_swot_chain()
            _apply_epic_swot_aliases(result, result.get("epic_swot"))
        else:
            reuse = find_latest_open_swot_epic()
            result["epic_swot"] = {
                "ok": False,
                "skipped": True,
                "reason": policy.get("decision_reason", "blocked by policy"),
                "confidence_score": policy.get("confidence_score", 0.0),
            }
            if reuse:
                result["epic_swot"]["reused_open_epic"] = True
                result["epic_swot"]["epic_id"] = reuse.get("epic_id", "")
                result["epic_swot"]["epic_title"] = reuse.get("epic_title", "")
                result["epic_swot"]["timestamp_utc"] = reuse.get("timestamp_utc", "")
                result["epic_swot"]["telemetry_key"] = reuse.get("telemetry_key", "")
                task_reuse = find_open_swot_task_for_epic(reuse.get("epic_id", ""))
                if task_reuse:
                    result["epic_swot"]["reused_open_task"] = True
                    result["epic_swot"]["task_id"] = task_reuse.get("task_id", "")
                    result["epic_swot"]["task_title"] = task_reuse.get("task_title", "")
                result["epic_swot"]["parent_update"] = {"ok": False}
                _apply_epic_swot_aliases(result, result.get("epic_swot"))

    auto_turn_policy = _load_auto_turn_policy_config()
    trigger_eval = _evaluate_auto_turn_trigger(
        auto_turn_index=auto_turn_index,
        auto_turn_threshold=auto_turn_threshold,
        beads_ready_count=len(beads),
        git_changed_files=len((git or {}).get("status_short") or []),
        policy_signals=(result.get("epic_swot_policy") or {}).get("signals") or {},
        policy_config=auto_turn_policy,
    )
    result["auto_turn"]["trigger_eval"] = trigger_eval
    auto_turn_triggered = bool(trigger_eval.get("triggered"))
    result["auto_turn"]["triggered_closeout"] = auto_turn_triggered

    harvest_mode = "none"
    if args.harvest:
        harvest_mode = "full"
    elif auto_turn_triggered:
        harvest_mode = "session_end"
    result["auto_turn"]["harvest_mode"] = harvest_mode
    if harvest_mode != "none":
        harvest_cmd = [
            sys.executable,
            str(_REPO / "scripts" / "harvest_rigs.py"),
            "--execute",
        ]
        if harvest_mode == "session_end":
            harvest_cmd.append("--session-end")
        harvest_code, harvest_out = _run(harvest_cmd, timeout=180)
        result["harvest"] = {
            "mode": harvest_mode,
            "exit": harvest_code,
            "ok": harvest_code == 0,
            "output": harvest_out[:2000],
        }

    if args.promote_wiki and harvest_mode != "none":
        promo = promote_learnings_to_wiki(execute=True)
        result["wiki_promotion"] = promo
        # Auto-commit + branch-push + PR if any files were actually copied (-t5ob)
        if promo.get("ok") and promo.get("promoted", 0) > 0:
            _wiki_raw = os.environ.get("CHROMATIC_WIKI_ROOT", "")
            _wiki_root = (
                Path(_wiki_raw).resolve()
                if _wiki_raw
                else Path(r"C:\Users\kas41\chromatic-wiki")
            )
            result["wiki_git_push"] = wiki_git_push(_wiki_root)
        else:
            result["wiki_git_push"] = {
                "ok": True,
                "branch": "",
                "pr_url": "",
                "skipped_reason": "nothing promoted; no wiki commit needed",
            }
    elif harvest_mode == "none":
        result["wiki_promotion"] = {
            "ok": False,
            "promoted": 0,
            "skipped_reason": "harvest_mode is none; wiki promotion skipped",
        }
        result["wiki_git_push"] = {
            "ok": True,
            "skipped_reason": "wiki promotion skipped",
        }
    else:
        result["wiki_promotion"] = {
            "ok": False,
            "promoted": 0,
            "skipped_reason": "--no-promote-wiki flag set",
        }
        result["wiki_git_push"] = {
            "ok": True,
            "skipped_reason": "--no-promote-wiki flag set",
        }

    if args.wiki_dry_run:
        _run(
            [
                sys.executable,
                str(_REPO / "scripts" / "analyze_auto_turn_observations.py"),
                "--write",
            ],
            timeout=120,
        )
        _run(
            [
                sys.executable,
                str(_REPO / "scripts" / "promote_to_wiki.py"),
                "--dry-run",
            ],
            timeout=120,
        )

    if args.git_triage:
        _run(
            [sys.executable, str(_REPO / "scripts" / "git_triage.py"), "--from-log"],
            timeout=90,
        )

    # Change-gated quality (-477a): ruff/pytest default-on when code changed.
    run_pytest = args.pytest or not args.no_pytest
    quality = run_change_gated_quality(run_pytest=run_pytest)
    result["quality"] = quality
    if quality.get("pytest") and not quality["pytest"]["ok"]:
        result["pytest_exit"] = quality["pytest"]["exit"]
        handoff_prep["risks"].append(
            f"pytest failed (exit {quality['pytest']['exit']})"
        )
    if quality.get("ruff") and not quality["ruff"]["ok"]:
        handoff_prep["risks"].append("ruff check found issues")

    log_activity(
        args.summary or f"session closeout ({source}); budget={snapshot.decision}",
        decision="ok" if snapshot.decision != "halt_human" else "halt",
    )

    spawn = False
    if not args.no_spawn and snapshot.decision == "spawn":
        if args.spawn_successor or os.environ.get(
            "CHROMATIC_AUTO_SPAWN", ""
        ).strip() in (
            "1",
            "true",
            "yes",
        ):
            spawn = True

    if spawn:
        code, out = _run(
            [
                sys.executable,
                str(_REPO / "scripts" / "spawn_successor_agent.py"),
                "--packet",
                str(_REPO / ".agents" / "handoffs" / "transfer_packet.json"),
            ],
            timeout=120,
        )
        result["spawn_exit"] = code
        result["spawn_output"] = out[:2000]
    else:
        result["spawn"] = "skipped"
        result["spawn_reason"] = (
            "budget or CHROMATIC_AUTO_SPAWN"
            if snapshot.decision != "spawn"
            else "not requested"
        )

    if args.auto_start_next_agent:
        packet_path = str(_REPO / ".agents" / "handoffs" / "transfer_packet.json")
        succ_code, succ_out = _run(
            [
                sys.executable,
                str(_REPO / "scripts" / "spawn_successor_agent.py"),
                "--packet",
                packet_path,
                "--force",
            ],
            timeout=180,
        )
        boot_code, boot_out = _run(
            [
                sys.executable,
                str(_REPO / "scripts" / "session_boot_automation.py"),
                "--invoked-by",
                "preflight",
            ],
            timeout=240,
        )
        result["next_session_auto_start"] = {
            "successor_spawn_force_exit": succ_code,
            "successor_spawn_force_output": succ_out[:2000],
            "session_boot_exit": boot_code,
            "session_boot_output": boot_out[:2000],
            "ok": succ_code == 0 and boot_code == 0,
        }
    result["auto_start_ok"] = bool(
        (result.get("next_session_auto_start") or {}).get("ok", False)
    )

    if args.with_api:
        result["with_api"] = "not_implemented_phase_c"

    telemetry_paths = _write_closeout_telemetry_snapshot(result)
    result["closeout_telemetry_path"] = telemetry_paths["latest"]
    result["closeout_telemetry_history_path"] = telemetry_paths["history"]

    result["harness_health"] = _run_harness_health_snapshot()

    if auto_turn_triggered:
        artifact_kind = _select_auto_turn_artifact_kind(result)
        result["auto_turn"]["artifact_kind"] = artifact_kind
        post_mortem_path = _write_auto_turn_post_mortem(
            result,
            auto_turn_index=auto_turn_index,
            auto_turn_threshold=auto_turn_threshold,
            artifact_kind=artifact_kind,
        )
        result["auto_turn"]["post_mortem_path"] = post_mortem_path

    result["auto_turn"]["observation_log_path"] = _append_auto_turn_observation(result)

    # Emit session.end telemetry to the two-log audit spine (fail-open).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_RUNTIME"))
        from audit.session_events import emit_session_end

        result["session_end_event"] = emit_session_end(
            Path(__file__).resolve().parents[1], invoked_by=args.invoked_by
        )
    except Exception as exc:  # noqa: BLE001
        result["session_end_event"] = {"ok": False, "error": str(exc)}

    result["learning_outcomes"] = _emit_injected_learning_outcomes()

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
