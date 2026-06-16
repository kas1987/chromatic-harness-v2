#!/usr/bin/env python3
"""Generate weekly CI governance markdown + JSON summary artifact."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
CI_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
POLICY_PATH = CI_DIR / "policy_matrix_latest.json"
RUNTIME_PATH = CI_DIR / "runtime_budget_latest.json"
PROMOTION_PATH = CI_DIR / "gate_promotion_latest.json"
BRANCH_PATH = CI_DIR / "branch_governance_latest.json"
OUT_JSON = CI_DIR / "weekly_summary_latest.json"
OUT_MD = CI_DIR / "weekly_summary_latest.md"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _md(payload: dict[str, Any]) -> str:
    policy = payload.get("policy", {})
    runtime = payload.get("runtime", {})
    promotion = payload.get("promotion", {})
    branch = payload.get("branch_governance", {})

    policy_errors = policy.get("errors") or []
    over_budget = bool(((runtime.get("budget") or {}).get("over_budget")))
    recs = promotion.get("recommendations") or []
    ready = [r for r in recs if isinstance(r, dict) and r.get("ready_for_promotion")]

    return "\n".join(
        [
            "# Weekly CI Governance Summary",
            "",
            f"Generated: {payload.get('generated_at')}",
            "",
            "## Policy matrix",
            "",
            f"- errors: {len(policy_errors)}",
            f"- status: {'ok' if not policy_errors else 'needs_action'}",
            "",
            "## Runtime budgets",
            "",
            f"- sample_count: {runtime.get('sample_count', 0)}",
            f"- over_budget: {over_budget}",
            "",
            "## Advisory promotion readiness",
            "",
            f"- advisory checks evaluated: {len(recs)}",
            f"- ready_for_candidate_required: {len(ready)}",
            "",
            "## Branch governance",
            "",
            f"- local_total: {branch.get('local_total', 0)}",
            f"- remote_total: {branch.get('remote_total', 0)}",
            f"- local_stale: {branch.get('local_stale', 0)}",
            f"- remote_stale: {branch.get('remote_stale', 0)}",
            f"- violations: {branch.get('violations', 0)}",
        ]
    ) + "\n"


def main() -> int:
    policy = _load(POLICY_PATH)
    runtime = _load(RUNTIME_PATH)
    promotion = _load(PROMOTION_PATH)
    branch = _load(BRANCH_PATH)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "errors": policy.get("errors") or [],
            "check_count": len(policy.get("checks") or []),
        },
        "runtime": {
            "sample_count": runtime.get("sample_count", 0),
            "budget": runtime.get("budget") or {},
        },
        "promotion": {
            "recommendations": promotion.get("recommendations") or [],
        },
        "branch_governance": {
            "local_total": ((branch.get("counts") or {}).get("local_total", 0)),
            "remote_total": ((branch.get("counts") or {}).get("remote_total", 0)),
            "local_stale": ((branch.get("counts") or {}).get("local_stale", 0)),
            "remote_stale": ((branch.get("counts") or {}).get("remote_stale", 0)),
            "violations": len(branch.get("violations") or []),
        },
    }

    CI_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUT_MD.write_text(_md(payload), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
