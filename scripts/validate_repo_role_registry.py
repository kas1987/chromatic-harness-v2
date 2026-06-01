#!/usr/bin/env python3
"""Validate Chromatic repo role registry for basic federation safety."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REQUIRED_REPOS = {
    "kas1987/chromatic-harness-v2",
    "kas1987/chromatic-wiki",
    "kas1987/chromatic-stack",
    "kas1987/claude-config",
    "kas1987/Chromatic_Brain",
    "kas1987/ChromaticSystems",
}

EXCLUSIVE_DOMAINS = {
    "runtime_execution",
    "queue_dispatch",
    "shipping_authority",
    "ci_release_readiness",
    "confidence_gate",
    "verifier_gate",
    "lease_collision_control",
}


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("authority_root") != "kas1987/chromatic-harness-v2":
        errors.append("authority_root must be kas1987/chromatic-harness-v2")

    repos = data.get("repos") or []
    seen = {r.get("repo") for r in repos}
    missing = REQUIRED_REPOS - seen
    if missing:
        errors.append(f"missing required repos: {sorted(missing)}")

    owners: dict[str, list[str]] = {}
    for repo in repos:
        name = repo.get("repo", "<unknown>")
        for field in ("repo", "role", "status", "owns", "forbidden"):
            if field not in repo:
                errors.append(f"{name}: missing {field}")
        owns = repo.get("owns") or []
        forbidden = repo.get("forbidden") or []
        overlap = sorted(set(owns) & set(forbidden))
        if overlap:
            errors.append(f"{name}: owns and forbids same domains: {overlap}")
        for domain in owns:
            if domain in EXCLUSIVE_DOMAINS:
                owners.setdefault(domain, []).append(name)

    for domain, domain_owners in owners.items():
        if len(domain_owners) > 1:
            errors.append(f"exclusive domain {domain} has multiple owners: {domain_owners}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", nargs="?", default="config/repo_role_registry.yaml")
    args = parser.parse_args()
    path = Path(args.registry)
    data = load_yaml(path)
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {path} federation registry is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
