"""AdapterFactory: load adapters from adapters.yaml instead of a hardcoded if-elif chain."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

_REGISTRY_PATH = Path(__file__).parent / "adapters.yaml"


def _load_registry(registry_path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("pyyaml required for AdapterFactory: pip install pyyaml") from exc
    return yaml.safe_load(registry_path.read_text(encoding="utf-8"))


def _instantiate(entry: dict[str, Any], name: str, cfg: dict[str, Any]):
    mod = importlib.import_module(entry["module"])
    cls = getattr(mod, entry["class"])
    if entry.get("pass_name"):
        return cls(name, cfg)
    return cls(cfg)


def build(
    providers: dict[str, Any],
    registry_path: Path | None = None,
) -> dict:
    """Return {provider_name: adapter_instance} for every provider in *providers*.

    Providers with no registry entry are silently skipped (same behaviour as
    the old if-elif chain which had no else branch).
    """
    from .base import BaseAdapter

    registry = _load_registry(registry_path or _REGISTRY_PATH)
    exact: dict[str, Any] = registry.get("adapters", {})
    prefixes: dict[str, Any] = registry.get("prefixes", {})

    result: dict[str, BaseAdapter] = {}
    for name, cfg in providers.items():
        entry = exact.get(name)
        if entry is None:
            for prefix, pentry in prefixes.items():
                if name.startswith(prefix):
                    entry = pentry
                    break
        if entry is None:
            continue
        result[name] = _instantiate(entry, name, cfg)

    return result
