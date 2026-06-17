/**
 * Budget guard for policy enforcement on dangerous operations
 */

import { TaskContext } from "./context";
import { auditLog } from "../otel/audit-logger";

export interface BudgetDecision {
  continue: boolean;
  stopReason?: string;
  warningMessage?: string;
}

export class BudgetGuard {
  private dangerousPatterns = [
    // System-level destruction
    /rm\s+-rf\s+\/(?!home\/)/i,
    /rm\s+-rf\s+C:/i,
    /del\s+\/s\s+\/q\s+C:/i,
    /format\s+[A-Z]:/i,
    // Project directory wipes
    /rm\s+-rf\s+\.\//i,
    /rmdir\s+\/s\s+\/q/i,
    /find\s+.+-delete/i,
    // Git destructive operations
    /git\s+reset\s+--hard/i,
    /git\s+push\s+.*--force/i,
    /git\s+push\s+.*\s-f(\s|$)/i,
    // Database schema destruction
    /DROP\s+TABLE/i,
    /DROP\s+DATABASE/i,
    /DROP\s+SCHEMA/i,
    /TRUNCATE\s+TABLE/i,
    /ALTER\s+TABLE\s+\S+\s+DROP\s+COLUMN/i,
    // Infrastructure teardown
    /terraform\s+destroy/i,
    /kubectl\s+delete\s+namespace/i,
  ];

  private protectedPaths = [
    "/etc/passwd",
    "/etc/shadow",
    "/root/.ssh",
    "C:\\Windows\\System32",
    "C:\\Program Files",
  ];

  private sensitiveFilePatterns = [
    /\.env(\.(local|production|staging|development|test))?$/i,
    /\.pem$/i,
    /\.key$/i,
    /\bid_rsa\b/i,
    /credentials\.json$/i,
    /secrets\.ya?ml$/i,
  ];

  evaluateBashCommand(command: string, ctx: TaskContext): BudgetDecision {
    // Check for dangerous patterns
    for (const pattern of this.dangerousPatterns) {
      if (pattern.test(command)) {
        const reason = `Dangerous command blocked: ${pattern.source}`;
        auditLog.write({ kind: "budget_block", decision: "block", reason, toolName: "Bash", meta: { command: command.slice(0, 200) } });
        return { continue: false, stopReason: reason };
      }
    }

    // Check for protected paths
    for (const path of this.protectedPaths) {
      if (command.includes(path)) {
        const reason = `Protected path blocked: ${path}`;
        auditLog.write({ kind: "budget_block", decision: "block", reason, toolName: "Bash", meta: { command: command.slice(0, 200) } });
        return { continue: false, stopReason: reason };
      }
    }

    return { continue: true };
  }

  evaluateFileWrite(filePath: string, ctx: TaskContext): BudgetDecision {
    // Block writes to protected system paths
    for (const path of this.protectedPaths) {
      if (filePath.includes(path)) {
        return {
          continue: false,
          stopReason: `Protected path blocked: ${path}`,
        };
      }
    }

    // Block writes to sensitive credential/secret files
    const fileName = filePath.replace(/\\/g, "/").split("/").pop() ?? "";
    for (const pattern of this.sensitiveFilePatterns) {
      if (pattern.test(fileName) || pattern.test(filePath)) {
        const reason = `Sensitive file blocked: ${filePath}`;
        auditLog.write({ kind: "budget_block", decision: "block", reason, toolName: "Write", meta: { filePath } });
        return { continue: false, stopReason: reason };
      }
    }

    return { continue: true };
  }
}
