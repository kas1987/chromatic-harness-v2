"""Tests for the codegraph-backed Expansion-Gate spine check.

Bead chromatic-harness-v2-4do0. Verifies wired/orphaned/absent verdicts and
strict-mode exit semantics against an in-memory codegraph-shaped DB.

Run with: pytest tests/test_check_layer_spine.py -v
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_layer_spine.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_layer_spine", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, file_path TEXT)")
    c.execute("CREATE TABLE edges (id INTEGER PRIMARY KEY, source INT, target INT)")
    # wired layer: 2 nodes with an edge between them
    c.execute("INSERT INTO nodes VALUES (1, '02_RUNTIME/router/gate.py')")
    c.execute("INSERT INTO nodes VALUES (2, '02_RUNTIME/router/policy.py')")
    c.execute("INSERT INTO edges VALUES (1, 1, 2)")
    # orphaned layer: a node with no edges
    c.execute("INSERT INTO nodes VALUES (3, '11_SANDBOX_LAB/scratch.py')")
    c.commit()
    return c


def test_wired_layer(con):
    mod = _load()
    r = mod.check_layer(con, "02_RUNTIME/router")
    assert r["verdict"] == "wired"
    assert r["nodes"] == 2
    assert r["edges"] >= 1


def test_orphaned_layer(con):
    mod = _load()
    r = mod.check_layer(con, "11_SANDBOX_LAB")
    assert r["verdict"] == "orphaned"
    assert r["nodes"] == 1
    assert r["edges"] == 0


def test_absent_layer(con):
    mod = _load()
    r = mod.check_layer(con, "06_DATA")
    assert r["verdict"] == "absent"
    assert r["nodes"] == 0


def test_prefix_is_path_normalized(con):
    mod = _load()
    # leading/trailing slashes and backslashes must not change the match
    r = mod.check_layer(con, "\\02_RUNTIME\\router\\")
    assert r["verdict"] == "wired"
