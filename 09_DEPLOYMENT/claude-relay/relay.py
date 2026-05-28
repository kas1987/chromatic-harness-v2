"""Host-side relay: wraps `claude -p` so Docker containers can use the subscription CLI."""

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
MODEL_DEFAULT = "claude-haiku-4-5-20251001"

# Resolve claude CLI — check env override first, then common Windows npm path, then PATH
import os, shutil as _shutil

_CLAUDE_CMD = (
    os.environ.get("CLAUDE_BIN")
    or _shutil.which("claude")
    or os.path.expandvars(r"%APPDATA%\npm\claude.cmd")
)


class Handler(BaseHTTPRequestHandler):
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
        elif self.path == "/debug":
            import os as _os

            self._send_json(
                200,
                {
                    "claude_cmd": _CLAUDE_CMD,
                    "platform": sys.platform,
                    "appdata": _os.environ.get("APPDATA", ""),
                    "exists": bool(_CLAUDE_CMD and _os.path.exists(_CLAUDE_CMD)),
                },
            )
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/complete":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        prompt = body.get("prompt", "")
        model = body.get("model", MODEL_DEFAULT)
        system = body.get("system", "")

        cmd = [_CLAUDE_CMD, "-p", prompt, "--output-format", "json", "--model", model]
        if system:
            cmd += ["--system-prompt", system]

        try:
            # Windows requires shell=True for .cmd files; also needs a string not a list
            if sys.platform == "win32":
                run_cmd = subprocess.list2cmdline(cmd)
                run_shell = True
            else:
                run_cmd = cmd
                run_shell = False
            result = subprocess.run(
                run_cmd, capture_output=True, text=True, timeout=120, shell=run_shell
            )
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


if __name__ == "__main__":
    # Bind to 0.0.0.0 so Docker containers can reach via host.docker.internal
    print(f"Claude relay listening on 0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
