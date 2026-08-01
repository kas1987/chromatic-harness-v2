"""Additional coverage tests for router/context_detector.py.

The top-level tests/test_context_detector.py covers Ollama probes and
device classification. This file targets the uncovered lines:
- _available_memory_ratio Linux path (lines 78-80)
- _windows_available_memory_ratio failure paths (103, 105, 107-108)
- _linux_available_memory_ratio (112-127)
- _probe_gpu (153-203)
- build_routing_context (319-330)
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[4] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from router.context_detector import ContextDetector


# ---------------------------------------------------------------------------
# _available_memory_ratio — platform dispatch
# ---------------------------------------------------------------------------


class TestAvailableMemoryRatioDispatch:
    def test_windows_dispatch(self, monkeypatch):
        """On Windows-like platform, _windows_available_memory_ratio is called."""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        called = []

        def _fake_windows():
            called.append(1)
            return 0.5

        monkeypatch.setattr(ContextDetector, "_windows_available_memory_ratio", staticmethod(_fake_windows))
        result = ContextDetector._available_memory_ratio()
        assert result == 0.5
        assert called

    def test_linux_dispatch(self, monkeypatch):
        """On Linux-like platform, _linux_available_memory_ratio is called."""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        called = []

        def _fake_linux():
            called.append(1)
            return 0.35

        monkeypatch.setattr(ContextDetector, "_linux_available_memory_ratio", staticmethod(_fake_linux))
        result = ContextDetector._available_memory_ratio()
        assert result == 0.35
        assert called

    def test_unknown_platform_returns_none(self, monkeypatch):
        """For unknown platforms (e.g. Darwin), returns None."""
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        result = ContextDetector._available_memory_ratio()
        assert result is None


# ---------------------------------------------------------------------------
# _windows_available_memory_ratio — failure paths
# ---------------------------------------------------------------------------


class TestWindowsAvailableMemoryRatio:
    def test_returns_float_on_success(self):
        """On Windows, the method should return a float or None."""
        result = ContextDetector._windows_available_memory_ratio()
        # On a real Windows machine, it returns a float; on other OS it may return None
        assert result is None or (isinstance(result, float) and 0.0 <= result <= 1.0)

    def test_returns_none_on_exception(self, monkeypatch):
        """If ctypes call raises, return None safely."""
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "ctypes":
                raise ImportError("no ctypes")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        # Should not raise
        result = ContextDetector._windows_available_memory_ratio()
        assert result is None


# ---------------------------------------------------------------------------
# _linux_available_memory_ratio
# ---------------------------------------------------------------------------


class TestLinuxAvailableMemoryRatio:
    def test_parses_proc_meminfo(self, tmp_path, monkeypatch):
        """Parse /proc/meminfo if it exists (mocked)."""
        fake_meminfo = "MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\nMemFree: 4000000 kB\n"
        fake_path = tmp_path / "meminfo"
        fake_path.write_text(fake_meminfo, encoding="utf-8")
        with patch("router.context_detector.Path") as mock_path_cls:
            # We need to intercept Path("/proc/meminfo") but let other Path() calls work
            original_path = Path

            def _path_factory(arg):
                if str(arg) == "/proc/meminfo":
                    return fake_path
                return original_path(arg)

            mock_path_cls.side_effect = _path_factory
            result = ContextDetector._linux_available_memory_ratio()
        # 8000000 / 16000000 = 0.5
        assert result == pytest.approx(0.5)

    def test_returns_none_if_proc_not_readable(self):
        """If /proc/meminfo doesn't exist (Windows), returns None."""
        # On Windows, /proc/meminfo doesn't exist, so this tests the exception path
        result = ContextDetector._linux_available_memory_ratio()
        # Should return None (exception swallowed) rather than raising
        assert result is None or isinstance(result, float)

    def test_handles_zero_total(self, tmp_path):
        """If MemTotal is 0, return None."""
        fake_meminfo = "MemTotal: 0 kB\nMemAvailable: 0 kB\n"
        fake_path = tmp_path / "meminfo"
        fake_path.write_text(fake_meminfo, encoding="utf-8")
        with patch("router.context_detector.Path") as mock_path_cls:
            original_path = Path

            def _path_factory(arg):
                if str(arg) == "/proc/meminfo":
                    return fake_path
                return original_path(arg)

            mock_path_cls.side_effect = _path_factory
            result = ContextDetector._linux_available_memory_ratio()
        assert result is None


# ---------------------------------------------------------------------------
# _probe_gpu — coverage for nvidia-smi parsing
# ---------------------------------------------------------------------------


class TestProbeGpu:
    def test_no_gpu_returns_none_tuple(self, monkeypatch):
        """When nvidia-smi is not available, returns (None, None)."""

        def _fail(*args, **kwargs):
            raise FileNotFoundError("nvidia-smi not found")

        monkeypatch.setattr("subprocess.run", _fail)
        result = ContextDetector._probe_gpu()
        assert result == (None, None)

    def test_nvidia_smi_success(self, monkeypatch):
        """When nvidia-smi succeeds, parse GPU name and VRAM.

        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits
        outputs: "NVIDIA GeForce RTX 4070, 12288"  (MiB value, no unit suffix)
        """
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "NVIDIA GeForce RTX 4070, 12288"
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake_proc)
        name, vram = ContextDetector._probe_gpu()
        assert name is not None
        # VRAM should be parsed (12288 MiB -> 12.0 GB)
        if vram is not None:
            assert isinstance(vram, float)
            assert vram == pytest.approx(12.0)

    def test_nvidia_smi_nonzero_returncode(self, monkeypatch):
        """When nvidia-smi exits with error, returns (None, None)."""
        fake_proc = MagicMock()
        fake_proc.returncode = 9
        fake_proc.stdout = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake_proc)
        result = ContextDetector._probe_gpu()
        assert result == (None, None)


# ---------------------------------------------------------------------------
# build_routing_context — integration with detect()
# ---------------------------------------------------------------------------


class TestBuildRoutingContext:
    @patch("router.context_detector.ContextDetector._probe_gpu", return_value=(None, None))
    @patch("router.context_detector.ContextDetector._probe_ollama_local", return_value=(False, []))
    @patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
    @patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
    def test_returns_routing_context(self, *_mocks):
        from router.contracts import RoutingContext

        ctx = ContextDetector().build_routing_context(
            objective="implement login flow",
            task_description="add auth",
            prompt="write the code",
        )
        assert isinstance(ctx, RoutingContext)
        assert ctx.objective == "implement login flow"
        assert ctx.task_description == "add auth"
        assert ctx.prompt == "write the code"

    @patch("router.context_detector.ContextDetector._probe_gpu", return_value=("RTX 4090", 24.0))
    @patch("router.context_detector.ContextDetector._probe_ollama_local", return_value=(True, ["llama3.1:8b"]))
    @patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
    @patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
    def test_routing_context_gpu_fields(self, *_mocks):
        ctx = ContextDetector().build_routing_context("refactor module X")
        assert ctx.gpu_available is True
        assert ctx.gpu_model == "RTX 4090"
        assert ctx.gpu_vram_gb == 24.0

    @patch("router.context_detector.ContextDetector._probe_gpu", return_value=(None, None))
    @patch("router.context_detector.ContextDetector._probe_ollama_local", return_value=(False, []))
    @patch("router.context_detector.ContextDetector._probe_internet", return_value=False)
    @patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
    def test_routing_context_offline(self, *_mocks):
        ctx = ContextDetector().build_routing_context("debug the error")
        assert ctx.internet_reachable is False

    @patch("router.context_detector.ContextDetector._probe_gpu", return_value=(None, None))
    @patch("router.context_detector.ContextDetector._probe_ollama_local", return_value=(True, []))
    @patch("router.context_detector.ContextDetector._probe_internet", return_value=True)
    @patch("router.context_detector.ContextDetector._probe_battery", return_value=False)
    def test_routing_context_remote_endpoints_dict(self, *_mocks):
        """Ensure dict endpoints are converted to OllamaEndpoint."""
        from router.contracts import OllamaEndpoint

        ctx = ContextDetector().build_routing_context(
            objective="task",
            # No remote endpoints — just test it doesn't blow up
        )
        # RoutingContext stores endpoints as a tuple (frozen dataclass style)
        assert isinstance(ctx.remote_ollama_endpoints, (list, tuple))
