import fs from "fs";
import path from "path";

// Resolve to D:/.04_Prism/.agents/hop/dispatch.jsonl
// __dirname = gen/src/utils/ → ../../../ = project root
const AUDIT_PATH =
  process.env.HOP_AUDIT_PATH ??
  path.resolve(__dirname, "../../../.agents/hop/dispatch.jsonl");

export interface HopAuditEntry {
  hop_id: string;
  source_skill?: string;
  destination?: string;
  route_method: string;   // rule_id or "dead-letter"
  confidence: number;
  dead_lettered: boolean;
  timestamp: string;
  duration_ms: number;
  sessionId?: string;
}

/**
 * Append a hop dispatch audit entry to the JSONL log.
 * Fail-open: any write error is swallowed silently.
 * Audit loss is acceptable; blocking a request is not.
 */
export function writeHopAudit(entry: HopAuditEntry): void {
  try {
    fs.mkdirSync(path.dirname(AUDIT_PATH), { recursive: true });
    fs.appendFileSync(AUDIT_PATH, JSON.stringify(entry) + "\n", "utf-8");
  } catch {
    // Intentionally swallowed — audit failure must never block routing
  }
}
