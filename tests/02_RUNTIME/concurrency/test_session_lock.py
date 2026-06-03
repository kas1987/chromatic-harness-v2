"""Tests for concurrency/session_lock.py — SQLite-backed session locks."""

from __future__ import annotations

import os
import sqlite3
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[4] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# Stub out workflows.run_log as a fallback in case the real module is unavailable.
# The conftest pre-loads the real workflows package; setdefault is a no-op when real
# workflows is already present, so this only fires in isolated runs without conftest.
_fake_workflows = MagicMock()
_fake_run_log = MagicMock()
_fake_run_log.append_run_log = MagicMock()
sys.modules.setdefault("workflows", _fake_workflows)
sys.modules.setdefault("workflows.run_log", _fake_run_log)

from concurrency.session_lock import (  # noqa: E402
    acquire_lock,
    release_lock,
    session_lock,
    _ensure_db,
    _utc_now,
    _utc_iso,
    _parse_iso,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Redirect the lock DB to a fresh temp file per test."""
    import concurrency.session_lock as _mod

    db_file = tmp_path / "test_locks.sqlite3"
    monkeypatch.setattr(_mod, "LOCK_DB", db_file)
    yield db_file


@pytest.fixture(autouse=True)
def set_pytest_env(monkeypatch):
    """Keep PYTEST_CURRENT_TEST set so _emit_lock_metric is suppressed."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "yes")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


class TestUtilityFunctions:
    def test_utc_now_returns_aware_datetime(self):
        import datetime

        dt = _utc_now()
        assert dt.tzinfo is not None

    def test_utc_iso_produces_z_suffix(self):
        import datetime

        dt = _utc_now()
        iso = _utc_iso(dt)
        assert iso.endswith("Z")

    def test_parse_iso_round_trips(self):
        dt = _utc_now()
        iso = _utc_iso(dt)
        parsed = _parse_iso(iso)
        # Allow 1 µs rounding
        assert abs((parsed - dt).total_seconds()) < 1e-3

    def test_parse_iso_handles_z_suffix(self):
        raw = "2025-01-01T12:00:00Z"
        dt = _parse_iso(raw)
        assert dt.year == 2025


# ---------------------------------------------------------------------------
# _ensure_db
# ---------------------------------------------------------------------------


class TestEnsureDb:
    def test_creates_table(self, tmp_db):
        conn = _ensure_db()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_locks'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent(self, tmp_db):
        _ensure_db().close()
        conn = _ensure_db()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_locks'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        import concurrency.session_lock as _mod

        nested = tmp_path / "deep" / "nested" / "locks.sqlite3"
        monkeypatch.setattr(_mod, "LOCK_DB", nested)
        conn = _ensure_db()
        conn.close()
        assert nested.exists()


# ---------------------------------------------------------------------------
# acquire_lock
# ---------------------------------------------------------------------------


class TestAcquireLock:
    def test_returns_owner_token_string(self, tmp_db):
        token = acquire_lock("mylock", session_id="s1")  # pragma: allowlist secret
        assert isinstance(token, str)
        assert "s1" in token

    def test_token_contains_session_id(self, tmp_db):
        token = acquire_lock("mylock", session_id="session-abc")  # pragma: allowlist secret
        assert token.startswith("session-abc:")

    def test_lock_row_inserted(self, tmp_db):
        acquire_lock("mylock", session_id="s1")
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT lock_name, owner_session_id FROM session_locks WHERE lock_name = ?",
            ("mylock",),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "mylock"
        assert row[1] == "s1"

    def test_different_locks_coexist(self, tmp_db):
        token_a = acquire_lock("lock-a", session_id="s1")
        token_b = acquire_lock("lock-b", session_id="s2")
        assert token_a != token_b

    def test_second_acquire_same_lock_times_out(self, tmp_db):
        acquire_lock("shared", session_id="s1")
        with pytest.raises(TimeoutError):
            acquire_lock("shared", session_id="s2", timeout_seconds=0.1, retry_interval_seconds=0.05)

    def test_timeout_error_message_contains_lock_name(self, tmp_db):
        acquire_lock("contested-lock", session_id="owner")
        with pytest.raises(TimeoutError, match="contested-lock"):
            acquire_lock(
                "contested-lock",
                session_id="waiter",
                timeout_seconds=0.1,
                retry_interval_seconds=0.05,
            )

    def test_expired_lock_can_be_reacquired(self, tmp_db):
        """A lock whose expires_at is in the past is treated as stale and cleared."""
        import concurrency.session_lock as _mod
        from datetime import datetime, timedelta, timezone

        # Manually insert an already-expired lock
        conn = _ensure_db()
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        conn.execute(
            "INSERT INTO session_locks (lock_name, owner_session_id, owner_token, acquired_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("stale-lock", "old-session", "old-token", _utc_iso(past), _utc_iso(past)),
        )
        conn.commit()
        conn.close()

        # Should succeed immediately because the stale lock is evicted
        token = acquire_lock("stale-lock", session_id="new-session", timeout_seconds=1.0)  # pragma: allowlist secret
        assert "new-session" in token

    def test_lease_seconds_stored_in_db(self, tmp_db):
        acquire_lock("lease-test", session_id="s1", lease_seconds=600)
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT expires_at, acquired_at FROM session_locks WHERE lock_name = ?",
            ("lease-test",),
        ).fetchone()
        conn.close()
        acquired = _parse_iso(row[1])
        expires = _parse_iso(row[0])
        delta = (expires - acquired).total_seconds()
        assert abs(delta - 600) < 5  # allow a few seconds of clock drift


# ---------------------------------------------------------------------------
# release_lock
# ---------------------------------------------------------------------------


class TestReleaseLock:
    def test_release_removes_row(self, tmp_db):
        token = acquire_lock("rel-lock", session_id="s1")  # pragma: allowlist secret
        release_lock("rel-lock", token)
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute("SELECT * FROM session_locks WHERE lock_name = ?", ("rel-lock",)).fetchone()
        conn.close()
        assert row is None

    def test_release_wrong_token_does_not_remove(self, tmp_db):
        acquire_lock("other-lock", session_id="s1")
        release_lock("other-lock", "wrong-token")
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute("SELECT * FROM session_locks WHERE lock_name = ?", ("other-lock",)).fetchone()
        conn.close()
        assert row is not None

    def test_release_nonexistent_lock_is_noop(self, tmp_db):
        # Should not raise even if lock does not exist
        release_lock("ghost-lock", "any-token")

    def test_released_lock_can_be_reacquired(self, tmp_db):
        token = acquire_lock("reuse", session_id="s1")  # pragma: allowlist secret
        release_lock("reuse", token)
        new_token = acquire_lock("reuse", session_id="s2")  # pragma: allowlist secret
        assert "s2" in new_token


# ---------------------------------------------------------------------------
# session_lock context manager
# ---------------------------------------------------------------------------


class TestSessionLockContextManager:
    def test_yields_owner_token(self, tmp_db):
        with session_lock("ctx-lock", session_id="s1") as token:
            assert isinstance(token, str)
            assert "s1" in token

    def test_lock_released_on_exit(self, tmp_db):
        with session_lock("ctx-lock-2", session_id="s1"):
            pass
        # Should be able to re-acquire after the context exits
        token = acquire_lock("ctx-lock-2", session_id="s2")  # pragma: allowlist secret
        assert token is not None

    def test_lock_released_on_exception(self, tmp_db):
        try:
            with session_lock("exc-lock", session_id="s1"):
                raise ValueError("intentional error")
        except ValueError:
            pass
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute("SELECT * FROM session_locks WHERE lock_name = ?", ("exc-lock",)).fetchone()
        conn.close()
        assert row is None

    def test_nested_different_locks_allowed(self, tmp_db):
        with session_lock("outer", session_id="s1") as t1:
            with session_lock("inner", session_id="s1") as t2:
                assert t1 != t2

    def test_contention_raises_timeout(self, tmp_db):
        with session_lock("blocked", session_id="holder"):
            with pytest.raises(TimeoutError):
                with session_lock(
                    "blocked",
                    session_id="waiter",
                    timeout_seconds=0.1,
                ):
                    pass


# ---------------------------------------------------------------------------
# Concurrency: thread-safety smoke test
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_only_one_thread_holds_lock_at_a_time(self, tmp_db):
        """Two threads racing for the same lock; critical section must be atomic."""
        results: list[str] = []
        errors: list[Exception] = []

        def worker(name: str) -> None:
            try:
                with session_lock("race", session_id=name, timeout_seconds=5.0):
                    results.append(f"{name}-enter")
                    time.sleep(0.02)
                    results.append(f"{name}-exit")
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker, args=("thread-1",))
        t2 = threading.Thread(target=worker, args=("thread-2",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not errors, f"Unexpected errors: {errors}"
        # Entries should not interleave: exit must directly follow enter
        assert len(results) == 4
        # e.g. [enter-1, exit-1, enter-2, exit-2] or [enter-2, exit-2, enter-1, exit-1]
        for i in range(0, 4, 2):
            enter, exit_ = results[i], results[i + 1]
            assert enter.endswith("-enter")
            assert exit_.endswith("-exit")
            assert enter.split("-")[0] == exit_.split("-")[0]
