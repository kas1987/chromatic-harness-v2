"""Chromatic Harness v2 — Scope Enforcement Engine.

Detects file-scope violations by comparing pre-wave and post-wave file manifests.
Designed to run before and after any worker/agent dispatch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_RUNTIME = _HERE.parent
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from memory.store import SystemMemoryStore, ScopeViolation


@dataclass
class ScopeBaseline:
    mission_id: str
    expected_scope: str
    baseline_files: set[str] = field(default_factory=set)
    baseline_count: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ScopeCheckResult:
    passed: bool
    violations: list[str]
    new_files: list[str]
    modified_outside: list[str]
    deleted_outside: list[str]


class ScopeEnforcer:
    """Enforces FILE SCOPE boundaries using git diff and file-system snapshots."""

    def __init__(self, repo_root: Path | str | None = None):
        self.repo_root = Path(repo_root) if repo_root else self._detect_repo_root()
        self._store = SystemMemoryStore()

    def _detect_repo_root(self) -> Path:
        here = Path(__file__).resolve()
        for parent in [here, *here.parents]:
            if (parent / ".git").exists() or (parent / "00_SOURCE_OF_TRUTH").exists():
                return parent
        return Path.cwd()

    def _run_git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), *args],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def take_baseline(self, mission_id: str, expected_scope: str) -> ScopeBaseline:
        """Record current file manifest before dispatching work."""
        # Use git ls-files for tracked files + git status --porcelain for unstaged
        tracked = self._run_git("ls-files").splitlines()
        status = self._run_git("status", "--porcelain", "-u").splitlines()
        # Include untracked files
        untracked = [line[3:].strip() for line in status if line.startswith("?? ")]
        all_files = set(tracked + untracked)
        return ScopeBaseline(
            mission_id=mission_id,
            expected_scope=expected_scope,
            baseline_files=all_files,
            baseline_count=len(all_files),
        )

    def check_scope(
        self,
        baseline: ScopeBaseline,
        task_id: str = "",
    ) -> ScopeCheckResult:
        """Compare current state against baseline; flag violations."""
        # Diff against HEAD for modified files
        diff_names = self._run_git("diff", "--name-only", "HEAD").splitlines()
        # Untracked files
        status = self._run_git("status", "--porcelain", "-u").splitlines()
        untracked = [line[3:].strip() for line in status if line.startswith("?? ")]

        # Determine scope prefix (normalize)
        scope_prefix = baseline.expected_scope.strip("/")
        if not scope_prefix.endswith("/"):
            scope_prefix += "/"

        violations: list[str] = []
        new_files: list[str] = []
        modified_outside: list[str] = []

        for f in diff_names:
            if not f.startswith(scope_prefix):
                modified_outside.append(f)
                violations.append(f"modified outside scope: {f}")

        for f in untracked:
            if f not in baseline.baseline_files and not f.startswith(scope_prefix):
                new_files.append(f)
                violations.append(f"created outside scope: {f}")

        passed = len(violations) == 0
        return ScopeCheckResult(
            passed=passed,
            violations=violations,
            new_files=new_files,
            modified_outside=modified_outside,
            deleted_outside=[],
        )

    async def enforce_and_log(
        self,
        baseline: ScopeBaseline,
        task_id: str = "",
    ) -> ScopeCheckResult:
        """Run check and persist violations to system memory."""
        result = self.check_scope(baseline, task_id)
        if not result.passed:
            severity = "critical" if result.new_files else "warning"
            violation = ScopeViolation(
                id="",
                mission_id=baseline.mission_id,
                task_id=task_id,
                expected_scope=baseline.expected_scope,
                violated_files=result.violations,
                detected_by="scope_enforcer",
                resolution="pending",
                severity=severity,
            )
            await self._store.record_violation(violation)
        return result

    def build_scope_header(self, scope: str, rules: list[dict] | None = None) -> str:
        """Generate the FILE SCOPE governance header for worker prompts."""
        header = f"""
═══════════════════════════════════════════════════════════════
FILE SCOPE: {scope}
═══════════════════════════════════════════════════════════════

You MUST NOT write, create, or modify files outside FILE SCOPE.
Doing so will be detected by the orchestrator and reverted.

Scope creep check: git diff --name-only HEAD~1 must be a subset
of the declared file manifest.
═══════════════════════════════════════════════════════════════
""".strip()
        if rules:
            header += "\n\n--- Active Governance Rules ---\n"
            for r in rules:
                header += f"\n[{r['severity'].upper()}] {r['name']}: {r['description']}"
                if r.get("fix"):
                    header += f"\n  Fix pattern: {r['fix']}"
        return header
