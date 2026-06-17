# Modular Swap Model

Chromatic Harness is built to **swap capabilities in and out per dev need** rather than
run everything at once. Three swappable layers, each with its own switch:

| Layer | What swaps | How to switch | Constraint |
|---|---|---|---|
| **Skills** | Individual skill families (`core`, `pipeline`, `trust`, `toolchain`) | `skills-family.ps1 [family\|all]` | Load only the family the task needs (context-budget rule) |
| **Plugins** | One active plugin set | `/reload-plugins` | **Only one plugin active at a time** — deactivate before activating another |
| **Prompt modes** | Operator / Auditor / Designer command prompts | Load template from `docs/prompts/` + asset pack from `assets/prompt_variants/` | Modes are interchangeable; none claims authority over CMP or `CHROMATIC_TREES` |

## Skills

- Skills **auto-invoke** when a request matches their trigger — no need to ask.
- Surface the active set with the available-skills list; never invoke a skill not in that list.
- Toggle families with `skills-family.ps1` to keep `CLAUDE.md` / context under budget.

## Plugins

- Hot-swap per task, but **never stack** — one plugin active at a time to avoid conflicts.
- `/reload-plugins` re-reads the current set (plugins · skills · agents · hooks · MCP servers).
- Deactivate the current plugin before activating a different one.

## Prompt modes (Command Prompt System)

Pick the surface that fits the task; swap when the task changes:

| Task shape | Mode | Pair with |
|---|---|---|
| Execution, dispatch, GO-mode, confidence gates | **Operator** (`docs/prompts/operator_command_prompt.md`) | `pipeline` / `core` skills |
| Review, trace, evidence, risk, deterministic reporting | **Auditor** (`docs/prompts/auditor_command_prompt.md`) | `trust` skills |
| Visual/asset swapping, UI composition, theme generation | **Designer** (`docs/prompts/designer_command_prompt.md`) | `toolchain` skills |

See `docs/playbooks/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md` for switching mechanics and
`docs/pdr/PDR_COMMAND_PROMPT_SYSTEM.md` for the design record.

## Operating principle

Swapping is additive at the prompt/skill layer and exclusive at the plugin layer.
`CHROMATIC_TREES.md` remains the governing source of truth across every mode — swapping a
surface never swaps governance.
