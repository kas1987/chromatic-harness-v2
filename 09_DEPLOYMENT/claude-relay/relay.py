"""Host-side relay: wraps `claude -p` so Docker containers can use the subscription CLI.

Security defaults:
  * Binds to 127.0.0.1 unless CLAUDE_RELAY_BIND is set explicitly.
  * Requires a bearer token via CLAUDE_RELAY_TOKEN; set CLAUDE_RELAY_DEV_MODE=true
    to allow unauthenticated use only during local development.
  * Enforces a configurable max request body size.
  * Restricts accepted models to an allowlist.
  * Does not expose debug/system information without authentication.
"""

import json
import hmac
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL_DEFAULT = "claude-haiku-4-5-20251001"

BIND_HOST = os.environ.get("CLAUDE_RELAY_BIND", "127.0.0.1")
RELAY_TOKEN = os.environ.get("CLAUDE_RELAY_TOKEN", "")  # pragma: allowlist secret
DEV_MODE = os.environ.get("CLAUDE_RELAY_DEV_MODE", "false").lower() == "true"
MAX_BODY_SIZE = int(os.environ.get("CLAUDE_RELAY_MAX_BODY_SIZE", "65536"))

_allowlist_raw = os.environ.get("CLAUDE_RELAY_MODEL_ALLOWLIST", "").strip()
MODEL_ALLOWLIST = set(_allowlist_raw.split(",")) if _allowlist_raw else {MODEL_DEFAULT}

# Resolve claude CLI — check env override first, then common Windows npm path, then PATH
_CLAUDE_CMD = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or os.path.expandvars(r"%APPDATA%\npm\claude.cmd")


def _unauthorized(handler: BaseHTTPRequestHandler, detail: str = "unauthorized") -> None:
    handler._send_json(401, {"error": detail})


def _forbidden(handler: BaseHTTPRequestHandler, detail: str = "forbidden") -> None:
    handler._send_json(403, {"error": detail})


def _authenticate(handler: BaseHTTPRequestHandler) -> bool:
    """Return True if the request is authenticated (or dev mode is enabled)."""
    if DEV_MODE:
        return True
    if not RELAY_TOKEN:
        return False
    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    return hmac.compare_digest(auth_header[len("Bearer ") :].strip(), RELAY_TOKEN)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # suppress default access log noise
        pass

    def _send_json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"ok": True})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/complete":
            self._send_json(404, {"error": "not found"})
            return

        if not _authenticate(self):
            return _unauthorized(self)

        content_length_str = self.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_str)
        except ValueError:
            self._send_json(400, {"error": "invalid Content-Length"})
            return

        if content_length > MAX_BODY_SIZE:
            self._send_json(413, {"error": f"request body exceeds {MAX_BODY_SIZE} bytes"})
            return
        if content_length < 0:
            self._send_json(400, {"error": "Content-Length must be non-negative"})
            return

        try:
            body = json.loads(self.rfile.read(content_length))
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"invalid JSON: {exc}"})
            return
        if not isinstance(body, dict):
            self._send_json(400, {"error": "request body must be a JSON object"})
            return

        prompt = body.get("prompt", "")
        model = body.get("model", MODEL_DEFAULT)
        system = body.get("system", "")

        if model not in MODEL_ALLOWLIST:
            self._send_json(403, {"error": f"model {model!r} is not in the relay allowlist"})
            return

        if not isinstance(prompt, str):
            self._send_json(400, {"error": "prompt must be a string"})
            return

        cmd = [_CLAUDE_CMD, "-p", prompt, "--output-format", "json", "--model", model]
        if system:
            if not isinstance(system, str):
                self._send_json(400, {"error": "system must be a string"})
                return
            cmd += ["--system-prompt", system]

        try:
            # Keep prompt and system text as argument boundaries on every platform.
            # Windows can launch .cmd files without handing user input to cmd.exe.
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=False)
            if result.returncode != 0:
                self._send_json(500, {"error": result.stderr[:500]})
                return
            data = json.loads(result.stdout)
            if data.get("is_error"):
                self._send_json(500, {"error": data.get("result", "claude error")})
                return
            self._send_json(
                200,
                {
                    "result": data.get("result", ""),
                    "usage": data.get("usage", {}),
                    "duration_ms": data.get("duration_ms", 0),
                },
            )
        except subprocess.TimeoutExpired:
            self._send_json(504, {"error": "claude CLI timed out"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})


def _main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    if not _CLAUDE_CMD or not os.path.exists(_CLAUDE_CMD):
        print("WARNING: claude CLI not found; relay will fail requests.", file=sys.stderr)
    if not DEV_MODE and not RELAY_TOKEN:
        print(
            "ERROR: CLAUDE_RELAY_TOKEN is required. Set CLAUDE_RELAY_DEV_MODE=true only for local development.",
            file=sys.stderr,
        )
        sys.exit(1)

    server = HTTPServer((BIND_HOST, port), Handler)
    print(f"Claude relay listening on {server.server_address[0]}:{server.server_address[1]}", file=sys.stderr)
    sys.stderr.flush()
    server.serve_forever()


if __name__ == "__main__":
    _main()
