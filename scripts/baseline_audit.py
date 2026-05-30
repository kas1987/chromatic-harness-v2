#!/usr/bin/env python3
"""BASELINE audit — measure a surface's live config against its operating baseline.

One scorecard per surface (App / CLI / VS Code / Cursor) that flags context bloat,
hook sprawl, settings/instruction drift, and stale pre-session state — so we can tell
at a glance when a surface has drifted off its lean baseline.

It AGGREGATES existing audits (MCP context manifest, audit_hooks, instruction files,
settings.json, pre-session manifest) rather than re-measuring from scratch.

Usage:
  python scripts/baseline_audit.py --surface cli
  python scripts/baseline_audit.py --surface cursor --write
  python scripts/baseline_audit.py --all --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_REPO = Path(__file__).resolve().parents[1]
_BASELINES = _REPO / "config" / "baselines.yaml"
_MANIFEST = _REPO / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json"
_SETTINGS = _REPO / ".claude" / "settings.json"
_OUT_DIR = _REPO / "07_LOGS_AND_AUDIT" / "baseline"

SURFACES = ("app", "cli", "vscode", "cursor")
_METRICS = (
    "mcp_tokens",
    "mcp_count",
    "hook_count",
    "hook_high",
    "env_keys",
    "instruction_kib",
    "manifest_age_hrs",
)


# ── baseline spec ────────────────────────────────────────────────────────────
def load_baselines(path: Path | None = None) -> dict[str, Any]:
    p = path or _BASELINES
    if yaml is None or not p.is_file():
        return {"defaults": {}, "surfaces": {}, "advice": {}}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"defaults": {}, "surfaces": {}, "advice": {}}


def thresholds_for(spec: dict[str, Any], surface: str) -> dict[str, dict[str, float]]:
    merged = dict(spec.get("defaults") or {})
    for k, v in (spec.get("surfaces", {}).get(surface) or {}).items():
        merged[k] = v
    return merged


# ── pure evaluation ──────────────────────────────────────────────────────────
def status_for(value: float | None, band: dict[str, float]) -> str:
    if value is None:
        return "unknown"
    warn = float(band.get("warn", band.get("max", 0)))
    mx = float(band.get("max", warn))
    if value > mx:
        return "over"
    if value > warn:
        return "warn"
    return "ok"


_RANK = {"ok": 0, "unknown": 1, "warn": 2, "over": 3}


def evaluate_baseline(
    measurements: dict[str, float | None],
    thresholds: dict[str, dict[str, float]],
    advice: dict[str, str] | None = None,
) -> dict[str, Any]:
    advice = advice or {}
    rows: dict[str, Any] = {}
    worst = "ok"
    for metric in _METRICS:
        band = thresholds.get(metric) or {}
        value = measurements.get(metric)
        st = status_for(value, band)
        rows[metric] = {
            "value": value,
            "warn": band.get("warn"),
            "max": band.get("max"),
            "status": st,
            "advice": advice.get(metric, "") if st in ("warn", "over") else "",
        }
        if _RANK[st] > _RANK[worst]:
            worst = st
    return {"overall": worst, "metrics": rows}


# ── measurers (fail-open → None means "unknown") ─────────────────────────────
def _read_json(p: Path) -> dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def measure_mcp_tokens(manifest: Path | None = None) -> float | None:
    m = _read_json(manifest or _MANIFEST)
    if "mcp_tokens" in m:
        return float(m["mcp_tokens"])
    tok = (m.get("mcp_audit") or {}).get("estimated_tokens_if_enabled")
    return float(tok) if tok is not None else None


def measure_hook_count(settings: Path | None = None) -> float | None:
    s = _read_json(settings or _SETTINGS)
    hooks = s.get("hooks")
    if not isinstance(hooks, dict):
        return None
    total = 0
    for entries in hooks.values():
        for matcher in entries or []:
            total += len(matcher.get("hooks") or [])
    return float(total)


def measure_env_keys(settings: Path | None = None) -> float | None:
    s = _read_json(settings or _SETTINGS)
    env = s.get("env")
    return float(len(env)) if isinstance(env, dict) else None


def measure_instruction_kib(repo: Path | None = None) -> float | None:
    root = repo or _REPO
    files = [
        root / "CLAUDE.md",
        root / "AGENTS.md",
        Path.home() / ".claude" / "CLAUDE.md",
    ]
    files += (
        list((root / ".cursor" / "rules").glob("*.mdc"))
        if (root / ".cursor" / "rules").is_dir()
        else []
    )
    total = 0
    found = False
    for f in files:
        try:
            if f.is_file():
                total += f.stat().st_size
                found = True
        except OSError:
            continue
    return round(total / 1024, 1) if found else None


def measure_manifest_age_hrs(
    manifest: Path | None = None, *, now: datetime | None = None
) -> float | None:
    m = _read_json(manifest or _MANIFEST)
    raw = m.get("generated_at")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None
    now = now or datetime.now(timezone.utc)
    return round((now - ts).total_seconds() / 3600, 2)


def measure_hook_high() -> float | None:
    try:
        proc = subprocess.run(
            [sys.executable, str(_REPO / "scripts" / "audit_hooks.py"), "--json"],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        return float(
            sum(1 for f in data.get("findings", []) if f.get("severity") == "HIGH")
        )
    except (OSError, json.JSONDecodeError, subprocess.SubprocessError):
        return None


def collect_measurements() -> dict[str, float | None]:
    return {
        "mcp_tokens": measure_mcp_tokens(),
        "mcp_count": None,  # reliable "enabled" count is surface-specific; future work
        "hook_count": measure_hook_count(),
        "hook_high": measure_hook_high(),
        "env_keys": measure_env_keys(),
        "instruction_kib": measure_instruction_kib(),
        "manifest_age_hrs": measure_manifest_age_hrs(),
    }


# ── scorecard ────────────────────────────────────────────────────────────────
def audit_surface(
    surface: str,
    *,
    spec: dict[str, Any] | None = None,
    measurements: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    spec = spec or load_baselines()
    measurements = measurements if measurements is not None else collect_measurements()
    result = evaluate_baseline(
        measurements, thresholds_for(spec, surface), spec.get("advice") or {}
    )
    result["surface"] = surface
    return result


def _fmt(card: dict[str, Any]) -> str:
    glyph = {"ok": "OK ", "warn": "WARN", "over": "OVER", "unknown": "? "}
    lines = [f"BASELINE [{card['surface']}] overall={card['overall'].upper()}"]
    for metric, r in card["metrics"].items():
        v = r["value"]
        lines.append(
            f"  [{glyph[r['status']]}] {metric:<16} "
            f"value={'?' if v is None else v} (warn={r['warn']} max={r['max']})"
            + (f"  -> {r['advice']}" if r["advice"] else "")
        )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Per-surface BASELINE audit")
    p.add_argument("--surface", choices=SURFACES, default="cli")
    p.add_argument("--all", action="store_true", help="audit every surface")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--write",
        action="store_true",
        help="write scorecard to 07_LOGS_AND_AUDIT/baseline/",
    )
    args = p.parse_args()

    spec = load_baselines()
    measurements = collect_measurements()
    surfaces = SURFACES if args.all else (args.surface,)
    cards = [audit_surface(s, spec=spec, measurements=measurements) for s in surfaces]

    if args.write:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        for card in cards:
            (_OUT_DIR / f"{card['surface']}.json").write_text(
                json.dumps(card, indent=2), encoding="utf-8"
            )

    if args.json:
        print(json.dumps(cards if args.all else cards[0], indent=2))
    else:
        print("\n\n".join(_fmt(c) for c in cards))

    return 2 if any(c["overall"] == "over" for c in cards) else 0


if __name__ == "__main__":
    raise SystemExit(main())
