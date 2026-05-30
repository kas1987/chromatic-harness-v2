# Claude Instructions: Chromatic Harness Visual Control Plane

You are operating inside a Chromatic Harness repo.

## Source-of-truth order

1. `CHROMATIC_TREES.md`
2. `docs/pdr/PDR_VISUAL_CONTROL_PLANE.md`
3. `docs/playbooks/VISUAL_CONTROL_PLANE_PLAYBOOK.md`
4. `visual_node_registry.json`
5. `SPRINT_STATE.md`
6. `AGENT_HANDOFF_QUEUE.md`

## Operating rules

- Treat this file as an adapter, not governance.
- Do not override `CHROMATIC_TREES.md`.
- Before editing visuals, validate the node registry.
- After editing `visual_node_registry.json`, regenerate Mermaid diagrams.
- Use confidence scoring before mutating files.
- If confidence is below 60, create a plan only.
- Avoid broad repo exploration unless the task explicitly requires it.
- Stop and report if required context is missing, scope expands, or destructive actions are requested.

## Useful commands

```bash
python scripts/validate_visual_registry.py
python scripts/generate_harness_mermaid.py
```
