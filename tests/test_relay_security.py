"""Security tests for the Claude relay.

Avoids subprocess by running the relay Handler in a thread-bound HTTPServer.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import threading
from pathlib import Path

import pytest

RELAY_PATH = Path(__file__).resolve().parents[1] / "09_DEPLOYMENT" / "claude-relay" / "relay.py"


def _load_relay_module():
    spec = importlib.util.spec_from_file_location("relay", RELAY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fresh_relay(env: dict):
    """Load relay module with patched env and return (server, port)."""
    merged = {**os.environ, **env}
    old_environ = os.environ.copy()
    try:
        os.environ.update(merged)
        mod = _load_relay_module()
    finally:
        os.environ.clear()
        os.environ.update(old_environ)
    return mod


@pytest.fixture
def relay_server():
    """Yield a running HTTPServer on an ephemeral port."""
    # Default fixture: dev mode, default allowlist
    mod = _fresh_relay({"CLAUDE_RELAY_DEV_MODE": "true"})
    server = mod.HTTPServer(("127.0.0.1", 0), mod.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _request(server, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port)
    data = json.dumps(body).encode() if body is not None else b""
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    if data:
        merged_headers["Content-Length"] = str(len(data))
    conn.request(method, path, body=data, headers=merged_headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {"raw": raw.decode()}
    return resp.status, payload


def test_relay_health_no_auth(relay_server):
    status, body = _request(relay_server, "GET", "/health")
    assert status == 200
    assert body["ok"] is True


def test_relay_complete_requires_auth_without_dev_mode():
    mod = _fresh_relay({"CLAUDE_RELAY_TOKEN": "test-token-123"})
    server = mod.HTTPServer(("127.0.0.1", 0), mod.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(server, "POST", "/complete", body={"prompt": "hi"})
        assert status == 401
        assert "error" in body
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_relay_complete_accepts_valid_token():
    mod = _fresh_relay({"CLAUDE_RELAY_TOKEN": "test-token-123"})
    server = mod.HTTPServer(("127.0.0.1", 0), mod.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(
            server,
            "POST",
            "/complete",
            body={"prompt": "hi", "model": "claude-haiku-4-5-20251001"},
            headers={"Authorization": "Bearer test-token-123"},
        )
        # We expect a claude-not-found or timeout error, but never 401/403.
        assert status != 401
        assert status != 403
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_relay_rejects_unknown_model():
    mod = _fresh_relay({"CLAUDE_RELAY_DEV_MODE": "true"})
    server = mod.HTTPServer(("127.0.0.1", 0), mod.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(
            server,
            "POST",
            "/complete",
            body={"prompt": "hi", "model": "unlisted-model"},
        )
        assert status == 403
        assert "allowlist" in body.get("error", "")
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_relay_rejects_oversized_body():
    mod = _fresh_relay({"CLAUDE_RELAY_DEV_MODE": "true", "CLAUDE_RELAY_MAX_BODY_SIZE": "16"})
    server = mod.HTTPServer(("127.0.0.1", 0), mod.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(server, "POST", "/complete", body={"prompt": "this is too long"})
        assert status == 413
    finally:
        server.shutdown()
        thread.join(timeout=5)
