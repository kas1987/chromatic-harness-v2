"""Tests for workflows.go_modes — boost coverage from 36% to 100%."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from workflows.go_modes import mode_allows_mutation, mode_requires_swarm_approval, parse_go_mode
from workflows.models import GoMode


class TestParseGoMode:
    def test_plain_go(self):
        assert parse_go_mode("GO") == GoMode.GO

    def test_plain_go_lowercase(self):
        assert parse_go_mode("go") == GoMode.GO

    def test_plain_go_with_whitespace(self):
        assert parse_go_mode("  go  ") == GoMode.GO

    def test_go_deep(self):
        assert parse_go_mode("GO DEEP") == GoMode.GO_DEEP

    def test_go_build(self):
        assert parse_go_mode("GO BUILD") == GoMode.GO_BUILD

    def test_go_audit(self):
        assert parse_go_mode("GO AUDIT") == GoMode.GO_AUDIT

    def test_go_verify(self):
        assert parse_go_mode("GO VERIFY") == GoMode.GO_VERIFY

    def test_go_swarm(self):
        assert parse_go_mode("GO SWARM") == GoMode.GO_SWARM

    def test_go_ship(self):
        assert parse_go_mode("GO SHIP") == GoMode.GO_SHIP

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="unknown GO mode"):
            parse_go_mode("GO FAST")

    def test_extra_spaces_normalized(self):
        assert parse_go_mode("go  deep") == GoMode.GO_DEEP


class TestModeAllowsMutation:
    def test_go_allows(self):
        assert mode_allows_mutation(GoMode.GO) is True

    def test_go_build_allows(self):
        assert mode_allows_mutation(GoMode.GO_BUILD) is True

    def test_go_ship_allows(self):
        assert mode_allows_mutation(GoMode.GO_SHIP) is True

    def test_go_audit_does_not_allow(self):
        assert mode_allows_mutation(GoMode.GO_AUDIT) is False

    def test_go_verify_does_not_allow(self):
        assert mode_allows_mutation(GoMode.GO_VERIFY) is False

    def test_go_swarm_does_not_allow(self):
        assert mode_allows_mutation(GoMode.GO_SWARM) is False

    def test_go_deep_does_not_allow(self):
        assert mode_allows_mutation(GoMode.GO_DEEP) is False


class TestModeRequiresSwarmApproval:
    def test_go_swarm_requires(self):
        assert mode_requires_swarm_approval(GoMode.GO_SWARM) is True

    def test_go_does_not_require(self):
        assert mode_requires_swarm_approval(GoMode.GO) is False

    def test_go_build_does_not_require(self):
        assert mode_requires_swarm_approval(GoMode.GO_BUILD) is False

    def test_go_ship_does_not_require(self):
        assert mode_requires_swarm_approval(GoMode.GO_SHIP) is False

    def test_go_deep_does_not_require(self):
        assert mode_requires_swarm_approval(GoMode.GO_DEEP) is False
