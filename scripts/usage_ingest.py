#!/usr/bin/env python3
"""Usage-calibration ingest (harness side, off the render path).

Two idempotent steps:
  1. Archive: append new edge snapshots (~/.claude/usage/snapshots.jsonl) into the
     durable, never-rotated library (snapshots_archive.jsonl). Deduped by (ts, session_id).
  2. Token events: parse the transcripts referenced by recent snapshots into
     weighted-token events (wtok_events.jsonl). Deduped by request_id, so re-runs
     and growing transcripts are safe.

Run periodically (cron / autopilot). Safe to run repeatedly.
"""

from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_calibration_lib as L


def archive_new_snapshots():
    """Append edge snapshots not yet in the archive. Returns count appended."""
    seen = set()
    for rec in L.iter_jsonl(L.SNAPSHOTS_ARCHIVE):
        seen.add((rec.get("ts"), rec.get("session_id")))
    appended = 0
    for rec in L.iter_jsonl(L.EDGE_SNAPSHOTS):
        key = (rec.get("ts"), rec.get("session_id"))
        if key in seen:
            continue
        seen.add(key)
        L.append_jsonl(L.SNAPSHOTS_ARCHIVE, rec)
        appended += 1
    return appended


def _recent_transcript_paths():
    """Unique, existing transcript paths referenced by the edge snapshot tail."""
    paths = []
    seen = set()
    for rec in L.iter_jsonl(L.EDGE_SNAPSHOTS):
        tp = rec.get("transcript_path")
        if not tp or tp in seen:
            continue
        seen.add(tp)
        if Path(tp).exists():
            paths.append(tp)
    return paths


def ingest_transcripts():
    """Emit weighted-token events for unseen request_ids. Returns count emitted."""
    weights, version = L.load_weights()
    seen_req = set()
    for ev in L.iter_jsonl(L.WTOK_EVENTS):
        rid = ev.get("request_id")
        if rid:
            seen_req.add(rid)

    emitted = 0
    for tp in _recent_transcript_paths():
        for entry in L.iter_jsonl(tp):
            if entry.get("type") != "assistant":
                continue
            rid = entry.get("requestId")
            if not rid or rid in seen_req:
                continue
            msg = entry.get("message") or {}
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            seen_req.add(rid)
            model = msg.get("model")
            raw = {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "cache_creation": usage.get("cache_creation_input_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
            }
            L.append_jsonl(
                L.WTOK_EVENTS,
                {
                    "ts": _iso_to_epoch(entry.get("timestamp")),
                    "session_id": entry.get("sessionId"),
                    "model": model,
                    "request_id": rid,
                    "raw": raw,
                    "wtok": round(L.wtok(raw, model, weights), 2),
                    "weight_table_version": version,
                },
            )
            emitted += 1
    return emitted


def _iso_to_epoch(iso):
    if not iso:
        return None
    try:
        from datetime import datetime

        return int(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def main():
    archived = archive_new_snapshots()
    events = ingest_transcripts()
    print(f"ingest: archived {archived} snapshot(s), emitted {events} wtok event(s)")


if __name__ == "__main__":
    main()
