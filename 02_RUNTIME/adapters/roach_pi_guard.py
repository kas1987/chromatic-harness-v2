"""Python mirror of roach-pi scope guards and submodule health (CI / scripts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HEALTH_MARKERS = (
    "extensions/agentic-harness/package.json",
    "extensions/agentic-harness/index.ts",
)


def repo_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "00_SOURCE_OF_TRUTH").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


def default_roach_pi_root(root: Path | None = None) -> Path:
    base = repo_root(root)
    return base / "02_RUNTIME" / "runtime-engines" / "roach-pi"


def submodule_healthy(roach_root: Path) -> bool:
    return all((roach_root / rel).is_file() for rel in HEALTH_MARKERS)


def detect_mode(roach_root: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    base = repo_root(root)
    rp = (roach_root or default_roach_pi_root(base)).resolve()
    mode = "submodule" if submodule_healthy(rp) else "stub"
    return {"mode": mode, "root": str(rp), "healthy": mode == "submodule"}


def validate_scope_paths(scope: list[str], repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    normalized: list[str] = []
    repo_resolved = repo.resolve()

    for raw in scope:
        trimmed = (raw or "").strip()
        if not trimmed:
            warnings.append("empty scope entry skipped")
            continue
        if ".." in trimmed:
            errors.append(f"scope path must not contain '..': {trimmed}")
            continue
        if Path(trimmed).is_absolute():
            errors.append(f"scope path must be relative: {trimmed}")
            continue
        resolved = (repo_resolved / trimmed).resolve()
        try:
            resolved.relative_to(repo_resolved)
        except ValueError:
            errors.append(f"scope escapes repo root: {trimmed}")
            continue
        normalized.append(trimmed.replace("\\", "/"))

    if not normalized and not errors:
        errors.append("scope must have at least one valid path")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "normalized": normalized,
    }


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    path = repo_root(root) / "02_RUNTIME" / "runtime-engines" / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))
