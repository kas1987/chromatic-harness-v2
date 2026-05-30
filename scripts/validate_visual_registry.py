#!/usr/bin/env python3
"""Lightweight validation for visual_node_registry.json without external dependencies."""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_NODE_FIELDS = {"id", "label", "type", "layer"}


def main() -> None:
    path = Path("visual_node_registry.json")
    if not path.exists():
        raise SystemExit("Missing visual_node_registry.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    node_ids = set()
    for node in data.get("nodes", []):
        missing = REQUIRED_NODE_FIELDS - set(node)
        if missing:
            raise SystemExit(f"Node missing fields {missing}: {node}")
        if node["id"] in node_ids:
            raise SystemExit(f"Duplicate node id: {node['id']}")
        node_ids.add(node["id"])
    for edge in data.get("edges", []):
        if len(edge) != 2:
            raise SystemExit(f"Invalid edge: {edge}")
        if edge[0] not in node_ids or edge[1] not in node_ids:
            raise SystemExit(f"Edge references unknown node: {edge}")
    print("visual_node_registry.json is valid")


if __name__ == "__main__":
    main()
