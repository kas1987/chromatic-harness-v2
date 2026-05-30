"""Dual-backlog lane helpers: title prefix + description line."""

from __future__ import annotations

import re

VALID_LANES = frozenset({"agent", "human", "review"})
_DEFAULT_LANE = "agent"

_PREFIX_RE = re.compile(r"^\[(agent|human|review)\]\s*", re.IGNORECASE)


def normalize_lane(lane: str | None) -> str:
    if lane and lane.lower() in VALID_LANES:
        return lane.lower()
    return _DEFAULT_LANE


def lane_title_prefix(lane: str) -> str:
    return f"[{normalize_lane(lane)}]"


def lane_description_line(lane: str) -> str:
    return f"lane: {normalize_lane(lane)}"


def parse_lane_from_title(title: str) -> str | None:
    m = _PREFIX_RE.match(title.strip())
    if m:
        return m.group(1).lower()
    return None


def apply_lane_to_bead_fields(
    title: str,
    description: str = "",
    *,
    lane: str | None = None,
    context_lane: str | None = None,
) -> tuple[str, str]:
    """Apply [lane] prefix and lane: line to bead title/description."""
    resolved = normalize_lane(lane or context_lane or parse_lane_from_title(title))
    prefix = lane_title_prefix(resolved)
    base_title = _PREFIX_RE.sub("", title.strip()).strip() or title.strip()
    if not base_title.lower().startswith(prefix.lower()):
        new_title = f"{prefix} {base_title}" if base_title else prefix
    else:
        new_title = base_title

    desc = (description or "").strip()
    lane_line = lane_description_line(resolved)
    if desc.startswith("lane:"):
        lines = desc.splitlines()
        lines[0] = lane_line
        new_desc = "\n".join(lines)
    elif desc:
        new_desc = f"{lane_line}\n\n{desc}"
    else:
        new_desc = lane_line
    return new_title, new_desc
