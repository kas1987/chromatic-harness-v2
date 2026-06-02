"""Tests for bead_enrich.py — gate-readiness report + enricher.

Network-free: bd is never invoked. Items are injected; scoring reuses go_mode
(offline). Verifies that the description/acceptance_criteria field-mapping fix
makes real beads score accurately, that enriched beads clear the dispatch gate,
and that the bd-update argv is built correctly (no fabrication).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location("bead_enrich", REPO / "scripts" / "bead_enrich.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["bead_enrich"] = mod
    spec.loader.exec_module(mod)
    return mod


BE = _load()


# A bead as bd ready --json actually emits it: title + description, no criteria.
SPARSE = {
    "id": "x.1",
    "title": "Define RoutingContext",
    "description": "Define RoutingContext dataclass in router/contracts.py; refactor over it.",
    "issue_type": "task",
}

# Same bead enriched with real acceptance criteria (>=3, includes a test criterion).
ENRICHED = {
    **SPARSE,
    "acceptance_criteria": "RoutingContext dataclass defined; functions refactored pure; "
    "unit tests validate behaviour and pytest green",
}

ENRICHED_WITH_SCOPE = {
    **ENRICHED,
    "labels": ["scope:02_RUNTIME/router/contracts.py"],
}


def test_sparse_bead_is_not_gate_ready():
    a = BE.gate_assessment(SPARSE)
    assert a["score"] == 54.0  # description counts (objective 80) but no criteria
    assert a["dispatch_allowed"] is False
    assert "evidence_quality" in a["weak_factors"]
    assert any("acceptance criteria" in s for s in a["suggestions"])


def test_description_is_read_after_fieldmap_fix():
    # Without the field-map fix this bead would collapse to the all-neutral 50.
    a = BE.gate_assessment(SPARSE)
    assert a["score"] > 50.0


def test_enriched_bead_clears_the_gate():
    a = BE.gate_assessment(ENRICHED)
    assert a["score"] >= 75.0
    assert a["dispatch_allowed"] is True
    assert a["band"] in ("execute", "execute_logged")


def test_scope_label_adds_margin():
    base = BE.gate_assessment(ENRICHED)["score"]
    scoped = BE.gate_assessment(ENRICHED_WITH_SCOPE)["score"]
    assert scoped > base
    assert BE.gate_assessment(ENRICHED_WITH_SCOPE)["dispatch_allowed"] is True


def test_report_counts_and_excludes_epics():
    items = [
        SPARSE,
        ENRICHED,
        {"id": "epic1", "title": "epic", "issue_type": "epic", "description": "x"},
    ]
    r = BE.report(items)
    assert r["total"] == 2  # epic excluded
    assert r["gate_ready"] == 1
    assert r["needs_work"] == 1
    assert r["ready_ids"] == ["x.1"]


def test_build_update_args_is_correct_and_supplies_no_content():
    args = BE.build_update_args("b1", "c1; c2; test c3", ["a.py", "b.py"], "low")
    assert args == [
        "update",
        "b1",
        "--acceptance",
        "c1; c2; test c3",
        "--add-label",
        "scope:a.py",
        "--add-label",
        "scope:b.py",
        "--add-label",
        "risk:low",
    ]


def test_build_update_args_minimal():
    assert BE.build_update_args("b1", "", [], "") == ["update", "b1"]
