#!/usr/bin/env python3
"""Validate CI workflow step coverage against check policy matrix.

Ensures declared checks in config/ci/check_policy_matrix.yaml map to named steps
in .github/workflows/ci.yml and that required checks are not marked
continue-on-error.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO / "config" / "ci" / "check_policy_matrix.yaml"
WORKFLOW_PATH = REPO / ".github" / "workflows" / "ci.yml"
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "ci"
ARTIFACT_PATH = ARTIFACT_DIR / "policy_matrix_latest.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _step_map(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs = workflow.get("jobs") or {}
    if not isinstance(jobs, dict):
        return {}

    step_map: dict[str, dict[str, Any]] = {}
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            name = step.get("name")
            if isinstance(name, str) and name.strip():
                step_map[name.strip()] = step
    return step_map


def _validate(matrix: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
    checks = matrix.get("checks") or []
    if not isinstance(checks, list):
        raise ValueError("'checks' must be a list in check policy matrix")

    steps = _step_map(workflow)
    errors: list[str] = []
    results: list[dict[str, Any]] = []

    for entry in checks:
        if not isinstance(entry, dict):
            errors.append("Invalid check entry: expected mapping")
            continue

        name = str(entry.get("name") or "").strip()
        enforcement = str(entry.get("enforcement") or "").strip().lower()
        owner = str(entry.get("owner") or "").strip()

        if not name:
            errors.append("Check entry missing 'name'")
            continue
        if not owner:
            errors.append(f"Check '{name}' missing owner")
        if enforcement not in {"required", "candidate_required", "advisory"}:
            errors.append(f"Check '{name}' has invalid enforcement '{enforcement}'")
            continue

        step = steps.get(name)
        exists = step is not None
        continue_on_error = bool(step.get("continue-on-error")) if isinstance(step, dict) else None

        if not exists:
            errors.append(f"Workflow step missing for check '{name}'")
        elif enforcement == "required" and continue_on_error:
            errors.append(f"Required check '{name}' is configured continue-on-error")

        results.append(
            {
                "name": name,
                "owner": owner,
                "enforcement": enforcement,
                "exists_in_workflow": exists,
                "continue_on_error": continue_on_error,
            }
        )

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "checks": results,
    }


def _write_artifact(report: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        **report,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_path": str(MATRIX_PATH.relative_to(REPO)).replace("\\", "/"),
        "workflow_path": str(WORKFLOW_PATH.relative_to(REPO)).replace("\\", "/"),
    }
    ARTIFACT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    try:
        matrix = _load_yaml(MATRIX_PATH)
        workflow = _load_yaml(WORKFLOW_PATH)
        report = _validate(matrix, workflow)
        _write_artifact(report)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
