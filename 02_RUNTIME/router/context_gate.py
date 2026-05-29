"""Context Gate — filters what resources are loaded into pre-context."""

from __future__ import annotations

from typing import Literal

from .contracts import (
    ContextGateResult,
    DeniedResource,
    RouteRequest,
)
from .context_manifest import ContextResourceManifest
from .context_policy import ContextPolicyLoader

CLevel = Literal["C1", "C2", "C3", "C4"]


class ContextGate:
    """Gate that computes what context resources should be loaded for a task.

    Runs BEFORE Privacy/Confidence/Budget gates so the model never sees
    resources it is not allowed to use.
    """

    def __init__(
        self,
        manifest: ContextResourceManifest | None = None,
        policy_loader: ContextPolicyLoader | None = None,
    ):
        self.manifest = manifest or ContextResourceManifest.build_defaults()
        self.policy_loader = policy_loader or ContextPolicyLoader()

    def check(
        self,
        req: RouteRequest,
        complexity_level: CLevel = "C4",
    ) -> ContextGateResult:
        logs: list[str] = []
        denied: list[DeniedResource] = []
        allowed: list[str] = []

        # Resolve policy for this task
        policy = self.policy_loader.resolve(
            req.task_type,
            complexity_level,
            req.constraints.privacy_class,
        )

        logs.append(
            f"ContextGate: task={req.task_type.value} "
            f"complexity={complexity_level} privacy={req.constraints.privacy_class.value}"
        )

        # Get candidate resources from manifest
        candidates = self.manifest.filter(
            task_type=req.task_type,
            complexity=complexity_level,
            privacy=req.constraints.privacy_class,
            max_risk=policy.effective_max_risk(),
        )
        logs.append(f"ContextGate: {len(candidates)} candidates from manifest")

        # Apply allowlist if specified
        if req.constraints.context_resource_allowlist:
            candidates = [
                c
                for c in candidates
                if c.resource_id in req.constraints.context_resource_allowlist
            ]
            logs.append(
                f"ContextGate: allowlist applied → {len(candidates)} candidates"
            )

        # Evaluate each candidate against policy + constraints
        for resource in candidates:
            if policy.is_blocked(resource.resource_id):
                denied.append(
                    DeniedResource(
                        resource.resource_id,
                        f"Blocked by policy for {req.task_type.value}/{req.constraints.privacy_class.value}",
                    )
                )
                continue

            if not policy.is_type_allowed(resource.resource_type):
                denied.append(
                    DeniedResource(
                        resource.resource_id,
                        f"Resource type '{resource.resource_type}' not allowed by policy",
                    )
                )
                continue

            # Constraint-level type gating
            if resource.resource_type == "tool" and not req.constraints.allow_tools:
                denied.append(DeniedResource(resource.resource_id, "allow_tools=False"))
                continue

            if resource.resource_type == "skill" and not req.constraints.allow_skills:
                denied.append(
                    DeniedResource(resource.resource_id, "allow_skills=False")
                )
                continue

            if resource.resource_type == "mcp" and not req.constraints.allow_mcp:
                denied.append(DeniedResource(resource.resource_id, "allow_mcp=False"))
                continue

            allowed.append(resource.resource_id)

        # Apply global resource cap
        effective_cap = min(
            policy.effective_max_resources(),
            req.constraints.max_context_resources,
        )
        if len(allowed) > effective_cap:
            overflow = allowed[effective_cap:]
            allowed = allowed[:effective_cap]
            for rid in overflow:
                denied.append(
                    DeniedResource(rid, f"Resource cap ({effective_cap}) exceeded")
                )
            logs.append(f"ContextGate: capped to {effective_cap} resources")

        estimated_tokens = self.manifest.total_estimated_tokens(allowed)
        max_budget_tokens = int(
            req.constraints.max_tokens * policy.effective_budget_pct() / 100
        )

        # Token budget check
        ok = True
        if estimated_tokens > max_budget_tokens:
            ok = False
            allowed = []  # governance: blocked = nothing allowed
            logs.append(
                f"ContextGate: BLOCKED — estimated {estimated_tokens} tokens "
                f"exceeds budget {max_budget_tokens} ({policy.effective_budget_pct()}% of {req.constraints.max_tokens})"
            )
        else:
            logs.append(
                f"ContextGate: allowed {len(allowed)} resources, "
                f"{estimated_tokens}/{max_budget_tokens} tokens within budget"
            )

        return ContextGateResult(
            ok=ok,
            allowed_resources=allowed,
            denied_resources=denied,
            estimated_context_tokens=estimated_tokens,
            logs=logs,
        )
