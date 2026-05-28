"""Budget gate for cost estimation and daily cap enforcement."""

import os
from .contracts import RouteRequest, RouteResponse, RouteLogs
from .policy import PolicyLoader


class BudgetGate:
    """Checks per-request cost caps and daily spend limits."""

    def __init__(self, loader: PolicyLoader | None = None):
        self.loader = loader or PolicyLoader()
        self.budget = self.loader.budget()
        self.costs = self.loader.provider_costs()
        self._daily_spend_key = "CHROMATIC_ROUTER_DAILY_SPEND"

    def _get_daily_spend(self) -> float:
        try:
            return float(os.environ.get(self._daily_spend_key, "0.0"))
        except ValueError:
            return 0.0

    def estimate(self, provider: str, max_tokens: int) -> float:
        per_1k = self.costs.get(provider, 0.0)
        return round((max_tokens / 1000.0) * per_1k, 6)

    def check(self, req: RouteRequest, provider: str) -> tuple[bool, RouteLogs, float]:
        """Returns (allowed, logs, estimated_cost_usd)."""
        logs = RouteLogs()
        est = self.estimate(provider, req.constraints.max_tokens)
        cap = self.budget.get("daily_usd_cap", 10.0)
        per_req_max = req.constraints.max_cost_usd
        daily = self._get_daily_spend()

        if est > per_req_max:
            logs.errors.append(
                f"Cost estimate ${est} exceeds per-request max ${per_req_max}."
            )
            return False, logs, est

        if daily + est > cap:
            logs.errors.append(
                f"Daily cap ${cap} would be exceeded (current ${daily} + est ${est})."
            )
            return False, logs, est

        logs.policy_checks.append(f"Budget gate passed: est ${est} within limits.")
        return True, logs, est
