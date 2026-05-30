# Chromatic Harness Visual Control Plane

Portable PDR + scaffold for visualizing every operating layer of a Chromatic Harness repo across Claude, VS Code, Cursor, GitHub, n8n, Mermaid, LangGraph-style agent traces, and Grafana/OpenTelemetry observability.

## Purpose

This package creates a visual operating layer that answers:

1. What layer am I looking at?
2. Which agents, workflows, and playbooks are active?
3. What task is running?
4. What confidence score authorized it?
5. What files can the agent touch?
6. What node failed?
7. What tool calls exploded?
8. What changed in the repo?
9. What is queued next?
10. Did the system respect ChromaticTrees?

## Install into a repo

```bash
python scripts/install_visual_control_plane.py --target /path/to/repo
```

On Windows PowerShell:

```powershell
python scripts/install_visual_control_plane.py --target C:\Path\To\Repo
```

## Main files

| File | Purpose |
|---|---|
| `docs/pdr/PDR_VISUAL_CONTROL_PLANE.md` | Main project design record |
| `docs/visuals/HARNESS_LAYER_MAP.md` | Mermaid overview of all harness layers |
| `docs/visuals/GO_MODE_FLOW.md` | GO-mode autonomy and confidence-gate flow |
| `docs/visuals/AGENT_ROUTER_GRAPH.md` | Agent routing and dispatch graph |
| `docs/visuals/OBSERVABILITY_PIPELINE.md` | OpenTelemetry/Grafana pipeline map |
| `docs/playbooks/VISUAL_CONTROL_PLANE_PLAYBOOK.md` | Operating playbook |
| `schemas/visual_node.schema.json` | Machine-readable visual node registry schema |
| `schemas/harness_event.schema.json` | Telemetry event schema |
| `scripts/generate_harness_mermaid.py` | Generates Mermaid from registry JSON |
| `.vscode/tasks.json` | VS Code tasks |
| `.cursor/rules/chromatic-visual-control-plane.mdc` | Cursor operating rules |
| `.claude/CLAUDE.md` | Claude repo instructions |

## Operating principle

`CHROMATIC_TREES.md` remains the governing source of truth. This package visualizes and validates the harness; it does not replace repo governance.
