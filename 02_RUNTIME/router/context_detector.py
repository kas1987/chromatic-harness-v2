"""Runtime context detection for provider-neutral routing."""

from __future__ import annotations

import dataclasses
import os
import platform
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


@dataclasses.dataclass(frozen=True)
class RuntimeContext:
    device_type: str  # "laptop" | "desktop" | "server" | "unknown"
    gpu_model: str | None
    gpu_vram_gb: float | None
    gpu_available: bool
    ollama_local_reachable: bool
    ollama_local_models: list[str]
    remote_ollama_endpoints: list[dict[str, Any]]
    internet_reachable: bool
    connectivity: str  # "full" | "limited" | "offline"
    memory_pressure: str  # "low" | "medium" | "high" — not implemented yet
    os_family: str  # "windows" | "linux" | "macos"
    cpu_count: int
    is_battery: bool  # True if laptop on battery


class ContextDetector:
    """Detect the machine's capabilities and network state."""

    OLLAMA_LOCAL_URL = "http://localhost:11434/api/tags"
    TIMEOUT_S = 2

    def detect(self) -> RuntimeContext:
        gpu_model, gpu_vram = self._probe_gpu()
        ollama_reachable, ollama_models = self._probe_ollama_local()
        internet = self._probe_internet()
        device = self._classify_device(gpu_available=gpu_model is not None)
        battery = self._probe_battery()

        return RuntimeContext(
            device_type=device,
            gpu_model=gpu_model,
            gpu_vram_gb=gpu_vram,
            gpu_available=gpu_model is not None,
            ollama_local_reachable=ollama_reachable,
            ollama_local_models=ollama_models,
            remote_ollama_endpoints=[],  # populated by caller after reading prefs
            internet_reachable=internet,
            connectivity="full" if internet else "offline",
            memory_pressure=self._detect_memory_pressure(),
            os_family=platform.system().lower(),
            cpu_count=os.cpu_count() or 1,
            is_battery=battery,
        )

    @classmethod
    def _detect_memory_pressure(cls) -> str:
        available_ratio = cls._available_memory_ratio()
        if available_ratio is None:
            return "medium"
        if available_ratio < 0.20:
            return "high"
        if available_ratio < 0.45:
            return "medium"
        return "low"

    @classmethod
    def _available_memory_ratio(cls) -> float | None:
        system = platform.system().lower()
        if system == "windows":
            return cls._windows_available_memory_ratio()
        if system == "linux":
            return cls._linux_available_memory_ratio()
        return None

    @staticmethod
    def _windows_available_memory_ratio() -> float | None:
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            if not status.ullTotalPhys:
                return None
            return status.ullAvailPhys / status.ullTotalPhys
        except Exception:
            return None

    @staticmethod
    def _linux_available_memory_ratio() -> float | None:
        try:
            meminfo: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition(":")
                parts = value.strip().split()
                if not parts:
                    continue
                meminfo[key] = int(parts[0])

            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            if total <= 0:
                return None
            return available / total
        except Exception:
            return None

    # ── GPU detection ────────────────────────────────────────────────────────

    @staticmethod
    def _probe_gpu() -> tuple[str | None, float | None]:
        """Return (gpu_model, vram_gb) or (None, None)."""
        # Windows: try nvidia-smi
        try:
            out = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                line = out.stdout.strip().splitlines()[0]
                parts = line.split(",")
                model = parts[0].strip()
                vram_mb = float(parts[1].strip())
                return model, round(vram_mb / 1024, 1)
        except FileNotFoundError:
            pass

        # Windows fallback: wmic
        try:
            out = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if out.returncode == 0:
                lines = out.stdout.strip().splitlines()
                if len(lines) >= 2:
                    # Parse header + first data row
                    # Name                    AdapterRAM
                    # NVIDIA GeForce RTX 4070 128000000
                    data = lines[1].strip()
                    # rough extraction
                    if "NVIDIA" in data or "AMD" in data or "Intel Arc" in data:
                        name = data.rsplit(None, 1)[0] if " " in data else data
                        # AdapterRAM is bytes; crude parse
                        return name.strip(), None
        except FileNotFoundError:
            pass

        # Linux / WSL2 fallback
        try:
            out = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                shell=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                line = out.stdout.strip().splitlines()[0]
                parts = line.split(",")
                model = parts[0].strip()
                vram_mb = float(parts[1].strip())
                return model, round(vram_mb / 1024, 1)
        except FileNotFoundError:
            pass

        return None, None

    # ── Ollama local ────────────────────────────────────────────────────────

    @classmethod
    def _probe_ollama_local(cls) -> tuple[bool, list[str]]:
        try:
            req = urllib.request.Request(
                cls.OLLAMA_LOCAL_URL,
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=cls.TIMEOUT_S) as resp:
                if resp.status == 200:
                    import json

                    data = json.loads(resp.read())
                    models = [
                        m.get("name", m.get("model", ""))
                        for m in data.get("models", [])
                    ]
                    return True, [m for m in models if m]
        except Exception:
            pass
        return False, []

    # ── Internet ────────────────────────────────────────────────────────────

    @classmethod
    def _probe_internet(cls) -> bool:
        for host in ("https://dns.google", "https://1.1.1.1", "https://cloudflare.com"):
            try:
                req = urllib.request.Request(host, method="HEAD")
                with urllib.request.urlopen(req, timeout=cls.TIMEOUT_S):
                    return True
            except Exception:
                continue
        return False

    # ── Device classification ───────────────────────────────────────────────

    @staticmethod
    def _classify_device(gpu_available: bool) -> str:
        """Heuristic: GPU usually means desktop (or high-end laptop)."""
        sys_plat = platform.system().lower()
        if sys_plat == "darwin":
            # macOS: check if MacBook Pro vs Mac Studio
            try:
                out = subprocess.run(
                    ["sysctl", "-n", "hw.model"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if "macbook" in out.stdout.lower():
                    return "laptop"
                return "desktop"
            except Exception:
                return "unknown"

        # Windows / Linux
        if gpu_available:
            # Very rough: discrete GPU usually desktop unless known mobile SKU
            return "desktop"

        # No GPU → probably laptop (or server, but we assume laptop for dev)
        return "laptop"

    @staticmethod
    def _probe_battery() -> bool:
        """Return True if running on battery power."""
        try:
            if platform.system().lower() == "windows":
                import ctypes

                # GetSystemPowerStatus
                class SYSTEM_POWER_STATUS(ctypes.Structure):
                    _fields_ = [
                        ("ACLineStatus", ctypes.c_ubyte),
                        ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte),
                        ("Reserved1", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_ulong),
                        ("BatteryFullLifeTime", ctypes.c_ulong),
                    ]

                sps = SYSTEM_POWER_STATUS()
                if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                    return sps.ACLineStatus == 0  # type: ignore[return-value]  # 0 = battery, 1 = AC
        except Exception:
            pass

        try:
            # Linux /sys/class/power_supply/BAT0/status
            bat_status = (
                Path("/sys/class/power_supply/BAT0/status").read_text().strip().lower()
            )
            return bat_status == "discharging"
        except Exception:
            pass

        return False  # assume AC if we can't tell
