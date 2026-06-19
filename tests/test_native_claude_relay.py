"""Tests for native_claude_relay.py (B2 acceptance criteria)."""

import http.client
import json
import os
import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Import the relay module
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "scripts"))
import native_claude_relay as relay


# ── Helpers ──────────────────────────────────────────────────────────────────

def start_relay_server(port: int):
    server = http.server.HTTPServer(("127.0.0.1", port), relay.RelayHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)  # let the server bind
    return server


import http.server


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def setup_method(self):
        self.port = 19090
        self.server = start_relay_server(self.port)

    def teardown_method(self):
        self.server.shutdown()

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = json.loads(resp.read())
        conn.close()
        return resp.status, body

    def test_health_returns_200(self):
        status, body = self._get("/health")
        assert status == 200
        assert body["status"] == "ok"

    def test_unknown_path_returns_404(self):
        status, _ = self._get("/unknown")
        assert status == 404


# ── /complete ─────────────────────────────────────────────────────────────────

class TestComplete:
    def setup_method(self):
        self.port = 19091
        self.server = start_relay_server(self.port)

    def teardown_method(self):
        self.server.shutdown()

    def _post(self, body: dict):
        data = json.dumps(body).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/complete", body=data, headers={"Content-Length": str(len(data))})
        resp = conn.getresponse()
        result = json.loads(resp.read())
        conn.close()
        return resp.status, result

    def test_missing_prompt_returns_400(self):
        status, body = self._post({"model": "claude-sonnet-4-6"})
        assert status == 400
        assert "error" in body

    def test_invalid_json_returns_400(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        bad = b"not json"
        conn.request("POST", "/complete", body=bad, headers={"Content-Length": str(len(bad))})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_successful_complete_returns_result_shape(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello, world!"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            status, body = self._post({"prompt": "Say hello", "model": "claude-sonnet-4-6"})

        assert status == 200
        assert body["result"] == "Hello, world!"
        assert body["model"] == "claude-sonnet-4-6"
        assert isinstance(body["latency_ms"], int)

    def test_cli_nonzero_exit_returns_500(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "authentication failed"

        with patch("subprocess.run", return_value=mock_result):
            status, body = self._post({"prompt": "hello"})

        assert status == 500
        assert "error" in body

    def test_cli_not_found_returns_500(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("claude not found")):
            status, body = self._post({"prompt": "hello"})

        assert status == 500
        assert "not found" in body["error"].lower()

    def test_timeout_returns_500(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60)):
            status, body = self._post({"prompt": "hello"})

        assert status == 500
        assert "timed out" in body["error"].lower()

    def test_system_prompt_included_in_cmd(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "response"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            self._post({"prompt": "hello", "model": "claude-sonnet-4-6", "system": "Be concise."})
            cmd = mock_run.call_args[0][0]
            assert "--system" in cmd
            assert "Be concise." in cmd
