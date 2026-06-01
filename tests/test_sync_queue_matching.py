"""Regression tests for sync_queue_to_github._find_matching_issue (bead rnbm).

The matcher must use delimited matching so a prefix bead id (e.g. 'trsk.1')
does not match a longer id ('trsk.10') — otherwise --close-done could close
the wrong GitHub issue. Network-free: pure function only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("sync_queue_to_github", REPO / "scripts" / "sync_queue_to_github.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _issue(num, body="", title=""):
    return {"number": num, "body": body, "title": title}


def test_body_marker_exact_match():
    mod = _load()
    issues = [_issue(1, body="Mirrored.\n\nbead:trsk.1\n\nClose when done.")]
    assert mod._find_matching_issue(issues, "trsk.1")["number"] == 1


def test_prefix_id_does_not_match_longer_body_marker():
    mod = _load()
    # Only trsk.10 exists; searching for trsk.1 must NOT match it.
    issues = [_issue(10, body="bead:trsk.10")]
    assert mod._find_matching_issue(issues, "trsk.1") is None
    # And the exact id still matches.
    assert mod._find_matching_issue(issues, "trsk.10")["number"] == 10


def test_prefix_id_does_not_match_longer_title():
    mod = _load()
    issues = [_issue(11, title="[OBS-011] trsk.11 something")]
    assert mod._find_matching_issue(issues, "trsk.1") is None
    assert mod._find_matching_issue(issues, "trsk.11")["number"] == 11


def test_correct_issue_chosen_among_prefix_siblings():
    mod = _load()
    issues = [
        _issue(1, body="bead:trsk.1"),
        _issue(10, body="bead:trsk.10"),
        _issue(11, body="bead:trsk.11"),
        _issue(12, body="bead:trsk.12"),
    ]
    for bid, expected in [("trsk.1", 1), ("trsk.10", 10), ("trsk.11", 11), ("trsk.12", 12)]:
        assert mod._find_matching_issue(issues, bid)["number"] == expected


def test_no_match_returns_none():
    mod = _load()
    assert mod._find_matching_issue([_issue(1, body="bead:other")], "trsk.1") is None


def test_body_marker_not_matched_mid_line():
    mod = _load()
    # A mention inside prose (not its own line) should not count as the marker.
    issues = [_issue(1, body="see bead:trsk.1 elsewhere", title="")]
    assert mod._find_matching_issue(issues, "trsk.1") is None


def test_title_segment_boundary_allows_exact_with_trailing_space():
    mod = _load()
    issues = [_issue(5, title="trsk.5: do the thing")]
    assert mod._find_matching_issue(issues, "trsk.5")["number"] == 5


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
