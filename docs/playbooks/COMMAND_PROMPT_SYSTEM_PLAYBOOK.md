# Command Prompt System Playbook

## 1. Purpose

Govern how Chromatic Harness switches between Operator, Auditor, and Designer command prompt modes.

## 2. Source of Truth

1. `CHROMATIC_TREES.md`
2. `docs/pdr/PDR_COMMAND_PROMPT_SYSTEM.md`
3. Prompt mode PDRs
4. Prompt templates
5. Asset packs
6. UI implementation

## 3. Mode Selection

| User Signal | Mode |
|---|---|
| GO, continue, run, dispatch, execute | Operator |
| review, audit, check, validate, are we aligned | Auditor |
| design, image, mockup, asset, theme, style | Designer |

## 4. Safety Rule

Prompt mode cannot override CMP. If a prompt requests an action forbidden by CMP, CMP wins.

## 5. Standard Loop

```text
Detect Mode -> Load Prompt Pack -> Apply CMP -> Render UI State -> Execute or Report -> Log Event -> Queue Next
```

## 6. Stop Conditions

Stop if:

- mode is ambiguous and action would mutate state
- prompt pack is missing required fields
- asset pack attempts to change governance logic
- Auditor mode is asked to mutate files without promotion
- Operator mode lacks confidence score
- Designer mode attempts to overwrite schemas
