import type Database from "better-sqlite3";
import type { IntentClass, ScopeLevel } from "../prompting/prompt-normalizer.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DispatchMode = "recommend" | "inject_context" | "block";

/**
 * Symbolic dispatch target.
 *
 * - `mcp:<name>`       — route to a named MCP server (e.g. "mcp:github", "mcp:comfyui")
 * - `skill:<id>`       — delegate to another skill by id (e.g. "skill:nsfw-pr23")
 * - `gen:local`        — handle in Gen itself (no external dispatch required)
 * - `rudalo:dispatch`  — forward to rudalo-dispatch FastAPI at :8741
 */
export type DispatchTarget =
  | `mcp:${string}`
  | `skill:${string}`
  | "gen:local"
  | "rudalo:dispatch";

export interface SkillDispatchRule {
  id: number;
  skillId: string;
  skillGlob: string | null;
  intentFilter: string[] | null;
  scopeFilter: string[] | null;
  dispatchTarget: DispatchTarget;
  dispatchMode: DispatchMode;
  capabilityTags: string[] | null;
  costTier: "free" | "metered" | "local";
  fallbackTarget: DispatchTarget | null;
  priority: number;
  enabled: boolean;
  notes: string | null;
}

export interface SkillDispatchContext {
  skillId: string;
  skillArgs: Record<string, unknown>;
  sessionId?: string;
  intent?: IntentClass;
  scope?: ScopeLevel;
}

export interface SkillDispatchDecision {
  matched: boolean;
  target: DispatchTarget;
  mode: DispatchMode;
  fallback: DispatchTarget | null;
  rationale: string;
  ruleId: number | null;
  capabilityTags: string[];
}

// ---------------------------------------------------------------------------
// Default decision (no rule matched)
// ---------------------------------------------------------------------------

const DEFAULT_DECISION: SkillDispatchDecision = {
  matched: false,
  target: "gen:local",
  mode: "recommend",
  fallback: null,
  rationale: "No skill dispatch rule matched; defaulting to local gen handler.",
  ruleId: null,
  capabilityTags: [],
};

// Session-level cache TTL: 5 minutes (matches sessionRoutingStore TTL)
const SESSION_TTL_MS = 5 * 60 * 1000;

interface CachedDecision {
  decision: SkillDispatchDecision;
  expiresAt: number;
}

// ---------------------------------------------------------------------------
// SkillDispatchRouter
// ---------------------------------------------------------------------------

export class SkillDispatchRouter {
  /**
   * Session-level cache: sessionId → Map<skillId, CachedDecision>
   * Avoids re-querying the DB for the same skill within the same session window.
   */
  private sessionCache = new Map<string, Map<string, CachedDecision>>();

  constructor(private db: Database.Database) {}

  /**
   * Resolve the dispatch target for a given skill invocation.
   * Returns the first matching rule ordered by priority (ASC).
   * Falls back to DEFAULT_DECISION when nothing matches.
   */
  resolve(ctx: SkillDispatchContext): SkillDispatchDecision {
    // 1. Check session cache
    if (ctx.sessionId) {
      const cached = this.getSessionCached(ctx.sessionId, ctx.skillId);
      if (cached) {
        return { ...cached, rationale: cached.rationale + " [session-cached]" };
      }
    }

    // 2. Query DB and evaluate rules
    let decision: SkillDispatchDecision = DEFAULT_DECISION;
    try {
      const rules = this.loadRules(ctx.skillId);
      for (const rule of rules) {
        if (!this.matchesContext(rule, ctx)) continue;
        decision = {
          matched: true,
          target: rule.dispatchTarget,
          mode: rule.dispatchMode,
          fallback: rule.fallbackTarget,
          rationale: rule.notes ?? `Matched rule #${rule.id} (priority ${rule.priority})`,
          ruleId: rule.id,
          capabilityTags: rule.capabilityTags ?? [],
        };
        break; // first match wins (rules already sorted by priority ASC)
      }
    } catch (err) {
      console.warn("[skill-dispatch] Rule query failed, using default:", err);
      // Fail open
    }

    // 3. Write-back to session cache
    if (ctx.sessionId && decision.matched) {
      this.writeSessionCache(ctx.sessionId, ctx.skillId, decision);
    }

    return decision;
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  private loadRules(skillId: string): SkillDispatchRule[] {
    const rows = this.db
      .prepare(
        `SELECT * FROM skill_dispatch_rules
         WHERE enabled = 1
           AND (skill_id = ? OR skill_glob IS NOT NULL)
         ORDER BY priority ASC`,
      )
      .all(skillId) as Record<string, unknown>[];

    return rows
      .filter((r) => r["skill_id"] === skillId || this.globMatches(r["skill_glob"] as string | null, skillId))
      .map(this.deserializeRow);
  }

  private matchesContext(rule: SkillDispatchRule, ctx: SkillDispatchContext): boolean {
    if (rule.intentFilter && ctx.intent && !rule.intentFilter.includes(ctx.intent)) return false;
    if (rule.scopeFilter && ctx.scope && !rule.scopeFilter.includes(ctx.scope)) return false;
    return true;
  }

  /**
   * Simple prefix glob: "nsfw-*" matches any skillId starting with "nsfw-".
   * Exact match on non-glob globs (treated as literal).
   */
  private globMatches(glob: string | null, skillId: string): boolean {
    if (!glob) return false;
    if (glob.endsWith("*")) return skillId.startsWith(glob.slice(0, -1));
    return glob === skillId;
  }

  private deserializeRow(row: Record<string, unknown>): SkillDispatchRule {
    const parseJsonArray = (val: unknown): string[] | null => {
      if (!val || typeof val !== "string") return null;
      try {
        const parsed = JSON.parse(val);
        return Array.isArray(parsed) ? parsed : null;
      } catch {
        return null;
      }
    };

    return {
      id: row["id"] as number,
      skillId: row["skill_id"] as string,
      skillGlob: (row["skill_glob"] as string | null) ?? null,
      intentFilter: parseJsonArray(row["intent_filter"]),
      scopeFilter: parseJsonArray(row["scope_filter"]),
      dispatchTarget: row["dispatch_target"] as DispatchTarget,
      dispatchMode: (row["dispatch_mode"] as DispatchMode) ?? "recommend",
      capabilityTags: parseJsonArray(row["capability_tags"]),
      costTier: (row["cost_tier"] as "free" | "metered" | "local") ?? "free",
      fallbackTarget: (row["fallback_target"] as DispatchTarget | null) ?? null,
      priority: (row["priority"] as number) ?? 100,
      enabled: Boolean(row["enabled"]),
      notes: (row["notes"] as string | null) ?? null,
    };
  }

  // ---------------------------------------------------------------------------
  // Session cache helpers
  // ---------------------------------------------------------------------------

  private getSessionCached(sessionId: string, skillId: string): SkillDispatchDecision | null {
    const skillMap = this.sessionCache.get(sessionId);
    if (!skillMap) return null;
    const cached = skillMap.get(skillId);
    if (!cached) return null;
    if (cached.expiresAt <= Date.now()) {
      skillMap.delete(skillId);
      return null;
    }
    return cached.decision;
  }

  private writeSessionCache(sessionId: string, skillId: string, decision: SkillDispatchDecision): void {
    let skillMap = this.sessionCache.get(sessionId);
    if (!skillMap) {
      skillMap = new Map();
      this.sessionCache.set(sessionId, skillMap);
    }
    skillMap.set(skillId, { decision, expiresAt: Date.now() + SESSION_TTL_MS });
  }

  /** Exposed for testing — evict all expired entries across all sessions. */
  evictExpired(): void {
    const now = Date.now();
    for (const [sessionId, skillMap] of this.sessionCache) {
      for (const [skillId, cached] of skillMap) {
        if (cached.expiresAt <= now) skillMap.delete(skillId);
      }
      if (skillMap.size === 0) this.sessionCache.delete(sessionId);
    }
  }
}

// ---------------------------------------------------------------------------
// Module-level singleton wiring (mirrors session-routing-store pattern)
// ---------------------------------------------------------------------------

let _router: SkillDispatchRouter | null = null;

export function initializeSkillDispatchRouter(db: Database.Database): void {
  _router = new SkillDispatchRouter(db);
  console.log("[skill-dispatch] SkillDispatchRouter initialized");
}

export function getSkillDispatchRouter(): SkillDispatchRouter | null {
  return _router;
}
