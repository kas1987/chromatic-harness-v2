import type Database from "better-sqlite3";
import { nanoid } from "nanoid";
import type { LlmProvider } from "../llm/llm-types.js";

export interface ModelPerformanceRecord {
  model: string;
  intent: string;
  scope: string;
  successCount: number;
  failureCount: number;
  avgLatencyMs: number;
  avgCostUsd: number;
}

interface RawRow {
  id: string;
  model: string;
  intent: string;
  scope: string;
  success_count: number;
  failure_count: number;
  avg_latency_ms: number;
  avg_cost_usd: number;
  updated_at: string;
}

const CREATE_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS model_performance (
  id TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  intent TEXT NOT NULL,
  scope TEXT NOT NULL,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  avg_latency_ms REAL DEFAULT 0,
  avg_cost_usd REAL DEFAULT 0,
  updated_at TEXT NOT NULL,
  UNIQUE(model, intent, scope)
)
`;

export class ModelPerformanceTracker {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
    this.db.exec(CREATE_TABLE_SQL);
  }

  record(
    model: LlmProvider,
    intent: string,
    scope: string,
    outcome: "success" | "failure",
    latencyMs: number,
    costUsd: number,
  ): void {
    const existing = this.db
      .prepare<[string, string, string], RawRow>(
        "SELECT * FROM model_performance WHERE model = ? AND intent = ? AND scope = ?",
      )
      .get(model, intent, scope);

    const now = new Date().toISOString();

    if (existing) {
      const oldCount = existing.success_count + existing.failure_count;
      const newSuccessCount =
        existing.success_count + (outcome === "success" ? 1 : 0);
      const newFailureCount =
        existing.failure_count + (outcome === "failure" ? 1 : 0);

      const newAvgLatency =
        (existing.avg_latency_ms * oldCount + latencyMs) / (oldCount + 1);
      const newAvgCost =
        (existing.avg_cost_usd * oldCount + costUsd) / (oldCount + 1);

      this.db
        .prepare(
          `UPDATE model_performance
           SET success_count = ?, failure_count = ?, avg_latency_ms = ?, avg_cost_usd = ?, updated_at = ?
           WHERE model = ? AND intent = ? AND scope = ?`,
        )
        .run(
          newSuccessCount,
          newFailureCount,
          newAvgLatency,
          newAvgCost,
          now,
          model,
          intent,
          scope,
        );
    } else {
      this.db
        .prepare(
          `INSERT INTO model_performance (id, model, intent, scope, success_count, failure_count, avg_latency_ms, avg_cost_usd, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .run(
          nanoid(),
          model,
          intent,
          scope,
          outcome === "success" ? 1 : 0,
          outcome === "failure" ? 1 : 0,
          latencyMs,
          costUsd,
          now,
        );
    }
  }

  getBestModel(intent: string, scope: string): LlmProvider | null {
    const rows = this.db
      .prepare<[string, string], RawRow>(
        `SELECT * FROM model_performance
         WHERE intent = ? AND scope = ? AND success_count >= 5`,
      )
      .all(intent, scope);

    if (rows.length === 0) return null;

    let best: RawRow | null = null;
    let bestRate = -1;

    for (const row of rows) {
      const total = row.success_count + row.failure_count;
      const rate = total > 0 ? row.success_count / total : 0;
      if (rate > bestRate) {
        bestRate = rate;
        best = row;
      }
    }

    return best ? (best.model as LlmProvider) : null;
  }

  getStats(): ModelPerformanceRecord[] {
    const rows = this.db
      .prepare<[], RawRow>("SELECT * FROM model_performance")
      .all();

    return rows.map((row) => ({
      model: row.model,
      intent: row.intent,
      scope: row.scope,
      successCount: row.success_count,
      failureCount: row.failure_count,
      avgLatencyMs: row.avg_latency_ms,
      avgCostUsd: row.avg_cost_usd,
    }));
  }
}
