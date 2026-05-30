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


def test_normalize_reads_dict_confidence_score_key() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-7",
        "provider": "claude",
        "model": "claude-sonnet-4",
        "confidence": {"score": 72, "reasoning": "high task familiarity"},
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.confidence_score == 72.0


def test_normalize_reads_dict_confidence_confidence_score_key() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-8",
        "provider": "claude",
        "model": "claude-sonnet-4",
        "confidence": {"confidence_score": 55},
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.confidence_score == 55.0


def test_normalize_reads_latency_ms_alias_duration() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-9",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "duration_ms": 1234,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.latency_ms == 1234.0


def test_normalize_reads_latency_ms_alias_elapsed() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-10",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "elapsed_ms": 567,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.latency_ms == 567.0


def test_normalize_reads_cost_usd_direct() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-11",
        "provider": "claude",
        "model": "claude-sonnet-4",
        "cost_usd": 0.003,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.cost_usd == 0.003


def test_normalize_reads_actual_cost_alias() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-12",
        "provider": "claude",
        "model": "claude-sonnet-4",
        "actual_cost": 0.007,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.cost_usd == 0.007


def test_normalize_confidence_score_field_takes_precedence_over_confidence() -> None:
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-13",
        "provider": "claude",
        "model": "claude-sonnet-4",
        "confidence_score": 90,
        "confidence": 50,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.confidence_score == 90.0


def test_normalize_dict_confidence_unknown_keys_yields_none() -> None:
    """Dict confidence with no recognized key should produce no score."""
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-14",
        "provider": "claude",
        "model": "claude-sonnet-4",
        "confidence": {"level": "high", "rationale": "lots of evidence"},
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.confidence_score is None


def test_normalize_string_confidence_coerced_to_float() -> None:
    """confidence as a string '0.85' should coerce to 0.85."""
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-15",
        "provider": "openai",
        "model": "gpt-4o",
        "confidence": "0.85",
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.confidence_score == 0.85


def test_normalize_zero_confidence_not_dropped() -> None:
    """confidence_score of 0 is a valid payload value and must not be discarded."""
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-16",
        "provider": "openai",
        "model": "gpt-4o",
        "confidence_score": 0,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.confidence_score == 0.0


def test_normalize_selected_provider_alias() -> None:
    """selected_provider (routing log schema) maps to provider."""
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-17",
        "selected_provider": "ollama",
        "selected_model": "llama3",
        "execution_status": "execute",
    }

    event = _normalize("routing", row)
    assert event.provider == "ollama"
    assert event.model == "llama3"


def test_normalize_estimated_cost_alias() -> None:
    """estimated_cost maps to cost_usd when no higher-priority key present."""
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "task_id": "t-18",
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "estimated_cost": 0.012,
        "execution_status": "execute",
    }

    event = _normalize("workflow", row)
    assert event.cost_usd == 0.012


def test_normalize_bead_id_as_task_id_alias() -> None:
    """bead_id maps to task_id when no task_id key is present."""
    row = {
        "timestamp": "2026-05-30T00:00:00Z",
        "bead_id": "chromatic-harness-v2-abc1",
        "provider": "claude",
        "model": "claude-sonnet-4",
        "execution_status": "execute",
    }

    event = _normalize("bead_hook", row)
    assert event.task_id == "chromatic-harness-v2-abc1"


def test_normalize_empty_row_all_none() -> None:
    """An empty payload should produce a NormalizedEvent with all None fields."""
    event = _normalize("manual", {})
    assert event.provider is None
    assert event.model is None
    assert event.confidence_score is None
    assert event.cost_usd is None
    assert event.latency_ms is None
    assert event.task_id is None
    assert event.execution_status is None
