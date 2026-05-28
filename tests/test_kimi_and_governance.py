"""Tests for Kimi provider registration and Orchestrator.complete_mission()."""

import json
import pathlib
import tempfile

from router.policy import PolicyLoader
from router.router import ChromaticRouter
import router.observability as observability_mod


# ---------------------------------------------------------------------------
# Kimi provider registration
# ---------------------------------------------------------------------------


def test_kimi_in_providers_yaml():
    loader = PolicyLoader()
    providers = loader.providers()
    assert "kimi" in providers
    cfg = providers["kimi"]
    assert cfg["type"] == "broker"
    assert cfg["env_key"] == "MOONSHOT_API_KEY"
    assert "moonshot" in cfg.get("base_url", "")


def test_kimi_in_privacy_allowlists():
    loader = PolicyLoader()
    privacy = loader.privacy()
    assert "kimi" in privacy["P0"]["allowed_providers"]
    assert "kimi" in privacy["P1"]["allowed_providers"]
    assert "kimi" not in privacy["P2"].get("allowed_providers", [])


def test_kimi_adapter_registered():
    router = ChromaticRouter()
    assert "kimi" in router.adapters


def test_kimi_budget_cost_defined():
    loader = PolicyLoader()
    costs = loader.provider_costs()
    assert "kimi" in costs
    assert costs["kimi"]["input"] >= 0


def test_coding_route_uses_kimi_as_default():
    loader = PolicyLoader()
    route = loader.route_for_task("coding")
    assert route.get("default") == "kimi"
    assert "openai" in route.get("fallback", [])


# ---------------------------------------------------------------------------
# Orchestrator.complete_mission() writes AGENT_RUN_LOG
# ---------------------------------------------------------------------------


def test_complete_mission_writes_agent_run_log():
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        agent_log = td_path / "AGENT_RUN_LOG.jsonl"

        # Patch ObservabilityLogger to write to our temp log
        original_init = observability_mod.ObservabilityLogger.__init__

        def patched_init(self, log_dir=None, agent_run_log=None):
            original_init(self, log_dir=td_path, agent_run_log=agent_log)

        observability_mod.ObservabilityLogger.__init__ = patched_init
        try:
            from orchestrator.orchestrator import Orchestrator, MissionPacket

            orch = Orchestrator()
            mission = MissionPacket(
                mission_id="m-test-001",
                objective="scaffold new module",
                agent_role="builder",
                autonomy_level="L1",
                confidence_required=80.0,
                allowed_tools=["filesystem.read", "filesystem.write"],
                stop_conditions=["confidence_below_threshold"],
                required_outputs=["summary"],
            )
            orch.complete_mission(
                mission,
                model="moonshot-v1-32k",
                role="builder",
                files_touched=["src/new_module.py", "tests/test_new_module.py"],
                result="text",
                validation="2/2 tests pass",
                next_task="review new_module with Sonnet",
                tools_used=4,
            )
        finally:
            observability_mod.ObservabilityLogger.__init__ = original_init

        assert agent_log.exists()
        lines = [line for line in agent_log.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["task_id"] == "m-test-001"
        assert record["model"] == "moonshot-v1-32k"
        assert record["role"] == "builder"
        assert record["tools_used"] == 4
        assert record["files_touched"] == [
            "src/new_module.py",
            "tests/test_new_module.py",
        ]
        assert record["validation"] == "2/2 tests pass"
        assert record["next_task"] == "review new_module with Sonnet"
        assert record["risk_level"] in ("low", "medium", "high", "critical")
