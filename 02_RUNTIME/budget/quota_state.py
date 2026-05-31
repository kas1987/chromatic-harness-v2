"""Quota state schema + source-abstracted reader with staleness guard.

This is the consumer-facing half of the Axis P (prepaid weekly quota) capture
layer per TOKEN_ECONOMY_SPEC §4. The producer today is ``quota_proxy.py`` (a
fail-open reverse proxy that scrapes ``anthropic-ratelimit-unified-*`` headers
into ``~/.claude/powerline/usage/quota_state.json``). Consumers (controller,
forecaster, exporter) MUST read through :class:`QuotaStateReader` so the
producer can later swap to native OTEL (anthropic #16942) or statusline
(#20636) without touching any consumer.

Doctrine: Axis P is the *verified-only* deterministic source of the weekly %.
If the file is missing, malformed, or stale (>5 min) the reader returns a
state with ``is_fresh() is False`` — consumers fall back to conservative
behavior rather than trusting a dead producer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Default staleness window per spec §7 (controller 5-minute staleness guard).
STALENESS_SECONDS = 300

# Extended TTL for manually-seeded quota state (spec §4); manual seeds are not
# refreshed by a live proxy so we honor them for a full 24-hour window.
MANUAL_SEED_TTL_SECONDS = 86400

# Canonical producer drop location (spec §3).
DEFAULT_QUOTA_STATE_PATH = (
    Path.home() / ".claude" / "powerline" / "usage" / "quota_state.json"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        # Tolerate trailing 'Z' which fromisoformat rejects before 3.11.
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _coerce_pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class QuotaState:
    """Parsed ``quota_state.json`` record (spec §3 contract).

    All numeric fields are optional: a partial record (e.g. only the 7d window
    present) is still usable. ``source`` records which producer emitted the
    record so consumers can reason about provenance across the abstraction.
    """

    weekly_pct: float | None = None
    weekly_reset: str | None = None
    session_5h_pct: float | None = None
    session_5h_reset: str | None = None
    representative_claim: str | None = None
    status: str | None = None
    captured_at: str | None = None
    source: str = "unknown"
    # True only when the record was loaded clean AND within the staleness window.
    present: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def age_seconds(self, *, now: datetime | None = None) -> float | None:
        """Seconds since ``captured_at``; None if unparseable/missing."""
        captured = _parse_ts(self.captured_at)
        if captured is None:
            return None
        delta = (now or _now()) - captured
        return delta.total_seconds()

    def is_fresh(
        self,
        *,
        max_age_seconds: int = STALENESS_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        """True iff the record is present and within the staleness window."""
        if not self.present:
            return False
        age = self.age_seconds(now=now)
        if age is None:
            return False
        return 0 <= age <= max_age_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "weekly_pct": self.weekly_pct,
            "weekly_reset": self.weekly_reset,
            "session_5h_pct": self.session_5h_pct,
            "session_5h_reset": self.session_5h_reset,
            "representative_claim": self.representative_claim,
            "status": self.status,
            "captured_at": self.captured_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuotaState":
        return cls(
            weekly_pct=_coerce_pct(data.get("weekly_pct")),
            weekly_reset=data.get("weekly_reset"),
            session_5h_pct=_coerce_pct(data.get("session_5h_pct")),
            session_5h_reset=data.get("session_5h_reset"),
            representative_claim=data.get("representative_claim"),
            status=data.get("status"),
            captured_at=data.get("captured_at"),
            source=str(data.get("source", "proxy")),
            present=True,
            raw=dict(data),
        )


# An empty / never-produced state. Consumers treat this as "no Axis P signal".
EMPTY_STATE = QuotaState(present=False, source="absent")


class QuotaStateReader:
    """Source-abstracted reader for the Axis P quota signal.

    Consumers depend ONLY on this interface, never on the producer. Swapping
    the producer (proxy -> OTEL -> statusline) is a one-line change here.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        max_age_seconds: int = STALENESS_SECONDS,
    ) -> None:
        self.path = Path(path) if path is not None else DEFAULT_QUOTA_STATE_PATH
        self.max_age_seconds = max_age_seconds

    def read(self) -> QuotaState:
        """Load + parse the quota state. Never raises — fail-open to EMPTY_STATE."""
        try:
            if not self.path.is_file():
                return EMPTY_STATE
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return EMPTY_STATE
        if not isinstance(data, dict):
            return EMPTY_STATE
        return QuotaState.from_dict(data)

    def read_fresh(self) -> QuotaState | None:
        """Return the state only if fresh; otherwise None (staleness guard)."""
        state = self.read()
        if state.is_fresh(max_age_seconds=self.max_age_seconds):
            return state
        return None

    def is_stale(self, *, now: datetime | None = None) -> bool:
        """True when there is no usable, fresh Axis P signal."""
        return not self.read().is_fresh(max_age_seconds=self.max_age_seconds, now=now)


def read_quota_state(
    path: Path | str | None = None,
    *,
    max_age_seconds: int = STALENESS_SECONDS,
) -> QuotaState:
    """Convenience one-shot reader (spec §4 source abstraction)."""
    return QuotaStateReader(path, max_age_seconds=max_age_seconds).read()
