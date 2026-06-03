"""Verify Router vs Orchestrator boundary (bead u8uj.4).

Orchestrator must NOT import ChromaticRouter, RouteRequest, or router contracts
at module level — that coupling belongs in api/main.py._route_for_mission().
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RUNTIME = _HERE.parent / "02_RUNTIME"

ORCH_PATH = _RUNTIME / "orchestrator" / "orchestrator.py"
API_PATH = _RUNTIME / "api" / "main.py"


def _top_level_imports(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    return [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) and n.col_offset == 0]


def test_orchestrator_no_top_level_router_imports():
    imports = _top_level_imports(ORCH_PATH)
    router_imports = [i for i in imports if "router" in i]
    assert router_imports == [], f"Orchestrator must not import router at module level; found: {router_imports}"


def test_orchestrator_has_no_route_to_provider():
    src = ORCH_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    method_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert "route_to_provider" not in method_names, (
        "Orchestrator.route_to_provider() was removed — routing belongs in api/main.py._route_for_mission()"
    )


def test_api_has_route_for_mission_helper():
    src = API_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    assert "_route_for_mission" in fn_names, (
        "api/main.py must define _route_for_mission() to own the routing→mission composition"
    )


def test_route_for_mission_is_async():
    src = API_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    async_fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)}
    assert "_route_for_mission" in async_fns
