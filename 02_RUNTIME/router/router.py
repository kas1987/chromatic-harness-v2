"""Chromatic API Router — main entry point for provider-neutral routing."""

__all__ = ["ChromaticRouter", "RouteRequest", "RouteResponse"]

import os
import time
import uuid
from typing import Any

from .contracts import (
    RouteRequest,
    RouteResponse,
    RouteLogs,
    RouteOutput,
    OutputType,
    PrivacyClass,
)
from .policy import PolicyLoader
from .confidence import ConfidenceGate
from .privacy import PrivacyGate
from .budget import BudgetGate
from .observability import ObservabilityLogger
from .adapters.base import AdapterHealth, BaseAdapter
from .adapters.mock import MockAdapter
from .adapters.adapter_factory import build as _build_adapters
from .complexity_classifier import ComplexityClassifier
from .context_detector import ContextDetector
from .provider_selector import ProviderSelector
from .context_gate import ContextGate
from .context_policy import ContextPolicyLoader


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
        allow_mock_fallback: bool | None = None,
    ):
        self.loader = loader or PolicyLoader()
        self.logger = logger or ObservabilityLogger()
        if allow_mock_fallback is None:
            allow_mock_fallback = os.environ.get("ROUTER_ALLOW_MOCK_FALLBACK", "false").lower() == "true"
        self.allow_mock_fallback = allow_mock_fallback
        self.context_gate = ContextGate()
        self.context_policy_loader = ContextPolicyLoader()
        self.confidence_gate = ConfidenceGate()
        self.privacy_gate = PrivacyGate(self.loader)
        self.budget_gate = BudgetGate(self.loader)

        self.complexity_classifier = ComplexityClassifier()
        self.context_detector = ContextDetector()
        self.provider_selector = ProviderSelector()
        self.adapters: dict[str, BaseAdapter] = {}
        self.provider_health_cache: dict[str, AdapterHealth] = {}
        if adapters:
            self.adapters.update(adapters)
        else:
            # All adapters now come from the YAML factory; logical providers are
            # declared in providers.yaml and wired via adapters.yaml.
            providers = self.loader.providers()
            self.adapters.update(_build_adapters(providers))

    async def _probe_provider_health(self, provider_names: list[str] | None = None) -> None:
        names = provider_names or list(self.adapters.keys())
        for provider_name in names:
            adapter = self.adapters.get(provider_name)
            if adapter is None:
                continue
            try:
                health = await adapter.health()
            except Exception as exc:  # pragma: no cover - defensive fallback
                health = AdapterHealth(reachable=False, latency_ms=0, error=str(exc))
            self.provider_health_cache[provider_name] = health

    async def _provider_is_available_async(self, name: str, req: RouteRequest | None = None) -> bool:
        adapter = self.adapters.get(name)
        if not adapter:
            return False
        if not adapter.enabled:
            return False
        if name == "openhuman":
            import os

            if os.environ.get("OPENHUMAN_ENABLED", "false").lower() != "true":
                return False
            if req is not None:
                if not req.constraints.allow_openhuman:
                    return False
                if req.constraints.privacy_class.value in ("P3", "P4", "P5"):
                    return False
        health = self.provider_health_cache.get(name)
        if health is not None and not health.reachable:
            return False
        return True

    @staticmethod
    def _request_prompt_text(req: RouteRequest) -> str:
        parts: list[str] = []

        for message in req.input.messages:
            content = message.get("content", "") if isinstance(message, dict) else ""
            if isinstance(content, str):
                text = content.strip()
                if text:
                    parts.append(text)
                continue
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = str(item.get("text", "")).strip()
                        if text:
                            parts.append(text)

        metadata = req.input.metadata
        if isinstance(metadata, dict):
            metadata_prompt = metadata.get("prompt")
            if isinstance(metadata_prompt, str) and metadata_prompt.strip():
                parts.append(metadata_prompt.strip())

        return "\n".join(parts)

    def _resolve_provider(self, req: RouteRequest) -> tuple[str, list[str], RouteLogs]:
        logs = RouteLogs()
        preferred = req.preferred_provider
        pc = req.constraints.privacy_class

        # ── AUTO: context-aware route (canonical) ───────────────────────────
        if not preferred or preferred == "auto":
            try:
                context = self.context_detector.detect()
                complexity = self.complexity_classifier.classify(
                    description=req.objective,
                    prompt=self._request_prompt_text(req),
                )
                selection = self.provider_selector.select(
                    complexity=complexity,
                    context=context,
                    privacy_class=pc.value,
                )
                ranked = selection.ranked_choices
                if ranked:
                    primary = ranked[0].provider
                    fallback = [c.provider for c in ranked[1:]]
                    logs.policy_checks.append(
                        f"Context route: C={complexity.level} speed={selection.speed_mode} "
                        f"provider={primary} ({len(fallback)} fallbacks)"
                    )
                    return self._apply_privacy_gate(primary, fallback, pc, logs)
                logs.warnings.append("Context routing produced no candidates.")
            except Exception as exc:
                logs.warnings.append(f"Context routing failed ({exc}).")

            # Auto-routing no longer falls back to the legacy task-type table.
            # Let the privacy gate record the failure and return a safe default.
            return self._apply_privacy_gate("mock", [], pc, logs)

        # ── EXPLICIT: operator/provider override ─────────────────────────────
        primary = preferred
        fallback = list(req.fallback_chain)
        return self._apply_privacy_gate(primary, fallback, pc, logs)

    # Provider names used by the routing table now map 1:1 to registered
    # adapter instances. Logical Ollama endpoints (ollama_local,
    # ollama_remote_desktop, ollama_remote) are first-class entries in
    # providers.yaml and are built by the YAML adapter factory.
    def _resolve_adapter_name(self, name: str) -> str:
        return name

    def _apply_privacy_gate(
        self,
        primary: str,
        fallback: list[str],
        pc: PrivacyClass,
        logs: RouteLogs,
    ) -> tuple[str, list[str], RouteLogs]:
        privacy_cfg = self.privacy_gate.policy.get(pc.value, {})
        allowed = set(privacy_cfg.get("allowed_providers", []))
        candidates = [primary, *fallback]
        filtered = []
        for cand in candidates:
            if cand == "local_vault":
                cand = "mock"
            if cand in allowed or (cand == "mock" and self.allow_mock_fallback):
                filtered.append(cand)
            else:
                logs.warnings.append(f"Provider {cand} removed by privacy policy for {pc.value}.")
        if not filtered:
            logs.errors.append("No candidate provider passed privacy gate.")
            if self.allow_mock_fallback:
                return "mock", [], logs
            return "", [], logs
        return filtered[0], filtered[1:], logs

    def _provider_is_available(self, name: str, req: RouteRequest | None = None) -> bool:
        adapter = self.adapters.get(name)
        if not adapter:
            return False
        if not adapter.enabled:
            return False
        if name == "openhuman":
            import os

            if os.environ.get("OPENHUMAN_ENABLED", "false").lower() != "true":
                return False
            if req is not None:
                if not req.constraints.allow_openhuman:
                    return False
                if req.constraints.privacy_class.value in ("P3", "P4", "P5"):
                    return False
        return True

    async def route(self, req: RouteRequest | None = None, **kwargs: Any) -> RouteResponse:
        if req is None:
            req = self._build_request(**kwargs)

        t0 = time.perf_counter()
        logs = RouteLogs()

        # 0. Context Resource Gate — runs BEFORE privacy/confidence/budget
        complexity = self.complexity_classifier.classify(req.objective)
        cg_result = self.context_gate.check(req, complexity_level=complexity.level)
        logs.policy_checks.extend(cg_result.logs)
        if not cg_result.ok:
            resp = RouteResponse(
                request_id=req.request_id,
                selected_provider="",
                route_reason="context_gate_blocked",
                confidence_score=req.confidence.score,
                privacy_class=req.constraints.privacy_class,
                context_resources=cg_result.allowed_resources,
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content="Blocked by context gate. Context budget exceeded or critical resources blocked.",
                ),
                logs=logs,
            )
            self.logger.log(req, resp)
            return resp

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
                context_resources=cg_result.allowed_resources,
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content="Blocked by privacy gate. See logs.errors.",
                ),
                logs=logs,
            )
            self.logger.log(req, resp)
            return resp

        await self._probe_provider_health(list(self.adapters.keys()))

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
                context_resources=cg_result.allowed_resources,
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

        if not chosen:
            resp = RouteResponse(
                request_id=req.request_id,
                selected_provider="",
                route_reason="all_providers_failed",
                confidence_score=req.confidence.score,
                privacy_class=req.constraints.privacy_class,
                context_resources=cg_result.allowed_resources,
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content="No provider passed the routing gates and mock fallback is disabled.",
                ),
                logs=logs,
            )
            self.logger.log(req, resp)
            return resp

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
                context_resources=cg_result.allowed_resources,
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
        resp: RouteResponse | None = None  # type: ignore[no-redef]
        last_error_resp: RouteResponse | None = None
        for cand in [chosen, *fallbacks]:
            if cand == "mock" and not self.allow_mock_fallback:
                logs.warnings.append("Mock fallback disabled by configuration.")
                continue
            health = self.provider_health_cache.get(cand)
            if health is not None and not health.reachable:
                logs.warnings.append(
                    f"Provider {cand} marked unreachable at startup ({health.error or 'health check failed'})."
                )
                continue
            if not await self._provider_is_available_async(cand, req):
                logs.warnings.append(f"Provider {cand} not available or disabled.")
                continue
            adapter = self.adapters.get(cand)
            if not await self._provider_is_available_async(cand, req):
                health = self.provider_health_cache.get(cand)
                if health is not None and not health.reachable:
                    logs.warnings.append(
                        f"Provider {cand} marked unreachable at startup ({health.error or 'health check failed'})."
                    )
                else:
                    logs.warnings.append(f"Provider {cand} not available or disabled.")
                continue
            adapter = self.adapters.get(cand)
            if adapter is None:
                logs.warnings.append(f"No adapter registered for {cand}.")
                continue
            try:
                candidate_resp = await adapter.complete(req)
                # Stamp the cost estimate before any early-out so that an error
                # response surfaced from last_error_resp still carries it.
                candidate_resp.cost_estimate_usd = est_cost
                # An adapter that returns an ERROR-typed response (rather than
                # raising) is still a failure — fall through to the next provider
                # instead of breaking on it. This is what lets a broken provider
                # (e.g. native_claude with no working CLI) hand off to a
                # reachable one (e.g. local Ollama) instead of erroring out.
                if candidate_resp.output is not None and candidate_resp.output.type == OutputType.ERROR:
                    err_text = candidate_resp.output.content
                    logs.warnings.append(f"Provider {cand} returned error: {err_text}")
                    candidate_resp.selected_provider = cand
                    last_error_resp = candidate_resp
                    continue
                if cand != chosen:
                    fallback_used = True
                provider_used = cand
                resp = candidate_resp
                break
            except Exception as exc:
                logs.errors.append(f"Provider {cand} failed: {exc}")
                continue

        if resp is None:
            mock = self.adapters.get("mock")
            if mock and self.allow_mock_fallback:
                resp = await mock.complete(req)
                provider_used = "mock"
                fallback_used = True
            elif mock and not self.allow_mock_fallback:
                logs.warnings.append("Mock fallback disabled by configuration.")
                resp = RouteResponse(
                    request_id=req.request_id,
                    selected_provider="",
                    route_reason="all_providers_failed",
                    output=RouteOutput(
                        type=OutputType.ERROR,
                        content="All providers failed and mock fallback is disabled.",
                    ),
                )
            elif last_error_resp is not None:
                # No mock, but at least one provider gave a real error — surface it.
                resp = last_error_resp
                resp.route_reason = "all_providers_failed"
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
        resp.context_resources = cg_result.allowed_resources

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
        from .contracts import (
            RouteInput,
            RouteConstraints,
            RouteConfidence,
            RouteAudit,
            TaskType,
        )

        return RouteRequest(
            request_id=request_id or str(uuid.uuid4()),
            task_id=task_id,
            task_type=TaskType(task_type),
            objective=objective,
            input=RouteInput(),
            constraints=RouteConstraints(
                privacy_class=PrivacyClass(privacy_class),
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k
                    in {
                        "max_cost_usd",
                        "max_latency_ms",
                        "max_tokens",
                        "allow_cloud",
                        "allow_broker",
                        "allow_openhuman",
                        "allow_tools",
                        "allow_skills",
                        "allow_mcp",
                        "max_context_resources",
                        "context_resource_allowlist",
                    }
                },
            ),
            confidence=RouteConfidence(
                score=confidence_score,
                band=ConfidenceGate.band_from_score(confidence_score),
            ),
            preferred_provider=preferred_provider,
            fallback_chain=fallback_chain or [],
            audit=RouteAudit(caller=caller),
        )
