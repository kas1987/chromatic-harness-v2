"""Tests for the DB layer in 02_RUNTIME/api/db.py.

Covers:
- init_db: all tables created, idempotent execution
- get_db: yields an aiosqlite connection with row_factory set
- CHROMATIC_DB_PATH env-var override
"""

from __future__ import annotations

import os
import asyncio
import tempfile
from pathlib import Path

import pytest
import aiosqlite

# conftest already puts 02_RUNTIME/api on sys.path
import db as db_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_TABLES = {
    "missions",
    "magnet_events",
    "beads",
    "agent_profiles",
    "users",
}


async def _list_tables(conn: aiosqlite.Connection) -> set[str]:
    async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
        rows = await cur.fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_creates_all_tables(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())

            async def _check():
                async with aiosqlite.connect(db_path) as conn:
                    return await _list_tables(conn)

            tables = asyncio.get_event_loop().run_until_complete(_check())
            assert _EXPECTED_TABLES.issubset(tables)
        finally:
            del os.environ["CHROMATIC_DB_PATH"]

    def test_idempotent_double_init(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test2.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
            # Second init must not raise
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
        finally:
            del os.environ["CHROMATIC_DB_PATH"]

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = str(tmp_path / "subdir" / "deeper" / "db.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = nested
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
            assert Path(nested).exists()
        finally:
            del os.environ["CHROMATIC_DB_PATH"]


# ---------------------------------------------------------------------------
# _db_path / env var
# ---------------------------------------------------------------------------


class TestDbPath:
    def test_default_path_used_when_no_env(self) -> None:
        os.environ.pop("CHROMATIC_DB_PATH", None)
        path = db_module._db_path()
        assert path == db_module._DEFAULT_DB_PATH

    def test_env_var_overrides_path(self) -> None:
        os.environ["CHROMATIC_DB_PATH"] = "/tmp/override.sqlite"
        try:
            path = db_module._db_path()
            assert path == "/tmp/override.sqlite"
        finally:
            del os.environ["CHROMATIC_DB_PATH"]


# ---------------------------------------------------------------------------
# get_db
# ---------------------------------------------------------------------------


class TestGetDb:
    def test_get_db_yields_connection_with_row_factory(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "getdb.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path

        async def _run():
            await db_module.init_db()
            gen = db_module.get_db()
            conn = await gen.__anext__()
            assert isinstance(conn, aiosqlite.Connection)
            assert conn.row_factory is aiosqlite.Row
            # Clean shutdown
            try:
                await gen.athrow(GeneratorExit)
            except (GeneratorExit, StopAsyncIteration):
                pass

        try:
            asyncio.get_event_loop().run_until_complete(_run())
        finally:
            del os.environ["CHROMATIC_DB_PATH"]

    def test_get_db_connection_supports_queries(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "query.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path

        async def _run():
            await db_module.init_db()
            async for conn in db_module.get_db():
                # Should be able to execute a query without error
                async with conn.execute("SELECT 1") as cur:
                    row = await cur.fetchone()
                assert row is not None
                break  # only need one iteration

        try:
            asyncio.get_event_loop().run_until_complete(_run())
        finally:
            del os.environ["CHROMATIC_DB_PATH"]


# ---------------------------------------------------------------------------
# Table schema checks
# ---------------------------------------------------------------------------


class TestTableSchemas:
    def _get_columns(self, db_path: str, table: str) -> list[str]:
        async def _run():
            async with aiosqlite.connect(db_path) as conn:
                async with conn.execute(f"PRAGMA table_info({table})") as cur:
                    rows = await cur.fetchall()
            return [r[1] for r in rows]  # column names at index 1

        return asyncio.get_event_loop().run_until_complete(_run())

    def test_missions_table_schema(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "schema.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
            cols = self._get_columns(db_path, "missions")
            assert "mission_id" in cols
            assert "data" in cols
            assert "created_at" in cols
        finally:
            del os.environ["CHROMATIC_DB_PATH"]

    def test_magnet_events_table_schema(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "schema2.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
            cols = self._get_columns(db_path, "magnet_events")
            assert "event_id" in cols
            assert "mission_id" in cols
            assert "data" in cols
        finally:
            del os.environ["CHROMATIC_DB_PATH"]

    def test_users_table_schema(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "schema3.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
            cols = self._get_columns(db_path, "users")
            assert "user_id" in cols
            assert "username" in cols
            assert "hashed_password" in cols
            assert "role" in cols
        finally:
            del os.environ["CHROMATIC_DB_PATH"]

    def test_agent_profiles_table_schema(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "schema4.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
            cols = self._get_columns(db_path, "agent_profiles")
            assert "agent_id" in cols
            assert "data" in cols
            assert "updated_at" in cols
        finally:
            del os.environ["CHROMATIC_DB_PATH"]

    def test_beads_table_schema(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "schema5.sqlite")
        os.environ["CHROMATIC_DB_PATH"] = db_path
        try:
            asyncio.get_event_loop().run_until_complete(db_module.init_db())
            cols = self._get_columns(db_path, "beads")
            assert "bead_id" in cols
            assert "mission_id" in cols
            assert "data" in cols
        finally:
            del os.environ["CHROMATIC_DB_PATH"]
