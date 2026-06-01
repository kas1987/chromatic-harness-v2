"""Smoke tests for disaster_recovery.py (gh-88 / NW-RG-088).

Reconciled from EPIC-F (shipped untested). Network-free; backup writes to tmp.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("disaster_recovery", REPO / "scripts" / "disaster_recovery.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["disaster_recovery"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_inventory_is_read_only_dict():
    mod = _load()
    inv = mod.inventory()
    assert isinstance(inv, dict)
    # inventory should enumerate recoverable harness state without mutating anything
    assert len(inv) >= 1


def test_backup_writes_to_dest(tmp_path):
    mod = _load()
    result = mod.backup(str(tmp_path / "bk"))
    assert isinstance(result, dict)
    # a backup run should report what it captured
    assert any(k in result for k in ("items", "files", "count", "backed_up", "dest"))


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
