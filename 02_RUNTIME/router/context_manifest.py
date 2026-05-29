"""Context Resource Manifest — registry of tools, skills, MCPs, agents for pre-context governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from .contracts import PrivacyClass, TaskType

CLevel = Literal["C1", "C2", "C3", "C4"]
RiskLevel = Literal["low", "medium", "high", "critical"]
ResourceType = Literal["tool", "skill", "mcp", "extension", "agent"]


@dataclass(frozen=True)
class ContextResource:
    """A single item that could be loaded into pre-context."""

    resource_id: str
    resource_type: ResourceType
    description: str = ""
    complexity_tiers: list[CLevel] = field(default_factory=list)
    privacy_classes: list[PrivacyClass] = field(default_factory=list)
    task_types: list[TaskType] = field(default_factory=list)
    provider_bindings: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    risk_level: RiskLevel = "low"
    enabled: bool = True

    def matches_task(self, task_type: TaskType) -> bool:
        return not self.task_types or task_type in self.task_types

    def matches_privacy(self, pc: PrivacyClass) -> bool:
        return not self.privacy_classes or pc in self.privacy_classes

    def matches_complexity(self, level: CLevel) -> bool:
        return not self.complexity_tiers or level in self.complexity_tiers


@dataclass
class ContextResourceManifest:
    """Registry of all context resources with query methods."""

    resources: dict[str, ContextResource] = field(default_factory=dict)

    # ── Loading ────────────────────────────────────────────────────────

    @classmethod
    def load_from_policy(cls, path: Path | str) -> ContextResourceManifest:
        """Load a YAML manifest file."""
        manifest = cls()
        p = Path(path)
        if not p.exists():
            return manifest
        with open(p, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        for item in raw.get("resources", []):
            manifest.register(
                ContextResource(
                    resource_id=item["resource_id"],
                    resource_type=item["resource_type"],
                    description=item.get("description", ""),
                    complexity_tiers=item.get("complexity_tiers", []),
                    privacy_classes=[
                        PrivacyClass(c) for c in item.get("privacy_classes", [])
                    ],
                    task_types=[TaskType(t) for t in item.get("task_types", [])],
                    provider_bindings=item.get("provider_bindings", []),
                    estimated_tokens=item.get("estimated_tokens", 0),
                    risk_level=item.get("risk_level", "low"),
                    enabled=item.get("enabled", True),
                )
            )
        return manifest

    @classmethod
    def build_defaults(cls) -> ContextResourceManifest:
        """Factory method returning a sensible default manifest."""
        manifest = cls()
        defaults: list[ContextResource] = [
            # ── Core tools (universal, low risk) ──────────────────────
            ContextResource(
                "read",
                "tool",
                "Read file contents",
                complexity_tiers=["C1", "C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1, PrivacyClass.P2],
                task_types=[
                    TaskType.CLASSIFICATION,
                    TaskType.PLANNING,
                    TaskType.CODING,
                    TaskType.REVIEW,
                    TaskType.RESEARCH,
                ],
                estimated_tokens=80,
                risk_level="low",
            ),
            ContextResource(
                "write",
                "tool",
                "Write or overwrite files",
                complexity_tiers=["C1", "C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1, PrivacyClass.P2],
                task_types=[TaskType.PLANNING, TaskType.CODING, TaskType.REVIEW],
                estimated_tokens=80,
                risk_level="low",
            ),
            ContextResource(
                "edit",
                "tool",
                "Precise file edits",
                complexity_tiers=["C1", "C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1, PrivacyClass.P2],
                task_types=[TaskType.PLANNING, TaskType.CODING, TaskType.REVIEW],
                estimated_tokens=100,
                risk_level="low",
            ),
            ContextResource(
                "bash",
                "tool",
                "Execute shell commands",
                complexity_tiers=["C1", "C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[
                    TaskType.CODING,
                    TaskType.REVIEW,
                    TaskType.PERSONAL_CONTEXT,
                ],
                estimated_tokens=120,
                risk_level="high",
            ),
            # ── Skills (task-specific) ─────────────────────────────────
            ContextResource(
                "audit",
                "skill",
                "Audit/refactor skills",
                complexity_tiers=["C2", "C3"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.REVIEW, TaskType.CODING],
                estimated_tokens=600,
                risk_level="low",
            ),
            ContextResource(
                "test",
                "skill",
                "Test generation and coverage",
                complexity_tiers=["C2", "C3"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.CODING, TaskType.REVIEW],
                estimated_tokens=500,
                risk_level="low",
            ),
            ContextResource(
                "security",
                "skill",
                "Security scanning",
                complexity_tiers=["C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.REVIEW, TaskType.CODING],
                estimated_tokens=700,
                risk_level="medium",
            ),
            ContextResource(
                "council",
                "skill",
                "Multi-model consensus",
                complexity_tiers=["C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.RESEARCH, TaskType.PLANNING],
                estimated_tokens=800,
                risk_level="low",
            ),
            # ── MCP servers ────────────────────────────────────────────
            ContextResource(
                "github_read",
                "mcp",
                "GitHub read ops",
                complexity_tiers=["C1", "C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.RESEARCH, TaskType.INTEGRATION_ACTION],
                provider_bindings=["native_claude", "openai", "anthropic"],
                estimated_tokens=400,
                risk_level="low",
            ),
            ContextResource(
                "github_write",
                "mcp",
                "GitHub write ops",
                complexity_tiers=["C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0],
                task_types=[TaskType.INTEGRATION_ACTION],
                provider_bindings=["native_claude", "openai", "anthropic"],
                estimated_tokens=450,
                risk_level="medium",
            ),
            ContextResource(
                "web_search",
                "mcp",
                "Web search/browse",
                complexity_tiers=["C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.RESEARCH],
                provider_bindings=["native_claude", "openai", "google"],
                estimated_tokens=350,
                risk_level="low",
            ),
            ContextResource(
                "shell_execute",
                "mcp",
                "Remote shell execution",
                complexity_tiers=["C3", "C4"],
                privacy_classes=[PrivacyClass.P0],
                task_types=[TaskType.CODING, TaskType.INTEGRATION_ACTION],
                provider_bindings=["native_claude", "prism-orchestrator"],
                estimated_tokens=500,
                risk_level="high",
            ),
            ContextResource(
                "secrets_read",
                "mcp",
                "Secret manager access",
                complexity_tiers=["C4"],
                privacy_classes=[PrivacyClass.P0],
                task_types=[TaskType.INTEGRATION_ACTION],
                provider_bindings=["native_claude"],
                estimated_tokens=300,
                risk_level="critical",
            ),
            # ── Extensions / agents ──────────────────────────────────────
            ContextResource(
                "browser",
                "extension",
                "Browser automation",
                complexity_tiers=["C2", "C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.RESEARCH],
                estimated_tokens=600,
                risk_level="medium",
            ),
            ContextResource(
                "codex_team",
                "agent",
                "Codex sub-agents",
                complexity_tiers=["C3", "C4"],
                privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
                task_types=[TaskType.CODING, TaskType.RESEARCH],
                provider_bindings=["openai", "native_claude"],
                estimated_tokens=900,
                risk_level="medium",
            ),
        ]
        for r in defaults:
            manifest.register(r)
        return manifest

    # ── Registry ops ─────────────────────────────────────────────────

    def register(self, resource: ContextResource) -> None:
        self.resources[resource.resource_id] = resource

    def get(self, resource_id: str) -> ContextResource | None:
        return self.resources.get(resource_id)

    def enabled(self) -> list[ContextResource]:
        return [r for r in self.resources.values() if r.enabled]

    # ── Filtering ──────────────────────────────────────────────────────

    def filter(
        self,
        task_type: TaskType | None = None,
        complexity: CLevel | None = None,
        privacy: PrivacyClass | None = None,
        resource_type: ResourceType | None = None,
        provider: str | None = None,
        max_risk: RiskLevel | None = None,
    ) -> list[ContextResource]:
        """Return resources matching ALL provided criteria."""
        candidates = self.enabled()

        # Risk ordering for max_risk comparison
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        max_risk_idx = risk_order[max_risk] if max_risk else None

        results: list[ContextResource] = []
        for r in candidates:
            if task_type and not r.matches_task(task_type):
                continue
            if complexity and not r.matches_complexity(complexity):
                continue
            if privacy and not r.matches_privacy(privacy):
                continue
            if resource_type and r.resource_type != resource_type:
                continue
            if provider and r.provider_bindings and provider not in r.provider_bindings:
                continue
            if (
                max_risk_idx is not None
                and risk_order.get(r.risk_level, 0) > max_risk_idx
            ):
                continue
            results.append(r)
        return results

    def by_type(self, resource_type: ResourceType) -> list[ContextResource]:
        return [r for r in self.enabled() if r.resource_type == resource_type]

    def total_estimated_tokens(self, resource_ids: list[str]) -> int:
        return sum(
            self.resources[r_id].estimated_tokens
            for r_id in resource_ids
            if r_id in self.resources
        )

    def __len__(self) -> int:
        return len(self.resources)
