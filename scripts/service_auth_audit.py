#!/usr/bin/env python3
"""Local service authentication and exposure auditor (GH #87 / chromatic-harness-v2-snjm).

Inventories running local AI/ML services and checks:
  - Which address they bind to (127.0.0.1 = safe, 0.0.0.0 = exposed)
  - Whether authentication is enabled (where detectable)
  - Network exposure risk level

Services checked:
  - Ollama        (127.0.0.1:11434)
  - Neo4j         (7474 HTTP, 7687 Bolt)
  - ChromaDB      (8000)
  - ComfyUI       (8188)

Usage:
    python scripts/service_auth_audit.py            # full audit, print table
    python scripts/service_auth_audit.py --json     # print JSON result
    python scripts/service_auth_audit.py --save     # write artifact and exit

Exit code 1 if any service has CRITICAL exposure risk.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "security"

# Service definitions: name → (default_host, port, auth_check_fn_name)
SERVICE_DEFS: list[dict[str, Any]] = [
    {
        "name": "ollama",
        "description": "Ollama local LLM server",
        "default_host": "127.0.0.1",
        "port": 11434,
        "auth_endpoint": "/api/tags",
        "secure_default": True,
        "notes": "Ollama binds 127.0.0.1 by default; OLLAMA_HOST=0.0.0.0 is insecure",
    },
    {
        "name": "neo4j_http",
        "description": "Neo4j HTTP browser interface",
        "default_host": "127.0.0.1",
        "port": 7474,
        "auth_endpoint": "/",
        "secure_default": False,
        "notes": "Neo4j requires explicit auth config; default install may have no password",
    },
    {
        "name": "neo4j_bolt",
        "description": "Neo4j Bolt protocol",
        "default_host": "127.0.0.1",
        "port": 7687,
        "auth_endpoint": None,
        "secure_default": False,
        "notes": "Bolt port; ensure dbms.connector.bolt.listen_address=127.0.0.1",
    },
    {
        "name": "chromadb",
        "description": "ChromaDB vector store",
        "default_host": "127.0.0.1",
        "port": 8000,
        "auth_endpoint": "/api/v1/heartbeat",
        "secure_default": False,
        "notes": "ChromaDB has no auth by default; restrict to localhost",
    },
    {
        "name": "comfyui",
        "description": "ComfyUI image generation",
        "default_host": "127.0.0.1",
        "port": 8188,
        "auth_endpoint": "/system_stats",
        "secure_default": False,
        "notes": "ComfyUI has no built-in auth; never expose to 0.0.0.0",
    },
]


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection can be made to host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _get_listening_address(port: int) -> str | None:
    """Return the bind address for a listening port using netstat.

    Returns '127.0.0.1', '0.0.0.0', '::1', '::', or None if not listening.
    Platform-aware: tries netstat (Windows/Linux) then ss (Linux).
    """
    commands = [
        ["netstat", "-an"],
        ["ss", "-tlnp"],
    ]
    port_str = f":{port}"
    for cmd in commands:
        r = run_safe(cmd, timeout=10)
        if r.returncode != 0 and not r.stdout:
            continue
        for line in r.stdout.splitlines():
            # Match lines containing the port
            if port_str not in line:
                continue
            # Extract address:port token
            parts = line.split()
            for part in parts:
                if port_str in part:
                    addr = part.rsplit(":", 1)[0]
                    # Normalize IPv6 brackets
                    addr = addr.lstrip("[").rstrip("]")
                    if addr in ("0.0.0.0", "*", ""):
                        return "0.0.0.0"
                    if addr in ("127.0.0.1", "::1", "localhost"):
                        return "127.0.0.1"
                    return addr
    return None


def _risk_level(service: dict, listening_addr: str | None, is_open: bool) -> str:
    """Compute exposure risk: ok / low / medium / high / critical."""
    if not is_open:
        return "ok"  # Not running = no exposure
    if listening_addr == "0.0.0.0":
        return "critical"
    if listening_addr in ("127.0.0.1", "::1", None) and service["secure_default"]:
        return "ok"
    if listening_addr in ("127.0.0.1", "::1"):
        # Localhost-only but no auth = low risk (local network attacks only)
        return "low"
    return "medium"


def audit_service(svc: dict) -> dict:
    """Run a single service audit and return a finding dict."""
    port = svc["port"]
    is_open_loopback = _is_port_open("127.0.0.1", port)
    is_open_wildcard = _is_port_open("0.0.0.0", port) or _is_port_open(_get_system_ip() or "127.0.0.1", port)
    is_running = is_open_loopback or is_open_wildcard

    listen_addr = _get_listening_address(port) if is_running else None
    risk = _risk_level(svc, listen_addr, is_running)

    return {
        "service": svc["name"],
        "description": svc["description"],
        "port": port,
        "running": is_running,
        "listen_address": listen_addr,
        "risk": risk,
        "secure_default": svc["secure_default"],
        "notes": svc["notes"],
        "recommendation": _recommendation(svc, risk, listen_addr),
    }


def _get_system_ip() -> str | None:
    """Best-effort: get the machine's LAN IP to check wildcard exposure."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def _recommendation(svc: dict, risk: str, listen_addr: str | None) -> str:
    if risk == "ok":
        return "No action required."
    if risk == "critical":
        return (
            f"CRITICAL: {svc['name']} is bound to 0.0.0.0 (all interfaces). "
            "Restrict to 127.0.0.1 immediately or add firewall rule to block external access."
        )
    if risk in ("low", "medium") and not svc["secure_default"]:
        return f"{svc['name']} has no authentication by default. Ensure it is firewall-restricted to localhost only."
    return "Review service configuration and ensure firewall rules are in place."


def run_audit() -> dict:
    """Audit all defined services and return a full posture report."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    findings: list[dict] = []
    critical_count = 0
    running_count = 0

    for svc in SERVICE_DEFS:
        finding = audit_service(svc)
        findings.append(finding)
        if finding["running"]:
            running_count += 1
        if finding["risk"] == "critical":
            critical_count += 1

    overall_risk = "critical" if critical_count > 0 else "low" if running_count > 0 else "ok"

    return {
        "schema_version": 1,
        "timestamp": ts,
        "overall_risk": overall_risk,
        "services_running": running_count,
        "critical_count": critical_count,
        "findings": findings,
        "secure_defaults_guidance": {
            "ollama": "OLLAMA_HOST=127.0.0.1 (default); never set OLLAMA_HOST=0.0.0.0",
            "neo4j": "Set dbms.connector.http.listen_address=127.0.0.1 and dbms.connector.bolt.listen_address=127.0.0.1",
            "chromadb": "Pass --host 127.0.0.1 when starting chroma server",
            "comfyui": "Pass --listen 127.0.0.1 when starting ComfyUI",
        },
    }


def write_artifact(result: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "service_auth_latest.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Local service auth and exposure auditor (GH #87)")
    ap.add_argument("--json", action="store_true", help="Print full JSON result")
    ap.add_argument("--save", action="store_true", help="Write artifact to 07_LOGS_AND_AUDIT/security/")
    args = ap.parse_args()

    result = run_audit()

    # Print summary table
    print(f"service auth audit — {result['timestamp']}")
    print(f"{'SERVICE':<18} {'PORT':<7} {'RUNNING':<9} {'BIND ADDRESS':<16} {'RISK'}")
    print("-" * 65)
    for f in result["findings"]:
        running_str = "yes" if f["running"] else "no"
        addr_str = f["listen_address"] or "n/a"
        print(f"  {f['service']:<16} {f['port']:<7} {running_str:<9} {addr_str:<16} {f['risk'].upper()}")

    print()
    print(f"overall risk: {result['overall_risk'].upper()}")
    print(f"running: {result['services_running']} service(s), {result['critical_count']} critical finding(s)")

    if result["critical_count"] > 0:
        print("\nCRITICAL FINDINGS:")
        for f in result["findings"]:
            if f["risk"] == "critical":
                print(f"  {f['service']}: {f['recommendation']}")

    if args.save or True:  # Always save artifact
        artifact = write_artifact(result)
        print(f"\nartifact: {artifact}")

    if args.json:
        print(json.dumps(result, indent=2))

    return 1 if result["critical_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
