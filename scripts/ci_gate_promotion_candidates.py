#!/usr/bin/env python3
"""Generate advisory-to-candidate-required promotion recommendations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO / "config" / "ci" / "check_policy_matrix.yaml"
POLICY_REPORT = REPO / "07_LOGS_AND_AUDIT" / "ci" / "policy_matrix_latest.json"
RUNTIME_REPORT = REPO / "07_LOGS_AND_AUDIT" / "ci" / "runtime_budget_latest.json"
OUTPUT_PATH = REPO / "07_LOGS_AND_AUDIT" / "ci" / "gate_promotion_latest.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main() -> int:
    matrix = _load_yaml(MATRIX_PATH)
    policy = _load_json(POLICY_REPORT)
    runtime = _load_json(RUNTIME_REPORT)

    by_name = {c.get("name"): c for c in (policy.get("checks") or []) if isinstance(c, dict)}
    runtime_over = bool(((runtime.get("budget") or {}).get("over_budget")))

    recommendations: list[dict[str, Any]] = []
    for check in matrix.get("checks") or []:
        if not isinstance(check, dict):
            continue

        enforcement = str(check.get("enforcement") or "").lower()
        if enforcement != "advisory":
            continue

        name = str(check.get("name") or "")
        state = by_name.get(name) or {}
        exists = bool(state.get("exists_in_workflow"))
        coe = bool(state.get("continue_on_error")) if state else None

        ready = exists and (coe is False) and (not runtime_over)
        reasons: list[str] = []
        if not exists:
            reasons.append("missing_workflow_step")
        if coe is not False:
            reasons.append("continue_on_error_enabled")
        if runtime_over:
            reasons.append("runtime_budget_over")

        recommendations.append(
            {
                "name": name,
                "current_enforcement": enforcement,
                "recommended_enforcement": "candidate_required" if ready else "advisory",
                "ready_for_promotion": ready,
                "reasons": reasons,
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_path": str(MATRIX_PATH.relative_to(REPO)).replace("\\", "/"),
        "policy_report_path": str(POLICY_REPORT.relative_to(REPO)).replace("\\", "/"),
        "runtime_report_path": str(RUNTIME_REPORT.relative_to(REPO)).replace("\\", "/"),
        "recommendations": recommendations,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
