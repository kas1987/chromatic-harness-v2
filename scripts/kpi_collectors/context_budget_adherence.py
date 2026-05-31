"""Context budget adherence collector — stub until budget tracking is instrumented."""

import json


def collect():
    return {"status": "not_instrumented"}


if __name__ == "__main__":
    print(json.dumps(collect()))
