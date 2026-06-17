#!/usr/bin/env python3
"""Validate the Chromatic Command Prompt System pack inside chromatic-harness-v2.

Promoted from the portable pack (docs/handoffs/HANDOFF_IMPLEMENT_COMMAND_PROMPT_SYSTEM.md).
REQUIRED[] is mapped to the numbered taxonomy (CHROMATIC_TREES rank-2 SoT) rather than
the pack's original flat docs/* layout: PDRs -> 08_PDRS, playbook -> 04_PLAYBOOKS, the
mockup -> 05_FRONTEND_CONSOLE/mockups; prompts/schemas/asset packs keep their canonical
homes (docs/prompts, schemas/, assets/prompt_variants).

Run:  python scripts/validate_command_prompt_pack.py
Exit non-zero (SystemExit) if any required artifact is missing or a schema is invalid JSON.
"""

from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

# Canonical (taxonomy) locations of every artifact the pack must ship.
REQUIRED = [
    # PDRs — canonical home is 08_PDRS (docs/pdr retains pointer stubs)
    "08_PDRS/PDR_COMMAND_PROMPT_SYSTEM.md",
    "08_PDRS/PDR_OPERATOR_COMMAND_PROMPT.md",
    "08_PDRS/PDR_AUDITOR_COMMAND_PROMPT.md",
    "08_PDRS/PDR_DESIGNER_COMMAND_PROMPT.md",
    # Playbook — canonical home is 04_PLAYBOOKS (docs/playbooks retains pointer stub)
    "04_PLAYBOOKS/COMMAND_PROMPT_SYSTEM_PLAYBOOK.md",
    # Prompt templates — no numbered tier owns prompts; docs/prompts is canonical-primary
    "docs/prompts/operator_command_prompt.md",
    "docs/prompts/auditor_command_prompt.md",
    "docs/prompts/designer_command_prompt.md",
    # Schemas — canonical home is schemas/ (registered in 01_PROTOCOLS/_schema_registry.yaml)
    "schemas/command_prompt_pack.schema.json",
    "schemas/command_action.schema.json",
    "schemas/asset_swap_pack.schema.json",
    # Command Center mode-switcher mockup — already reconciled into the frontend tier
    "05_FRONTEND_CONSOLE/mockups/COMMAND_CENTER_MODE_SWITCHER.md",
    # Asset (theme) packs consumed by scripts/generate_console_themes.py
    "assets/prompt_variants/default_neon.asset_pack.yaml",
    "assets/prompt_variants/magnetic_gold.asset_pack.yaml",
    "assets/prompt_variants/prism_cosmic.asset_pack.yaml",
]

# Pack schemas that must be valid JSON.
SCHEMAS = [
    "schemas/command_prompt_pack.schema.json",
    "schemas/command_action.schema.json",
    "schemas/asset_swap_pack.schema.json",
]


def main() -> None:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        raise SystemExit("Missing required Command Prompt System artifacts:\n  " + "\n  ".join(missing))

    bad: list[str] = []
    for rel in SCHEMAS:
        try:
            json.loads((ROOT / rel).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:  # pragma: no cover - defensive
            bad.append(f"{rel}: {exc}")
    if bad:
        raise SystemExit("Invalid pack schema JSON:\n  " + "\n  ".join(bad))

    print("Command Prompt System pack validation passed (taxonomy layout).")


if __name__ == "__main__":
    main()
