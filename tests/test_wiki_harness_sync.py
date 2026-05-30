"""Wiki EPIC-0001 ↔ Harness sync map checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SYNC = REPO / "config" / "wiki_harness_sync.yaml"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "check_wiki_harness_sync",
        REPO / "scripts" / "check_wiki_harness_sync.py",
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_sync_yaml_exists():
    assert SYNC.is_file()


def test_wiki_tasks_cover_wk_002_through_020():
    import yaml

    data = yaml.safe_load(SYNC.read_text(encoding="utf-8"))
    wks = {row["wk"] for row in data["wiki_tasks"]}
    for n in range(2, 21):
        assert f"WK-{n:03d}" in wks


def test_route_tasks_match_harness_export():
    mod = _load_module()
    report = mod.run(github=False, strict=False)
    assert report["beads_loaded"] >= 1
    assert len(report["route_checks"]) == 8
    drift = [r for r in report["route_checks"] if not r["ok"]]
    assert drift == [], drift
