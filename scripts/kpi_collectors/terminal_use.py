"""Terminal use collector — fraction of recent sessions with low bash/tool call counts."""

import json
import pathlib

WINDOW = 7
LOW_THRESHOLD = 5


def collect():
    telemetry_path = (
        pathlib.Path(__file__).parents[2] / "05_REPORTS" / "telemetry.jsonl"
    )
    if not telemetry_path.exists():
        return {"status": "not_instrumented"}

    records = []
    try:
        for line in telemetry_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return {"status": "not_instrumented"}

    # Take last WINDOW records
    recent = records[-WINDOW:]
    if not recent:
        return {"status": "not_instrumented"}

    # Check if any record has bash_calls or tool_calls field
    instrumented = [r for r in recent if "bash_calls" in r or "tool_calls" in r]
    if not instrumented:
        return {"status": "not_instrumented"}

    low_count = sum(
        1
        for r in instrumented
        if (r.get("bash_calls", 0) + r.get("tool_calls", 0)) < LOW_THRESHOLD
    )
    pct = round(low_count / len(instrumented) * 100, 1)
    return {
        "terminal_use_low_pct": pct,
        "window": len(instrumented),
        "low_threshold": LOW_THRESHOLD,
        "status": "ok",
    }


if __name__ == "__main__":
    print(json.dumps(collect()))
