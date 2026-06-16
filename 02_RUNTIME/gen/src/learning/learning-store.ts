/**
 * SQLite-backed store for task outcomes and routing patterns.
 * All operations are synchronous (better-sqlite3).
 */

import Database from "better-sqlite3";
import { nanoid } from "nanoid";
import type { TaskOutcome, RoutingPattern } from "./learning-types";

export class LearningStore {
  constructor(private db: Database.Database) {
    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS task_outcomes (
        id           TEXT PRIMARY KEY,
        task_id      TEXT NOT NULL,
        agent_role   TEXT NOT NULL,
        project_id   TEXT NOT NULL,
        intent       TEXT NOT NULL,
        tool_used    TEXT NOT NULL,
        succeeded    INTEGER NOT NULL,
        duration_ms  INTEGER NOT NULL,
        tokens_used  INTEGER NOT NULL,
        error_message TEXT,
        recorded_at  TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS routing_patterns (
        id              TEXT PRIMARY KEY,
        agent_role      TEXT NOT NULL,
        intent          TEXT NOT NULL,
        preferred_tool  TEXT NOT NULL,
        success_rate    REAL NOT NULL,
        avg_duration_ms REAL NOT NULL,
        sample_count    INTEGER NOT NULL,
        last_updated_at TEXT NOT NULL,
        UNIQUE(agent_role, intent)
      );

      CREATE INDEX IF NOT EXISTS idx_outcomes_role_intent
        ON task_outcomes(agent_role, intent);
    `);
    this.migrateTaskOutcomesRoutingColumns();
  }

  private migrateTaskOutcomesRoutingColumns(): void {
    const cols = this.db.prepare("PRAGMA table_info(task_outcomes)").all() as { name: string }[];
    const names = new Set(cols.map((c) => c.name));
    const add = (name: string, sqlType: string) => {
      if (!names.has(name)) {
        this.db.exec(`ALTER TABLE task_outcomes ADD COLUMN ${name} ${sqlType}`);
      }
    };
    add("prompt_intent", "TEXT");
    add("prompt_scope", "TEXT");
    add("active_llm", "TEXT");
    add("suggested_llm", "TEXT");
  }

  // ---------------------------------------------------------------------------
  // Outcomes
  // ---------------------------------------------------------------------------

  recordOutcome(
    outcome: Omit<TaskOutcome, "id" | "recordedAt">,
  ): TaskOutcome {
    const id = nanoid();
    const recordedAt = new Date().toISOString();

    this.db
      .prepare(
        `INSERT INTO task_outcomes
           (id, task_id, agent_role, project_id, intent, tool_used,
            succeeded, duration_ms, tokens_used, error_message, recorded_at,
            prompt_intent, prompt_scope, active_llm, suggested_llm)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        id,
        outcome.taskId,
        outcome.agentRole,
        outcome.projectId,
        outcome.intent,
        outcome.toolUsed,
        outcome.succeeded ? 1 : 0,
        outcome.durationMs,
        outcome.tokensUsed,
        outcome.errorMessage ?? null,
        recordedAt,
        outcome.promptIntent ?? null,
        outcome.promptScope ?? null,
        outcome.activeLlm ?? null,
        outcome.suggestedLlm ?? null,
      );

    return { ...outcome, id, recordedAt };
  }

  /**
   * Returns outcomes for a given (agentRole, intent) pair,
   * most-recent first. Pass limit=0 to return all.
   */
  getOutcomesForIntent(
    agentRole: string,
    intent: string,
    limit = 0,
  ): TaskOutcome[] {
    const sql =
      limit > 0
        ? `SELECT * FROM task_outcomes
           WHERE agent_role = ? AND intent = ?
           ORDER BY recorded_at DESC
           LIMIT ?`
        : `SELECT * FROM task_outcomes
           WHERE agent_role = ? AND intent = ?
           ORDER BY recorded_at DESC`;

    const rows = limit > 0
      ? (this.db.prepare(sql).all(agentRole, intent, limit) as any[])
      : (this.db.prepare(sql).all(agentRole, intent) as any[]);

    return rows.map(this.rowToOutcome);
  }

  // ---------------------------------------------------------------------------
  // Patterns
  // ---------------------------------------------------------------------------

  upsertPattern(
    pattern: Omit<RoutingPattern, "id" | "lastUpdatedAt">,
  ): RoutingPattern {
    const lastUpdatedAt = new Date().toISOString();

    // Check if a row already exists so we can preserve its id
    const existing = this.db
      .prepare(
        `SELECT id FROM routing_patterns WHERE agent_role = ? AND intent = ?`,
      )
      .get(pattern.agentRole, pattern.intent) as { id: string } | undefined;

    const id = existing?.id ?? nanoid();

    this.db
      .prepare(
        `INSERT INTO routing_patterns
           (id, agent_role, intent, preferred_tool, success_rate,
            avg_duration_ms, sample_count, last_updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(agent_role, intent) DO UPDATE SET
           preferred_tool  = excluded.preferred_tool,
           success_rate    = excluded.success_rate,
           avg_duration_ms = excluded.avg_duration_ms,
           sample_count    = excluded.sample_count,
           last_updated_at = excluded.last_updated_at`,
      )
      .run(
        id,
        pattern.agentRole,
        pattern.intent,
        pattern.preferredTool,
        pattern.successRate,
        pattern.avgDurationMs,
        pattern.sampleCount,
        lastUpdatedAt,
      );

    return { ...pattern, id, lastUpdatedAt };
  }

  getPattern(agentRole: string, intent: string): RoutingPattern | null {
    const row = this.db
      .prepare(
        `SELECT * FROM routing_patterns WHERE agent_role = ? AND intent = ?`,
      )
      .get(agentRole, intent) as any | undefined;

    return row ? this.rowToPattern(row) : null;
  }

  getAllPatterns(agentRole?: string): RoutingPattern[] {
    const rows = agentRole
      ? (this.db
          .prepare(
            `SELECT * FROM routing_patterns WHERE agent_role = ? ORDER BY last_updated_at DESC`,
          )
          .all(agentRole) as any[])
      : (this.db
          .prepare(
            `SELECT * FROM routing_patterns ORDER BY last_updated_at DESC`,
          )
          .all() as any[]);

    return rows.map(this.rowToPattern);
  }

  /**
   * Reads all outcomes for (agentRole, intent), computes aggregate stats,
   * and upserts a routing pattern. Returns null if there are fewer than 3 samples.
   */
  computeAndStorePattern(
    agentRole: string,
    intent: string,
  ): RoutingPattern | null {
    const outcomes = this.getOutcomesForIntent(agentRole, intent);

    if (outcomes.length < 3) {
      return null;
    }

    // Aggregate per-tool stats
    const toolStats: Record<
      string,
      { successes: number; total: number; totalDurationMs: number }
    > = {};

    for (const o of outcomes) {
      if (!toolStats[o.toolUsed]) {
        toolStats[o.toolUsed] = { successes: 0, total: 0, totalDurationMs: 0 };
      }
      toolStats[o.toolUsed].total += 1;
      toolStats[o.toolUsed].totalDurationMs += o.durationMs;
      if (o.succeeded) {
        toolStats[o.toolUsed].successes += 1;
      }
    }

    // Overall stats across all tools
    const totalSuccesses = outcomes.filter((o) => o.succeeded).length;
    const successRate = totalSuccesses / outcomes.length;
    const avgDurationMs =
      outcomes.reduce((sum, o) => sum + o.durationMs, 0) / outcomes.length;

    // Preferred tool = the one with the highest success rate (ties broken by more samples)
    const preferredTool = Object.entries(toolStats).reduce(
      (best, [tool, stats]) => {
        const rate = stats.successes / stats.total;
        const bestRate = best.successes / best.total;
        return rate > bestRate || (rate === bestRate && stats.total > best.total)
          ? { tool, ...stats }
          : best;
      },
      { tool: outcomes[0].toolUsed, ...toolStats[outcomes[0].toolUsed] },
    ).tool;

    return this.upsertPattern({
      agentRole,
      intent,
      preferredTool,
      successRate,
      avgDurationMs,
      sampleCount: outcomes.length,
    });
  }

  // ---------------------------------------------------------------------------
  // Row mappers
  // ---------------------------------------------------------------------------

  private rowToOutcome(r: any): TaskOutcome {
    return {
      id: r.id,
      taskId: r.task_id,
      agentRole: r.agent_role,
      projectId: r.project_id,
      intent: r.intent,
      toolUsed: r.tool_used,
      succeeded: Boolean(r.succeeded),
      durationMs: r.duration_ms,
      tokensUsed: r.tokens_used,
      errorMessage: r.error_message ?? undefined,
      recordedAt: r.recorded_at,
      promptIntent: r.prompt_intent ?? undefined,
      promptScope: r.prompt_scope ?? undefined,
      activeLlm: r.active_llm ?? undefined,
      suggestedLlm: r.suggested_llm ?? undefined,
    };
  }

  private rowToPattern(r: any): RoutingPattern {
    return {
      id: r.id,
      agentRole: r.agent_role,
      intent: r.intent,
      preferredTool: r.preferred_tool,
      successRate: r.success_rate,
      avgDurationMs: r.avg_duration_ms,
      sampleCount: r.sample_count,
      lastUpdatedAt: r.last_updated_at,
    };
  }
}
