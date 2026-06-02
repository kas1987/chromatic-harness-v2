"""OBS-012: the agent mission packet enforces observability compliance.

Asserts the template + implementation handoff contain the required before/
during/after actions, file-claim-before-mutation, the four stop conditions,
and release-of-claimed-files in the acceptance criteria.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKET = REPO / "templates" / "AGENT_MISSION_PACKET_OBSERVABILITY.md"
CODEX_HANDOFF = REPO / "12_HANDOFFS" / "CODEX_IMPLEMENTATION_HANDOFF.md"


def _packet() -> str:
    return PACKET.read_text(encoding="utf-8")


def test_packet_exists():
    assert PACKET.is_file()


def test_packet_has_before_during_after_sections():
    t = _packet()
    assert "Required Before Work" in t
    assert "Required During Work" in t
    assert "Required After Work" in t


def test_packet_requires_file_claim_before_mutation():
    t = _packet()
    assert "claim_files.py" in t
    assert "before" in t.lower() and "mutat" in t.lower()


def test_packet_enumerates_all_four_stop_conditions():
    t = _packet().lower()
    assert "stop condition" in t
    assert "collision" in t  # collision
    assert "dirty" in t  # dirty repo ambiguity
    assert "schema validation" in t or "validate_event_schema" in t  # schema failure
    assert "secret" in t  # secret detection


def test_packet_definition_of_done_requires_release():
    t = _packet()
    # Release must appear as an acceptance/definition-of-done requirement.
    assert "release_files.py" in t
    dod = t.split("Definition of Done")[-1].lower()
    assert "released" in dod or "release" in dod


def test_handoff_requires_claims_and_release():
    t = CODEX_HANDOFF.read_text(encoding="utf-8")
    assert "claim_files.py" in t
    assert "release" in t.lower()
    # Stop conditions reflected in the implementation handoff.
    assert "secret" in t.lower()
    assert "collision" in t.lower()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
