"""Mission event persistence + optional Redis pub/sub for multi-instance fanout."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "00_SOURCE_OF_TRUTH").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


@dataclass
class FileEventStore:
    root: Path

    def __post_init__(self) -> None:
        self.dir = self.root / "07_LOGS_AND_AUDIT" / "ws_events"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, mission_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in mission_id)
        return self.dir / f"{safe}.jsonl"

    def append(self, mission_id: str, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False, default=str)
        with self._path(mission_id).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def replay(self, mission_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        path = self._path(mission_id)
        if not path.is_file():
            return []
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        out: list[dict[str, Any]] = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out


class RedisEventBus:
    """Redis pub/sub bus; no-op when REDIS_URL unset or redis package missing."""

    def __init__(self, url: str | None = None, *, prefix: str = "chromatic:mission") -> None:
        self.url = url or os.environ.get("REDIS_URL", "").strip() or None
        self.prefix = prefix
        self._client = None
        self._pub = None

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def _channel(self, mission_id: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in mission_id)
        return f"{self.prefix}:{safe}"

    def _ensure_client(self) -> bool:
        if not self.url:
            return False
        if self._client is not None:
            return True
        try:
            import redis
        except ImportError:
            return False
        self._client = redis.from_url(self.url, decode_responses=True)
        return True

    def publish(self, mission_id: str, event: dict[str, Any]) -> bool:
        if not self._ensure_client():
            return False
        payload = json.dumps(event, ensure_ascii=False, default=str)
        self._client.publish(self._channel(mission_id), payload)
        return True

    def subscribe(
        self,
        mission_id: str,
        handler: Callable[[dict[str, Any]], None],
        *,
        global_channel: bool = False,
    ) -> None:
        if not self._ensure_client():
            return
        pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        channels = [self._channel(mission_id)]
        if global_channel:
            channels.append(f"{self.prefix}:all")
        pubsub.subscribe(*channels)
        for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            handler(data)


class MissionEventHub:
    """Append-only history + optional Redis fanout."""

    def __init__(self, repo_root: Path | None = None) -> None:
        root = repo_root or _repo_root()
        self.file = FileEventStore(root)
        self.redis = RedisEventBus()

    def publish(self, mission_id: str, event: dict[str, Any]) -> dict[str, Any]:
        record = {**event, "mission_id": mission_id}
        self.file.append(mission_id, record)
        redis_ok = self.redis.publish(mission_id, record)
        return {"persisted": True, "redis_published": redis_ok}

    def replay(self, mission_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.file.replay(mission_id, limit=limit)
