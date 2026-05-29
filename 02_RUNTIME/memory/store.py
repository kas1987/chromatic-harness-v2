"""Chromatic Harness v2 — System Memory Store.

Persistent SQLite-backed awareness layer.
Provides: learnings, governance rules, scope violations, session continuity.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
_DB_PATH = Path(
    os.environ.get(
        "CHROMATIC_MEMORY_DB",
        Path(__file__).resolve().parent.parent.parent
        / "06_DATA"
        / "system_memory.sqlite",
    )
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Learning:
    id: str
    title: str
    category: str
    confidence: str
    scope: str
    content: str
    source: str = ""
    epic: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    active: bool = True


@dataclass
class GovernanceRule:
    id: str
    rule_name: str
    category: str
    severity: str
    description: str
    enforcement: str
    pseudocode_fix: str = ""
    created_at: str = field(default_factory=_now)
    active: bool = True


@dataclass
class ScopeViolation:
    id: str
    mission_id: str
    task_id: str
    expected_scope: str
    violated_files: list[str]
    detected_by: str
    resolution: str
    created_at: str = field(default_factory=_now)
    severity: str = "warning"


class SystemMemoryStore:
    """SQLite-backed system memory."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else _DB_PATH

    async def _ensure_schema(self, conn: aiosqlite.Connection) -> None:
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        await conn.executescript(schema)
        await conn.commit()

    async def _conn(self) -> aiosqlite.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db_str = str(self.db_path)
        # Support shared in-memory databases for testing
        if db_str.startswith("file::memory:"):
            conn = await aiosqlite.connect(db_str, uri=True)
        else:
            conn = await aiosqlite.connect(db_str)
        conn.row_factory = sqlite3.Row
        await self._ensure_schema(conn)
        return conn

    async def _execute(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = await self._conn()
        try:
            cursor = await conn.execute(sql, params)
            # Only fetch if this is a SELECT-like query
            if sql.strip().upper().startswith(("SELECT", "PRAGMA")):
                rows = await cursor.fetchall()
            else:
                rows = []
            await conn.commit()
            return rows  # type: ignore[return-value]
        finally:
            await conn.close()

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = await self._conn()
        try:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            await conn.commit()
            return rows  # type: ignore[return-value]
        finally:
            await conn.close()

    async def _executemany(self, sql: str, params: list[tuple]) -> None:
        conn = await self._conn()
        try:
            await conn.executemany(sql, params)
            await conn.commit()
        finally:
            await conn.close()

    async def _executescript(self, script: str) -> None:
        conn = await self._conn()
        try:
            await conn.executescript(script)
            await conn.commit()
        finally:
            await conn.close()

    # ── Learnings ────────────────────────────────────────────────────────────

    async def insert_learning(self, learning: Learning) -> None:
        await self._execute(
            """INSERT OR REPLACE INTO learnings
               (id, title, category, confidence, scope, content, source, epic, created_at, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                learning.id,
                learning.title,
                learning.category,
                learning.confidence,
                learning.scope,
                learning.content,
                learning.source,
                learning.epic,
                learning.created_at,
                learning.active,
            ),
        )

    async def get_learnings(
        self,
        *,
        category: str | None = None,
        scope: str | None = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> list[Learning]:
        sql = "SELECT * FROM learnings WHERE 1=1"
        params: list[Any] = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if scope:
            sql += " AND scope = ?"
            params.append(scope)
        if active_only:
            sql += " AND active = 1"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = await self._execute(sql, tuple(params))
        return [Learning(**dict(r)) for r in rows]

    # ── Governance Rules ─────────────────────────────────────────────────────

    async def get_governance_rules(
        self,
        *,
        category: str | None = None,
        severity: str | None = None,
        active_only: bool = True,
    ) -> list[GovernanceRule]:
        sql = "SELECT * FROM governance_rules WHERE 1=1"
        params: list[Any] = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if active_only:
            sql += " AND active = 1"
        sql += " ORDER BY severity DESC, created_at DESC"
        rows = await self._execute(sql, tuple(params))
        return [GovernanceRule(**dict(r)) for r in rows]

    async def get_rule_by_name(self, name: str) -> GovernanceRule | None:
        rows = await self._execute(
            "SELECT * FROM governance_rules WHERE rule_name = ? LIMIT 1", (name,)
        )
        if rows:
            return GovernanceRule(**dict(rows[0]))
        return None

    # ── Scope Violations ─────────────────────────────────────────────────────

    async def record_violation(self, violation: ScopeViolation) -> None:
        await self._execute(
            """INSERT INTO scope_violations
               (id, mission_id, task_id, expected_scope, violated_files,
                detected_by, resolution, created_at, severity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                violation.id or str(uuid.uuid4()),
                violation.mission_id,
                violation.task_id,
                violation.expected_scope,
                json.dumps(violation.violated_files),
                violation.detected_by,
                violation.resolution,
                violation.created_at,
                violation.severity,
            ),
        )

    async def get_violations(
        self,
        mission_id: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[ScopeViolation]:
        sql = "SELECT * FROM scope_violations WHERE 1=1"
        params: list[Any] = []
        if mission_id:
            sql += " AND mission_id = ?"
            params.append(mission_id)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = await self._execute(sql, tuple(params))
        result = []
        for r in rows:
            d = dict(r)
            d["violated_files"] = json.loads(d["violated_files"])
            result.append(ScopeViolation(**d))
        return result

    # ── Session Continuity ─────────────────────────────────────────────────

    async def start_session(self, agent_id: str, project_context: dict) -> str:
        sid = str(uuid.uuid4())
        await self._execute(
            "INSERT INTO agent_sessions (id, agent_id, session_start, project_context) VALUES (?, ?, ?, ?)",
            (sid, agent_id, _now(), json.dumps(project_context)),
        )
        return sid

    async def end_session(
        self, session_id: str, outcome: str, injected_memory: list[str]
    ) -> None:
        await self._execute(
            "UPDATE agent_sessions SET session_end = ?, outcome = ?, injected_memory = ? WHERE id = ?",
            (_now(), outcome, json.dumps(injected_memory), session_id),
        )

    # ── Context Assembly ───────────────────────────────────────────────────

    async def assemble_context(
        self,
        *,
        mission_type: str = "",
        privacy_class: str = "",
        include_rules: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build a memory context packet for injection into agent prompts."""
        rules = await self.get_governance_rules(
            category=None,
            severity="critical" if privacy_class in ("P3", "P4") else None,
        )
        if include_rules:
            rules = [
                r
                for r in rules
                if r.rule_name in include_rules or r.category in include_rules
            ]

        recent_learnings = await self.get_learnings(
            scope="cross-cutting",
            active_only=True,
            limit=10,
        )
        recent_violations = await self.get_violations(severity="critical", limit=5)

        return {
            "governance_rules": [
                {
                    "name": r.rule_name,
                    "severity": r.severity,
                    "description": r.description,
                    "enforcement": r.enforcement,
                    "fix": r.pseudocode_fix,
                }
                for r in rules
            ],
            "recent_learnings": [
                {"title": l.title, "category": l.category, "content": l.content}
                for l in recent_learnings
            ],
            "recent_scope_violations": [
                {
                    "mission": v.mission_id,
                    "expected": v.expected_scope,
                    "files": v.violated_files,
                    "severity": v.severity,
                }
                for v in recent_violations
            ],
            "injected_at": _now(),
        }
