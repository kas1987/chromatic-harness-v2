"""Tests for WebSocket event persistence and Redis bus (optional)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from console_api.event_store import FileEventStore, MissionEventHub, RedisEventBus  # noqa: E402


def test_file_store_append_and_replay(tmp_path: Path):
    store = FileEventStore(tmp_path)
    mission = "CHR-WS-TEST"
    for i in range(3):
        store.append(
            mission,
            {"type": "magnet_event", "mission_id": mission, "timestamp": i, "data": {"i": i}},
        )
    replay = store.replay(mission, limit=10)
    assert len(replay) == 3
    assert replay[-1]["data"]["i"] == 2


def test_mission_event_hub_publish(tmp_path: Path):
    hub = MissionEventHub(tmp_path)
    mission = "m-hub-1"
    hub.publish(
        mission,
        {"type": "gate_decision", "mission_id": mission, "timestamp": 1, "data": {"gate_name": "intent"}},
    )
    events = hub.replay(mission)
    assert len(events) == 1
    assert events[0]["type"] == "gate_decision"


def test_redis_bus_disabled_without_url():
    bus = RedisEventBus(url="")
    assert not bus.enabled
    assert bus.publish("m1", {"x": 1}) is False


def test_ws_publish_cli():
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "ws_publish_event.py"),
            "--mission-id",
            "cli-test",
            "--type",
            "magnet_event",
            "--data",
            json.dumps({"score": 0.9}),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "persisted" in proc.stdout
