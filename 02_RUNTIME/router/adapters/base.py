"""Base adapter contract for all provider adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..contracts import RouteRequest, RouteResponse, OutputType, RouteOutput, RouteUsage


class AdapterError(Exception):
    """Raised by any adapter for SDK-missing, blocked, or empty-response errors."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.cause = cause


@dataclass
class AdapterHealth:
    reachable: bool
    latency_ms: int
    error: str = ""


class BaseAdapter(ABC):
    """Every provider adapter must implement these."""

    def __init__(self, name: str, cfg: dict[str, Any]):
        self.name = name
        self.cfg = cfg
        self.enabled = cfg.get("enabled", False)

    @abstractmethod
    async def health(self) -> AdapterHealth:
        """Quick liveness check."""
        ...

    @abstractmethod
    async def complete(self, req: RouteRequest) -> RouteResponse:
        """Execute the route and return a normalized response."""
        ...

    def normalize_error(self, request_id: str, message: str) -> RouteResponse:
        return RouteResponse(
            request_id=request_id,
            selected_provider=self.name,
            route_reason="adapter_error",
            output=RouteOutput(type=OutputType.ERROR, content=message),
        )
