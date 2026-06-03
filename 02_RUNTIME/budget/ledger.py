"""Monthly / daily / session budget ledger for agent transfer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

TransferDecision = Literal["spawn", "handoff_only", "halt_human"]


def _repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "config" / "agent_budget.yaml").exists():
            return parent
    return Path.cwd()


def load_agent_budget_config(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    path = root / "config" / "agent_budget.yaml"
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def daily_cap_usd(config: dict[str, Any] | None = None) -> float:
    """Shared daily cap for router BudgetGate and transfer ledger."""
    cfg = config or load_agent_budget_config()
    return float((cfg.get("caps") or {}).get("daily_usd", 25.0))


@dataclass
class BudgetSnapshot:
    session_est_tokens: int = 0
    session_cap_tokens: int = 200_000
    daily_spent_usd: float = 0.0
    daily_cap_usd: float = 25.0
    monthly_spent_usd: float = 0.0
    monthly_cap_usd: float = 400.0
    decision: TransferDecision = "handoff_only"
    reasons: list[str] = field(default_factory=list)

    def to_budget_dict(self) -> dict[str, Any]:
        return {
            "session_est_tokens": self.session_est_tokens,
            "session_cap_tokens": self.session_cap_tokens,
            "daily_spent_usd": round(self.daily_spent_usd, 4),
            "daily_cap_usd": self.daily_cap_usd,
            "monthly_spent_usd": round(self.monthly_spent_usd, 4),
            "monthly_cap_usd": self.monthly_cap_usd,
            "decision": self.decision,
            "reasons": self.reasons,
        }


def decide_transfer(snapshot: BudgetSnapshot, config: dict[str, Any]) -> TransferDecision:
    """Return spawn | handoff_only | halt_human from caps and thresholds."""
    caps = config.get("caps") or {}
    thresholds = config.get("thresholds") or {}
    reserve = float(config.get("successor_reserve_usd", 2.0))

    session_cap = float(caps.get("session_tokens", snapshot.session_cap_tokens))
    daily_cap = float(caps.get("daily_usd", snapshot.daily_cap_usd))
    monthly_cap = float(caps.get("monthly_usd", snapshot.monthly_cap_usd))

    spawn_daily_min = float(thresholds.get("spawn_min_daily_remaining_pct", 15)) / 100.0
    spawn_monthly_min = float(thresholds.get("spawn_min_monthly_remaining_pct", 10)) / 100.0
    handoff_session_pct = float(thresholds.get("handoff_only_below_session_pct", 80)) / 100.0

    reasons: list[str] = []

    if snapshot.monthly_spent_usd >= monthly_cap:
        reasons.append(f"monthly cap reached (${snapshot.monthly_spent_usd:.2f} >= ${monthly_cap:.2f})")
        snapshot.reasons = reasons
        return "halt_human"

    if snapshot.daily_spent_usd >= daily_cap:
        reasons.append(f"daily cap reached (${snapshot.daily_spent_usd:.2f} >= ${daily_cap:.2f})")
        snapshot.reasons = reasons
        return "halt_human"

    daily_remaining = daily_cap - snapshot.daily_spent_usd
    monthly_remaining = monthly_cap - snapshot.monthly_spent_usd
    session_ratio = snapshot.session_est_tokens / session_cap if session_cap > 0 else 0.0

    if session_ratio >= handoff_session_pct:
        reasons.append(f"session context high ({snapshot.session_est_tokens}/{int(session_cap)} tokens)")

    if daily_remaining < daily_cap * spawn_daily_min + reserve:
        reasons.append(f"daily headroom low (${daily_remaining:.2f} remaining, need {spawn_daily_min:.0%}+ reserve)")

    if monthly_remaining < monthly_cap * spawn_monthly_min + reserve:
        reasons.append(f"monthly headroom low (${monthly_remaining:.2f} remaining)")

    if reasons:
        snapshot.reasons = reasons
        return "handoff_only"

    snapshot.reasons = ["budget headroom OK for successor spawn"]
    return "spawn"


class BudgetLedger:
    """Load caps, estimate session burn, append daily ledger lines."""

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = (repo_root or _repo_root()).resolve()
        self.config = load_agent_budget_config(self.repo_root)
        self.budget_dir = self.repo_root / "07_LOGS_AND_AUDIT" / "budget"
        self.daily_log = self.budget_dir / "daily.jsonl"
        self.monthly_file = self.budget_dir / "monthly.json"

    def _ensure_dir(self) -> None:
        self.budget_dir.mkdir(parents=True, exist_ok=True)

    def _router_daily_spend(self) -> float:
        try:
            return float(os.environ.get("CHROMATIC_ROUTER_DAILY_SPEND", "0.0"))
        except ValueError:
            return 0.0

    def _sum_daily_ledger(self, month_key: str | None = None) -> float:
        if not self.daily_log.is_file():
            return 0.0
        total = 0.0
        month_key = month_key or datetime.now(timezone.utc).strftime("%Y-%m")
        for line in self.daily_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = str(row.get("timestamp", ""))
            if not ts.startswith(month_key):
                continue
            total += float(row.get("amount_usd", 0.0))
        return total

    def _read_monthly_rollup(self) -> float:
        if not self.monthly_file.is_file():
            return self._sum_daily_ledger()
        try:
            data = json.loads(self.monthly_file.read_text(encoding="utf-8"))
            key = datetime.now(timezone.utc).strftime("%Y-%m")
            return float((data.get("months") or {}).get(key, self._sum_daily_ledger(key)))
        except (json.JSONDecodeError, TypeError, ValueError):
            return self._sum_daily_ledger()

    def _write_monthly_rollup(self, monthly_spent: float) -> None:
        self._ensure_dir()
        key = datetime.now(timezone.utc).strftime("%Y-%m")
        data: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat(), "months": {}}
        if self.monthly_file.is_file():
            try:
                data = json.loads(self.monthly_file.read_text(encoding="utf-8"))
                if "months" not in data:
                    data["months"] = {}
            except json.JSONDecodeError:
                data = {"updated_at": datetime.now(timezone.utc).isoformat(), "months": {}}
        data["months"][key] = round(monthly_spent, 4)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.monthly_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def estimate_session_tokens(self) -> int:
        """Best-effort session token estimate from pre-session manifest or MCP audit."""
        manifest = self.repo_root / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                est = data.get("estimated_tokens") or data.get("mcp_estimated_tokens")
                if est is not None:
                    return int(est)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        audit = self.repo_root / ".agents" / "audits" / "latest_audit.json"
        if audit.is_file():
            try:
                text = audit.read_text(encoding="utf-8")
                if "Estimate:" in text or "estimated_tokens" in text:
                    data = json.loads(text)
                    for key in ("estimated_tokens", "mcp_tokens"):
                        if key in data:
                            return int(data[key])
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Activity log lines this session (rough proxy: 500 tok per event)
        activity = self.repo_root / "07_LOGS_AND_AUDIT" / "activity" / "agent_activity.jsonl"
        if activity.is_file():
            try:
                lines = [ln for ln in activity.read_text(encoding="utf-8").splitlines() if ln.strip()]
                return min(50_000, len(lines) * 500)
            except OSError:
                pass

        return 25_000

    def append_daily(self, amount_usd: float, *, source: str, note: str = "", decision_id: str = "") -> None:
        self._ensure_dir()
        row: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount_usd": round(amount_usd, 6),
            "source": source,
            "note": note,
        }
        if decision_id:
            row["decision_id"] = decision_id
        with open(self.daily_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def ingest_claude_usage_hook(self) -> float:
        """Phase B: parse ~/.claude/hooks usage output if a repo-local drop exists."""
        drop = self.repo_root / "07_LOGS_AND_AUDIT" / "budget" / "claude_usage_last.json"
        if not drop.is_file():
            return 0.0
        try:
            data = json.loads(drop.read_text(encoding="utf-8"))
            return float(data.get("session_cost_usd", 0.0))
        except (json.JSONDecodeError, TypeError, ValueError):
            return 0.0

    def snapshot(
        self,
        *,
        session_tokens: int | None = None,
        extra_daily_usd: float = 0.0,
    ) -> BudgetSnapshot:
        caps = self.config.get("caps") or {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_spend = 0.0
        if self.daily_log.is_file():
            for line in self.daily_log.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("timestamp", "")).startswith(today):
                    today_spend += float(row.get("amount_usd", 0.0))

        daily_spent = max(self._router_daily_spend(), today_spend) + extra_daily_usd + self.ingest_claude_usage_hook()

        monthly_spent = self._read_monthly_rollup()
        if monthly_spent < daily_spent:
            monthly_spent = self._sum_daily_ledger() + extra_daily_usd

        snap = BudgetSnapshot(
            session_est_tokens=session_tokens if session_tokens is not None else self.estimate_session_tokens(),
            session_cap_tokens=int(caps.get("session_tokens", 200_000)),
            daily_spent_usd=daily_spent,
            daily_cap_usd=float(caps.get("daily_usd", 25.0)),
            monthly_spent_usd=monthly_spent,
            monthly_cap_usd=float(caps.get("monthly_usd", 400.0)),
        )
        snap.decision = decide_transfer(snap, self.config)
        self._write_monthly_rollup(monthly_spent)
        return snap
