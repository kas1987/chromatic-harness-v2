"""Network-free unit tests for scripts/epic_review.py.

Covers:
- ship-when-all-closed
- no-ship-when-any-open
- eval-item parsing
- artifact shape
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


def _load(mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, REPO / "scripts" / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


er = _load("epic_review")

# ---------------------------------------------------------------------------
# parse_eval_items
# ---------------------------------------------------------------------------

SAMPLE_DESC = """\
Fix the thing.

## Scope
- Something.

## Eval requirements (definition of done)
- [ ] Gate A passes
- [x] Gate B passes
- [ ] Gate C passes

## Routing
C-level hint: C2 | owner: unassigned
"""


def test_parse_eval_items_counts():
    items = er.parse_eval_items(SAMPLE_DESC)
    assert len(items) == 3


def test_parse_eval_items_checked():
    items = er.parse_eval_items(SAMPLE_DESC)
    checked = [i for i in items if i["checked"]]
    assert len(checked) == 1
    assert checked[0]["text"] == "Gate B passes"


def test_parse_eval_items_empty_section():
    desc = "## Eval requirements (definition of done)\n\n## Routing\n"
    items = er.parse_eval_items(desc)
    assert items == []


def test_parse_eval_items_no_section():
    items = er.parse_eval_items("No eval section here.")
    assert items == []


# ---------------------------------------------------------------------------
# resolve_epic
# ---------------------------------------------------------------------------

FAKE_LEDGER = {
    "epic-ci-and-quality-hardening": "chromatic-harness-v2-nzn0",
    "epic-governance-and-review-layer": "chromatic-harness-v2-skqu",
    "gh-57": "chromatic-harness-v2-j12l",
    "gh-58": "chromatic-harness-v2-a8fu",
    "gh-60": "chromatic-harness-v2-0f37",
}


def test_resolve_epic_by_suffix():
    result = er.resolve_epic("nzn0", FAKE_LEDGER)
    assert result is not None
    epic_id, title, nums = result
    assert epic_id == "chromatic-harness-v2-nzn0"
    assert "CI" in title
    assert set(nums) == {57, 58, 60}


def test_resolve_epic_by_title_fragment():
    result = er.resolve_epic("Quality", FAKE_LEDGER)
    assert result is not None
    epic_id, title, _ = result
    assert epic_id == "chromatic-harness-v2-nzn0"


def test_resolve_epic_unknown():
    result = er.resolve_epic("does-not-exist", FAKE_LEDGER)
    assert result is None


# ---------------------------------------------------------------------------
# build_review — ship when all closed
# ---------------------------------------------------------------------------


def _make_bd_show(records: dict[str, dict]):
    """Factory for a fake bd_show that returns records by bead_id."""

    def fake_bd_show(bead_id: str) -> dict | None:
        return records.get(bead_id)

    return fake_bd_show


ALL_CLOSED_RECORDS = {
    "chromatic-harness-v2-j12l": {
        "id": "chromatic-harness-v2-j12l",
        "title": "Security gates",
        "status": "closed",
        "description": SAMPLE_DESC,
    },
    "chromatic-harness-v2-a8fu": {
        "id": "chromatic-harness-v2-a8fu",
        "title": "Coverage gates",
        "status": "closed",
        "description": "## Eval requirements (definition of done)\n- [x] Coverage 80%\n",
    },
    "chromatic-harness-v2-0f37": {
        "id": "chromatic-harness-v2-0f37",
        "title": "Lint gates",
        "status": "closed",
        "description": "## Eval requirements (definition of done)\n- [x] Lint passes\n",
    },
}

ONE_OPEN_RECORDS = {
    **ALL_CLOSED_RECORDS,
    "chromatic-harness-v2-j12l": {
        "id": "chromatic-harness-v2-j12l",
        "title": "Security gates",
        "status": "open",
        "description": SAMPLE_DESC,
    },
}


def test_ship_when_all_closed():
    with patch.object(er, "bd_show", side_effect=_make_bd_show(ALL_CLOSED_RECORDS)):
        review = er.build_review(
            "chromatic-harness-v2-nzn0",
            "CI & Quality Hardening",
            [57, 58, 60],
            FAKE_LEDGER,
        )
    assert review["ship"] is True
    assert review["decision"] == "SHIP"
    assert review["blockers"] == []


def test_no_ship_when_any_open():
    with patch.object(er, "bd_show", side_effect=_make_bd_show(ONE_OPEN_RECORDS)):
        review = er.build_review(
            "chromatic-harness-v2-nzn0",
            "CI & Quality Hardening",
            [57, 58, 60],
            FAKE_LEDGER,
        )
    assert review["ship"] is False
    assert review["decision"] == "NO-SHIP"
    blocker_refs = [b["ext_ref"] for b in review["blockers"]]
    assert "gh-57" in blocker_refs


def test_no_ship_includes_unseeded():
    ledger_missing = {k: v for k, v in FAKE_LEDGER.items() if k != "gh-57"}
    with patch.object(er, "bd_show", side_effect=_make_bd_show(ALL_CLOSED_RECORDS)):
        review = er.build_review(
            "chromatic-harness-v2-nzn0",
            "CI & Quality Hardening",
            [57, 58, 60],
            ledger_missing,
        )
    assert review["ship"] is False
    blocker_refs = [b["ext_ref"] for b in review["blockers"]]
    assert "gh-57" in blocker_refs


# ---------------------------------------------------------------------------
# Artifact shape
# ---------------------------------------------------------------------------


def test_artifact_shape():
    with patch.object(er, "bd_show", side_effect=_make_bd_show(ALL_CLOSED_RECORDS)):
        review = er.build_review(
            "chromatic-harness-v2-nzn0",
            "CI & Quality Hardening",
            [57, 58, 60],
            FAKE_LEDGER,
        )
    required_keys = {"epic_id", "epic_title", "timestamp", "children", "ship", "decision", "blockers", "eval_summary"}
    assert required_keys.issubset(review.keys())
    assert review["child_count"] == 3
    es = review["eval_summary"]
    assert "total_items" in es and "checked_items" in es and "percent" in es


def test_artifact_write(tmp_path: Path):
    with patch.object(er, "REVIEW_DIR", tmp_path):
        with patch.object(er, "bd_show", side_effect=_make_bd_show(ALL_CLOSED_RECORDS)):
            review = er.build_review(
                "chromatic-harness-v2-nzn0",
                "CI & Quality Hardening",
                [57, 58, 60],
                FAKE_LEDGER,
            )
        named, latest = er.write_artifacts(review)
    assert named.exists()
    assert latest.exists()
    data = json.loads(named.read_text())
    assert data["epic_id"] == "chromatic-harness-v2-nzn0"
    assert data["decision"] == "SHIP"


# ---------------------------------------------------------------------------
# Note text is ASCII-only
# ---------------------------------------------------------------------------


def test_note_text_is_ascii():
    with patch.object(er, "bd_show", side_effect=_make_bd_show(ALL_CLOSED_RECORDS)):
        review = er.build_review(
            "chromatic-harness-v2-nzn0",
            "CI & Quality Hardening",
            [57, 58, 60],
            FAKE_LEDGER,
        )
    note = er.build_note_text(review)
    note.encode("ascii")  # raises UnicodeEncodeError on regression


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
