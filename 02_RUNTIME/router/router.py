"""Chromatic API Router — main entry point for provider-neutral routing."""

import time
import uuid
from typing import Any

from .contracts import (
    RouteRequest,
    RouteResponse,
    RouteLogs,
    RouteOutput,
    OutputType,
    ConfidenceBand,
    PrivacyClass,
)
from .policy import PolicyLoader
from .confidence import ConfidenceGate
from .privacy import PrivacyGate
from .budget import BudgetGate
from .observability import ObservabilityLogger
from .adapters.base import BaseAdapter
from .adapters.mock import MockAdapter
from .adapters.openhuman_adapter import OpenHumanAdapter


class ChromaticRouter:
    """
    One router. One policy. One log trail.
    OpenHuman safely reachable, disabled by default, read-only when enabled.
    """

    def __init__(
        self,
        loader: PolicyLoader | None = None,
        logger: ObservabilityLogger | None = None,
        adapters: dict[str, BaseAdapter] | None = None,
    ):
        self.loader = loader or PolicyLoader()
        self.logger = logger or ObservabilityLogger()
        self.confidence_gate = ConfidenceGate()
        self.privacy_gate = PrivacyGate(self.loader)
        self.budget_gate = BudgetGate(self.loader)

        self.adapters: dict[str, BaseAdapter] = {}
        if adapters:
            self.adapters.update(adapters)
        else:
            self._register_default_adapters()

    def _register_default_adapters(self):
        providers = self.loader.providers()
        for name, cfg in providers.items():
            if name == "openhuman":
                self.adapters[name] = OpenHumanAdapter(cfg)
        if "mock" not in self.adapters:
            self.adapters["mock"] = MockAdapter()

    def _resolve_provider(self, req: RouteRequest) -> tuple[str, list[str], RouteLogs]:
        logs = RouteLogs()
        task_route = self.loader.route_for_task(req.task_type.value)

        if req.preferred_provider != "auto" and req.preferred_provider:
            primary = req.preferred_provider
            fallback = list(req.fallback_chain)
        else:
            primary = task_route.get("default", "mock")
            fallback = list(task_route.get("fallback", []))

        pc = req.constraints.privacy_class
        privacy_cfg = self.privacy_gate.policy.get(pc.value, {})
        allowed = set(privacy_cfg.get("allowed_providers", []))

        candidates = [primary, *fallback]
        filtered = []
        for cand in candidates:
            if cand == "local_vault":
                cand = "mock"
            if cand in allowed or cand == "mock":
                filtered.append(cand)
            else:
                logs.warnings.append(f"Provider {cand} removed by privacy policy for {pc.value}.")

        if not filtered:
            logs.errors.append("No candidate provider passed privacy gate.")
            return "mock", [], logs

        chosen = filtered[0]
        remaining = filtered[1:]
        logs.policy_checks.append(f"Resolved provider={chosen} (fallbacks={remaining}).")
        return chosen, remaining, logs

    def _provider_is_available(self, name: str) -> bool:
        adapter = self.adapters.get(name)
        if not adapter:
            return False
        return adapter.enabled

    async def route(self, req: RouteRequest | None = None, **kwargs: Any) -> RouteResponse:
        if req is None:
            req = self._build_request(**kwargs)

        t0 = time.perf_counter()
        logs = RouteLogs()

        # 1. Privacy gate
        ok, plogs = self.privacy_gate.check(req)
        logs.policy_checks.extend(plogs.policy_checks)
        logs.warnings.extend(plogs.warnings)
        logs.errors.extend(plogs.errors)
        if not ok:
            resp = RouteResponse(
                request_id=req.request_id,
                selected_provider="",
                route_reason="privacy_gate_blocked",
                confidence_score=req.confidence.score,
                privacy_class=req.constraints.privacy_class,
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content="Blocked by privacy gate. See logs.errors.",
                ),
                logs=logs,
            )
            self.logger.log(req, resp)
            return resp

        # 2. Confidence gate
        ok, clogs = self.confidence_gate.check(req)
        logs.policy_checks.extend(clogs.policy_checks)
        logs.warnings.extend(clogs.warnings)
        logs.errors.extend(clogs.errors)
        if not ok:
            resp = RouteResponse(
                request_id=req.request_id,
                selected_provider="",
                route_reason="confidence_gate_blocked",
                confidence_score=req.confidence.score,
                privacy_class=req.constraints.privacy_class,
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content="Blocked by confidence gate. Score < 60.",
                ),
                logs=logs,
            )
            self.logger.log(req, resp)
            return resp

        # 3. Resolve provider + budget gate
        chosen, fallbacks, rlogs = self._resolve_provider(req)
        logs.policy_checks.extend(rlogs.policy_checks)
        logs.warnings.extend(rlogs.warnings)
        logs.errors.extend(rlogs.errors)

        ok, blogs, est_cost = self.budget_gate.check(req, chosen)
        logs.policy_checks.extend(blogs.policy_checks)
        logs.warnings.extend(blogs.warnings)
        logs.errors.extend(blogs.errors)
        if not ok:
            resp = RouteResponse(
                request_id=req.request_id,
                selected_provider=chosen,
                route_reason="budget_gate_blocked",
                confidence_score=req.confidence.score,
                privacy_class=req.constraints.privacy_class,
                cost_estimate_usd=est_cost,
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content="Blocked by budget gate. See logs.errors.",
                ),
                logs=logs,
            )
            self.logger.log(req, resp)
            return resp

        # 4. Execute via adapter with fallback
        provider_used = chosen
        fallback_used = False
        resp: RouteResponse | None = None
        for cand in [chosen, *fallbacks]:
            if not self._provider_is_available(cand):
                logs.warnings.append(f"Provider {cand} not available or disabled.")
                continue
            adapter = self.adapters.get(cand)
            if adapter is None:
                logs.warnings.append(f"No adapter registered for {cand}.")
                continue
            try:
                resp = await adapter.complete(req)
                resp.cost_estimate_usd = est_cost
                if cand != chosen:
                    fallback_used = True
                provider_used = cand
                break
            except Exception as exc:
                logs.errors.append(f"Provider {cand} failed: {exc}")
                continue

        if resp is None:
            mock = self.adapters.get("mock")
            if mock:
                resp = await mock.complete(req)
                provider_used = "mock"
                fallback_used = True
            else:
                resp = RouteResponse(
                    request_id=req.request_id,
                    selected_provider="",
                    route_reason="all_providers_failed",
                    output=RouteOutput(
                        type=OutputType.ERROR,
                        content="All providers failed and mock is unavailable.",
                    ),
                )

        if provider_used == "mock" and req.preferred_provider not in ("mock", "auto"):
            fallback_used = True

        resp.logs.policy_checks.extend(logs.policy_checks)
        resp.logs.warnings.extend(logs.warnings)
        resp.logs.errors.extend(logs.errors)
        resp.fallback_used = fallback_used
        resp.privacy_class = req.constraints.privacy_class
        resp.confidence_score = req.confidence.score

        latency = int((time.perf_counter() - t0) * 1000)
        resp.latency_ms = latency

        self.logger.log(req, resp)
        return resp

    def _build_request(
        self,
        *,
        request_id: str | None = None,
        task_id: str = "",
        task_type: str = "classification",
        objective: str = "",
        privacy_class: str = "P1",
        confidence_score: float = 75.0,
        preferred_provider: str = "auto",
        fallback_chain: list[str] | None = None,
        caller: str = "unknown",
        **kwargs: Any,
    ) -> RouteRequest:
        from .contracts import RouteInput, RouteConstraints, RouteConfidence, RouteAudit, TaskType

        return RouteRequest(
            request_id=request_id or str(uuid.uuid4()),
            task_id=task_id,
            task_type=TaskType(task_type),
            objective=objective,
            input=RouteInput(),
            constraints=RouteConstraints(
                privacy_class=PrivacyClass(privacy_class),
                **{k: v for k, v in kwargs.items() if k in {
                    "max_cost_usd", "max_latency_ms", "max_tokens",
                    "allow_cloud", "allow_broker", "allow_openhuman", "allow_tools"
                }},
            ),
            confidence=RouteConfidence(
                score=confidence_score,
                band=ConfidenceGate.band_from_score(confidence_score),
            ),
            preferred_provider=preferred_provider,
            fallback_chain=fallback_chain or [],
            audit=RouteAudit(caller=caller),
        )
