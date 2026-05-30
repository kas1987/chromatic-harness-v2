"""Tests for ContextDetector Ollama probes and ProviderSelector remote Ollama."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from router.context_detector import ContextDetector, RuntimeContext
from router.complexity_classifier import ComplexityClassifier
from router.provider_selector import ProviderSelector


OLLAMA_TAGS_RESPONSE = {
    "models": [
        {"name": "llama3.2:3b", "model": "llama3.2:3b"},
        {"name": "qwen2.5-coder:14b", "model": "qwen2.5-coder:14b"},
    ]
}


def _mock_urlopen_response(status: int = 200, body: dict | None = None):
    payload = json.dumps(body or OLLAMA_TAGS_RESPONSE).encode()
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = payload
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestOllamaLocalProbe:
    def test_probe_ollama_local_reachable(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_response()):
            reachable, models = ContextDetector._probe_ollama_local()
        assert reachable is True
        assert "llama3.2:3b" in models
        assert "qwen2.5-coder:14b" in models

    def test_probe_ollama_local_unreachable(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            reachable, models = ContextDetector._probe_ollama_local()
        assert reachable is False
        assert models == []

    def test_probe_ollama_local_uses_tags_endpoint(self):
        captured: list[str] = []

        def _capture(req, timeout=2):
            captured.append(req.full_url)
            return _mock_urlopen_response()

        with patch("urllib.request.urlopen", side_effect=_capture):
            ContextDetector._probe_ollama_local()
        assert captured == ["http://localhost:11434/api/tags"]


class TestDeviceClassification:
    def test_laptop_no_gpu(self):
        assert ContextDetector._classify_device(gpu_available=False) == "laptop"

    def test_desktop_with_gpu(self):
        assert ContextDetector._classify_device(gpu_available=True) == "desktop"

    @patch(
        "router.context_detector.ContextDetector._probe_gpu", return_value=(None, None)
    )
    @patch(
        "router.context_detector.ContextDetector._probe_ollama_local",
        return_value=(False, []),
    )
    @patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
    @patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
    def test_detect_laptop_no_gpu(self, *_mocks):
        ctx = ContextDetector().detect()
        assert ctx.device_type == "laptop"
        assert ctx.gpu_available is False
        assert ctx.gpu_model is None

    @patch(
        "router.context_detector.ContextDetector._probe_gpu",
        return_value=("NVIDIA GeForce RTX 4070", 12.0),
    )
    @patch(
        "router.context_detector.ContextDetector._probe_ollama_local",
        return_value=(True, ["llama3.1:8b"]),
    )
    @patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
    @patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
    def test_detect_desktop_rtx4070(self, *_mocks):
        ctx = ContextDetector().detect()
        assert ctx.device_type == "desktop"
        assert ctx.gpu_available is True
        assert ctx.gpu_model == "NVIDIA GeForce RTX 4070"
        assert ctx.gpu_vram_gb == 12.0


class TestConnectivity:
    @patch(
        "router.context_detector.ContextDetector._probe_gpu", return_value=(None, None)
    )
    @patch(
        "router.context_detector.ContextDetector._probe_ollama_local",
        return_value=(False, []),
    )
    @patch(
        "router.context_detector.ContextDetector._probe_internet", return_value=False
    )
    @patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
    def test_offline_connectivity(self, *_mocks):
        ctx = ContextDetector().detect()
        assert ctx.internet_reachable is False
        assert ctx.connectivity == "offline"

    @patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
    def test_probe_internet_reachable(self, _mock):
        assert ContextDetector._probe_internet() is True

    @patch(
        "router.context_detector.ContextDetector._probe_internet", return_value=False
    )
    def test_probe_internet_unreachable(self, _mock):
        assert ContextDetector._probe_internet() is False


class TestManifestSerialization:
    def test_runtime_context_json_serializable(self):
        ctx = RuntimeContext(
            device_type="laptop",
            gpu_model=None,
            gpu_vram_gb=None,
            gpu_available=False,
            ollama_local_reachable=True,
            ollama_local_models=["llama3.2:3b"],
            remote_ollama_endpoints=[{"host": "desktop.local", "port": 11434}],
            internet_reachable=True,
            connectivity="full",
            memory_pressure="medium",
            os_family="windows",
            cpu_count=8,
            is_battery=False,
        )
        payload = dataclasses.asdict(ctx)
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
        assert decoded["device_type"] == "laptop"
        assert decoded["ollama_local_reachable"] is True
        assert decoded["remote_ollama_endpoints"][0]["host"] == "desktop.local"

    def test_manifest_routing_context_shape(self):
        """Fields align with scripts/pre_session_manifest._routing_context()."""
        ctx = RuntimeContext(
            device_type="desktop",
            gpu_model="RTX 4070",
            gpu_vram_gb=12.0,
            gpu_available=True,
            ollama_local_reachable=True,
            ollama_local_models=["llama3.1:8b"],
            remote_ollama_endpoints=[],
            internet_reachable=True,
            connectivity="full",
            memory_pressure="medium",
            os_family="windows",
            cpu_count=12,
            is_battery=True,
        )
        manifest_slice = {
            "device_type": ctx.device_type,
            "gpu_available": ctx.gpu_available,
            "ollama_local_reachable": ctx.ollama_local_reachable,
            "internet_reachable": ctx.internet_reachable,
            "connectivity": ctx.connectivity,
            "is_battery": ctx.is_battery,
        }
        json.dumps(manifest_slice)


class TestRemoteOllamaProbe:
    def test_probe_remote_reachable_hostname(self):
        endpoints = [{"host": "desktop.local", "port": 11434, "enabled": True}]
        with patch("urllib.request.urlopen", return_value=_mock_urlopen_response()):
            assert ProviderSelector._probe_remote_ollama(endpoints) is True

    def test_probe_remote_reachable_ip(self):
        endpoints = [{"host": "192.168.1.50", "port": 11434, "enabled": True}]
        captured: list[str] = []

        def _capture(req, timeout=2):
            captured.append(req.full_url)
            return _mock_urlopen_response()

        with patch("urllib.request.urlopen", side_effect=_capture):
            assert ProviderSelector._probe_remote_ollama(endpoints) is True
        assert captured == ["http://192.168.1.50:11434/api/tags"]

    def test_probe_remote_unreachable(self):
        endpoints = [{"host": "desktop.local", "port": 11434, "enabled": True}]
        with patch("urllib.request.urlopen", side_effect=TimeoutError("offline")):
            assert ProviderSelector._probe_remote_ollama(endpoints) is False

    def test_probe_remote_skips_disabled_endpoints(self):
        endpoints = [
            {"host": "desktop.local", "port": 11434, "enabled": False},
            {"host": "192.168.1.50", "port": 11434, "enabled": True},
        ]
        captured: list[str] = []

        def _capture(req, timeout=2):
            captured.append(req.full_url)
            return _mock_urlopen_response()

        with patch("urllib.request.urlopen", side_effect=_capture):
            assert ProviderSelector._probe_remote_ollama(endpoints) is True
        assert captured == ["http://192.168.1.50:11434/api/tags"]

    def test_probe_remote_tries_next_on_failure(self):
        endpoints = [
            {"host": "sleeping-desktop.local", "port": 11434, "enabled": True},
            {"host": "desktop.local", "port": 11434, "enabled": True},
        ]
        calls: list[str] = []

        def _side_effect(req, timeout=2):
            calls.append(req.full_url)
            if "sleeping-desktop" in req.full_url:
                raise OSError("host unreachable")
            return _mock_urlopen_response()

        with patch("urllib.request.urlopen", side_effect=_side_effect):
            assert ProviderSelector._probe_remote_ollama(endpoints) is True
        assert len(calls) == 2


@pytest.fixture
def selector():
    return ProviderSelector(prefs_path=Path("/tmp/empty_prefs.yaml"))


@pytest.fixture
def classifier():
    return ComplexityClassifier()


def _laptop_remote_ctx(*, remote_endpoints: list[dict]) -> RuntimeContext:
    return RuntimeContext(
        device_type="laptop",
        gpu_model=None,
        gpu_vram_gb=None,
        gpu_available=False,
        ollama_local_reachable=True,
        ollama_local_models=["llama3.2:3b"],
        remote_ollama_endpoints=remote_endpoints,
        internet_reachable=True,
        connectivity="full",
        memory_pressure="medium",
        os_family="windows",
        cpu_count=8,
        is_battery=False,
    )


class TestRemoteOllamaRouting:
    @pytest.mark.parametrize(
        "c_level,task_desc,prompt",
        [
            ("C2", "scaffold a new module", "scaffold the directory layout"),
            ("C3", "debug the failing request path", "root cause the 500 error"),
        ],
    )
    def test_prefers_remote_ollama_when_reachable(
        self, selector, classifier, c_level, task_desc, prompt, monkeypatch
    ):
        monkeypatch.setattr(
            ProviderSelector,
            "_probe_remote_ollama",
            staticmethod(lambda eps: True),
        )
        result = classifier.classify(task_desc, prompt)
        assert result.level == c_level
        ctx = _laptop_remote_ctx(
            remote_endpoints=[{"host": "desktop.local", "port": 11434}]
        )
        sel = selector.select(result, ctx, speed_mode="balance")
        assert sel.context_key == "context_laptop_remote"
        assert sel.ranked_choices[0].provider == "ollama_remote_desktop"

    def test_skips_remote_when_unreachable(self, selector, classifier, monkeypatch):
        monkeypatch.setattr(
            ProviderSelector,
            "_probe_remote_ollama",
            staticmethod(lambda eps: False),
        )
        result = classifier.classify(
            "scaffold a new module", "scaffold the directory layout"
        )
        ctx = _laptop_remote_ctx(
            remote_endpoints=[{"host": "desktop.local", "port": 11434}]
        )
        sel = selector.select(result, ctx, speed_mode="balance")
        providers = [c.provider for c in sel.ranked_choices]
        assert "ollama_remote_desktop" not in providers
        assert sel.ranked_choices[0].provider == "ollama_local"
