#!/usr/bin/env python3
"""Central GitHub App webhook receiver for Chromatic Review Intake.

Receives GitHub review events from multiple repos, normalizes them,
and stores findings in the central SQLite database.

Run locally:
  uvicorn scripts.review_intake_webhook_app:app --port 8000
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from review_intake_central_collector import init_db, ingest_findings
from classify_review_finding import enrich_finding
from review_intake import normalize_event

DEFAULT_DB = "07_LOGS_AND_AUDIT/review_intake/central_collector.sqlite3"
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

app = FastAPI(title="Chromatic Review Intake Webhook")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def verify_signature(payload: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        return True
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> dict:
    payload = await request.body()
    if not verify_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = json.loads(payload)
    repo = event.get("repository", {}).get("full_name") or event.get("repository") or "unknown/repo"
    finding = normalize_event(x_github_event, event, repo)

    if not finding:
        return {"status": "ignored", "reason": "no actionable finding"}

    enriched = enrich_finding(finding)
    db_path = Path(DEFAULT_DB)
    if not db_path.exists():
        init_db(db_path)
    n = ingest_findings(db_path, [enriched])

    return {
        "status": "ingested",
        "finding_id": enriched["finding_id"],
        "finding_type": enriched.get("finding_type"),
        "confidence_score": enriched.get("confidence_score"),
        "ingested": n > 0,
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "chromatic-review-intake"}
