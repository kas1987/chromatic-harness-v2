import type Database from "better-sqlite3";
import { nanoid } from "nanoid";

const CREATE_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS routing_decisions (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  hook_event TEXT NOT NULL,
  session_id TEXT,
  task_id TEXT,
  tool_name TEXT,
  suggested_llm TEXT,
  actual_llm TEXT,
  pretool_routing_source TEXT,
  routing_reconciliation TEXT,
  prompt_intent TEXT,
  prompt_scope TEXT,
  session_hint_age_bucket TEXT,
  intent_tool_coherence TEXT,
  skill_id TEXT,
  skill_dispatch_target TEXT,
  skill_dispatch_mode TEXT
)`;

const CREATE_INDEX_SQL = [
  "CREATE INDEX IF NOT EXISTS idx_routing_decisions_ts ON routing_decisions(ts)",
  "CREATE INDEX IF NOT EXISTS idx_routing_decisions_session ON routing_decisions(session_id)",
];

export interface RoutingDecisionRow {
  hookEvent: string;
  sessionId?: string;
  taskId?: string;
  toolName?: string;
  suggestedLlm?: string;
  actualLlm?: string;
  pretoolRoutingSource?: string;
  routingReconciliation?: string;
  promptIntent?: string;
  promptScope?: string;
  sessionHintAgeBucket?: string;
  intentToolCoherence?: string;
  skillId?: string;
  skillDispatchTarget?: string;
  skillDispatchMode?: string;
}

export class RoutingDecisionLog {
  constructor(private db: Database.Database) {
    this.db.exec(CREATE_TABLE_SQL);
    for (const sql of CREATE_INDEX_SQL) {
      this.db.exec(sql);
    }
  }

  append(row: RoutingDecisionRow): void {
    const id = nanoid();
    const ts = new Date().toISOString();
    this.db
      .prepare(
        `INSERT INTO routing_decisions (
          id, ts, hook_event, session_id, task_id, tool_name,
          suggested_llm, actual_llm, pretool_routing_source, routing_reconciliation,
          prompt_intent, prompt_scope, session_hint_age_bucket, intent_tool_coherence,
          skill_id, skill_dispatch_target, skill_dispatch_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        id,
        ts,
        row.hookEvent,
        row.sessionId ?? null,
        row.taskId ?? null,
        row.toolName ?? null,
        row.suggestedLlm ?? null,
        row.actualLlm ?? null,
        row.pretoolRoutingSource ?? null,
        row.routingReconciliation ?? null,
        row.promptIntent ?? null,
        row.promptScope ?? null,
        row.sessionHintAgeBucket ?? null,
        row.intentToolCoherence ?? null,
        row.skillId ?? null,
        row.skillDispatchTarget ?? null,
        row.skillDispatchMode ?? null,
      );
  }
}
