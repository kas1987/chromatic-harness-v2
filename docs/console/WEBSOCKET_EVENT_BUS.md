# WebSocket Event Bus (Persistence + Multi-Instance)

Phase 6.5 WebSocket streams magnet events. This layer adds **JSONL persistence** (replay) and optional **Redis pub/sub** (horizontal scale).

## Single instance

1. `MissionEventBus.publish()` writes `07_LOGS_AND_AUDIT/ws_events/<mission>.jsonl`
2. `WebSocketManager` replays last 50 events on connect, then streams live events
3. `GET /missions/:id/events/replay` via `ConsoleServer.handleReplayEvents()`

## Multi-instance (Redis)

| Env | Purpose |
|-----|---------|
| `REDIS_URL` | e.g. `redis://localhost:6379/0` |
| `CONSOLE_INSTANCE_URLS` | Comma-separated Console API bases |

1. Each instance publishes to Redis on `chromatic:mission:<id>` (Python hub)
2. Run fanout worker:

```bash
python scripts/ws_redis_fanout.py
```

3. Worker POSTs events to each instance `POST /internal/events` → local WebSocket broadcast

Use **sticky sessions** on the load balancer for WebSocket upgrades; Redis handles cross-instance event propagation.

## CLI

```bash
python scripts/ws_publish_event.py --mission-id CHR-001 --type magnet_event --data '{"score":0.8}'
```

## Load balancer notes

- nginx: `proxy_http_version 1.1`, `Upgrade`, `Connection "upgrade"`, `ip_hash` or sticky cookie
- Without Redis: each instance only sees its own connections; replay still works per instance from JSONL
