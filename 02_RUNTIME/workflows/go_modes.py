"""Parse GO mode commands."""

from __future__ import annotations

from workflows.models import GoMode


def parse_go_mode(raw: str) -> GoMode:
    normalized = " ".join(raw.strip().upper().split())
    if normalized == "GO":
        return GoMode.GO
    for mode in GoMode:
        if mode.value == normalized:
            return mode
    raise ValueError(f"unknown GO mode: {raw!r}")


def mode_allows_mutation(mode: GoMode) -> bool:
    return mode in (GoMode.GO, GoMode.GO_BUILD, GoMode.GO_SHIP)


def mode_requires_swarm_approval(mode: GoMode) -> bool:
    return mode == GoMode.GO_SWARM
