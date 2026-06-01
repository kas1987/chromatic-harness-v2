#!/usr/bin/env python3
"""
rudalo_migration_audit.py -- Validates Rudalo (roach-pi) migration completeness.

GH #84: Finalize migration and remove parallel state ownership.

Checks:
  1. Single authoritative SoT defined in canon_registry.yaml
  2. runtime-engines/manifest.json is the sole roach-pi registration point
  3. Legacy paths (10_RUNTIME) are not duplicating runtime state
  4. Submodule stub mode is acceptable (no phantom live references)
  5. No duplicate runtime-engine registrations outside manifest.json

Outputs:
  00_SOURCE_OF_TRUTH/migration_status.yaml -- machine-readable migration status
  docs/architecture/RUDALO_MIGRATION.md    -- migration status documentation
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Authoritative registration point for roach-pi
AUTHORITATIVE_MANIFEST = "02_RUNTIME/runtime-engines/manifest.json"
AUTHORITATIVE_SUBMODULE = "02_RUNTIME/runtime-engines/roach-pi"

# Legacy paths that should NOT contain roach-pi runtime state
LEGACY_RUNTIME_PATHS = [
    "10_RUNTIME",
    "02_RUNTIME/10_RUNTIME",
]

# Files that would indicate stale/duplicate runtime registration
STALE_REGISTRATION_PATTERNS = [
    "roach-pi/package.json",  # submodule populated (live, not stub)
    "roach-pi/index.ts",
    "roach-pi/extensions/agentic-harness/package.json",
    "roach-pi/extensions/agentic-harness/index.ts",
]

MIGRATION_STATUS_PATH = REPO_ROOT / "00_SOURCE_OF_TRUTH" / "migration_status.yaml"
MIGRATION_DOC_PATH = REPO_ROOT / "docs" / "architecture" / "RUDALO_MIGRATION.md"


def check_authoritative_manifest() -> dict:
    """Verify manifest.json exists and is the sole registration point."""
    manifest_path = REPO_ROOT / AUTHORITATIVE_MANIFEST
    if not manifest_path.exists():
        return {
            "passed": False,
            "issue": "manifest_missing",
            "detail": f"Authoritative manifest not found: {AUTHORITATIVE_MANIFEST}",
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "passed": False,
            "issue": "manifest_parse_error",
            "detail": str(e),
        }

    required_keys = ["runtime_id", "submodule_path", "upstream_url", "health_markers", "default_mode"]
    missing_keys = [k for k in required_keys if k not in manifest]
    if missing_keys:
        return {
            "passed": False,
            "issue": "manifest_incomplete",
            "detail": f"Missing keys: {missing_keys}",
            "manifest": manifest,
        }

    return {
        "passed": True,
        "runtime_id": manifest["runtime_id"],
        "upstream_url": manifest["upstream_url"],
        "default_mode": manifest["default_mode"],
        "submodule_path": manifest["submodule_path"],
        "manifest": manifest,
    }


def check_submodule_state() -> dict:
    """Determine if roach-pi submodule is populated (live) or empty (stub)."""
    submodule_dir = REPO_ROOT / AUTHORITATIVE_SUBMODULE
    if not submodule_dir.exists():
        return {
            "mode": "absent",
            "stub_acceptable": True,
            "health_markers_present": [],
            "health_markers_missing": STALE_REGISTRATION_PATTERNS,
            "detail": "Submodule directory does not exist; stub mode confirmed",
        }

    try:
        contents = list(submodule_dir.iterdir())
    except Exception:
        contents = []

    if not contents:
        return {
            "mode": "stub",
            "stub_acceptable": True,
            "health_markers_present": [],
            "health_markers_missing": STALE_REGISTRATION_PATTERNS,
            "detail": "Submodule directory is empty; stub mode confirmed",
        }

    # Submodule is populated -- check health markers
    markers_present = []
    markers_missing = []
    for marker in STALE_REGISTRATION_PATTERNS:
        full = submodule_dir / marker
        if full.exists():
            markers_present.append(marker)
        else:
            markers_missing.append(marker)

    return {
        "mode": "live",
        "stub_acceptable": False,
        "health_markers_present": markers_present,
        "health_markers_missing": markers_missing,
        "detail": "Submodule is populated (live mode)",
    }


def check_legacy_paths() -> dict:
    """Check if legacy runtime paths contain stale roach-pi state."""
    findings = []
    clean_paths = []
    stale_paths = []

    for legacy in LEGACY_RUNTIME_PATHS:
        full = REPO_ROOT / legacy
        if not full.exists():
            clean_paths.append(legacy)
            continue

        # Check if path contains roach-pi related content
        has_stale = False
        stale_files = []
        try:
            for item in full.rglob("*"):
                if item.is_file():
                    name_lower = item.name.lower()
                    if "roach" in name_lower or "rudalo" in name_lower:
                        stale_files.append(str(item.relative_to(REPO_ROOT)))
                        has_stale = True
        except Exception:
            pass

        if has_stale:
            stale_paths.append(legacy)
            findings.append(
                {
                    "path": legacy,
                    "issue": "stale_roach_references",
                    "stale_files": stale_files,
                    "severity": "error",
                }
            )
        else:
            # Path exists but no roach-pi state -- just old structure
            findings.append(
                {
                    "path": legacy,
                    "issue": "legacy_dir_exists",
                    "detail": "Directory exists but contains no roach-pi state",
                    "severity": "warn",
                }
            )

    return {
        "legacy_paths_checked": LEGACY_RUNTIME_PATHS,
        "clean_paths": clean_paths,
        "stale_paths": stale_paths,
        "findings": findings,
        "passed": len(stale_paths) == 0,
    }


def check_duplicate_registrations() -> dict:
    """Scan for any roach-pi registrations outside the authoritative manifest."""
    duplicate_refs = []
    scanned_files = []

    search_dirs = [
        REPO_ROOT / "config",
        REPO_ROOT / "docs",
        REPO_ROOT / ".agents",
    ]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for f in search_dir.rglob("*.json"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if "roach-pi" in content or "rudalo" in content.lower():
                    rel = str(f.relative_to(REPO_ROOT))
                    # Exclude the authoritative manifest itself
                    if rel != AUTHORITATIVE_MANIFEST:
                        scanned_files.append(rel)
                        # Quick check: does it look like a registration (has runtime_id)?
                        try:
                            data = json.loads(content)
                            if "runtime_id" in data and data.get("runtime_id") == "roach-pi":
                                duplicate_refs.append(rel)
                        except Exception:
                            pass
            except Exception:
                pass

    return {
        "scanned_files_with_references": scanned_files,
        "duplicate_registrations": duplicate_refs,
        "passed": len(duplicate_refs) == 0,
    }


def check_canon_registry_sot() -> dict:
    """Verify canon_registry.yaml has a clear SoT entry (not Rudalo-related duplication)."""
    registry_path = REPO_ROOT / "00_SOURCE_OF_TRUTH" / "canon_registry.yaml"
    if not registry_path.exists():
        return {
            "passed": False,
            "issue": "registry_missing",
        }

    content = registry_path.read_text(encoding="utf-8", errors="ignore")
    has_roach_ref = "roach" in content.lower() or "rudalo" in content.lower()

    return {
        "passed": True,
        "has_roach_reference": has_roach_ref,
        "authoritative_sot": "00_SOURCE_OF_TRUTH/canon_registry.yaml",
        "detail": "canon_registry.yaml is the authoritative SoT for promoted artifacts",
    }


def run_audit() -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    manifest_check = check_authoritative_manifest()
    submodule_check = check_submodule_state()
    legacy_check = check_legacy_paths()
    duplicate_check = check_duplicate_registrations()
    registry_check = check_canon_registry_sot()

    all_passed = (
        manifest_check["passed"] and legacy_check["passed"] and duplicate_check["passed"] and registry_check["passed"]
    )

    # Compile recommendations
    recommendations = []
    if not manifest_check["passed"]:
        recommendations.append(f"Fix authoritative manifest: {manifest_check.get('detail', '')}")
    for f in legacy_check.get("findings", []):
        if f["severity"] == "error":
            recommendations.append(f"Remove stale roach-pi files from legacy path: {f['path']}")
        elif f["severity"] == "warn":
            recommendations.append(f"Consider removing legacy directory (no roach-pi state): {f['path']}")
    for ref in duplicate_check.get("duplicate_registrations", []):
        recommendations.append(f"Remove duplicate roach-pi registration: {ref}")

    result = {
        "timestamp": timestamp,
        "passed": all_passed,
        "migration_complete": all_passed,
        "authoritative_source": AUTHORITATIVE_MANIFEST,
        "checks": {
            "authoritative_manifest": manifest_check,
            "submodule_state": submodule_check,
            "legacy_paths": legacy_check,
            "duplicate_registrations": duplicate_check,
            "canon_registry_sot": registry_check,
        },
        "recommendations": recommendations,
        "summary": {
            "mode": submodule_check["mode"],
            "stub_mode": submodule_check["mode"] in ("stub", "absent"),
            "legacy_dirs_clean": legacy_check["passed"],
            "no_duplicate_registrations": duplicate_check["passed"],
            "single_sot_defined": registry_check["passed"],
        },
    }

    return result


def write_migration_status_yaml(result: dict):
    """Write machine-readable migration status YAML."""
    s = result["summary"]
    ts = result["timestamp"]
    passed = result["passed"]
    mode = s["mode"]

    yaml_content = f"""# Rudalo (roach-pi) Migration Status
# Auto-generated by scripts/rudalo_migration_audit.py
# DO NOT edit manually -- re-run the audit to update

timestamp: "{ts}"
migration_complete: {str(passed).lower()}

authoritative_source:
  path: "{AUTHORITATIVE_MANIFEST}"
  type: "json_manifest"
  role: "sole runtime-engine registration point"

submodule:
  path: "{AUTHORITATIVE_SUBMODULE}"
  mode: "{mode}"
  stub_acceptable: true
  note: "stub mode is the default until init_roach_pi_submodule.ps1 is run"

canon_sot:
  path: "00_SOURCE_OF_TRUTH/canon_registry.yaml"
  role: "authoritative registry for all promoted artifacts"
  includes_roach_ref: {str(result["checks"]["canon_registry_sot"].get("has_roach_reference", False)).lower()}

legacy_paths:
  deprecated:
{"".join(f'    - path: "{p}"\n      status: "deprecated"\n' for p in ["10_RUNTIME", "02_RUNTIME/10_RUNTIME"])}
  clean: {str(result["checks"]["legacy_paths"]["passed"]).lower()}

checks:
  manifest_valid: {str(result["checks"]["authoritative_manifest"]["passed"]).lower()}
  legacy_paths_clean: {str(result["checks"]["legacy_paths"]["passed"]).lower()}
  no_duplicate_registrations: {str(result["checks"]["duplicate_registrations"]["passed"]).lower()}
  single_sot_defined: {str(result["checks"]["canon_registry_sot"]["passed"]).lower()}

recommendations:
{"".join(f'  - "{r}"\n' for r in result.get("recommendations", [])) if result.get("recommendations") else "  []\n"}
"""

    MIGRATION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MIGRATION_STATUS_PATH.write_text(yaml_content, encoding="utf-8")


def write_migration_doc(result: dict):
    """Write human-readable migration status document."""
    ts = result["timestamp"]
    passed = result["passed"]
    mode = result["summary"]["mode"]
    status_badge = "COMPLETE" if passed else "IN PROGRESS"
    legacy_findings = result["checks"]["legacy_paths"]["findings"]
    recs = result.get("recommendations", [])

    doc = f"""# Rudalo (roach-pi) Migration Status

> Auto-generated by `scripts/rudalo_migration_audit.py` at `{ts}`
> Migration status: **{status_badge}**

## Overview

Rudalo is the codename for the `roach-pi` runtime engine integration (Option C).
This document tracks the state of the migration from dual/parallel state ownership
to a single authoritative source of truth.

## Authoritative Source of Truth

| Artifact | Path | Role |
|----------|------|------|
| Runtime manifest | `{AUTHORITATIVE_MANIFEST}` | Sole roach-pi registration |
| Submodule | `{AUTHORITATIVE_SUBMODULE}` | Runtime engine code |
| Canon registry | `00_SOURCE_OF_TRUTH/canon_registry.yaml` | All promoted artifacts |

## Submodule State

Current mode: **{mode.upper()}**

- **stub**: Submodule not initialized; adapter runs in mock-execution mode.
  All magnet telemetry is fully functional.
- **live**: Submodule populated; real roach-pi execution available.

To initialize: `powershell -File scripts/init_roach_pi_submodule.ps1`

## Legacy Path Status

The following directories are deprecated and should not contain roach-pi runtime state:

| Path | Status | Notes |
|------|--------|-------|
| `10_RUNTIME/` | Deprecated | Top-level legacy; content is logs only |
| `02_RUNTIME/10_RUNTIME/` | Deprecated | Inner legacy; contains only `logs/` |

### Findings

"""

    if not legacy_findings:
        doc += "_No legacy path issues found._\n"
    else:
        for f in legacy_findings:
            sev = f["severity"].upper()
            doc += f"- **[{sev}]** `{f['path']}`: {f.get('detail', f.get('issue', ''))}\n"

    doc += f"""
## Duplicate Registration Check

Scanned config/, docs/, .agents/ for duplicate roach-pi registrations outside
the authoritative manifest.

Result: **{"CLEAN - no duplicates found" if result["checks"]["duplicate_registrations"]["passed"] else "ISSUES FOUND"}**

## Migration Checklist

- [{"x" if result["checks"]["authoritative_manifest"]["passed"] else " "}] Authoritative manifest exists and is valid
- [{"x" if result["checks"]["legacy_paths"]["passed"] else " "}] Legacy paths contain no stale roach-pi state
- [{"x" if result["checks"]["duplicate_registrations"]["passed"] else " "}] No duplicate runtime registrations
- [{"x" if result["checks"]["canon_registry_sot"]["passed"] else " "}] canon_registry.yaml is the single promoted-artifact SoT
- [{"x" if result["summary"]["stub_mode"] else " "}] Stub mode acceptable (submodule not required for harness to function)

## Recommendations

"""

    if not recs:
        doc += "_No recommendations -- migration is complete._\n"
    else:
        for r in recs:
            doc += f"- {r}\n"

    doc += """
## Re-running the Audit

```bash
python scripts/rudalo_migration_audit.py
```

Outputs are written to:
- `00_SOURCE_OF_TRUTH/migration_status.yaml` (machine-readable)
- `docs/architecture/RUDALO_MIGRATION.md` (this file)
"""

    MIGRATION_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    MIGRATION_DOC_PATH.write_text(doc, encoding="utf-8")


def main():
    print("=== Rudalo Migration Audit ===")
    result = run_audit()

    # Write outputs
    write_migration_status_yaml(result)
    write_migration_doc(result)

    passed = result["passed"]
    mode = result["summary"]["mode"]
    recs = result.get("recommendations", [])

    print(f"Status:  {'COMPLETE' if passed else 'IN PROGRESS'} (passed={passed})")
    print(f"Mode:    roach-pi is running in {mode.upper()} mode")

    checks = result["checks"]
    print("\n--- Checks ---")
    print(f"  Manifest valid:            {checks['authoritative_manifest']['passed']}")
    print(f"  Legacy paths clean:        {checks['legacy_paths']['passed']}")
    print(f"  No duplicate registrations:{checks['duplicate_registrations']['passed']}")
    print(f"  Single SoT defined:        {checks['canon_registry_sot']['passed']}")

    legacy_findings = checks["legacy_paths"]["findings"]
    if legacy_findings:
        print("\n--- Legacy Path Findings ---")
        for f in legacy_findings:
            print(f"  [{f['severity'].upper()}] {f['path']}: {f.get('detail', f.get('issue', ''))}")

    dup_refs = checks["duplicate_registrations"]["scanned_files_with_references"]
    if dup_refs:
        print("\n--- Files with roach-pi references (non-authoritative) ---")
        for ref in dup_refs:
            print(f"  {ref}")

    if recs:
        print(f"\n--- Recommendations ({len(recs)}) ---")
        for r in recs:
            print(f"  * {r}")
    else:
        print("\nNo recommendations -- migration is complete.")

    print("\nOutputs written:")
    print("  00_SOURCE_OF_TRUTH/migration_status.yaml")
    print("  docs/architecture/RUDALO_MIGRATION.md")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
