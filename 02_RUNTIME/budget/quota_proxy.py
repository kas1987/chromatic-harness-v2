"""Transparent FAIL-OPEN reverse proxy for the Axis P quota signal.

Per TOKEN_ECONOMY_SPEC §4: a plain HTTP->HTTPS reverse proxy that listens on
``http://127.0.0.1:PORT`` and forwards every request verbatim to
``https://api.anthropic.com``. It is the verified-only deterministic source of
the weekly prepaid quota %. Point the harness at it with::

    export ANTHROPIC_BASE_URL=http://127.0.0.1:8788

On each response it scrapes the rate-limit headers

    anthropic-ratelimit-unified-7d-utilization
    anthropic-ratelimit-unified-5h-utilization
    anthropic-ratelimit-unified-7d-reset / -5h-reset
    anthropic-ratelimit-unified-status
    anthropic-ratelimit-unified-representative-claim

and writes ``~/.claude/powerline/usage/quota_state.json`` (the contract read by
:mod:`budget.quota_state`).

Design constraints:
  * FAIL-OPEN — the proxy NEVER blocks or mutates the API path. Any error in
    header scraping / state writing is swallowed; the response is forwarded
    untouched. A dead proxy must degrade to a missing/stale state file, caught
    downstream by the staleness guard, not to a broken API.
  * NO MITM CA — plain HTTP inbound, HTTPS outbound. No TLS interception, no
    certificate, no request-body inspection.
  * Source-abstracted — consumers read via ``quota_state.py`` and never import
    this module, so the producer can later swap to OTEL / statusline.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

UPSTREAM_HOST = "api.anthropic.com"
DEFAULT_PORT = 8788
DEFAULT_STATE_PATH = (
    Path.home() / ".claude" / "powerline" / "usage" / "quota_state.json"
)

# Header -> internal key. Header lookups are case-insensitive.
_H_7D_UTIL = "anthropic-ratelimit-unified-7d-utilization"
_H_5H_UTIL = "anthropic-ratelimit-unified-5h-utilization"
_H_7D_RESET = "anthropic-ratelimit-unified-7d-reset"
_H_5H_RESET = "anthropic-ratelimit-unified-5h-reset"
_H_STATUS = "anthropic-ratelimit-unified-status"
_H_CLAIM = "anthropic-ratelimit-unified-representative-claim"

# Hop-by-hop headers must not be forwarded (RFC 7230 §6.1).
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


def _get_ci(headers: Any, name: str) -> str | None:
    """Case-insensitive header lookup against an email.Message-like object."""
    try:
        # http.client.HTTPResponse.getheader is case-insensitive.
        if hasattr(headers, "getheader"):
            return headers.getheader(name)
        if hasattr(headers, "get"):
            return headers.get(name)
    except Exception:  # noqa: BLE001 — fail-open
        return None
    return None


def _to_pct(value: str | None) -> float | None:
    """Parse a utilization header (e.g. ``"0.42"`` or ``"42"``) into a percent."""
    if value is None:
        return None
    try:
        num = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None
    # Headers may be a fraction (0..1) or already a percent (0..100).
    return round(num * 100.0, 4) if num <= 1.0 else round(num, 4)


def parse_quota_headers(headers: Any) -> dict[str, Any]:
    """Build a ``quota_state.json`` record from response headers.

    Pure + fail-open: unknown/missing headers map to ``None``. Used by the
    proxy and exercised directly by the smoke test (no live socket needed).
    """
    return {
        "weekly_pct": _to_pct(_get_ci(headers, _H_7D_UTIL)),
        "weekly_reset": _get_ci(headers, _H_7D_RESET),
        "session_5h_pct": _to_pct(_get_ci(headers, _H_5H_UTIL)),
        "session_5h_reset": _get_ci(headers, _H_5H_RESET),
        "representative_claim": _get_ci(headers, _H_CLAIM),
        "status": _get_ci(headers, _H_STATUS),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "proxy",
    }


def write_quota_state(record: dict[str, Any], path: Path | None = None) -> bool:
    """Atomically write the quota state. Fail-open: returns False, never raises."""
    target = path or DEFAULT_STATE_PATH
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        tmp.replace(target)
        return True
    except OSError:
        return False


def _has_any_signal(record: dict[str, Any]) -> bool:
    return any(
        record.get(k) is not None
        for k in ("weekly_pct", "session_5h_pct", "status", "representative_claim")
    )


class QuotaProxyHandler(BaseHTTPRequestHandler):
    """Forward every method to the upstream over HTTPS, scrape, never block."""

    protocol_version = "HTTP/1.1"
    state_path: Path = DEFAULT_STATE_PATH

    # Quiet the default stderr access log; keep one-line errors only.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
        return

    def _proxy(self) -> None:
        body = b""
        length = self.headers.get("Content-Length")
        if length:
            try:
                body = self.rfile.read(int(length))
            except (ValueError, OSError):
                body = b""

        # Forward request headers minus hop-by-hop; force upstream Host.
        fwd_headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
        }
        fwd_headers["Host"] = UPSTREAM_HOST

        try:
            conn = http.client.HTTPSConnection(UPSTREAM_HOST, timeout=120)
            conn.request(
                self.command, self.path, body=body or None, headers=fwd_headers
            )
            resp = conn.getresponse()
            resp_body = resp.read()
        except Exception as exc:  # noqa: BLE001 — fail-open upstream error
            self._send_gateway_error(exc)
            return

        # Best-effort scrape — must never affect what the client receives.
        try:
            record = parse_quota_headers(resp)
            if _has_any_signal(record):
                write_quota_state(record, self.state_path)
        except Exception:  # noqa: BLE001 — fail-open
            pass

        # Relay the upstream response verbatim.
        try:
            self.send_response(resp.status, resp.reason)
            for key, value in resp.getheaders():
                if key.lower() in _HOP_BY_HOP or key.lower() == "content-length":
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _send_gateway_error(self, exc: Exception) -> None:
        payload = json.dumps(
            {
                "type": "error",
                "error": {"type": "proxy_upstream_error", "message": str(exc)},
            }
        ).encode("utf-8")
        try:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except OSError:
            pass

    # All HTTP methods route through the single transparent forwarder.
    do_GET = _proxy
    do_POST = _proxy
    do_PUT = _proxy
    do_DELETE = _proxy
    do_PATCH = _proxy
    do_HEAD = _proxy
    do_OPTIONS = _proxy


def build_server(
    port: int = DEFAULT_PORT,
    *,
    host: str = "127.0.0.1",
    state_path: Path | None = None,
) -> ThreadingHTTPServer:
    """Construct (but do not start) the threading proxy server."""
    handler = type(
        "BoundQuotaProxyHandler",
        (QuotaProxyHandler,),
        {"state_path": state_path or DEFAULT_STATE_PATH},
    )
    return ThreadingHTTPServer((host, port), handler)


def serve(
    port: int = DEFAULT_PORT,
    *,
    host: str = "127.0.0.1",
    state_path: Path | None = None,
) -> None:
    """Run the proxy until interrupted (blocking)."""
    server = build_server(port, host=host, state_path=state_path)
    bound_host, bound_port = server.server_address[:2]
    sys.stderr.write(
        f"[quota_proxy] forwarding http://{bound_host}:{bound_port} "
        f"-> https://{UPSTREAM_HOST} (fail-open)\n"
    )
    sys.stderr.write(
        f"[quota_proxy] export ANTHROPIC_BASE_URL=http://{bound_host}:{bound_port}\n"
    )
    thread = threading.current_thread()
    thread.name = "quota-proxy"
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = int(os.environ.get("QUOTA_PROXY_PORT", DEFAULT_PORT))
    if argv:
        try:
            port = int(argv[0])
        except ValueError:
            sys.stderr.write(f"[quota_proxy] invalid port: {argv[0]!r}\n")
            return 2
    serve(port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
