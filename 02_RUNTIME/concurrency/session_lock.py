"""Session-aware SQLite locks for concurrent Harness operations."""

from __future__ import annotations

import sqlite3
import time
import uuid
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from workflows.run_log import append_run_log

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_DB = REPO_ROOT / ".agents" / "locks" / "session_locks.sqlite3"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _parse_iso(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _ensure_db() -> sqlite3.Connection:
    LOCK_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LOCK_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_locks (
            lock_name TEXT PRIMARY KEY,
            owner_session_id TEXT NOT NULL,
            owner_token TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _emit_lock_metric(
    *,
    event_type: str,
    lock_name: str,
    session_id: str,
    wait_seconds: float,
    attempts: int,
    decision: str,
    error: str = "",
) -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    payload = {
        "mode": "LOCK METRIC",
        "event_type": event_type,
        "lock_name": lock_name,
        "lock_owner": session_id,
        "lock_wait_ms": int(wait_seconds * 1000),
        "lock_attempts": attempts,
        "decision": decision,
    }
    if error:
        payload["error"] = error[:500]
    try:
        append_run_log(REPO_ROOT, payload)
    except OSError:
        pass


def acquire_lock(
    lock_name: str,
    *,
    session_id: str,
    timeout_seconds: float = 30.0,
    lease_seconds: int = 120,
    retry_interval_seconds: float = 0.5,
) -> str:
    owner_token = f"{session_id}:{uuid.uuid4()}"
    started = time.monotonic()
    attempts = 0

    while True:
        attempts += 1
        now = _utc_now()
        expires = now + timedelta(seconds=lease_seconds)
        conn = _ensure_db()
        try:
            stale = conn.execute(
                "SELECT expires_at FROM session_locks WHERE lock_name = ?",
                (lock_name,),
            ).fetchone()
            if stale:
                try:
                    stale_ts = _parse_iso(str(stale[0]))
                except ValueError:
                    stale_ts = now - timedelta(seconds=1)
                if stale_ts <= now:
                    conn.execute("DELETE FROM session_locks WHERE lock_name = ?", (lock_name,))

            try:
                conn.execute(
                    """
                    INSERT INTO session_locks
                    (lock_name, owner_session_id, owner_token, acquired_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        lock_name,
                        session_id,
                        owner_token,
                        _utc_iso(now),
                        _utc_iso(expires),
                    ),
                )
                conn.commit()
                wait_seconds = time.monotonic() - started
                _emit_lock_metric(
                    event_type="lock.acquire",
                    lock_name=lock_name,
                    session_id=session_id,
                    wait_seconds=wait_seconds,
                    attempts=attempts,
                    decision="ok",
                )
                return owner_token
            except sqlite3.IntegrityError:
                pass
        finally:
            conn.close()

        if time.monotonic() - started >= timeout_seconds:
            wait_seconds = time.monotonic() - started
            _emit_lock_metric(
                event_type="lock.timeout",
                lock_name=lock_name,
                session_id=session_id,
                wait_seconds=wait_seconds,
                attempts=attempts,
                decision="failed",
                error=f"timed out acquiring lock '{lock_name}' after {timeout_seconds:.1f}s",
            )
            raise TimeoutError(
                f"timed out acquiring lock '{lock_name}' after {timeout_seconds:.1f}s"
            )
        time.sleep(retry_interval_seconds)


def release_lock(lock_name: str, owner_token: str) -> None:
    conn = _ensure_db()
    try:
        conn.execute(
            "DELETE FROM session_locks WHERE lock_name = ? AND owner_token = ?",
            (lock_name, owner_token),
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def session_lock(
    lock_name: str,
    *,
    session_id: str,
    timeout_seconds: float = 30.0,
    lease_seconds: int = 120,
) -> Iterator[str]:
    owner_token = acquire_lock(
        lock_name,
        session_id=session_id,
        timeout_seconds=timeout_seconds,
        lease_seconds=lease_seconds,
    )
    try:
        yield owner_token
    finally:
        release_lock(lock_name, owner_token)
