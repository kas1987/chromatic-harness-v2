# Handoff: Implement Command Prompt System

## Objective

Integrate Operator, Auditor, and Designer command prompt modes into Chromatic Harness V2.

## Files to Add

- `08_PDRS/PDR_COMMAND_PROMPT_SYSTEM.md`
- `08_PDRS/PDR_OPERATOR_COMMAND_PROMPT.md`
- `08_PDRS/PDR_AUDITOR_COMMAND_PROMPT.md`
- `08_PDRS/PDR_DESIGNER_COMMAND_PROMPT.md`
- `01_PROTOCOLS/COMMAND_PROMPTS/COMMAND_PROMPT_SPEC.md`
- `templates/prompts/operator_command_prompt.md`
- `templates/prompts/auditor_command_prompt.md`
- `templates/prompts/designer_command_prompt.md`
- `schemas/command_prompt_pack.schema.json`
- `schemas/asset_swap_pack.schema.json`
- `05_FRONTEND_CONSOLE/assets/prompt_variants/*.yaml`
- `05_FRONTEND_CONSOLE/docs/COMMAND_CENTER_MODE_SWITCHER.md`

## Files to Modify

- `README.md`
- `05_FRONTEND_CONSOLE/src/app/page.tsx`
- `05_FRONTEND_CONSOLE/src/lib/api.ts`
- `02_RUNTIME/orchestrator/orchestrator.py`

## Acceptance Criteria

- Mode is selectable in frontend.
- Mode is included in mission metadata.
- Operator/Auditor/Designer prompts exist.
- Asset packs exist and are validated.
- Auditor mode blocks mutation by default.
- Designer mode only writes scoped visual/design artifacts by default.
- Operator mode still requires CMP confidence gates.

## Suggested Beads

1. `P0` Add command prompt PDRs and protocol spec.
2. `P1` Add prompt templates and asset packs.
3. `P1` Add frontend mode selector.
4. `P1` Add mode metadata to MissionPacket.
5. `P2` Add schema validation and tests.
6. `P2` Update README and CHROMATIC_TREES references.
