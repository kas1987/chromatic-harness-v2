"""Policy loader for routing, privacy, budget, and provider configs."""

import os
import yaml
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    """Locate repo root from runtime or CWD."""
    here = Path(__file__).resolve().parent
    # Walk up until we see a known harness directory or .git
    for parent in [here, *here.parents]:
        if (parent / "00_SOURCE_OF_TRUTH").exists() or (parent / ".git").exists():
            return parent
    return Path(os.getcwd())


def _config_dir() -> Path:
    root = _repo_root()
    return root / "09_DEPLOYMENT" / "config" / "routing"


class PolicyLoader:
    """Loads YAML policy files from 09_DEPLOYMENT/config/routing/."""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or _config_dir()
        self._cache: dict[str, Any] = {}

    def _load(self, name: str) -> Any:
        if name not in self._cache:
            path = self.config_dir / name
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self._cache[name] = yaml.safe_load(f)
            else:
                self._cache[name] = {}
        return self._cache[name]

    def providers(self) -> dict[str, Any]:
        data = self._load("providers.yaml") or {}
        return data.get("providers", {})

    def routes(self) -> dict[str, Any]:
        data = self._load("routing-table.yaml") or {}
        return data.get("routes", {})

    def privacy(self) -> dict[str, Any]:
        data = self._load("privacy-policy.yaml") or {}
        return data.get("privacy_classes", {})

    def budget(self) -> dict[str, Any]:
        data = self._load("budget-policy.yaml") or {}
        return data.get("budget", {})

    def provider_costs(self) -> dict[str, float]:
        data = self._load("budget-policy.yaml") or {}
        return data.get("provider_cost_estimates", {})

    def route_for_task(self, task_type: str) -> dict[str, Any]:
        return self.routes().get(task_type, {})

    def provider_cfg(self, name: str) -> dict[str, Any]:
        return self.providers().get(name, {})
