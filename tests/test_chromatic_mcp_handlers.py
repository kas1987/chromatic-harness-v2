"""Tests for Chromatic MCP tool handlers (no MCP stdio)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_list_tool_specs_count():
    from chromatic_mcp.handlers import list_tool_specs

    specs = list_tool_specs()
    assert len(specs) >= 8
    names = {s["name"] for s in specs}
    assert "workflow_go" in names
    assert "auto_intake" in names


def test_call_tool_unknown():
    from chromatic_mcp.handlers import call_tool

    out = call_tool("not_a_tool", {})
    assert out["ok"] is False


def test_intake_queue_list_handler():
    from chromatic_mcp.handlers import intake_queue_list

    result = intake_queue_list()
    assert result["ok"] is True
    assert "count" in result


def test_workflow_go_audit_subprocess():
    from chromatic_mcp.handlers import workflow_go

    result = workflow_go("GO AUDIT")
    assert result["ok"] is True
    data = json.loads(result["stdout"].strip())
    assert data["mode"] == "GO AUDIT"


def test_call_tool_workflow_go():
    from chromatic_mcp.handlers import call_tool

    out = call_tool("workflow_go", {"mode": "GO AUDIT"})
    assert out["ok"] is True
    assert out["result"]["ok"] is True
