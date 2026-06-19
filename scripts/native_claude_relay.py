#!/usr/bin/env python3
"""
native_claude_relay.py — Localhost HTTP relay for Claude Code CLI on Windows.

Exposes:
  GET  /health   → {"status": "ok"}
  POST /complete → {"result": "<text>", "model": "<model>", "latency_ms": N}
               or {"error": "<message>"} on failure

Binds to 127.0.0.1 only (security: localhost-only, no auth needed).
Port: NATIVE_CLAUDE_RELAY_PORT env var, default 9090.
Timeout: NATIVE_CLAUDE_RELAY_TIMEOUT_S env var, default 60.
"""

import http.server
import json
import os
import socketserver
import subprocess
import sys
import time


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


PORT = int(os.environ.get("NATIVE_CLAUDE_RELAY_PORT", "9090"))
TIMEOUT_S = int(os.environ.get("NATIVE_CLAUDE_RELAY_TIMEOUT_S", "60"))


class RelayHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access log noise
        pass

    def _send_json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/complete":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self._send_json(400, {"error": f"invalid JSON: {e}"})
            return

        prompt = body.get("prompt", "")
        model = body.get("model", "claude-sonnet-4-6")
        system = body.get("system", "")

        if not prompt:
            self._send_json(400, {"error": "prompt is required"})
            return

        cmd = ["claude", "-p", prompt, "--model", model]
        if system:
            cmd += ["--system", system]

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            self._send_json(500, {"error": f"claude CLI timed out after {TIMEOUT_S}s"})
            return
        except FileNotFoundError:
            self._send_json(500, {"error": "claude CLI not found on PATH"})
            return
        except Exception as e:
            self._send_json(500, {"error": str(e)})
            return

        latency_ms = int((time.monotonic() - t0) * 1000)

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            self._send_json(500, {"error": f"claude CLI exited {result.returncode}: {err}"})
            return

        self._send_json(
            200,
            {
                "result": result.stdout.strip(),
                "model": model,
                "latency_ms": latency_ms,
            },
        )


def main():
    server = _ThreadingHTTPServer(("127.0.0.1", PORT), RelayHandler)
    print(f"native_claude_relay: listening on http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nnative_claude_relay: shutting down", flush=True)


if __name__ == "__main__":
    main()
