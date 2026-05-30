"""Regression tests for governance intelligence normalization fallbacks."""

from scripts.llm_governance_intelligence import _normalize


def test_normalize_falls_back_model_from_provider_when_blank() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-1",
        "provider": "gemini",
        "model": "",
        "result_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.provider == "gemini"
    assert event.model == "gemini:default"


def test_normalize_preserves_existing_model() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-2",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "result_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.provider == "gemini"
    assert event.model == "gemini-2.5-pro"
