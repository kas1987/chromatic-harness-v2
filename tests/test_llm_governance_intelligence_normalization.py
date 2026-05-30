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


def test_normalize_reads_execution_status_direct_field() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-3",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.execution_status == "execute"


def test_normalize_prefers_execution_status_over_result_status() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-4",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "execution_status": "execute",
        "result_status": "error",
    }

    event = _normalize("workflow", row)
    assert event.execution_status == "execute"


def test_normalize_reads_scalar_confidence_field() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-5",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "confidence": 88,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.confidence_score == 88.0


def test_normalize_reads_cost_estimate_usd_alias() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-6",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "cost_estimate_usd": 0.042,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.cost_usd == 0.042
