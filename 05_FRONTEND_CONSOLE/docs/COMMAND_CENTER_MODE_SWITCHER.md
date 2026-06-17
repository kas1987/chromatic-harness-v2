# Command Center Mode Switcher

## Purpose

Add a mode switcher to the frontend Command Center so the user can switch between:

```text
Operator | Auditor | Designer
```

## UI Placement

Recommended location: top bar, next to active mission and confidence score.

## Mode Effects

| Mode | Panels Prioritized | Theme | Default Action |
|---|---|---|---|
| Operator | Mission, Pipeline, Agents, Validation, Beads | default_neon | Execute scoped mission |
| Auditor | Evidence, Logs, Magnets, Risk, Findings | magnetic_gold | Audit/report |
| Designer | Mockups, Assets, Components, Prompt Packs | prism_cosmic | Generate design output |

## State Contract

Frontend state should include:

```ts
type CommandMode = "operator" | "auditor" | "designer";
```

Mission creation should include:

```ts
{
  objective: string,
  mode: commandMode,
  confidence_required: modeDefaults[commandMode].confidence_required,
  required_gates: modeDefaults[commandMode].required_gates
}
```

## Acceptance Criteria

- Mode selector visible in top bar.
- Selected mode persists during session.
- Mode changes visible panels and theme pack.
- Mission creation sends mode metadata.
- Auditor mode disables mutation action buttons by default.
