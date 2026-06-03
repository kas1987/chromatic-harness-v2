"""Tests for activity/lanes.py — lane normalization, prefixes, routing helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.lanes import (
    VALID_LANES,
    _DEFAULT_LANE,
    _PREFIX_RE,
    apply_lane_to_bead_fields,
    lane_description_line,
    lane_title_prefix,
    normalize_lane,
    parse_lane_from_title,
)


# ---------------------------------------------------------------------------
# normalize_lane
# ---------------------------------------------------------------------------

class TestNormalizeLane:
    @pytest.mark.parametrize("lane", ["agent", "human", "review"])
    def test_valid_lanes_pass_through(self, lane: str) -> None:
        assert normalize_lane(lane) == lane

    @pytest.mark.parametrize("lane", ["AGENT", "Human", "REVIEW"])
    def test_valid_lanes_case_insensitive(self, lane: str) -> None:
        assert normalize_lane(lane) == lane.lower()

    def test_none_returns_default(self) -> None:
        assert normalize_lane(None) == _DEFAULT_LANE

    def test_empty_string_returns_default(self) -> None:
        assert normalize_lane("") == _DEFAULT_LANE

    def test_unknown_lane_returns_default(self) -> None:
        assert normalize_lane("robot") == _DEFAULT_LANE

    def test_default_lane_is_agent(self) -> None:
        assert _DEFAULT_LANE == "agent"

    def test_valid_lanes_frozenset(self) -> None:
        assert VALID_LANES == frozenset({"agent", "human", "review"})


# ---------------------------------------------------------------------------
# lane_title_prefix
# ---------------------------------------------------------------------------

class TestLaneTitlePrefix:
    def test_agent_prefix(self) -> None:
        assert lane_title_prefix("agent") == "[agent]"

    def test_human_prefix(self) -> None:
        assert lane_title_prefix("human") == "[human]"

    def test_review_prefix(self) -> None:
        assert lane_title_prefix("review") == "[review]"

    def test_unknown_lane_gets_default_prefix(self) -> None:
        assert lane_title_prefix("bogus") == f"[{_DEFAULT_LANE}]"

    def test_uppercase_input_normalised(self) -> None:
        assert lane_title_prefix("HUMAN") == "[human]"


# ---------------------------------------------------------------------------
# lane_description_line
# ---------------------------------------------------------------------------

class TestLaneDescriptionLine:
    def test_agent_description_line(self) -> None:
        assert lane_description_line("agent") == "lane: agent"

    def test_human_description_line(self) -> None:
        assert lane_description_line("human") == "lane: human"

    def test_review_description_line(self) -> None:
        assert lane_description_line("review") == "lane: review"

    def test_invalid_lane_falls_back_to_default(self) -> None:
        assert lane_description_line("unknown") == f"lane: {_DEFAULT_LANE}"


# ---------------------------------------------------------------------------
# parse_lane_from_title
# ---------------------------------------------------------------------------

class TestParseLaneFromTitle:
    @pytest.mark.parametrize("lane", ["agent", "human", "review"])
    def test_parses_prefixed_title(self, lane: str) -> None:
        title = f"[{lane}] Fix something"
        assert parse_lane_from_title(title) == lane

    def test_case_insensitive_parsing(self) -> None:
        assert parse_lane_from_title("[HUMAN] My task") == "human"
        assert parse_lane_from_title("[Agent] Another task") == "agent"

    def test_returns_none_for_unprefixed_title(self) -> None:
        assert parse_lane_from_title("Fix something") is None

    def test_returns_none_for_empty_title(self) -> None:
        assert parse_lane_from_title("") is None

    def test_returns_none_for_wrong_bracket_content(self) -> None:
        assert parse_lane_from_title("[robot] do things") is None

    def test_prefix_with_extra_whitespace(self) -> None:
        # Leading whitespace in title is stripped before matching
        assert parse_lane_from_title("  [human] Some task") == "human"


# ---------------------------------------------------------------------------
# apply_lane_to_bead_fields
# ---------------------------------------------------------------------------

class TestApplyLaneToBeadFields:
    def test_adds_prefix_to_title(self) -> None:
        title, _ = apply_lane_to_bead_fields("Fix tests", lane="human")
        assert title.startswith("[human]")
        assert "Fix tests" in title

    def test_adds_lane_line_to_description(self) -> None:
        _, desc = apply_lane_to_bead_fields("Fix tests", "Some context", lane="human")
        assert desc.startswith("lane: human")

    def test_description_preserves_original_content(self) -> None:
        _, desc = apply_lane_to_bead_fields("Fix tests", "Some context", lane="agent")
        assert "Some context" in desc

    def test_empty_description_becomes_lane_line(self) -> None:
        _, desc = apply_lane_to_bead_fields("Fix tests", "", lane="agent")
        assert desc == "lane: agent"

    def test_does_not_double_prefix_already_prefixed_title(self) -> None:
        title, _ = apply_lane_to_bead_fields("[agent] Do work", lane="agent")
        # Should not produce "[agent] [agent] Do work"
        assert title.count("[agent]") == 1

    def test_replaces_existing_prefix_with_new_lane(self) -> None:
        # Title has [agent] prefix but we request human lane
        title, _ = apply_lane_to_bead_fields("[agent] Do work", lane="human")
        assert title.startswith("[human]")
        assert "[agent]" not in title

    def test_uses_context_lane_when_lane_not_provided(self) -> None:
        title, desc = apply_lane_to_bead_fields("Do work", context_lane="review")
        assert title.startswith("[review]")
        assert desc.startswith("lane: review")

    def test_explicit_lane_overrides_context_lane(self) -> None:
        title, _ = apply_lane_to_bead_fields("Do work", lane="human", context_lane="agent")
        assert title.startswith("[human]")

    def test_parses_lane_from_title_when_no_lane_args(self) -> None:
        title, desc = apply_lane_to_bead_fields("[review] Inspect changes")
        assert title.startswith("[review]")
        assert desc.startswith("lane: review")

    def test_unknown_lane_falls_back_to_default(self) -> None:
        title, desc = apply_lane_to_bead_fields("Do work", lane="robot")
        assert title.startswith(f"[{_DEFAULT_LANE}]")
        assert desc.startswith(f"lane: {_DEFAULT_LANE}")

    def test_replaces_existing_lane_line_in_description(self) -> None:
        _, desc = apply_lane_to_bead_fields(
            "Fix tests",
            "lane: agent\n\nOld description",
            lane="human",
        )
        lines = desc.splitlines()
        assert lines[0] == "lane: human"
        assert "Old description" in desc

    def test_prepends_lane_line_to_nonempty_description(self) -> None:
        _, desc = apply_lane_to_bead_fields("Fix tests", "Some detail", lane="agent")
        assert desc.startswith("lane: agent\n\nSome detail")

    def test_returns_tuple_of_two_strings(self) -> None:
        result = apply_lane_to_bead_fields("Title", "Desc", lane="agent")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(s, str) for s in result)

    # Lane isolation: events routed to lane A do not appear in lane B
    def test_human_lane_fields_do_not_contain_agent_markers(self) -> None:
        title, desc = apply_lane_to_bead_fields("Task", lane="human")
        assert "agent" not in title
        assert "agent" not in desc

    def test_agent_lane_fields_do_not_contain_human_markers(self) -> None:
        title, desc = apply_lane_to_bead_fields("Task", lane="agent")
        assert "human" not in title
        assert "human" not in desc

    def test_review_lane_fields_do_not_contain_other_lanes(self) -> None:
        title, desc = apply_lane_to_bead_fields("Task", lane="review")
        assert "human" not in title
        assert "agent" not in desc
        assert "human" not in desc
        assert "agent" not in title
