"""Test pyramid ratio analysis (unit / integration / e2e)."""

from __future__ import annotations

import re
from typing import Any, TypedDict

DEFAULT_PYRAMID_TARGETS = {"unit": 0.7, "integration": 0.2, "e2e": 0.1}

def _is_e2e(blob: str, path: str) -> bool:
    b = blob.lower()
    if re.search(r"[/\\]e2e[/\\]", path, re.I):
        return True
    return any(
        token in b
        for token in ("e2e", "end-to-end", "end_to_end", "playwright", "cypress", "selenium", "browser")
    )


def _is_integration(blob: str, path: str) -> bool:
    b = blob.lower()
    if re.search(r"[/\\]integration[/\\]", path, re.I):
        return True
    return any(
        token in b
        for token in ("integration", "api_test", "api-test", "contract_test", "contract-test")
    )


class TestLayer:
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"


def classify_test(test: dict[str, Any]) -> str:
    layer = test.get("layer")
    if layer in ("unit", "integration", "e2e"):
        return layer
    name = test.get("test_name") or test.get("name") or ""
    path = test.get("suite_path") or test.get("path") or ""
    blob = f"{path} {name}"
    if _is_e2e(blob, path):
        return TestLayer.E2E
    if _is_integration(blob, path):
        return TestLayer.INTEGRATION
    return TestLayer.UNIT


def analyze_test_pyramid(
    results: list[dict[str, Any]],
    targets: dict[str, float] | None = None,
    *,
    warn_threshold: float = 0.15,
    error_threshold: float = 0.25,
) -> dict[str, Any]:
    tgt = targets or dict(DEFAULT_PYRAMID_TARGETS)
    active = [t for t in results if t.get("status") != "skip"]
    counts = {"unit": 0, "integration": 0, "e2e": 0}
    for test in active:
        counts[classify_test(test)] += 1

    total = len(active)
    ratios = {k: (counts[k] / total if total else 0.0) for k in counts}
    deviations = {k: abs(ratios[k] - tgt[k]) for k in counts}
    max_deviation = max(deviations.values()) if deviations else 0.0
    warnings: list[str] = []

    if total == 0:
        warnings.append("Test pyramid: no runnable tests to classify")
        return {
            "total": 0,
            "counts": counts,
            "ratios": ratios,
            "targets": tgt,
            "deviations": deviations,
            "max_deviation": 0.0,
            "warnings": warnings,
            "balanced": False,
        }

    def pct(n: float) -> str:
        return f"{n * 100:.0f}%"

    for layer in ("unit", "integration", "e2e"):
        dev = deviations[layer]
        actual = ratios[layer]
        target = tgt[layer]
        if dev >= error_threshold:
            warnings.append(
                f"Test pyramid imbalance ({layer}): actual {pct(actual)} vs target {pct(target)} (Δ {pct(dev)})"
            )
        elif dev >= warn_threshold:
            warnings.append(
                f"Test pyramid drift ({layer}): actual {pct(actual)} vs target {pct(target)}"
            )

    if counts["e2e"] > counts["unit"] and total >= 3:
        warnings.append("Test pyramid inverted: more e2e than unit tests")

    return {
        "total": total,
        "counts": counts,
        "ratios": ratios,
        "targets": tgt,
        "deviations": deviations,
        "max_deviation": max_deviation,
        "warnings": warnings,
        "balanced": len(warnings) == 0,
    }
