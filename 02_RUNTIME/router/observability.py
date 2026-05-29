"""JSONL observability logging for router decisions."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import RouteRequest, RouteResponse


def _repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "00_SOURCE_OF_TRUTH").exists() or (parent / ".git").exists():
            return parent
    return Path(os.getcwd())


_GOVERNED_MODELS = {"sonnet", "kimi"}

# Maps ConfidenceBand → PDR risk_level label
_BAND_TO_RISK = {
    "very_high": "low",
    "high": "low",
    "medium": "medium",
    "low": "high",
    "blocked": "critical",
}


class ObservabilityLogger:
    """Append-only JSONL route log with redaction."""

    def __init__(
        self,
        log_dir: Path | None = None,
        agent_run_log: Path | None = None,
    ):
        root = _repo_root()
        self.log_dir = log_dir or (root / "07_LOGS_AND_AUDIT" / "routing")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._file = (
            self.log_dir
            / f"routes_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        )
        self._agent_run_log = agent_run_log or (
            root / "07_LOGS_AND_AUDIT" / "AGENT_RUN_LOG.jsonl"
        )

    def _redact(self, text: str) -> str:
        import re

        patterns = [
            (r"sk-[a-zA-Z0-9]{20,}", "sk-***"),
            (r"ghp_[a-zA-Z0-9]{20,}", "ghp_***"),
            (r"AKIA[0-9A-Z]{16}", "AKIA***"),
            (r"Bearer [a-zA-Z0-9\-_]{20,}", "Bearer ***"),
        ]
        for pat, repl in patterns:
            text = re.sub(pat, repl, text)
        return text

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._redact(value)
        if isinstance(value, dict):
            return {k: self._sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize(v) for v in value]
        return value

    def log(
        self,
        req: RouteRequest,
        resp: RouteResponse,
        extra: dict[str, Any] | None = None,
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": req.request_id,
            "task_id": req.task_id,
            "task_type": req.task_type.value,
            "caller": req.audit.caller,
            "repo": req.audit.repo,
            "selected_provider": resp.selected_provider,
            "selected_model": resp.selected_model,
            "route_reason": resp.route_reason,
            "fallback_used": resp.fallback_used,
            "confidence_score": resp.confidence_score,
            "privacy_class": resp.privacy_class.value,
            "cost_estimate_usd": resp.cost_estimate_usd,
            "latency_ms": resp.latency_ms,
            "result_status": resp.output.type.value,
            "warnings": resp.logs.warnings,
            "errors": resp.logs.errors,
        }
        if extra:
            entry.update(self._sanitize(extra))
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        model_key = (resp.selected_model or "").lower()
        if any(g in model_key for g in _GOVERNED_MODELS):
            self._log_agent_run(req, resp, extra)

    def _log_agent_run(
        self,
        req: RouteRequest,
        resp: RouteResponse,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Append a PDR-GOV-SONNET-KIMI-001 format record to AGENT_RUN_LOG.jsonl."""
        band = getattr(req.confidence, "band", None)
        if band is not None and hasattr(band, "value"):
            band_val = str(band.value)
        else:
            band_val = str(band or "")
        extra = extra or {}
        record = {
            "task_id": req.task_id,
            "model": resp.selected_model or "",
            "role": extra.get("role", ""),
            "confidence_score": resp.confidence_score,
            "risk_level": _BAND_TO_RISK.get(band_val, "medium"),
            "tools_used": extra.get("tools_used", 0),
            "files_touched": extra.get("files_touched", []),
            "result": resp.output.type.value,
            "validation": extra.get("validation", ""),
            "next_task": extra.get("next_task", ""),
        }
        with open(self._agent_run_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
