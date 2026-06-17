/**
 * Tracks cost estimate accuracy: compares pre-execution estimates vs actual spend.
 * Flags estimates that were > 20% off from actuals.
 */
import Database from "better-sqlite3";
import { nanoid } from "nanoid";

export interface CostAccuracyRecord {
  id: string;
  taskId: string;
  model: string;
  estimatedCostUsd: number;
  actualCostUsd: number;
  accuracyPct: number;      // 100 * |estimated - actual| / actual
  flagged: boolean;          // true if accuracyPct > 20
  recordedAt: string;
}

export class CostAccuracyTracker {
  constructor(private db: Database.Database) {
    this.ensureTable();
  }

  private ensureTable(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS cost_accuracy (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        model TEXT NOT NULL,
        estimated_cost_usd REAL NOT NULL,
        actual_cost_usd REAL NOT NULL,
        accuracy_pct REAL NOT NULL,
        flagged INTEGER NOT NULL DEFAULT 0,
        recorded_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_cost_accuracy_task ON cost_accuracy(task_id);
      CREATE INDEX IF NOT EXISTS idx_cost_accuracy_flagged ON cost_accuracy(flagged);
    `);
  }

  recordCompletion(
    taskId: string,
    model: string,
    estimatedCostUsd: number,
    actualCostUsd: number,
  ): CostAccuracyRecord {
    const accuracyPct = actualCostUsd > 0
      ? Math.abs(estimatedCostUsd - actualCostUsd) / actualCostUsd * 100
      : 0;
    const flagged = accuracyPct > 20;

    const record: CostAccuracyRecord = {
      id: nanoid(),
      taskId,
      model,
      estimatedCostUsd,
      actualCostUsd,
      accuracyPct,
      flagged,
      recordedAt: new Date().toISOString(),
    };

    if (flagged) {
      console.warn(
        `[cost-accuracy] Estimate off by ${accuracyPct.toFixed(1)}% for task ${taskId}: ` +
        `estimated $${estimatedCostUsd.toFixed(4)}, actual $${actualCostUsd.toFixed(4)}`
      );
    }

    this.db.prepare(
      `INSERT INTO cost_accuracy (id, task_id, model, estimated_cost_usd, actual_cost_usd, accuracy_pct, flagged, recorded_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    ).run(record.id, taskId, model, estimatedCostUsd, actualCostUsd, accuracyPct, flagged ? 1 : 0, record.recordedAt);

    return record;
  }

  getFlaggedRecords(limit = 20): CostAccuracyRecord[] {
    return (this.db.prepare(
      `SELECT * FROM cost_accuracy WHERE flagged = 1 ORDER BY recorded_at DESC LIMIT ?`
    ).all(limit) as any[]).map(rowToRecord);
  }

  getAverageAccuracy(model?: string): number {
    const row = model
      ? this.db.prepare(`SELECT AVG(accuracy_pct) as avg FROM cost_accuracy WHERE model = ?`).get(model) as { avg: number | null }
      : this.db.prepare(`SELECT AVG(accuracy_pct) as avg FROM cost_accuracy`).get() as { avg: number | null };
    return row?.avg ?? 0;
  }

  getAccuracySummary(): { totalRecords: number; flaggedCount: number; avgAccuracyPct: number; byModel: Record<string, number> } {
    const total = this.db.prepare(`SELECT COUNT(*) as cnt FROM cost_accuracy`).get() as { cnt: number };
    const flagged = this.db.prepare(`SELECT COUNT(*) as cnt FROM cost_accuracy WHERE flagged = 1`).get() as { cnt: number };
    const avg = this.db.prepare(`SELECT AVG(accuracy_pct) as avg FROM cost_accuracy`).get() as { avg: number | null };
    const byModel = this.db.prepare(`SELECT model, AVG(accuracy_pct) as avg FROM cost_accuracy GROUP BY model`).all() as { model: string; avg: number }[];

    return {
      totalRecords: total.cnt,
      flaggedCount: flagged.cnt,
      avgAccuracyPct: avg.avg ?? 0,
      byModel: Object.fromEntries(byModel.map(r => [r.model, r.avg])),
    };
  }
}

function rowToRecord(row: any): CostAccuracyRecord {
  return {
    id: row.id,
    taskId: row.task_id,
    model: row.model,
    estimatedCostUsd: row.estimated_cost_usd,
    actualCostUsd: row.actual_cost_usd,
    accuracyPct: row.accuracy_pct,
    flagged: Boolean(row.flagged),
    recordedAt: row.recorded_at,
  };
}
