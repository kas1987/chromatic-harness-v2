# Templates Index

Reusable templates for harness operations. **Any agent: pick the template for your task
below, copy it, fill it, save it to the indicated home.** The canonical operation→file map
lives in [`CHROMATIC_TREES.md` §5](../CHROMATIC_TREES.md#5-agent-quick-reference--operation--file).

## Planning templates (create work)

| Template | Use when you… | Save to |
|----------|---------------|---------|
| [`EPIC_TEMPLATE.md`](EPIC_TEMPLATE.md) | open a new epic (multi-bead work stream) | bd (`--type epic`) |
| [`BEAD_TEMPLATE.md`](BEAD_TEMPLATE.md) | create a task under an epic | bd (`--type task --parent`) |
| [`ROADMAP_TEMPLATE.md`](ROADMAP_TEMPLATE.md) | plan a version/program | `docs/research/<TOPIC>_ROADMAP.md` |
| [`../08_PDRS/_PDR_TEMPLATE.md`](../08_PDRS/_PDR_TEMPLATE.md) | write a design record (design-heavy work) | `08_PDRS/<feature>.md` |
| [`RETRO_TEMPLATE.md`](RETRO_TEMPLATE.md) | wrap up completed work | `docs/retros/YYYY-MM-DD-<slug>.md` |

## Record templates (capture runtime facts)

| Template | Use when you… |
|----------|---------------|
| [`LEARNING_RECORD_TEMPLATE.md`](LEARNING_RECORD_TEMPLATE.md) | record a reusable learning (or `bd remember`) |
| [`FIX_PATTERN_TEMPLATE.md`](FIX_PATTERN_TEMPLATE.md) | record a repeatable fix pattern |
| [`INCIDENT_RECORD_TEMPLATE.md`](INCIDENT_RECORD_TEMPLATE.md) | record an incident |
| [`COLLISION_RECORD_TEMPLATE.md`](COLLISION_RECORD_TEMPLATE.md) | record a write/branch collision |
| [`EVENT_RECORD_TEMPLATE.json`](EVENT_RECORD_TEMPLATE.json) | emit a harness event (schema: `00_META/observability/HARNESS_EVENT_SCHEMA.json`) |
| [`AGENT_MISSION_PACKET_OBSERVABILITY.md`](AGENT_MISSION_PACKET_OBSERVABILITY.md) | build an observability mission packet |
| [`AGENT_MISSION_PACKET_REVIEW_INTAKE.md`](AGENT_MISSION_PACKET_REVIEW_INTAKE.md) | build a review-intake mission packet |
| [`REVIEW_RESOLUTION_COMMENT.md`](REVIEW_RESOLUTION_COMMENT.md) | post a review-resolution comment |

---
*Adding a template? Update this index **and** `CHROMATIC_TREES.md` §5 in the same change — they must agree.*
