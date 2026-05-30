#!/usr/bin/env python3
"""Generate Mermaid diagrams from visual_node_registry.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def sanitize_id(value: str) -> str:
    return value.replace('-', '_').replace(' ', '_')


def generate_mermaid(registry: dict) -> str:
    nodes = {node["id"]: node for node in registry.get("nodes", [])}
    lines = ["flowchart TD"]
    for node_id, node in nodes.items():
        safe_id = sanitize_id(node_id)
        label = node.get("label", node_id).replace('"', "'")
        lines.append(f'    {safe_id}["{label}"]')
    for source, target in registry.get("edges", []):
        lines.append(f"    {sanitize_id(source)} --> {sanitize_id(target)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Chromatic Harness Mermaid diagrams.")
    parser.add_argument("--registry", default="visual_node_registry.json")
    parser.add_argument("--output", default="docs/visuals/GENERATED_LAYER_MAP.md")
    args = parser.parse_args()

    registry_path = Path(args.registry)
    output_path = Path(args.output)

    if not registry_path.exists():
        raise SystemExit(f"Registry not found: {registry_path}")

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    mermaid = generate_mermaid(registry)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "# Generated Harness Layer Map\n\n"
        "Generated from `visual_node_registry.json`. Do not hand-edit this file unless you also update the registry.\n\n"
        "```mermaid\n"
        f"{mermaid}\n"
        "```\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
