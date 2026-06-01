"""Tests for validate_repo_role_registry.py (federation alignment PDR)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "validate_repo_role_registry.py"
REGISTRY = REPO / "config" / "repo_role_registry.yaml"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_repo_role_registry", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["validate_repo_role_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_repo_role_registry_valid():
    mod = _load_validator()
    data = mod.load_yaml(REGISTRY)
    errors = mod.validate(data)
    assert errors == [], f"registry has errors: {errors}"


def test_harness_is_authority_root():
    mod = _load_validator()
    data = mod.load_yaml(REGISTRY)
    assert data["authority_root"] == "kas1987/chromatic-harness-v2"


def test_all_required_repos_present():
    mod = _load_validator()
    data = mod.load_yaml(REGISTRY)
    repos = {r["repo"] for r in data["repos"]}
    for required in mod.REQUIRED_REPOS:
        assert required in repos, f"missing required repo: {required}"


def test_no_exclusive_domain_collisions():
    mod = _load_validator()
    data = mod.load_yaml(REGISTRY)
    domain_owners: dict[str, list[str]] = {}
    for repo in data["repos"]:
        for domain in repo.get("owns", []):
            if domain in mod.EXCLUSIVE_DOMAINS:
                domain_owners.setdefault(domain, []).append(repo["repo"])
    for domain, owners in domain_owners.items():
        assert len(owners) == 1, f"exclusive domain '{domain}' claimed by: {owners}"


def test_harness_owns_runtime_execution():
    mod = _load_validator()
    data = mod.load_yaml(REGISTRY)
    harness = next(r for r in data["repos"] if r["repo"] == "kas1987/chromatic-harness-v2")
    assert "runtime_execution" in harness["owns"]


def test_claude_config_cannot_own_shipping():
    mod = _load_validator()
    data = mod.load_yaml(REGISTRY)
    cc = next((r for r in data["repos"] if r["repo"] == "kas1987/claude-config"), None)
    assert cc is not None
    assert "independent_shipping_logic" in cc["forbidden"] or "shipping_authority" in cc["forbidden"]


def test_brain_is_migration_source_not_active():
    mod = _load_validator()
    data = mod.load_yaml(REGISTRY)
    brain = next((r for r in data["repos"] if r["repo"] == "kas1987/Chromatic_Brain"), None)
    assert brain is not None
    assert brain["status"] == "migration_source"
    assert "active_queue_authority" in brain["forbidden"]


def test_validator_detects_missing_authority_root(tmp_path):
    mod = _load_validator()
    bad = {
        "schema_version": 1,
        "authority_root": "wrong/repo",
        "repos": [{"repo": "x", "role": "r", "status": "s", "owns": [], "forbidden": []}],
    }
    errors = mod.validate(bad)
    assert any("authority_root" in e for e in errors)


def test_validator_detects_missing_required_repo(tmp_path):
    mod = _load_validator()
    bad = {
        "schema_version": 1,
        "authority_root": "kas1987/chromatic-harness-v2",
        "repos": [
            {
                "repo": "kas1987/chromatic-harness-v2",
                "role": "execution_authority",
                "status": "active",
                "owns": [],
                "forbidden": [],
            }
        ],
    }
    errors = mod.validate(bad)
    assert any("missing required repos" in e for e in errors)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
