"""Budget gate for cost estimation and daily cap enforcement."""

import os
import sys
from pathlib import Path

from .contracts import RouteRequest, RouteLogs
from .policy import PolicyLoader

_RUNTIME = Path(__file__).resolve().parents[1]
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))


def _agent_daily_cap() -> float:
    try:
        from budget.ledger import daily_cap_usd

        return daily_cap_usd()
    except Exception:
        return 10.0


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
        raw = self.costs.get(provider, 0.0)
        if isinstance(raw, dict):
            per_1k = raw.get("per_1k_tokens_usd", 0.0)
        else:
            per_1k = raw
        return round((max_tokens / 1000.0) * per_1k, 6)

    def check(self, req: RouteRequest, provider: str) -> tuple[bool, RouteLogs, float]:
        logs = RouteLogs()
        est = self.estimate(provider, req.constraints.max_tokens)
        cap = self.budget.get("daily_usd_cap") or _agent_daily_cap()
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
