/**
 * audit-logger.ts — Always-on structured JSONL audit log.
 *
 * Runs regardless of whether OTEL is configured. Writes one JSON record
 * per line to gen/logs/gen-audit.jsonl for every budget decision, block,
 * LLM routing choice, and hook event.
 *
 * This is the local observability floor — no external endpoint required.
 */

import fs from "fs";
import path from "path";

export type AuditEventKind =
  | "budget_decision"
  | "budget_block"
  | "budget_warn"
  | "budget_bypass"
  | "path_guard_bypass"
  | "llm_routing"
  | "hook_user_prompt"
  | "hook_pretool"
  | "hook_posttool"
  | "auth_fail"
  | "startup"
  | "policy_change"
  | "mode_change"
  | "t3_hard_stop"
  | "t3_approval_granted"
  | "t3_approval_rejected";

export interface AuditEvent {
  ts: string;           // ISO 8601
  kind: AuditEventKind;
  sessionId?: string;
  decision?: string;    // "allow" | "block" | "warn"
  reason?: string;
  model?: string;
  provider?: string;
  intent?: string;
  costUsd?: number;
  budgetRemainingPct?: number;
  toolName?: string;
  meta?: Record<string, unknown>;
}

class AuditLogger {
  private logPath: string;
  private ready = false;

  constructor() {
    // Resolve relative to this file's location: gen/src/otel → gen/logs/
    const genRoot = path.resolve(__dirname, "..", "..");
    const logsDir = path.join(genRoot, "logs");
    this.logPath = path.join(logsDir, "gen-audit.jsonl");
    this.ensureDir(logsDir);
    this.ready = true;
    this.write({ kind: "startup", decision: "init", reason: `AuditLogger ready — ${this.logPath}` });
  }

  write(event: Omit<AuditEvent, "ts">): void {
    if (!this.ready) return;
    const record: AuditEvent = { ts: new Date().toISOString(), ...event };
    try {
      fs.appendFileSync(this.logPath, JSON.stringify(record) + "\n", "utf8");
    } catch {
      // Non-fatal — never crash the service over logging
    }
  }

  private ensureDir(dir: string): void {
    try {
      fs.mkdirSync(dir, { recursive: true });
    } catch {
      this.ready = false;
    }
  }
}

// Singleton — import and call `auditLog.write(...)` anywhere in Gen
export const auditLog = new AuditLogger();
