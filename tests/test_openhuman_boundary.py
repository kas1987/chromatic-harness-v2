"""Tests enforcing OpenHuman Phase-1 read-only boundary."""

import pytest
import importlib

import router.contracts as contracts_mod
import router.adapters.openhuman_adapter as oh_mod

importlib.reload(contracts_mod)
importlib.reload(oh_mod)

from router.contracts import (  # noqa: E402
    RouteRequest,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteInput,
    TaskType,
    PrivacyClass,
    OutputType,
)
from router.adapters.openhuman_adapter import OpenHumanAdapter  # noqa: E402
from router.confidence import ConfidenceGate  # noqa: E402


def make_oh_req(
    action: str = "memory_search",
    task_type: TaskType = TaskType.PERSONAL_CONTEXT,
    privacy_class: PrivacyClass = PrivacyClass.P1,
    confidence_score: float = 80.0,
    allow_openhuman: bool = True,
) -> RouteRequest:
    return RouteRequest(
        request_id="r-oh-test",
        task_id="t-oh-test",
        task_type=task_type,
        objective="test openhuman objective",
        input=RouteInput(metadata={"action": action}),
        constraints=RouteConstraints(
            privacy_class=privacy_class,
            allow_openhuman=allow_openhuman,
        ),
        confidence=RouteConfidence(
            score=confidence_score,
            band=ConfidenceGate.band_from_score(confidence_score),
        ),
        preferred_provider="openhuman",
        fallback_chain=["mock"],
        audit=RouteAudit(caller="test"),
    )


@pytest.mark.asyncio
async def test_openhuman_disabled_by_default():
    oh = OpenHumanAdapter()
    assert oh.enabled is False
    health = await oh.health()
    assert health.reachable is False
    assert "disabled" in health.error


@pytest.mark.asyncio
async def test_openhuman_readonly_allows_memory_search():
    oh = OpenHumanAdapter(
        {
            "enabled": True,
            "base_url": "http://127.0.0.1:8787",
            "default_mode": "read_only",
        }
    )
    req = make_oh_req(action="memory_search")
    resp = await oh.complete(req)
    assert resp.route_reason != "openhuman_readonly_blocked"
    assert resp.output.type == OutputType.ERROR


@pytest.mark.asyncio
async def test_openhuman_readonly_blocks_send_email():
    oh = OpenHumanAdapter(
        {
            "enabled": True,
            "base_url": "http://127.0.0.1:8787",
            "default_mode": "read_only",
        }
    )
    req = make_oh_req(action="send_email")
    resp = await oh.complete(req)
    assert resp.route_reason == "openhuman_readonly_blocked"
    assert any("send_email" in e for e in resp.logs.errors)
    assert resp.output.type == OutputType.ERROR


@pytest.mark.asyncio
async def test_openhuman_write_action_blocked_even_if_not_readonly():
    oh = OpenHumanAdapter(
        {
            "enabled": True,
            "base_url": "http://127.0.0.1:8787",
            "default_mode": "governed",
        }
    )
    req = make_oh_req(action="delete_files")
    resp = await oh.complete(req)
    assert resp.route_reason == "openhuman_write_blocked"
    assert any("delete_files" in e for e in resp.logs.errors)


@pytest.mark.asyncio
async def test_openhuman_disabled_when_allow_openhuman_false():
    from router.router import ChromaticRouter

    router = ChromaticRouter()
    req = make_oh_req(
        allow_openhuman=False, confidence_score=90.0, privacy_class=PrivacyClass.P1
    )
    resp = await router.route(req)
    assert resp.selected_provider == "mock"
    assert resp.fallback_used is True


@pytest.mark.asyncio
async def test_openhuman_never_receives_p3():
    from router.router import ChromaticRouter

    router = ChromaticRouter()
    req = make_oh_req(privacy_class=PrivacyClass.P3, confidence_score=95.0)
    resp = await router.route(req)
    assert resp.route_reason == "privacy_gate_blocked"
    assert any("P3" in e for e in resp.logs.errors)


@pytest.mark.asyncio
async def test_openhuman_p4_blocked_without_human_gate():
    from router.router import ChromaticRouter

    router = ChromaticRouter()
    req = make_oh_req(privacy_class=PrivacyClass.P4, confidence_score=95.0)
    resp = await router.route(req)
    assert resp.route_reason == "privacy_gate_blocked"
    assert any("P4" in e for e in resp.logs.errors)
