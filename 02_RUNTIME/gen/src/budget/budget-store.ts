/**
 * SQLite-backed store for TaskBudgetState records
 */

import Database from "better-sqlite3";
import { TaskBudgetState } from "./budget-types";

export class BudgetStore {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS budget_states (
        task_id TEXT PRIMARY KEY,
        agent_role TEXT NOT NULL,
        tokens_used INTEGER DEFAULT 0,
        external_calls INTEGER DEFAULT 0,
        handoffs INTEGER DEFAULT 0,
        wall_time_seconds REAL DEFAULT 0,
        started_at TEXT NOT NULL,
        warnings TEXT DEFAULT '[]',
        stopped INTEGER DEFAULT 0,
        stopped_reason TEXT
      );

      CREATE TABLE IF NOT EXISTS budget_config_overrides (
        role TEXT PRIMARY KEY,
        config_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS daily_budget_reset (
        id TEXT PRIMARY KEY,
        last_reset_date TEXT NOT NULL,
        last_reset_at TEXT NOT NULL,
        tokens_reset_count INTEGER DEFAULT 0
      );
    `);

    this.dailyReset();
  }

  /**
   * Reset daily token counts if UTC date has changed since last reset.
   * Uses SQLite transaction for atomicity (concurrent midnight resets safe).
   */
  dailyReset(): void {
    const today = new Date().toISOString().split("T")[0]; // YYYY-MM-DD

    const existing = this.db
      .prepare(
        "SELECT last_reset_date FROM daily_budget_reset WHERE id = 'singleton'"
      )
      .get() as { last_reset_date: string } | undefined;

    if (existing?.last_reset_date === today) {
      return; // Already reset today — idempotent
    }

    const resetTx = this.db.transaction(() => {
      // Double-check inside transaction (prevent TOCTOU)
      const check = this.db
        .prepare(
          "SELECT last_reset_date FROM daily_budget_reset WHERE id = 'singleton'"
        )
        .get() as { last_reset_date: string } | undefined;

      if (check?.last_reset_date === today) return; // Another concurrent reset won

      const result = this.db
        .prepare(
          "UPDATE budget_states SET tokens_used = 0 WHERE DATE(started_at) < DATE('now')"
        )
        .run();

      this.db
        .prepare(
          `INSERT OR REPLACE INTO daily_budget_reset (id, last_reset_date, last_reset_at, tokens_reset_count)
           VALUES ('singleton', ?, ?, ?)`
        )
        .run(today, new Date().toISOString(), result.changes);

      console.info(
        `[budget] Daily token reset: ${result.changes} tasks reset at UTC midnight`
      );
    });

    resetTx();
  }

  /**
   * Get total tokens used today (since last daily reset).
   */
  getTokensUsedToday(): number {
    const row = this.db
      .prepare(
        "SELECT COALESCE(SUM(tokens_used), 0) as total FROM budget_states WHERE DATE(started_at) >= DATE('now')"
      )
      .get() as { total: number };
    return row.total;
  }

  getOrCreate(taskId: string, agentRole: string): TaskBudgetState {
    const existing = this.getState(taskId);
    if (existing) {
      return existing;
    }

    const now = new Date().toISOString();
    this.db
      .prepare(
        `INSERT INTO budget_states
           (task_id, agent_role, tokens_used, external_calls, handoffs,
            wall_time_seconds, started_at, warnings, stopped, stopped_reason)
         VALUES (?, ?, 0, 0, 0, 0, ?, '[]', 0, NULL)`
      )
      .run(taskId, agentRole, now);

    return {
      taskId,
      agentRole,
      tokensUsed: 0,
      externalCalls: 0,
      handoffs: 0,
      wallTimeSeconds: 0,
      startedAt: now,
      warnings: [],
      stopped: false,
      stoppedReason: undefined,
    };
  }

  incrementTokens(taskId: string, tokens: number): void {
    this.db
      .prepare(
        `UPDATE budget_states SET tokens_used = tokens_used + ? WHERE task_id = ?`
      )
      .run(tokens, taskId);
  }

  incrementCalls(taskId: string): void {
    this.db
      .prepare(
        `UPDATE budget_states SET external_calls = external_calls + 1 WHERE task_id = ?`
      )
      .run(taskId);
  }

  updateWallTime(taskId: string): void {
    const row = this.db
      .prepare(`SELECT started_at FROM budget_states WHERE task_id = ?`)
      .get(taskId) as { started_at: string } | undefined;

    if (!row) return;

    const startedAt = new Date(row.started_at).getTime();
    const elapsedSeconds = (Date.now() - startedAt) / 1000;

    this.db
      .prepare(
        `UPDATE budget_states SET wall_time_seconds = ? WHERE task_id = ?`
      )
      .run(elapsedSeconds, taskId);
  }

  addWarning(taskId: string, warning: string): void {
    const row = this.db
      .prepare(`SELECT warnings FROM budget_states WHERE task_id = ?`)
      .get(taskId) as { warnings: string } | undefined;

    if (!row) return;

    const warnings: string[] = JSON.parse(row.warnings);
    warnings.push(warning);

    this.db
      .prepare(`UPDATE budget_states SET warnings = ? WHERE task_id = ?`)
      .run(JSON.stringify(warnings), taskId);
  }

  markStopped(taskId: string, reason: string): void {
    this.db
      .prepare(
        `UPDATE budget_states SET stopped = 1, stopped_reason = ? WHERE task_id = ?`
      )
      .run(reason, taskId);
  }

  getState(taskId: string): TaskBudgetState | null {
    const row = this.db
      .prepare(`SELECT * FROM budget_states WHERE task_id = ?`)
      .get(taskId) as Record<string, unknown> | undefined;

    if (!row) return null;
    return rowToState(row);
  }

  listActive(): TaskBudgetState[] {
    const rows = this.db
      .prepare(`SELECT * FROM budget_states WHERE stopped = 0`)
      .all() as Record<string, unknown>[];
    return rows.map(rowToState);
  }

  setConfigOverride(role: string, configJson: string): void {
    const now = new Date().toISOString();
    this.db
      .prepare(
        `INSERT OR REPLACE INTO budget_config_overrides (role, config_json, updated_at)
         VALUES (?, ?, ?)`
      )
      .run(role, configJson, now);
  }

  getConfigOverride(role: string): string | null {
    const row = this.db
      .prepare(
        `SELECT config_json FROM budget_config_overrides WHERE role = ?`
      )
      .get(role) as { config_json: string } | undefined;
    return row?.config_json ?? null;
  }
}

function rowToState(row: Record<string, unknown>): TaskBudgetState {
  return {
    taskId: row["task_id"] as string,
    agentRole: row["agent_role"] as string,
    tokensUsed: (row["tokens_used"] as number) ?? 0,
    externalCalls: (row["external_calls"] as number) ?? 0,
    handoffs: (row["handoffs"] as number) ?? 0,
    wallTimeSeconds: (row["wall_time_seconds"] as number) ?? 0,
    startedAt: row["started_at"] as string,
    warnings: JSON.parse((row["warnings"] as string) ?? "[]"),
    stopped: Boolean(row["stopped"]),
    stoppedReason: (row["stopped_reason"] as string | null) ?? undefined,
  };
}
