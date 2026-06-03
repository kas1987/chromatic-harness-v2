#!/usr/bin/env python3
"""Shared helpers for the usage-calibration pipeline.

Path constants, robust JSON/JSONL readers, model-type normalization, weight-table
loading, and the weighted-token (wtok) computation. Imported by usage_ingest.py
and usage_calibrate.py. No side effects on import.
"""

from __future__ import annotations
import json
import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
HOME = Path(os.path.expanduser("~"))
HARNESS = HOME / "chromatic-harness-v2"
CALIB_DIR = HARNESS / "07_LOGS_AND_AUDIT" / "usage_calibration"
EDGE_USAGE_DIR = HOME / ".claude" / "usage"

WEIGHT_TABLE_PATH = CALIB_DIR / "weight_table.json"
SNAPSHOTS_ARCHIVE = CALIB_DIR / "snapshots_archive.jsonl"
WTOK_EVENTS = CALIB_DIR / "wtok_events.jsonl"
CALIBRATION_HISTORY = CALIB_DIR / "calibration_history.jsonl"
CALIBRATED_CAPS = CALIB_DIR / "calibrated_caps.json"
INGEST_STATE = CALIB_DIR / "ingest_state.json"
EPOCHS = CALIB_DIR / "epochs.json"

EDGE_SNAPSHOTS = EDGE_USAGE_DIR / "snapshots.jsonl"
EDGE_CALIBRATED_CAPS = EDGE_USAGE_DIR / "calibrated_caps.json"  # feedback copy for statusline

# Token-usage keys as they appear in transcript `usage` objects, mapped to the
# weight-table token_type names.
USAGE_KEY_MAP = {
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_creation_input_tokens": "cache_creation",
    "cache_read_input_tokens": "cache_read",
}


# ── Robust IO ───────────────────────────────────────────────────────────────--
def read_json(path, default=None):
    """Read a JSON file; return default on any error (partial-write tolerant)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def iter_jsonl(path):
    """Yield parsed objects from a JSONL file, skipping unparsable/partial lines."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return


def append_jsonl(path, obj):
    """Append one compact JSON object as a line; create parent dir as needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, separators=(",", ":")) + "\n")


def write_json(path, obj):
    """Write JSON atomically-ish (temp + replace) so readers never see a partial file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, p)


def _now_iso():
    """Current UTC time as an ISO 8601 string (no Date.now restriction here — plain script)."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# ── Model normalization ─────────────────────────────────────────────────────--
def model_type(model_id):
    """Collapse a raw model id to a weight-table family key.

    Tolerates suffixes like 'claude-opus-4-8[1m]' and provider prefixes.
    """
    mid = (model_id or "").lower()
    if "sonnet" in mid:
        return "sonnet"
    if "opus" in mid:
        return "opus"
    if "haiku" in mid:
        return "haiku"
    return "default"


# ── Weight table + wtok ───────────────────────────────────────────────────────
def load_weights(path=WEIGHT_TABLE_PATH):
    """Return (weights_dict, version). Falls back to a sane default if missing."""
    wt = read_json(path)
    weights = wt.get("weights") if isinstance(wt, dict) else None
    if not weights:
        weights = {
            "sonnet": {"input": 1.0, "output": 5.0, "cache_creation": 1.25, "cache_read": 0.10},
            "opus": {"input": 5.0, "output": 25.0, "cache_creation": 6.25, "cache_read": 0.50},
            "haiku": {"input": 0.2667, "output": 1.3333, "cache_creation": 0.3333, "cache_read": 0.02667},
            "default": {"input": 1.0, "output": 5.0, "cache_creation": 1.25, "cache_read": 0.10},
        }
        version = "fallback"
    else:
        version = wt.get("version", "unknown")
    return weights, version


def wtok(raw_usage, model_id, weights):
    """Compute weighted tokens for one usage object.

    raw_usage may use either transcript keys (input_tokens, ...) or already-mapped
    keys (input, ...). Unknown models fall back to the 'default' weight row.
    """
    row = weights.get(model_type(model_id)) or weights.get("default") or {}
    total = 0.0
    for src_key, ttype in USAGE_KEY_MAP.items():
        val = raw_usage.get(src_key)
        if val is None:
            val = raw_usage.get(ttype, 0)  # already-mapped form
        total += (val or 0) * row.get(ttype, 0.0)
    return total
