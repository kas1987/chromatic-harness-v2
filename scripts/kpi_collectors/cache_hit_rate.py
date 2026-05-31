"""Cache hit rate collector — reads from unified_guard latest.json."""

import json
import pathlib


def collect():
    guard_path = (
        pathlib.Path(__file__).parents[2]
        / "07_LOGS_AND_AUDIT"
        / "unified_guard"
        / "latest.json"
    )
    if not guard_path.exists():
        return {"status": "not_instrumented"}
    try:
        data = json.loads(guard_path.read_text(encoding="utf-8"))
        rate = data.get("cache_hit_rate")
        if rate is None:
            return {"status": "not_instrumented"}
        return {"cache_hit_rate": rate, "status": "ok"}
    except Exception:
        return {"status": "not_instrumented"}


if __name__ == "__main__":
    print(json.dumps(collect()))
