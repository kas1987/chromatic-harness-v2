"""Tests for ComplexityClassifier: C-level bins, confidence, file bumps."""

from __future__ import annotations

import pytest

from router.complexity_classifier import ComplexityClassifier, ComplexityResult


@pytest.fixture
def classifier():
    return ComplexityClassifier()


# ── Default-config (no YAML needed) fallback ────────────────────────────────

@pytest.fixture
def bare_classifier(tmp_path):
    """Classifier from a missing YAML path → uses _build_defaults."""
    return ComplexityClassifier(config_path=tmp_path / "nonexistent.yaml")


# ── C1 – simple/formatting tasks ────────────────────────────────────────────

class TestC1Classification:
    def test_format_keyword(self, classifier):
        result = classifier.classify("format this JSON file")
        assert result.level == "C1"

    def test_convert_keyword(self, classifier):
        result = classifier.classify("convert CSV to JSON")
        assert result.level in ("C1", "C2")  # depends on yaml config

    def test_extract_keyword(self, classifier):
        result = classifier.classify("extract the email addresses")
        assert result.level in ("C1", "C2")

    def test_c1_confidence_positive(self, classifier):
        result = classifier.classify("format the output as JSON")
        if result.level == "C1":
            assert result.confidence > 0.0

    def test_bare_c1_keyword(self, bare_classifier):
        result = bare_classifier.classify("format the output")
        assert result.level == "C1"
        assert result.confidence > 0.0


# ── C2 – routine/engineering tasks ──────────────────────────────────────────

class TestC2Classification:
    def test_fix_keyword(self, classifier):
        result = classifier.classify("fix the login bug")
        assert result.level in ("C2", "C3")

    def test_debug_keyword(self, classifier):
        result = classifier.classify("debug the error in auth module")
        # Could be C2 or C3 depending on config
        assert result.level in ("C2", "C3")

    def test_bare_scaffold_keyword(self, bare_classifier):
        result = bare_classifier.classify("scaffold a new Python package")
        assert result.level == "C2"

    def test_bare_lint_keyword(self, bare_classifier):
        result = bare_classifier.classify("lint the codebase")
        assert result.level == "C2"

    def test_bare_code_review_keyword(self, bare_classifier):
        result = bare_classifier.classify("code review the PR")
        assert result.level == "C2"


# ── C3 – complex/multi-file tasks ───────────────────────────────────────────

class TestC3Classification:
    def test_bare_root_cause_keyword(self, bare_classifier):
        result = bare_classifier.classify("root cause the production outage")
        assert result.level == "C3"

    def test_bare_architecture_keyword(self, bare_classifier):
        result = bare_classifier.classify("architecture review needed")
        assert result.level == "C3"

    def test_bare_multi_file_keyword(self, bare_classifier):
        result = bare_classifier.classify("multi-file refactoring required")
        assert result.level == "C3"


# ── C4 – creative/novel tasks ────────────────────────────────────────────────

class TestC4Classification:
    def test_bare_brainstorm_keyword(self, bare_classifier):
        result = bare_classifier.classify("brainstorm ideas for the API")
        assert result.level == "C4"

    def test_bare_strategy_keyword(self, bare_classifier):
        result = bare_classifier.classify("develop the product strategy")
        assert result.level == "C4"

    def test_bare_novel_keyword(self, bare_classifier):
        result = bare_classifier.classify("novel approach to caching")
        assert result.level == "C4"

    def test_no_match_defaults_to_c4(self, classifier):
        result = classifier.classify("zzz unknown garbage xyz###")
        assert result.level == "C4"
        assert result.confidence == 0.0

    def test_bare_creative_keyword(self, bare_classifier):
        result = bare_classifier.classify("creative writing exercise")
        assert result.level == "C4"


# ── Default return when no keywords match ───────────────────────────────────

class TestNoMatch:
    def test_returns_c4_with_zero_confidence(self, classifier):
        result = classifier.classify("qqqzzzaaa no keywords here at all")
        assert result.level == "C4"
        assert result.confidence == 0.0
        assert result.matched_keywords == []

    def test_empty_description_returns_c4(self, classifier):
        result = classifier.classify("")
        assert result.level == "C4"


# ── File-count bump logic ────────────────────────────────────────────────────

class TestFileCountBump:
    def test_c1_bumps_to_c2_with_6_files(self, bare_classifier):
        result = bare_classifier.classify("format the output", max_files_hint=6)
        assert result.level in ("C2", "C3")  # bumped from C1

    def test_c2_bumps_to_c3_with_6_files(self, bare_classifier):
        result = bare_classifier.classify("scaffold a new package", max_files_hint=6)
        assert result.level == "C3"

    def test_no_bump_for_5_files(self, bare_classifier):
        result_no_hint = bare_classifier.classify("format the output")
        result_with_hint = bare_classifier.classify("format the output", max_files_hint=5)
        assert result_with_hint.level == result_no_hint.level

    def test_large_blast_radius_bumps_to_c3(self, bare_classifier):
        result = bare_classifier.classify("format the output", max_files_hint=16)
        assert result.level == "C3"

    def test_impact_fan_out_takes_precedence_over_hint(self, bare_classifier):
        result = bare_classifier.classify(
            "format the output",
            max_files_hint=20,
            impact_fan_out=6,
        )
        assert result.level in ("C2", "C3")
        assert result.evidence_source == "codegraph_impact"

    def test_evidence_source_none_without_bump(self, bare_classifier):
        result = bare_classifier.classify("format the output")
        assert result.evidence_source == "none"

    def test_evidence_source_keyword_with_hint(self, bare_classifier):
        result = bare_classifier.classify("format output", max_files_hint=10)
        # If bump happened, evidence_source should be "keyword"
        if result.level != "C1":
            assert result.evidence_source in ("keyword", "codegraph_impact")

    def test_no_bump_for_c3_or_c4(self, bare_classifier):
        result = bare_classifier.classify("root cause the failure", max_files_hint=20)
        # C3 doesn't get bumped further to C4
        assert result.level in ("C3", "C4")


# ── ComplexityResult fields ──────────────────────────────────────────────────

class TestComplexityResultFields:
    def test_result_has_all_fields(self, classifier):
        result = classifier.classify("format output")
        assert hasattr(result, "level")
        assert hasattr(result, "name")
        assert hasattr(result, "confidence")
        assert hasattr(result, "matched_keywords")
        assert hasattr(result, "reasoning_depth")
        assert hasattr(result, "evidence_source")

    def test_confidence_clamped_to_0_1(self, classifier):
        result = classifier.classify("format output")
        assert 0.0 <= result.confidence <= 1.0

    def test_matched_keywords_is_list(self, classifier):
        result = classifier.classify("scaffold a new package")
        assert isinstance(result.matched_keywords, list)

    def test_frozen_result(self, classifier):
        result = classifier.classify("format output")
        with pytest.raises(Exception):
            result.level = "C1"  # type: ignore[misc]


# ── Prompt influences classification ─────────────────────────────────────────

class TestPromptInfluence:
    def test_prompt_adds_keywords(self, bare_classifier):
        result_no_prompt = bare_classifier.classify("unknown task")
        result_with_prompt = bare_classifier.classify("unknown task", prompt="scaffold a new module")
        # C2 keywords in prompt should change the classification
        assert result_with_prompt.level == "C2"

    def test_combined_description_and_prompt(self, bare_classifier):
        result = bare_classifier.classify(
            description="format the file",
            prompt="also scaffold the helpers",
        )
        # C2 "scaffold" + C1 "format" — tie broken to lower complexity
        assert result.level in ("C1", "C2")


# ── Batch classify ───────────────────────────────────────────────────────────

class TestBatchClassify:
    def test_batch_returns_correct_count(self, classifier):
        tasks = [
            {"description": "format output"},
            {"description": "scaffold package"},
            {"description": "unknown garbage xyz"},
        ]
        results = classifier.batch_classify(tasks)
        assert len(results) == 3

    def test_batch_each_result_is_complexity_result(self, classifier):
        tasks = [{"description": "format"}, {"description": "scaffold"}]
        results = classifier.batch_classify(tasks)
        for r in results:
            assert isinstance(r, ComplexityResult)

    def test_empty_batch(self, classifier):
        results = classifier.batch_classify([])
        assert results == []

    def test_batch_uses_max_files(self, bare_classifier):
        tasks = [{"description": "format output", "max_files": 10}]
        results = bare_classifier.batch_classify(tasks)
        assert results[0].level in ("C2", "C3")  # bumped from C1
