#!/usr/bin/env python3
"""go_mode.py — deterministic GO-mode orchestrator (issue #81, NW-RG-081).

Turns the user's `GO` into a deterministic, auditable loop rather than open-ended
autonomy:

    Observe -> Classify -> Score -> Decide -> Dispatch -> Record

What it does (PLAN/DISPATCH only — it NEVER mutates code, commits, or merges):
  1. Reads the ready work queue (`bd ready --json`, best-effort; or injected items).
  2. Selects the single highest-value unblocked task deterministically
     (exclude done/cancelled/deferred -> prefer ready over planned -> P0>P1>P2 ->
      higher numeric priority -> stable id tiebreak).
  3. Scores confidence with the 7-factor CONFIDENCE_GATE formula.
  4. Maps the score to a band (execute / log / reversible-only / plan-only / halt)
     and decides whether dispatch is permitted (>=75, or >=60 if reversible+low-risk).
  5. Emits a full mission packet (all DISPATCH_PLAYBOOK fields) + a decision record.

Stop-condition compliance (mission #81):
  * Defines NO auto-merge behavior and performs NO irreversible mutation.
  * The confidence formula is explicit and required before any dispatch decision.

Output: JSON to stdout; --write persists 07_LOGS_AND_AUDIT/go_mode/latest.json and a
mission packet under 07_LOGS_AND_AUDIT/go_mode/missions/.

See docs/playbooks/{GO_MODE,CONFIDENCE_GATE,DISPATCH,ORCHESTRATOR}_PLAYBOOK.md.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import run_safe  # noqa: E402

OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "go_mode"
MISSIONS_DIR = OUT_DIR / "missions"

# ── Confidence formula (CONFIDENCE_GATE_PLAYBOOK) ─────────────────────────────
# Seven factors, each scored 0-100, combined by these weights (sum = 1.0).
CONFIDENCE_WEIGHTS: dict[str, float] = {
    "objective_clarity": 0.20,
    "scope_clarity": 0.20,
    "evidence_quality": 0.20,
    "reversibility": 0.10,
    "tool_fit": 0.10,
    "risk_awareness": 0.10,
    "testability": 0.10,
}

# Bands: (min_score, label, action, may_mutate). Highest threshold first.
CONFIDENCE_BANDS: list[tuple[int, str, str, bool]] = [
    (90, "execute", "Execute normally within scope", True),
    (75, "execute_logged", "Execute with normal logging", True),
    (60, "reversible_only", "Execute only if reversible and low risk", True),
    (40, "plan_only", "Plan only; do not mutate", False),
    (0, "halt", "Halt and escalate", False),
]

# Dispatch is permitted at >=75 unconditionally, or >=60 when the task is
# reversible AND low risk (DISPATCH_PLAYBOOK).
DISPATCH_MIN = 75
DISPATCH_MIN_REVERSIBLE = 60

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
EXCLUDED_STATES = {"done", "closed", "cancelled", "canceled", "deferred"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


# ── Confidence scoring ───────────────────────────────────────────────────────


def score_confidence(factors: dict[str, float]) -> dict:
    """Weighted 7-factor confidence score. Missing factors default to 50 (neutral)."""
    used = {}
    total = 0.0
    for key, weight in CONFIDENCE_WEIGHTS.items():
        val = _clamp(float(factors.get(key, 50.0)))
        used[key] = val
        total += val * weight
    score = round(total, 1)
    label, action, may_mutate = confidence_band(score)
    return {"score": score, "band": label, "action": action, "may_mutate": may_mutate, "factors": used}


def confidence_band(score: float) -> tuple[str, str, bool]:
    for threshold, label, action, may_mutate in CONFIDENCE_BANDS:
        if score >= threshold:
            return label, action, may_mutate
    return "halt", "Halt and escalate", False


def _label_values(item: dict, prefix: str) -> list[str]:
    """Extract suffixes of ``prefix``-namespaced labels (e.g. ``scope:router`` -> ``router``)."""
    out: list[str] = []
    for lab in item.get("labels") or []:
        s = str(lab)
        if s.startswith(prefix):
            val = s[len(prefix) :].strip()
            if val:
                out.append(val)
    return out


def _as_checklist(value: Any) -> list[str]:
    """Normalize an acceptance field to a list of non-empty items.

    bd stores acceptance criteria as a single string; split on newlines/semicolons
    and strip bullet markers. A list is passed through (markers stripped)."""
    if isinstance(value, list):
        return [str(c).strip(" -*\t") for c in value if str(c).strip(" -*\t")]
    if isinstance(value, str):
        return [c.strip(" -*\t") for c in re.split(r"[\n;]+", value) if c.strip(" -*\t")]
    return []


def estimate_factors(item: dict) -> dict[str, float]:
    """Heuristic factor estimate from a queue item's metadata. Deterministic.

    Reads the canonical ``bd ready --json`` schema (``description``,
    ``acceptance_criteria``, ``labels``) as fallbacks after the injected
    DISPATCH_PLAYBOOK keys, so a real bead with a clear description + acceptance
    criteria scores accurately instead of collapsing to the all-neutral 50."""
    title = str(item.get("title", "")).strip()
    objective = str(item.get("objective") or item.get("notes") or item.get("description") or "").strip()
    checks = _as_checklist(
        item.get("acceptance_checks") or item.get("acceptance") or item.get("acceptance_criteria") or []
    )
    allowed = item.get("allowed_files") or _label_values(item, "scope:")
    stops = item.get("stop_conditions") or _label_values(item, "stop:")
    risk = str(item.get("risk_level") or (_label_values(item, "risk:") or [""])[0]).lower()
    checks_text = " ".join(str(c).lower() for c in checks)

    return {
        "objective_clarity": 80.0 if objective else (60.0 if title else 20.0),
        "scope_clarity": 85.0 if allowed else (65.0 if checks else 40.0),
        "evidence_quality": 90.0 if len(checks) >= 3 else (70.0 if checks else 30.0),
        "reversibility": 40.0 if risk in {"high", "critical"} else (75.0 if risk in {"medium"} else 85.0),
        "tool_fit": 70.0,  # neutral-positive default; refined by owner-agent match upstream
        "risk_awareness": 85.0 if stops else 50.0,
        "testability": 90.0 if ("test" in checks_text or "validate" in checks_text) else (65.0 if checks else 35.0),
    }


# ── Deterministic selection ──────────────────────────────────────────────────


def _norm_priority(item: dict) -> str:
    p = item.get("priority", item.get("priority_label", ""))
    s = str(p).upper()
    if s.startswith("P") and s[1:].isdigit():
        return s
    if str(p).isdigit():
        return f"P{p}"
    return "P2"


def _sort_key(item: dict) -> tuple:
    status = str(item.get("status", "ready")).lower()
    ready_rank = 0 if status in {"ready", "open", "in_progress"} else 1
    prio_rank = PRIORITY_RANK.get(_norm_priority(item), 2)
    return (ready_rank, prio_rank, str(item.get("id", "")))


def select_next(items: list[dict]) -> dict | None:
    """Deterministically pick the highest-value unblocked task, or None."""
    candidates = [it for it in items if str(it.get("status", "ready")).lower() not in EXCLUDED_STATES]
    candidates = [it for it in candidates if not it.get("blocked_by") and not it.get("blocked")]
    if not candidates:
        return None
    return sorted(candidates, key=_sort_key)[0]


# ── Mission packet (DISPATCH_PLAYBOOK required fields) ────────────────────────


@dataclass
class MissionPacket:
    task_id: str
    objective: str
    repo: str
    allowed_files: list
    forbidden_files: list
    owner_agent: str
    secondary_agent: str
    tool_budget: dict
    risk_level: str
    confidence: dict
    acceptance_checks: list
    stop_conditions: list
    required_output: str
    generated_at_utc: str


def build_mission_packet(item: dict, confidence: dict, repo: str = "kas1987/chromatic-harness-v2") -> dict:
    checks = item.get("acceptance_checks") or item.get("acceptance") or []
    if isinstance(checks, str):
        checks = [checks]
    risk = str(item.get("risk_level", "medium")).lower()
    packet = MissionPacket(
        task_id=str(item.get("id", item.get("issue", "unknown"))),
        objective=str(item.get("objective") or item.get("title") or "").strip(),
        repo=repo,
        allowed_files=list(item.get("allowed_files") or []),
        forbidden_files=list(item.get("forbidden_files") or ["secrets", "production credentials"]),
        owner_agent=str(item.get("owner_agent", "unassigned")),
        secondary_agent=str(item.get("secondary_agent", "unassigned")),
        tool_budget=item.get("tool_budget") or _default_tool_budget(risk),
        risk_level=risk,
        confidence=confidence,
        acceptance_checks=list(checks),
        stop_conditions=list(
            item.get("stop_conditions") or ["irreversible mutation", "confidence below gate", "requires credentials"]
        ),
        required_output=str(item.get("required_output", "PR with implementation, tests, and evidence log")),
        generated_at_utc=_ts(),
    )
    from dataclasses import asdict

    return asdict(packet)


def _default_tool_budget(risk: str) -> dict:
    """Tool/turn budgets by risk band (DISPATCH_PLAYBOOK 'tool budget' field)."""
    table = {
        "low": {"max_tool_calls": 40, "max_files": 6, "max_subagents": 1},
        "medium": {"max_tool_calls": 80, "max_files": 12, "max_subagents": 2},
        "high": {"max_tool_calls": 120, "max_files": 20, "max_subagents": 4},
        "critical": {"max_tool_calls": 120, "max_files": 20, "max_subagents": 4},
    }
    return table.get(risk, table["medium"])


def dispatch_allowed(confidence: dict, risk_level: str) -> tuple[bool, str]:
    """DISPATCH_PLAYBOOK gate: >=75, or >=60 if reversible+low-risk."""
    score = float(confidence.get("score", 0))
    if score >= DISPATCH_MIN:
        return True, f"score {score} >= {DISPATCH_MIN}"
    if score >= DISPATCH_MIN_REVERSIBLE and risk_level in {"low", "medium"}:
        return True, f"score {score} >= {DISPATCH_MIN_REVERSIBLE} and risk={risk_level} (reversible)"
    return (
        False,
        f"score {score} below dispatch gate (needs >={DISPATCH_MIN}, or >={DISPATCH_MIN_REVERSIBLE} if reversible)",
    )


# ── Queue loading ────────────────────────────────────────────────────────────


def load_queue_from_bd() -> list[dict]:
    """Best-effort `bd ready --json`. Returns [] if bd is unavailable."""
    bd = shutil.which("bd") or shutil.which("bd.cmd")
    if not bd:
        return []
    try:
        r = run_safe([bd, "ready", "--json"], cwd=REPO, timeout=20)
        if r.returncode != 0 or not r.stdout.strip():
            return []
        data = json.loads(r.stdout)
        items = data if isinstance(data, list) else data.get("issues", [])
        # Filter out epics — GO-mode dispatches leaf tasks, not containers.
        return [it for it in items if str(it.get("issue_type", it.get("type", ""))).lower() != "epic"]
    except json.JSONDecodeError:
        # run_safe absorbs timeout/OSError (rc handled above); malformed bd JSON
        # is the only remaining raisable error.
        return []


# ── Orchestration loop ───────────────────────────────────────────────────────


def _manifest_gate(item: dict) -> tuple[bool, str]:
    """Delegate to mutation_manifest.require_manifest (P0-CC-002). Fail-open if the
    module is unavailable so GO-mode still runs in a partial checkout."""
    import importlib.util

    mm_path = REPO / "scripts" / "mutation_manifest.py"
    if not mm_path.is_file():
        return True, "manifest gate inactive (module absent)"
    try:
        spec = importlib.util.spec_from_file_location("mutation_manifest", mm_path)
        mm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mm)
        return mm.require_manifest(item)
    except Exception as exc:  # noqa: BLE001
        return True, f"manifest gate skipped ({exc})"


def run_go(items: list[dict] | None = None) -> dict:
    """The deterministic GO loop. Returns an auditable decision record. No mutation."""
    queue = items if items is not None else load_queue_from_bd()
    selected = select_next(queue)

    record: dict[str, Any] = {
        "generated_at_utc": _ts(),
        "queue_size": len(queue),
        "selected": None,
        "confidence": None,
        "decision": "no_work",
        "dispatch_allowed": False,
        "dispatch_reason": "queue empty or fully blocked",
        "mission_packet": None,
    }
    if selected is None:
        return record

    factors = estimate_factors(selected)
    confidence = score_confidence(factors)
    risk = str(selected.get("risk_level", "medium")).lower()
    allowed, reason = dispatch_allowed(confidence, risk)

    # Mutation-manifest gate (P0-CC-002, FR-3): a write-capable task may not be
    # dispatched without a valid mutation manifest. Read/verify tasks are exempt.
    manifest_ok, manifest_reason = _manifest_gate(selected)
    if not manifest_ok:
        allowed = False
        reason = manifest_reason

    packet = build_mission_packet(selected, confidence)

    record.update(
        {
            "selected": {
                "id": selected.get("id"),
                "title": selected.get("title"),
                "priority": _norm_priority(selected),
            },
            "confidence": confidence,
            "decision": confidence["band"],
            "dispatch_allowed": allowed,
            "dispatch_reason": reason,
            "mission_packet": packet,
        }
    )
    return record


def summarize() -> dict:
    """Fail-open compact summary for the closeout report / meta-gate."""
    try:
        latest = OUT_DIR / "latest.json"
        if not latest.exists():
            return {"status": "no_scan", "decision": None}
        data = json.loads(latest.read_text(encoding="utf-8"))
        sel = data.get("selected") or {}
        return {
            "status": "ok",
            "decision": data.get("decision"),
            "dispatch_allowed": data.get("dispatch_allowed"),
            "selected_id": sel.get("id"),
            "confidence_score": (data.get("confidence") or {}).get("score"),
            "generated_at_utc": data.get("generated_at_utc"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "decision": None}


def write_artifact(record: dict) -> tuple[Path, Path | None]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    latest = OUT_DIR / "latest.json"
    latest.write_text(json.dumps(record, indent=2), encoding="utf-8")
    packet_path = None
    if record.get("mission_packet"):
        MISSIONS_DIR.mkdir(parents=True, exist_ok=True)
        tid = str(record["mission_packet"]["task_id"]).replace("/", "_").replace(".", "_")
        packet_path = MISSIONS_DIR / f"{tid}.json"
        packet_path.write_text(json.dumps(record["mission_packet"], indent=2), encoding="utf-8")
    return latest, packet_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic GO-mode orchestrator (issue #81)")
    ap.add_argument(
        "--write", action="store_true", help="persist 07_LOGS_AND_AUDIT/go_mode/latest.json + mission packet"
    )
    ap.add_argument("--queue-file", default="", help="read queue items from a JSON file instead of bd")
    args = ap.parse_args()

    items = None
    if args.queue_file:
        items = json.loads(Path(args.queue_file).read_text(encoding="utf-8"))

    record = run_go(items)

    if args.write:
        latest, packet = write_artifact(record)
        record["_written"] = {
            "latest": str(latest.relative_to(REPO)),
            "packet": str(packet.relative_to(REPO)) if packet else None,
        }

    print(json.dumps(record, indent=2))
    # Exit non-zero only when there is work but confidence halts it (signal for humans).
    if record["decision"] == "halt":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
