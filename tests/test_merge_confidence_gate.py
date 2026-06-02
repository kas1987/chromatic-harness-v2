"""Unit tests for the merge confidence gate's pure core (Option B, Phase 1).

Targets decide_band() + compute_verdict() — both pure functions over a signals
dict, so these run network-free and deterministically (and gate the pre-push
suite via run-all-e2e.py).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Load scripts/merge_confidence_gate.py by path (scripts/ is not a package).
_spec = importlib.util.spec_from_file_location(
    "merge_confidence_gate", REPO / "scripts" / "merge_confidence_gate.py"
)
mcg = importlib.util.module_from_spec(_spec)
sys.modules["merge_confidence_gate"] = mcg
_spec.loader.exec_module(mcg)


# --- decide_band: thresholds mirror DecisionMagnet.decide_band ---------------
@pytest.mark.parametrize(
    "score,band",
    [
        (100, "proceed"),
        (90, "proceed"),
        (89, "reversible"),
        (70, "reversible"),
        (69, "self_heal"),
        (50, "self_heal"),
        (49, "escalate"),
        (0, "escalate"),
    ],
)
def test_decide_band_boundaries(score, band):
    assert mcg.decide_band(score) == band


# --- compute_verdict: clean change -------------------------------------------
def test_clean_change_is_auto():
    v = mcg.compute_verdict({})
    assert v["score"] == 100
    assert v["band"] == "proceed"
    assert v["verdict"] == "auto"
    assert v["hard_block"] is False


def test_empty_signals_have_a_reason():
    v = mcg.compute_verdict({})
    assert v["reasons"]  # never empty — explains the verdict


# --- hard blocks force "block" regardless of score ---------------------------
def test_p3_secret_in_diff_is_hard_block():
    v = mcg.compute_verdict({"privacy": {"p3_hits": ["sk-abc...redacted"]}})
    assert v["hard_block"] is True
    assert v["verdict"] == "block"


def test_pr_governance_failure_is_hard_block():
    v = mcg.compute_verdict({"pr_governance": {"passed": False}})
    assert v["hard_block"] is True
    assert v["verdict"] == "block"


def test_hard_block_wins_even_with_perfect_score():
    # No score penalties, but a P3 hit must still block.
    v = mcg.compute_verdict({"privacy": {"p3_hits": ["ghp_xxx"]}})
    assert v["score"] == 100
    assert v["band"] == "proceed"
    assert v["verdict"] == "block"


# --- P4 content downgrades to human_ack, never auto --------------------------
def test_p4_content_requires_human_ack():
    v = mcg.compute_verdict({"privacy": {"p4_hits": ["HIPAA compliance note"]}})
    assert v["human_ack"] is True
    assert v["verdict"] == "human_ack"
    assert v["hard_block"] is False


# --- score-driven bands map to verdicts --------------------------------------
def test_warn_size_plus_risk_lands_in_human_ack_band():
    # pr-size warn (-15) + ai risk 30 (-15) = 70 → reversible → human_ack
    v = mcg.compute_verdict(
        {"pr_size": {"risk_level": "warn"}, "ai_review": {"risk_score": 30, "level": "warn"}}
    )
    assert v["score"] == 70
    assert v["band"] == "reversible"
    assert v["verdict"] == "human_ack"


def test_failed_size_gate_blocks():
    # pr-size fail (-40) + protected (-20) = 40 → escalate → block
    v = mcg.compute_verdict(
        {"pr_size": {"risk_level": "fail", "protected_paths": ["settings.json"]}}
    )
    assert v["score"] == 40
    assert v["verdict"] == "block"


def test_protected_path_alone_stays_auto_band_but_caps_at_80():
    # protected (-20) → 80 → reversible → human_ack
    v = mcg.compute_verdict({"pr_size": {"risk_level": "ok", "protected_paths": ["git_hooks/pre-push"]}})
    assert v["score"] == 80
    assert v["verdict"] == "human_ack"


def test_ai_high_risk_drags_score_down():
    # ai risk 100 (-50) + level fail (-10) = 40 → escalate → block
    v = mcg.compute_verdict({"ai_review": {"risk_score": 100, "level": "fail"}})
    assert v["score"] == 40
    assert v["verdict"] == "block"


# --- gh-derived signals ------------------------------------------------------
def test_unresolved_reviews_penalty_caps_at_30():
    v = mcg.compute_verdict({"unresolved_reviews": 9})  # 9*10 capped to 30
    assert v["score"] == 70
    assert v["verdict"] == "human_ack"


def test_conflicting_peers_penalty():
    v = mcg.compute_verdict({"conflicting_peers": 1})  # -15 → 85 → reversible
    assert v["score"] == 85
    assert v["verdict"] == "human_ack"


# --- fail-open: malformed/partial signals never raise ------------------------
def test_none_and_missing_signal_values_are_ignored():
    v = mcg.compute_verdict(
        {"ai_review": {"risk_score": None}, "pr_size": None, "privacy": None, "pr_governance": None}
    )
    assert v["verdict"] == "auto"
    assert v["score"] == 100


def test_score_never_below_zero():
    v = mcg.compute_verdict(
        {
            "ai_review": {"risk_score": 100, "level": "fail"},
            "pr_size": {"risk_level": "fail", "protected_paths": ["a", "b"]},
            "unresolved_reviews": 5,
            "conflicting_peers": 3,
        }
    )
    assert v["score"] == 0
    assert v["verdict"] == "block"
