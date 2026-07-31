#!/usr/bin/env python3
"""Install/validate helper for the OmniRoute local free-tier gateway.

This script does **not** auto-install without user confirmation. It checks the
environment, prints the one-liner install command, optionally runs it, and then
validates that the gateway responds on http://localhost:20128/v1.

Usage:
    python scripts/install_omniroute.py --check
    python scripts/install_omniroute.py --install
    python scripts/install_omniroute.py --install --method docker
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

import httpx

OMNIROUTE_BASE_URL = os.environ.get("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
OMNIROUTE_API_KEY = os.environ.get("OMNIROUTE_API_KEY", "not-needed")  # pragma: allowlist secret


def _detect_method() -> Literal["npm", "docker"]:
    if shutil.which("docker"):
        return "docker"
    if shutil.which("npm") or shutil.which("pnpm") or shutil.which("yarn"):
        return "npm"
    return "npm"


def _package_manager() -> str:
    for cmd in ("pnpm", "yarn", "npm"):
        if shutil.which(cmd):
            return cmd
    return "npm"


def _is_reachable(base_url: str, api_key: str) -> bool:  # pragma: allowlist secret
    try:
        resp = httpx.get(
            f"{base_url.rstrip('/')}/models",
            # pragma: allowlist secret
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _run_install(method: Literal["npm", "docker"], dry_run: bool) -> int:
    system = platform.system().lower()

    if method == "docker":
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            "omniroute",
            "--restart",
            "unless-stopped",
            "--stop-timeout",
            "40",
            "-p",
            "20128:20128",
            "diegosouzapw/omniroute",
        ]
    else:
        pm = _package_manager()
        cmd = [pm, "install", "-g", "omniroute"]
        if pm == "npm" and shutil.which("npx"):
            # npm global install may need a follow-up start. Keep it simple.
            pass

    print(f"Detected platform: {platform.system()}")
    print(f"Install command: {' '.join(cmd)}")
    if dry_run:
        print("Dry run — not executing. Re-run without --dry-run to install.")
        return 0

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        print(f"Install failed with exit code {exc.returncode}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}", file=sys.stderr)
        return 1

    print("Install completed. Starting OmniRoute may require a separate command.")
    return 0


def _check(base_url: str, api_key: str) -> int:  # pragma: allowlist secret
    print(f"Checking OmniRoute at {base_url} ...")
    if _is_reachable(base_url, api_key):
        print("OK: OmniRoute gateway is reachable.")
        return 0
    print("Not reachable. If installed, start it with: omniroute start")
    print("Or with Docker: docker run -d --name omniroute -p 20128:20128 diegosouzapw/omniroute")
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniRoute install/validate helper")
    parser.add_argument("--check", action="store_true", help="Check if OmniRoute is reachable")
    parser.add_argument("--install", action="store_true", help="Show/run install command")
    parser.add_argument(
        "--method", choices=["npm", "docker"], default=None, help="Install method (default: auto-detect)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print install command without running")
    parser.add_argument("--base-url", default=OMNIROUTE_BASE_URL, help="OmniRoute base URL")
    parser.add_argument("--api-key", default=OMNIROUTE_API_KEY, help="OmniRoute API key")  # pragma: allowlist secret
    args = parser.parse_args()

    if not args.check and not args.install:
        parser.print_help()
        return 0

    if args.check:
        return _check(args.base_url, args.api_key)

    if args.install:
        method = args.method or _detect_method()
        print(f"Selected install method: {method}")
        rc = _run_install(method, dry_run=args.dry_run)
        if rc == 0 and not args.dry_run:
            return _check(args.base_url, args.api_key)
        return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
