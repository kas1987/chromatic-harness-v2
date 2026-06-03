"""Tests for console_api/event_store.py — FileEventStore, RedisEventBus, MissionEventHub."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from console_api.event_store import FileEventStore, MissionEventHub, RedisEventBus


# ---------------------------------------------------------------------------
# FileEventStore
# ---------------------------------------------------------------------------

class TestFileEventStore:
    def test_post_init_creates_directory(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        assert store.dir.is_dir()
        assert store.dir == tmp_path / "07_LOGS_AND_AUDIT" / "ws_events"

    def test_append_creates_file(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        store.append("mission-1", {"type": "start", "seq": 0})
        path = store._path("mission-1")
        assert path.is_file()

    def test_append_writes_valid_json_line(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        event = {"type": "gate_decision", "value": 42}
        store.append("m1", event)
        line = store._path("m1").read_text(encoding="utf-8").strip()
        parsed = json.loads(line)
        assert parsed["type"] == "gate_decision"
        assert parsed["value"] == 42

    def test_append_multiple_events_writes_multiple_lines(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        for i in range(5):
            store.append("m2", {"seq": i, "data": f"item-{i}"})
        lines = [
            ln for ln in store._path("m2").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        assert len(lines) == 5

    def test_replay_returns_events_in_order(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        for i in range(3):
            store.append("m3", {"seq": i})
        events = store.replay("m3")
        assert [e["seq"] for e in events] == [0, 1, 2]

    def test_replay_returns_empty_list_for_missing_mission(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        assert store.replay("nonexistent-mission") == []

    def test_replay_respects_limit(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        for i in range(20):
            store.append("m4", {"seq": i})
        events = store.replay("m4", limit=5)
        assert len(events) == 5
        # limit takes the last N entries
        assert events[-1]["seq"] == 19

    def test_replay_skips_invalid_json_lines(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        path = store._path("m5")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"seq": 0}\n'
            'THIS IS NOT JSON\n'
            '{"seq": 2}\n',
            encoding="utf-8",
        )
        events = store.replay("m5")
        assert len(events) == 2
        assert events[0]["seq"] == 0
        assert events[1]["seq"] == 2

    def test_replay_skips_blank_lines(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        path = store._path("m6")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"seq": 0}\n\n   \n{"seq": 1}\n',
            encoding="utf-8",
        )
        events = store.replay("m6")
        assert len(events) == 2

    def test_path_sanitizes_special_characters(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        # Characters other than alnum, '-', '_' should be replaced with '_'
        path = store._path("mission/with:special!chars")
        assert "/" not in path.name
        assert ":" not in path.name
        assert "!" not in path.name

    def test_path_preserves_alnum_and_dash_underscore(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        path = store._path("mission-123_ABC")
        assert path.name == "mission-123_ABC.jsonl"

    def test_append_persists_non_ascii_content(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        store.append("m7", {"label": "héllo wörld", "emoji": "🎉"})
        events = store.replay("m7")
        assert events[0]["label"] == "héllo wörld"

    def test_write_then_read_roundtrip(self, tmp_path: Path) -> None:
        store = FileEventStore(tmp_path)
        original = {"type": "test_event", "payload": {"a": 1, "b": [2, 3]}}
        store.append("roundtrip", original)
        events = store.replay("roundtrip")
        assert len(events) == 1
        assert events[0]["type"] == "test_event"
        assert events[0]["payload"]["b"] == [2, 3]


# ---------------------------------------------------------------------------
# RedisEventBus
# ---------------------------------------------------------------------------

class TestRedisEventBus:
    def test_disabled_without_url(self) -> None:
        bus = RedisEventBus(url="")
        assert not bus.enabled

    def test_disabled_when_no_url_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("REDIS_URL", raising=False)
        bus = RedisEventBus()
        assert not bus.enabled

    def test_enabled_with_url(self) -> None:
        bus = RedisEventBus(url="redis://localhost:6379")
        assert bus.enabled

    def test_publish_returns_false_when_disabled(self) -> None:
        bus = RedisEventBus(url="")
        result = bus.publish("m1", {"type": "event"})
        assert result is False

    def test_publish_returns_false_when_redis_import_fails(self) -> None:
        bus = RedisEventBus(url="redis://localhost:6379")
        with patch.dict("sys.modules", {"redis": None}):
            # Reset client so _ensure_client re-runs
            bus._client = None
            result = bus.publish("m1", {"type": "event"})
        assert result is False

    def test_channel_name_format(self) -> None:
        bus = RedisEventBus(url="redis://localhost:6379", prefix="test:ns")
        assert bus._channel("my-mission") == "test:ns:my-mission"

    def test_channel_sanitizes_special_chars(self) -> None:
        bus = RedisEventBus(url="redis://localhost:6379", prefix="ns")
        channel = bus._channel("mission/with:special")
        assert "/" not in channel.split(":", 1)[-1]
        assert ":" not in channel.split(":", 1)[-1]

    def test_publish_calls_redis_publish_when_client_ready(self) -> None:
        bus = RedisEventBus(url="redis://localhost:6379")
        mock_client = MagicMock()
        bus._client = mock_client

        result = bus.publish("test-mission", {"type": "ping"})

        assert result is True
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        channel_arg = call_args[0][0]
        payload_arg = call_args[0][1]
        assert "test-mission" in channel_arg
        data = json.loads(payload_arg)
        assert data["type"] == "ping"


# ---------------------------------------------------------------------------
# MissionEventHub
# ---------------------------------------------------------------------------

class TestMissionEventHub:
    def test_publish_persists_event(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        hub.publish("mission-A", {"type": "start"})
        events = hub.replay("mission-A")
        assert len(events) == 1
        assert events[0]["type"] == "start"

    def test_publish_adds_mission_id_to_record(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        hub.publish("mission-B", {"type": "gate"})
        events = hub.replay("mission-B")
        assert events[0]["mission_id"] == "mission-B"

    def test_publish_returns_persisted_true(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        result = hub.publish("mission-C", {"type": "x"})
        assert result["persisted"] is True

    def test_publish_returns_redis_published_false_when_no_redis(
        self, tmp_path: Path
    ) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        result = hub.publish("mission-D", {"type": "y"})
        assert result["redis_published"] is False

    def test_replay_returns_empty_for_unknown_mission(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        assert hub.replay("no-such-mission") == []

    def test_replay_multiple_events(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        for i in range(4):
            hub.publish("mission-E", {"seq": i})
        events = hub.replay("mission-E")
        assert len(events) == 4
        assert events[2]["seq"] == 2

    def test_replay_limit_respected(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        for i in range(10):
            hub.publish("mission-F", {"seq": i})
        events = hub.replay("mission-F", limit=3)
        assert len(events) == 3

    def test_two_missions_are_isolated(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        hub.publish("mission-X", {"type": "for_x"})
        hub.publish("mission-Y", {"type": "for_y"})

        x_events = hub.replay("mission-X")
        y_events = hub.replay("mission-Y")

        assert all(e["type"] == "for_x" for e in x_events)
        assert all(e["type"] == "for_y" for e in y_events)
        assert len(x_events) == 1
        assert len(y_events) == 1

    def test_publish_redis_called_when_client_available(self, tmp_path: Path) -> None:
        hub = MissionEventHub(repo_root=tmp_path)
        mock_client = MagicMock()
        hub.redis._client = mock_client
        hub.redis.url = "redis://localhost:6379"  # mark as enabled

        hub.publish("mission-G", {"type": "redis_test"})

        mock_client.publish.assert_called_once()
