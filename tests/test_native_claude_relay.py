"""Tests for native_claude_relay.py (B2 acceptance criteria)."""

import http.client
import http.server
import json
import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Import the relay module
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "scripts"))
import native_claude_relay as relay
from native_claude_relay import _ThreadingHTTPServer


# ── Helpers ──────────────────────────────────────────────────────────────────


def start_relay_server(port: int):
    server = _ThreadingHTTPServer(("127.0.0.1", port), relay.RelayHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)
    return server


def http_get(port, path, timeout=5):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = json.loads(resp.read())
    conn.close()
    return resp.status, body


def http_post(port, body: dict | bytes, timeout=10):
    if isinstance(body, dict):
        data = json.dumps(body).encode()
    else:
        data = body
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("POST", "/complete", body=data, headers={"Content-Length": str(len(data))})
    resp = conn.getresponse()
    result = json.loads(resp.read())
    conn.close()
    return resp.status, result


# ── /health ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def health_server():
    server = start_relay_server(19090)
    yield 19090
    server.shutdown()


def test_health_returns_200(health_server):
    status, body = http_get(health_server, "/health")
    assert status == 200
    assert body["status"] == "ok"


def test_unknown_path_returns_404(health_server):
    status, _ = http_get(health_server, "/unknown")
    assert status == 404


# ── /complete ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def complete_server():
    server = start_relay_server(19091)
    yield 19091
    server.shutdown()


def test_missing_prompt_returns_400(complete_server):
    status, body = http_post(complete_server, {"model": "claude-sonnet-4-6"})
    assert status == 400
    assert "error" in body


def test_invalid_json_returns_400(complete_server):
    data = b"not json"
    conn = http.client.HTTPConnection("127.0.0.1", complete_server, timeout=5)
    conn.request("POST", "/complete", body=data, headers={"Content-Length": str(len(data))})
    resp = conn.getresponse()
    resp.read()
    conn.close()
    assert resp.status == 400


def test_successful_complete_returns_result_shape(complete_server):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Hello, world!"
    mock_result.stderr = ""

    with patch("native_claude_relay.subprocess.run", return_value=mock_result):
        status, body = http_post(complete_server, {"prompt": "Say hello", "model": "claude-sonnet-4-6"})

    assert status == 200
    assert body["result"] == "Hello, world!"
    assert body["model"] == "claude-sonnet-4-6"
    assert isinstance(body["latency_ms"], int)


def test_cli_nonzero_exit_returns_500(complete_server):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "authentication failed"

    with patch("native_claude_relay.subprocess.run", return_value=mock_result):
        status, body = http_post(complete_server, {"prompt": "hello"})

    assert status == 500
    assert "error" in body


def test_cli_not_found_returns_500(complete_server):
    with patch("native_claude_relay.subprocess.run", side_effect=FileNotFoundError("claude not found")):
        status, body = http_post(complete_server, {"prompt": "hello"})

    assert status == 500
    assert "not found" in body["error"].lower()


def test_timeout_returns_500(complete_server):
    with patch("native_claude_relay.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60)):
        status, body = http_post(complete_server, {"prompt": "hello"})

    assert status == 500
    assert "timed out" in body["error"].lower()


def test_system_prompt_included_in_cmd(complete_server):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "response"
    mock_result.stderr = ""

    with patch("native_claude_relay.subprocess.run", return_value=mock_result) as mock_run:
        http_post(complete_server, {"prompt": "hello", "model": "claude-sonnet-4-6", "system": "Be concise."})
        cmd = mock_run.call_args[0][0]
        assert "--system" in cmd
        assert "Be concise." in cmd
