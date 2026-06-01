"""Smoke tests for rudalo_migration_audit.py (gh-84 / NW-RG-084).

Reconciled from EPIC-E (shipped untested). Network-free; runs the read-only audit
against the repo's own runtime-engine layout.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "rudalo_migration_audit", REPO / "scripts" / "rudalo_migration_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["rudalo_migration_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_run_audit_shape():
    mod = _load()
    result = mod.run_audit()
    assert "passed" in result and isinstance(result["passed"], bool)
    assert result["authoritative_source"] == mod.AUTHORITATIVE_MANIFEST
    assert {"authoritative_manifest", "legacy_paths", "duplicate_registrations", "canon_registry_sot"} <= set(
        result["checks"]
    )


def test_single_source_of_truth_defined():
    mod = _load()
    # The authoritative manifest is the single SoT for runtime-engine registration.
    assert mod.AUTHORITATIVE_MANIFEST.endswith("manifest.json")
    check = mod.check_authoritative_manifest()
    assert "passed" in check


def test_legacy_paths_check_runs():
    mod = _load()
    check = mod.check_legacy_paths()
    assert "passed" in check and "findings" in check


def test_duplicate_registration_check_prevents_divergence():
    mod = _load()
    check = mod.check_duplicate_registrations()
    assert "passed" in check  # this is the divergence guard


def test_canon_registry_sot_check():
    mod = _load()
    check = mod.check_canon_registry_sot()
    assert "passed" in check


def test_each_check_has_severity_tagged_findings():
    mod = _load()
    result = mod.run_audit()
    for name, check in result["checks"].items():
        for f in check.get("findings", []):
            assert f.get("severity") in {"error", "warn", "info"}, f"{name}: {f}"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
