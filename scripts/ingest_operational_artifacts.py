#!/usr/bin/env python3
"""Ingest operational artifacts and emit canonical applied outcome events.

Reads each configured artifact source, extracts outcome signals, and appends
applied_success / applied_failure events to the learning usage log with
idempotency dedup.

Usage:
    python scripts/ingest_operational_artifacts.py            # full run
    python scripts/ingest_operational_artifacts.py --dry-run  # report only
    python scripts/ingest_operational_artifacts.py --source agent_run_log
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "config" / "artifact_ingest_config.json"
USAGE_LOG = REPO / ".agents" / "metrics" / "learning_usage.jsonl"

_OUTCOME_SUCCESS = "applied_success"
_OUTCOME_FAILURE = "applied_failure"


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _idempotency_key(source_id: str, row: dict[str, Any], canonical_ts: str) -> str:
    raw = f"{source_id}|{canonical_ts}|{json.dumps(row, sort_keys=True, ensure_ascii=True)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _load_seen_keys(usage_log: Path) -> set[str]:
    seen: set[str] = set()
    if not usage_log.is_file():
        return seen
    for line in usage_log.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        key = str(row.get("idempotency_key") or "")
        if key:
            seen.add(key)
    return seen


def _is_skip_row(row: dict[str, Any], skip_keys: list[str]) -> bool:
    return any(k in row for k in skip_keys)


def _extract_timestamp(row: dict[str, Any], ts_field: str) -> str:
    raw = str(row.get(ts_field) or row.get("timestamp") or row.get("ts") or "").strip()
    if raw:
        return (
            raw[:26].rstrip("Z") + "Z"
            if raw.endswith("+00:00")
            else raw[:20] + "Z"
            if len(raw) >= 20
            else raw
        )
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _determine_outcome(row: dict[str, Any], rule: dict[str, Any]) -> str | None:
    result_field = str(rule.get("field") or "result")
    raw_value = str(row.get(result_field) or "").strip().lower()

    success_vals = [str(v).lower() for v in (rule.get("success_values") or [])]
    failure_vals = [str(v).lower() for v in (rule.get("failure_values") or [])]

    if raw_value in success_vals:
        return _OUTCOME_SUCCESS
    if raw_value in failure_vals:
        return _OUTCOME_FAILURE

    # Confidence-based outcome when explicit result is absent
    conf_field = str(rule.get("confidence_field") or "")
    conf_threshold = float(rule.get("confidence_success_threshold") or 0.0)
    if conf_field and conf_threshold > 0:
        raw_conf = row.get(conf_field)
        if raw_conf is not None:
            try:
                conf = float(raw_conf)
                if conf >= conf_threshold:
                    return _OUTCOME_SUCCESS
            except (TypeError, ValueError):
                pass

    return None


def _extract_learning_ref(
    row: dict[str, Any], ref_cfg: dict[str, Any]
) -> tuple[str, str]:
    strategy = str(ref_cfg.get("strategy") or "field")
    if strategy == "field":
        field = str(ref_cfg.get("field") or "learning_name")
        name = str(row.get(field) or "").strip()
        if name:
            return name, f".agents/learnings/{name}.md"

        fallback_field = str(ref_cfg.get("fallback_field") or "")
        fallback_prefix = str(ref_cfg.get("fallback_prefix") or "")
        if fallback_field:
            fallback_val = str(row.get(fallback_field) or "").strip()
            if fallback_val:
                return f"{fallback_prefix}{fallback_val}", ""

    return "", ""


def _process_source(
    source_cfg: dict[str, Any],
    seen_keys: set[str],
    dry_run: bool,
) -> dict[str, int]:
    stats = {
        "parsed": 0,
        "emitted": 0,
        "skipped_dup": 0,
        "skipped_no_outcome": 0,
        "skipped_no_ref": 0,
    }

    path = REPO / str(source_cfg.get("path") or "")
    source_id = str(source_cfg.get("id") or path.name)
    skip_keys = list(source_cfg.get("skip_rows_with_keys") or [])
    outcome_rule = source_cfg.get("outcome_rule") or {}
    ref_cfg = source_cfg.get("learning_ref") or {}
    canonical_fields = source_cfg.get("canonical_fields") or {}
    ts_field = str(canonical_fields.get("timestamp_utc") or "timestamp")
    rig_field = str(canonical_fields.get("rig_id") or "")
    notes_val = str(canonical_fields.get("notes") or f"{source_id}_ingest")

    if not path.is_file():
        return stats

    events_to_emit: list[dict[str, Any]] = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if _is_skip_row(row, skip_keys):
            continue

        stats["parsed"] += 1

        outcome = _determine_outcome(row, outcome_rule)
        if outcome is None:
            stats["skipped_no_outcome"] += 1
            continue

        learning_name, learning_path = _extract_learning_ref(row, ref_cfg)
        if not learning_name:
            stats["skipped_no_ref"] += 1
            continue

        canonical_ts = _extract_timestamp(row, ts_field)
        ikey = _idempotency_key(source_id, row, canonical_ts)

        if ikey in seen_keys:
            stats["skipped_dup"] += 1
            continue

        event: dict[str, Any] = {
            "timestamp_utc": canonical_ts,
            "event_type": outcome,
            "learning_name": learning_name,
            "idempotency_key": ikey,
            "notes": notes_val,
        }
        if learning_path:
            event["learning_path"] = learning_path
        if rig_field:
            rig_val = str(row.get(rig_field) or "").strip()
            if rig_val:
                event["rig_id"] = rig_val

        events_to_emit.append(event)
        seen_keys.add(ikey)
        stats["emitted"] += 1

    if not dry_run and events_to_emit:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as fh:
            for event in events_to_emit:
                fh.write(json.dumps(event, ensure_ascii=True) + "\n")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument("--source", default="", help="Ingest only this source ID")
    args = parser.parse_args()

    config = _load_json(CONFIG_PATH, {})
    if not config:
        print(f"ERROR: config not found: {CONFIG_PATH}", file=sys.stderr)
        return 1

    sources = config.get("sources") or []
    if args.source:
        sources = [s for s in sources if str(s.get("id") or "") == args.source]
        if not sources:
            print(f"ERROR: no source with id '{args.source}'", file=sys.stderr)
            return 1

    seen_keys = _load_seen_keys(USAGE_LOG)

    total = {
        "parsed": 0,
        "emitted": 0,
        "skipped_dup": 0,
        "skipped_no_outcome": 0,
        "skipped_no_ref": 0,
    }
    results: list[dict[str, Any]] = []

    for source_cfg in sources:
        sid = str(source_cfg.get("id") or "?")
        stats = _process_source(source_cfg, seen_keys, args.dry_run)
        results.append({"source": sid, **stats})
        for k, v in stats.items():
            total[k] = total.get(k, 0) + v

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}Artifact ingest complete")
    print(f"  parsed:             {total['parsed']}")
    print(f"  emitted:            {total['emitted']}")
    print(f"  skipped (dup):      {total['skipped_dup']}")
    print(f"  skipped (no outcome): {total['skipped_no_outcome']}")
    print(f"  skipped (no ref):   {total['skipped_no_ref']}")
    print()
    for r in results:
        print(
            f"  {r['source']}: parsed={r['parsed']} emitted={r['emitted']} "
            f"dup={r['skipped_dup']} no_outcome={r['skipped_no_outcome']} no_ref={r['skipped_no_ref']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
