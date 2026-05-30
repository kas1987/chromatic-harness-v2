# Agent Handoff: Visual Control Plane Implementation

## Role

You are acting as a scoped implementation agent for the Chromatic Harness Visual Control Plane.

## Objective

Implement or update the visual control plane without violating ChromaticTrees governance.

## Context

This repo uses a source-of-truth hierarchy:

1. `CHROMATIC_TREES.md`
2. `visual_node_registry.json`
3. Playbooks
4. Generated Mermaid docs
5. IDE bridge files

## Allowed Files

- `docs/visuals/**`
- `docs/pdr/PDR_VISUAL_CONTROL_PLANE.md`
- `docs/playbooks/VISUAL_CONTROL_PLANE_PLAYBOOK.md`
- `schemas/**`
- `scripts/generate_harness_mermaid.py`
- `scripts/validate_visual_registry.py`
- `.vscode/**`
- `.cursor/rules/**`
- `.claude/**`

## Forbidden Files

- Secrets
- Production deployment config
- Files outside assigned scope
- Source-of-truth governance files unless explicitly authorized

## Required Commands

```bash
python scripts/validate_visual_registry.py
python scripts/generate_harness_mermaid.py
```

## Acceptance Criteria

- Registry validates.
- Mermaid regenerates.
- Adapter files defer to source-of-truth docs.
- No destructive actions performed.
- Summary includes files changed and confidence score.

## Stop Conditions

Stop if:

- `CHROMATIC_TREES.md` conflicts with the requested edit.
- Registry validation fails and cannot be safely corrected.
- The task requires deleting files.
- The task expands beyond visual-control scope.
