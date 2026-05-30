#!/usr/bin/env python3
"""CI gate: Karpathy 4-pillar discipline wired across Cursor, Pi, and magnets."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

CANON = REPO / "docs" / "governance" / "KARPATHY_DISCIPLINE.md"
CURSOR_RULE = REPO / ".cursor" / "rules" / "karpathy-guidelines.mdc"
DISCIPLINE_TS = (
    REPO
    / "02_RUNTIME"
    / "runtime-engines"
    / "roach-pi"
    / "extensions"
    / "agentic-harness"
    / "discipline.ts"
)
DISCIPLINE_MAGNET = REPO / "02_RUNTIME" / "magnets" / "discipline_magnet.py"
PLUGIN = REPO / "02_RUNTIME" / "magnets" / "plugin.py"

PILLARS = (
    "Think before coding",
    "Simplicity first",
    "Surgical changes",
    "Goal-driven execution",
)

TS_MARKERS = (
    "Think Before Coding",
    "Simplicity First",
    "Surgical Changes",
    "Goal-Driven Execution",
    "KARPATHY_CANON_VERSION",
    "Read before you write",
)


def main() -> int:
    errors: list[str] = []

    sync_script = REPO / "scripts" / "sync_pi_karpathy_overlay.py"
    if sync_script.is_file():
        import subprocess

        subprocess.run([sys.executable, str(sync_script), "--quiet"], check=False)

    if not CANON.is_file():
        errors.append(f"Missing canonical doc: {CANON}")
    else:
        text = CANON.read_text(encoding="utf-8")
        for pillar in PILLARS:
            if pillar not in text:
                errors.append(f"KARPATHY_DISCIPLINE.md missing pillar: {pillar}")

    if not CURSOR_RULE.is_file():
        errors.append(f"Missing Cursor rule: {CURSOR_RULE}")
    else:
        rule = CURSOR_RULE.read_text(encoding="utf-8")
        if "KARPATHY_DISCIPLINE" not in rule:
            errors.append("karpathy-guidelines.mdc must reference KARPATHY_DISCIPLINE.md")

    if not DISCIPLINE_TS.is_file():
        errors.append(f"Missing Pi discipline.ts: {DISCIPLINE_TS}")
    else:
        ts = DISCIPLINE_TS.read_text(encoding="utf-8")
        for marker in TS_MARKERS:
            if marker not in ts:
                errors.append(f"discipline.ts missing marker: {marker}")

    if not DISCIPLINE_MAGNET.is_file():
        errors.append(f"Missing discipline_magnet.py: {DISCIPLINE_MAGNET}")
    else:
        magnet = DISCIPLINE_MAGNET.read_text(encoding="utf-8")
        for field in ("assumptions_stated", "verification_ran", "has_success_criteria"):
            if field not in magnet:
                errors.append(f"discipline_magnet.py missing signal: {field}")

    if PLUGIN.is_file():
        plug = PLUGIN.read_text(encoding="utf-8")
        if "DisciplineMagnet" not in plug:
            errors.append("plugin.py must register DisciplineMagnet")
    else:
        errors.append(f"Missing plugin registry: {PLUGIN}")

    if errors:
        print("KARPATHY DISCIPLINE VALIDATION FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Karpathy discipline OK (4-pillar canon + runtime wiring)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
