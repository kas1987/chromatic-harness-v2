"""Context policy loader — reads context-resource governance rules from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from .contracts import PrivacyClass, TaskType

CLevel = Literal["C1", "C2", "C3", "C4"]
RiskLevel = Literal["low", "medium", "high", "critical"]
ResourceType = Literal["tool", "skill", "mcp", "extension", "agent"]


@dataclass
class TaskRule:
    max_resources: int
    allowed_types: list[ResourceType]
    blocked_resources: list[str]
    context_budget_pct: int


@dataclass
class ComplexityCap:
    max_resources: int
    max_risk: RiskLevel
    allowed_types: list[ResourceType]


@dataclass
class PrivacyRule:
    max_risk: RiskLevel
    allowed_types: list[ResourceType]
    blocked_resources: list[str]


@dataclass
class ContextPolicy:
    """Resolved governance rules for a specific task context."""

    max_context_budget_pct: int
    max_resources: int
    task_rule: TaskRule | None = None
    complexity_cap: ComplexityCap | None = None
    privacy_rule: PrivacyRule | None = None

    def effective_max_resources(self) -> int:
        """Most restrictive of task, complexity, and global caps."""
        caps: list[int] = [self.max_resources]
        if self.task_rule:
            caps.append(self.task_rule.max_resources)
        if self.complexity_cap:
            caps.append(self.complexity_cap.max_resources)
        return min(caps)

    def effective_budget_pct(self) -> int:
        return (
            self.task_rule.context_budget_pct
            if self.task_rule
            else self.max_context_budget_pct
        )

    def effective_max_risk(self) -> RiskLevel | None:
        risks: list[str] = []
        if self.privacy_rule:
            risks.append(self.privacy_rule.max_risk)
        if self.complexity_cap:
            risks.append(self.complexity_cap.max_risk)
        if not risks:
            return None
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        # most restrictive = lowest risk level
        safest = min(risks, key=lambda r: order[r])
        return safest  # type: ignore[return-value]

    def is_blocked(self, resource_id: str) -> bool:
        blocked: set[str] = set()
        if self.task_rule:
            blocked.update(self.task_rule.blocked_resources)
        if self.privacy_rule:
            blocked.update(self.privacy_rule.blocked_resources)
        return resource_id in blocked

    def is_type_allowed(self, resource_type: ResourceType) -> bool:
        allowed: set[str] = set()
        if self.task_rule:
            allowed.update(self.task_rule.allowed_types)
        if self.complexity_cap:
            allowed.update(self.complexity_cap.allowed_types)
        if self.privacy_rule:
            allowed.update(self.privacy_rule.allowed_types)
        # If no rules specify allowed types, default to all
        return not allowed or resource_type in allowed


class ContextPolicyLoader:
    """Loads context-policy.yaml and resolves rules for a given task."""

    DEFAULT_PATH = (
        Path(__file__).resolve().parent.parent.parent
        / "09_DEPLOYMENT"
        / "config"
        / "routing"
        / "context-policy.yaml"
    )

    def __init__(self, policy_path: Path | str | None = None):
        self._path = Path(policy_path) if policy_path else self.DEFAULT_PATH
        self._raw: dict = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._raw = {}
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            self._raw = yaml.safe_load(fh) or {}

    # ── Public API ─────────────────────────────────────────────────────

    def defaults(self) -> dict[str, Any]:
        return self._raw.get("defaults", {})

    def rules_for_task(self, task_type: TaskType) -> TaskRule | None:
        raw = self._raw.get("task_rules", {}).get(task_type.value)
        if not raw:
            return None
        return TaskRule(
            max_resources=raw.get("max_resources", 20),
            allowed_types=raw.get("allowed_types", []),
            blocked_resources=raw.get("blocked_resources", []),
            context_budget_pct=raw.get("context_budget_pct", 25),
        )

    def rules_for_complexity(self, level: CLevel) -> ComplexityCap | None:
        raw = self._raw.get("complexity_caps", {}).get(level)
        if not raw:
            return None
        return ComplexityCap(
            max_resources=raw.get("max_resources", 20),
            max_risk=raw.get("max_risk", "critical"),
            allowed_types=raw.get("allowed_types", []),
        )

    def rules_for_privacy(self, pc: PrivacyClass) -> PrivacyRule | None:
        raw = self._raw.get("privacy_rules", {}).get(pc.value)
        if not raw:
            return None
        return PrivacyRule(
            max_risk=raw.get("max_risk", "critical"),
            allowed_types=raw.get("allowed_types", []),
            blocked_resources=raw.get("blocked_resources", []),
        )

    def context_budget_for_privacy(self, pc: PrivacyClass) -> int:
        return self._raw.get("context_budget", {}).get(pc.value, 25)

    def resolve(
        self,
        task_type: TaskType,
        complexity: CLevel,
        privacy: PrivacyClass,
    ) -> ContextPolicy:
        """Resolve the most restrictive combined policy for a task."""
        defaults = self.defaults()
        return ContextPolicy(
            max_context_budget_pct=defaults.get("max_context_budget_pct", 25),
            max_resources=defaults.get("max_resources", 20),
            task_rule=self.rules_for_task(task_type),
            complexity_cap=self.rules_for_complexity(complexity),
            privacy_rule=self.rules_for_privacy(privacy),
        )
