# PDR: Designer Command Prompt

| Field | Value |
|---|---|
| PDR ID | CHCC-PROMPT-003 |
| Mode | Designer |
| Purpose | Asset swapping, UI composition, visual prompt generation |
| Default Autonomy | L1-L3 |

## 1. Executive Summary

The Designer Command Prompt controls visual asset generation and UI composition for the Harness Command Center. It lets the user swap themes, icons, backgrounds, cards, panel styles, and dashboard layouts while preserving the same backend data contracts.

## 2. Best For

- Command Center mockups
- image prompts
- theme variants
- icon packs
- card/panel systems
- asset library generation
- frontend style handoff
- OpenArt / Claude Design prompts

## 3. Asset-Swappable Layers

| Asset Layer | Examples |
|---|---|
| Background | nebula, dark grid, storm, prism field |
| Panels | glass cards, neon borders, brushed metal, holo cards |
| Icons | CMP shield, Magnets horseshoe, MCP chain, Beads cluster |
| Graphs | pipeline, node graph, confidence gauge, event stream |
| Colorways | Prism Purple, Runtime Blue, MCP Green, Magnet Gold |
| Motion | pulse, shimmer, scanline, glow drift |

## 4. Output Shape

```markdown
## Design Mode
Designer

## Visual Objective
[desired screen / asset]

## Asset Pack
[name and style tokens]

## Layout
[screen zones and components]

## Image Prompt
[generator-ready prompt]

## Implementation Notes
[CSS/component tokens]

## Export Checklist
[assets needed]
```

## 5. UI Behavior

Primary panels:

- Asset Pack Selector
- Theme Preview
- Component Gallery
- Prompt Builder
- Layout Canvas
- Export Queue

Primary buttons:

- Generate Mockup
- Swap Theme
- Export Prompt
- Create Asset Bead
- Send to Claude Design
- Create CSS Tokens

## 6. Prompt Template

```text
You are the Designer layer for Chromatic Harness.

Goal: create visual command-center assets that preserve the harness data model.

Rules:
- Do not alter CMP/MCP/runtime logic.
- Keep visual language aligned to Chromatic Harness: dark, neon, layered, deterministic, operational.
- Produce reusable asset packs, not one-off decorations.
- Separate visual design from implementation data contracts.
- Include theme tokens, component notes, and image-generation prompt.

Return: visual objective, asset pack, layout, image prompt, implementation notes, export checklist.
```

## 7. Acceptance Criteria

- [ ] Output can be handed to OpenArt, Claude Design, or frontend agent.
- [ ] Asset pack is swappable.
- [ ] Does not change backend schema.
- [ ] Maintains CMP/ADK/MCP/Magnets/Beads visual identity.
