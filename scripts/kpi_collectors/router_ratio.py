"""Router ratio collector — stub until routing telemetry is instrumented."""

import json


def collect():
    return {"status": "not_instrumented"}


if __name__ == "__main__":
    print(json.dumps(collect()))
