"""Tests for ContextResourceManifest."""

from router.context_manifest import (
    ContextResource,
    ContextResourceManifest,
)
from router.contracts import PrivacyClass, TaskType


class TestContextResource:
    def test_matches_task(self):
        r = ContextResource(
            resource_id="test",
            resource_type="tool",
            task_types=[TaskType.CODING],
        )
        assert r.matches_task(TaskType.CODING) is True
        assert r.matches_task(TaskType.RESEARCH) is False

    def test_matches_task_empty_means_universal(self):
        r = ContextResource(resource_id="test", resource_type="tool")
        assert r.matches_task(TaskType.CODING) is True

    def test_matches_privacy(self):
        r = ContextResource(
            resource_id="test",
            resource_type="tool",
            privacy_classes=[PrivacyClass.P0, PrivacyClass.P1],
        )
        assert r.matches_privacy(PrivacyClass.P0) is True
        assert r.matches_privacy(PrivacyClass.P4) is False

    def test_matches_complexity(self):
        r = ContextResource(
            resource_id="test",
            resource_type="tool",
            complexity_tiers=["C1", "C2"],
        )
        assert r.matches_complexity("C1") is True
        assert r.matches_complexity("C4") is False


class TestContextResourceManifest:
    def test_build_defaults(self):
        manifest = ContextResourceManifest.build_defaults()
        assert len(manifest) > 0
        assert manifest.get("bash") is not None
        assert manifest.get("bash").resource_type == "tool"

    def test_filter_by_task_type(self):
        manifest = ContextResourceManifest.build_defaults()
        coding = manifest.filter(task_type=TaskType.CODING)
        assert all(r.matches_task(TaskType.CODING) for r in coding)

    def test_filter_by_complexity(self):
        manifest = ContextResourceManifest.build_defaults()
        c1 = manifest.filter(complexity="C1")
        assert all(r.matches_complexity("C1") for r in c1)

    def test_filter_by_privacy(self):
        manifest = ContextResourceManifest.build_defaults()
        p0 = manifest.filter(privacy=PrivacyClass.P0)
        assert all(r.matches_privacy(PrivacyClass.P0) for r in p0)

    def test_filter_by_resource_type(self):
        manifest = ContextResourceManifest.build_defaults()
        tools = manifest.filter(resource_type="tool")
        assert all(r.resource_type == "tool" for r in tools)

    def test_filter_by_max_risk(self):
        manifest = ContextResourceManifest.build_defaults()
        low = manifest.filter(max_risk="low")
        assert all(r.risk_level == "low" for r in low)

    def test_filter_by_provider(self):
        manifest = ContextResourceManifest.build_defaults()
        native = manifest.filter(provider="native_claude")
        assert all(
            not r.provider_bindings or "native_claude" in r.provider_bindings
            for r in native
        )

    def test_combined_filter(self):
        manifest = ContextResourceManifest.build_defaults()
        results = manifest.filter(
            task_type=TaskType.CODING,
            complexity="C1",
            privacy=PrivacyClass.P0,
            resource_type="tool",
            max_risk="low",
        )
        assert all(
            r.matches_task(TaskType.CODING)
            and r.matches_complexity("C1")
            and r.matches_privacy(PrivacyClass.P0)
            and r.resource_type == "tool"
            and r.risk_level == "low"
            for r in results
        )

    def test_total_estimated_tokens(self):
        manifest = ContextResourceManifest()
        manifest.register(ContextResource("a", "tool", estimated_tokens=100))
        manifest.register(ContextResource("b", "tool", estimated_tokens=200))
        assert manifest.total_estimated_tokens(["a", "b"]) == 300
        assert manifest.total_estimated_tokens(["a", "missing"]) == 100

    def test_enabled_filter(self):
        manifest = ContextResourceManifest()
        manifest.register(ContextResource("on", "tool", enabled=True))
        manifest.register(ContextResource("off", "tool", enabled=False))
        enabled = manifest.enabled()
        assert len(enabled) == 1
        assert enabled[0].resource_id == "on"

    def test_load_from_policy_file_not_found(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/nonexistent.yaml"
            manifest = ContextResourceManifest.load_from_policy(path)
            assert len(manifest) == 0
