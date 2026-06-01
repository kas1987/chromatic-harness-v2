"""Validate transfer packet example matches required fields."""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED = {
    "transfer_id",
    "updated_at",
    "source_runtime",
    "objective",
    "decision",
    "summary",
    "successor",
    "budget",
    "boot_commands",
    "forbidden",
    "handoff_path",
    "latest_pointer",
}


def test_example_packet_has_required_fields():
    path = Path(__file__).resolve().parents[1] / "docs" / "handoffs" / "transfer_packet.example.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED - set(data.keys())
    assert not missing, f"missing keys: {missing}"
    assert "decision" in data["budget"]
    assert data["budget"]["decision"] in ("spawn", "handoff_only", "halt_human")
    assert "runtime" in data["successor"]
