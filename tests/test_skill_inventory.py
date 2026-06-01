"""Smoke tests for skill_inventory.py (gh-83 / NW-RG-083).

Reconciled from EPIC-B (shipped untested). Network-free.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("skill_inventory", REPO / "scripts" / "skill_inventory.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["skill_inventory"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_generate_inventory_shape():
    mod = _load()
    inv = mod.generate_inventory()
    assert inv["harness_component"] == "skill_inventory"
    summary = inv["summary"]
    assert {"total_skills", "used_skills", "never_used", "deprecation_candidates"} <= set(summary)
    assert isinstance(inv["skills"], list)


def test_inventory_counts_consistent():
    mod = _load()
    inv = mod.generate_inventory()
    s = inv["summary"]
    assert s["total_skills"] >= s["used_skills"] >= 0
    assert s["never_used"] == s["total_skills"] - s["used_skills"]


def test_inventory_custom_root(tmp_path):
    mod = _load()
    sk = tmp_path / "skills" / "demo"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("# demo skill", encoding="utf-8")
    inv = mod.generate_inventory(roots=[tmp_path / "skills"])
    assert inv["summary"]["total_skills"] >= 1


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
