# MISSIONS/schemas

The **Mission Packet** schema is unified and lives at the single canonical path:

    01_PROTOCOLS/CMP/mission_packet.schema.json

It is the one source of truth for both the **plan** profile (M1–M4 governance)
and the **dispatch** profile (L0–L5 runtime contract). Registered in
`01_PROTOCOLS/_schema_registry.yaml` as id `mission_packet`.

Validate any packet (YAML or JSON) with the single validator:

    python scripts/validate_mission_packet.py <packet.yaml|.json>
    # MISSIONS/scripts/validate_mission_packet.py is a thin shim over the same logic.

`mission_log.schema.json` (in this directory) is the separate mission-log record
schema and is unaffected.
