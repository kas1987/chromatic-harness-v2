import Database from "better-sqlite3";
import type { LlmProvider } from "../llm/llm-types.js";

/**
 * Why a delegation attempt failed.
 * Used to decide whether to retry, fall back, or escalate.
 */
export type DelegationFailureReason =
  | "timeout"           // exceeded time budget
  | "unavailable"       // provider isAvailable() returned false
  | "schema_invalid"    // response didn't match expectedOutputFormat
  | "low_confidence"    // LLM self-reported or heuristic confidence < threshold
  | "empty_response"    // provider returned empty/null string
  | "provider_error"    // provider threw an exception
  | "retry_exhausted";  // hit max retries without success

export interface DelegationRecord {
  id: string;
  traceId: string;
  attemptNumber: number;
  provider: LlmProvider;
  model: string;
  /** Prompt sent to the provider (from buildDelegationPrompt). */
  promptSent: string;
  /** Raw response from the provider. Null if failed before getting a response. */
  response: string | null;
  success: boolean;
  latencyMs: number;
  failureReason: DelegationFailureReason | null;
  /** Whether this attempt caused a fallback to be triggered. */
  fallbackTriggered: boolean;
  /** Which provider resolved the task after fallback. Null if still pending. */
  resolvedBy: LlmProvider | null;
  /** Human-readable explanation for the fallback decision. */
  fallbackNote: string | null;
  createdAt: string;
}

/**
 * SQLite-backed logger for all delegation attempts.
 *
 * Every time the orchestration layer delegates a task to a provider,
 * it records the attempt here. This gives us:
 *   - A full audit trail of what was sent to which LLM
 *   - Failure pattern analysis (which providers fail most often)
 *   - Fallback history (how often does each provider cause a fallback)
 *   - Latency tracking per provider
 */
export class DelegationLog {
  constructor(private db: Database.Database) {
    this.ensureTable();
  }

  private ensureTable(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS delegation_log (
        id              TEXT PRIMARY KEY,
        trace_id        TEXT NOT NULL,
        attempt_number  INTEGER NOT NULL DEFAULT 1,
        provider        TEXT NOT NULL,
        model           TEXT NOT NULL,
        prompt_sent     TEXT NOT NULL,
        response        TEXT,
        success         INTEGER NOT NULL DEFAULT 0,
        latency_ms      INTEGER NOT NULL DEFAULT 0,
        failure_reason  TEXT,
        fallback_triggered INTEGER NOT NULL DEFAULT 0,
        resolved_by     TEXT,
        fallback_note   TEXT,
        created_at      TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_delegation_trace ON delegation_log(trace_id);
      CREATE INDEX IF NOT EXISTS idx_delegation_provider ON delegation_log(provider, success);
      CREATE INDEX IF NOT EXISTS idx_delegation_created ON delegation_log(created_at);
    `);
  }

  record(entry: Omit<DelegationRecord, "id" | "createdAt">): DelegationRecord {
    const id = `dlg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const createdAt = new Date().toISOString();
    this.db.prepare(`
      INSERT INTO delegation_log
        (id, trace_id, attempt_number, provider, model, prompt_sent, response,
         success, latency_ms, failure_reason, fallback_triggered, resolved_by,
         fallback_note, created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    `).run(
      id,
      entry.traceId,
      entry.attemptNumber,
      entry.provider,
      entry.model,
      entry.promptSent,
      entry.response ?? null,
      entry.success ? 1 : 0,
      entry.latencyMs,
      entry.failureReason ?? null,
      entry.fallbackTriggered ? 1 : 0,
      entry.resolvedBy ?? null,
      entry.fallbackNote ?? null,
      createdAt,
    );
    return { ...entry, id, createdAt };
  }

  /** All attempts for a given trace ID, in order. */
  getByTrace(traceId: string): DelegationRecord[] {
    return (this.db.prepare(
      "SELECT * FROM delegation_log WHERE trace_id = ? ORDER BY attempt_number ASC"
    ).all(traceId) as Record<string, unknown>[]).map(rowToRecord);
  }

  /** Recent failure records — useful for operational monitoring. */
  recentFailures(limitHours = 24, maxRows = 50): DelegationRecord[] {
    const since = new Date(Date.now() - limitHours * 3_600_000).toISOString();
    return (this.db.prepare(
      "SELECT * FROM delegation_log WHERE success = 0 AND created_at > ? ORDER BY created_at DESC LIMIT ?"
    ).all(since, maxRows) as Record<string, unknown>[]).map(rowToRecord);
  }

  /**
   * Failure rate per provider over the last N hours.
   */
  providerStats(hours = 24): { provider: string; total: number; failed: number }[] {
    const since = new Date(Date.now() - hours * 3_600_000).toISOString();
    return this.db.prepare(`
      SELECT provider,
             COUNT(*) as total,
             SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
      FROM delegation_log
      WHERE created_at > ?
      GROUP BY provider
    `).all(since) as { provider: string; total: number; failed: number }[];
  }

  /** Mark all attempts for a trace as resolved by the given provider. */
  markResolved(traceId: string, resolvedBy: LlmProvider): void {
    this.db.prepare(
      "UPDATE delegation_log SET resolved_by = ? WHERE trace_id = ? AND resolved_by IS NULL"
    ).run(resolvedBy, traceId);
  }
}

function rowToRecord(row: Record<string, unknown>): DelegationRecord {
  return {
    id:                row["id"] as string,
    traceId:           row["trace_id"] as string,
    attemptNumber:     row["attempt_number"] as number,
    provider:          row["provider"] as LlmProvider,
    model:             row["model"] as string,
    promptSent:        row["prompt_sent"] as string,
    response:          row["response"] as string | null,
    success:           Boolean(row["success"]),
    latencyMs:         row["latency_ms"] as number,
    failureReason:     (row["failure_reason"] as DelegationFailureReason) ?? null,
    fallbackTriggered: Boolean(row["fallback_triggered"]),
    resolvedBy:        (row["resolved_by"] as LlmProvider) ?? null,
    fallbackNote:      (row["fallback_note"] as string) ?? null,
    createdAt:         row["created_at"] as string,
  };
}
