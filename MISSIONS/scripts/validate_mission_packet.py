#!/usr/bin/env python3
"""Thin shim → the single canonical mission-packet validator.

The real logic lives in `scripts/validate_mission_packet.py` at the repo root
(one validator, one schema at 01_PROTOCOLS/CMP/mission_packet.schema.json). This
shim exists only so `python MISSIONS/scripts/validate_mission_packet.py <pkt>`
keeps working for authors browsing the MISSIONS/ suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

from validate_mission_packet import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
