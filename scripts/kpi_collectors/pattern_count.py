"""Pattern count KPI collector — reads .agents/patterns/ and counts by type."""

import json
import pathlib


def collect():
    patterns_dir = pathlib.Path(__file__).parents[2] / ".agents" / "patterns"
    if not patterns_dir.exists():
        return {"status": "not_instrumented"}

    counts = {"pattern": 0, "anti-pattern": 0, "principle": 0}

    for md_path in patterns_dir.glob("*.md"):
        if md_path.name in ("SCHEMA.md",):
            continue
        name = md_path.name
        if name.startswith("anti_pattern-"):
            counts["anti-pattern"] += 1
        elif name.startswith("principle-"):
            counts["principle"] += 1
        elif name.startswith("pattern-"):
            counts["pattern"] += 1

    return {
        "pattern_count": counts["pattern"],
        "anti_pattern_count": counts["anti-pattern"],
        "principle_count": counts["principle"],
        "status": "ok",
    }


if __name__ == "__main__":
    print(json.dumps(collect()))
