import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import Database from "better-sqlite3";
import { initializeDatabase } from "../../db/init.js";
import { SkillDispatchRouter } from "../skill-dispatch-router.js";
import type { SkillDispatchContext } from "../skill-dispatch-router.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeDb(): Database.Database {
  const db = initializeDatabase(":memory:");
  return db;
}

function insertRule(
  db: Database.Database,
  rule: {
    skill_id: string;
    skill_glob?: string | null;
    intent_filter?: string[] | null;
    scope_filter?: string[] | null;
    dispatch_target: string;
    dispatch_mode?: string;
    capability_tags?: string[] | null;
    cost_tier?: string;
    fallback_target?: string | null;
    priority?: number;
    enabled?: number;
    notes?: string | null;
  },
): void {
  db.prepare(`
    INSERT INTO skill_dispatch_rules
      (skill_id, skill_glob, intent_filter, scope_filter, dispatch_target, dispatch_mode,
       capability_tags, cost_tier, fallback_target, priority, enabled, notes)
    VALUES
      (@skill_id, @skill_glob, @intent_filter, @scope_filter, @dispatch_target, @dispatch_mode,
       @capability_tags, @cost_tier, @fallback_target, @priority, @enabled, @notes)
  `).run({
    skill_id: rule.skill_id,
    skill_glob: rule.skill_glob ?? null,
    intent_filter: rule.intent_filter ? JSON.stringify(rule.intent_filter) : null,
    scope_filter: rule.scope_filter ? JSON.stringify(rule.scope_filter) : null,
    dispatch_target: rule.dispatch_target,
    dispatch_mode: rule.dispatch_mode ?? "recommend",
    capability_tags: rule.capability_tags ? JSON.stringify(rule.capability_tags) : null,
    cost_tier: rule.cost_tier ?? "free",
    fallback_target: rule.fallback_target ?? null,
    priority: rule.priority ?? 100,
    enabled: rule.enabled ?? 1,
    notes: rule.notes ?? null,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SkillDispatchRouter", () => {
  let db: Database.Database;
  let router: SkillDispatchRouter;

  beforeEach(() => {
    vi.useFakeTimers();
    db = makeDb();
    router = new SkillDispatchRouter(db);
  });

  afterEach(() => {
    db.close();
    vi.useRealTimers();
  });

  // --- Basic resolution ---

  it("returns default (gen:local) when no rules exist", () => {
    const result = router.resolve({ skillId: "commit", skillArgs: {} });
    expect(result.matched).toBe(false);
    expect(result.target).toBe("gen:local");
    expect(result.mode).toBe("recommend");
    expect(result.ruleId).toBeNull();
  });

  it("resolves exact skill_id match", () => {
    insertRule(db, { skill_id: "review-pr", dispatch_target: "mcp:github", dispatch_mode: "inject_context" });
    const result = router.resolve({ skillId: "review-pr", skillArgs: {} });
    expect(result.matched).toBe(true);
    expect(result.target).toBe("mcp:github");
    expect(result.mode).toBe("inject_context");
    expect(result.ruleId).toBeGreaterThan(0);
  });

  // --- Glob matching ---

  it("resolves glob skill_glob match (nsfw-* → nsfw-prompts)", () => {
    insertRule(db, { skill_id: "*", skill_glob: "nsfw-*", dispatch_target: "mcp:comfyui" });
    const result = router.resolve({ skillId: "nsfw-prompts", skillArgs: {} });
    expect(result.matched).toBe(true);
    expect(result.target).toBe("mcp:comfyui");
  });

  it("glob does not match unrelated skill", () => {
    insertRule(db, { skill_id: "*", skill_glob: "nsfw-*", dispatch_target: "mcp:comfyui" });
    const result = router.resolve({ skillId: "commit", skillArgs: {} });
    expect(result.matched).toBe(false);
  });

  // --- Intent filter ---

  it("respects intent_filter — matches when intent is in filter", () => {
    insertRule(db, {
      skill_id: "nsfw-prompts",
      dispatch_target: "mcp:comfyui",
      intent_filter: ["dispatch", "code"],
    });
    const result = router.resolve({ skillId: "nsfw-prompts", skillArgs: {}, intent: "code" });
    expect(result.matched).toBe(true);
  });

  it("respects intent_filter — skips when intent is NOT in filter", () => {
    insertRule(db, {
      skill_id: "nsfw-prompts",
      dispatch_target: "mcp:comfyui",
      intent_filter: ["dispatch", "code"],
    });
    const result = router.resolve({ skillId: "nsfw-prompts", skillArgs: {}, intent: "explore" });
    expect(result.matched).toBe(false);
    expect(result.target).toBe("gen:local");
  });

  it("null intent_filter matches any intent", () => {
    insertRule(db, {
      skill_id: "commit",
      dispatch_target: "gen:local",
      intent_filter: null,
    });
    const result = router.resolve({ skillId: "commit", skillArgs: {}, intent: "explore" });
    expect(result.matched).toBe(true);
  });

  // --- Scope filter ---

  it("respects scope_filter — matches when scope is in filter", () => {
    insertRule(db, {
      skill_id: "nsfw-prompts",
      dispatch_target: "mcp:comfyui",
      scope_filter: ["medium", "complex"],
    });
    const result = router.resolve({ skillId: "nsfw-prompts", skillArgs: {}, scope: "medium" });
    expect(result.matched).toBe(true);
  });

  it("respects scope_filter — skips when scope is NOT in filter", () => {
    insertRule(db, {
      skill_id: "nsfw-prompts",
      dispatch_target: "mcp:comfyui",
      scope_filter: ["medium", "complex"],
    });
    const result = router.resolve({ skillId: "nsfw-prompts", skillArgs: {}, scope: "simple" });
    expect(result.matched).toBe(false);
  });

  // --- Priority ordering ---

  it("lower priority number wins over higher priority number", () => {
    insertRule(db, { skill_id: "review-pr", dispatch_target: "gen:local", priority: 200 });
    insertRule(db, { skill_id: "review-pr", dispatch_target: "mcp:github", priority: 10 });
    const result = router.resolve({ skillId: "review-pr", skillArgs: {} });
    expect(result.target).toBe("mcp:github"); // priority 10 wins
  });

  // --- Disabled rules ---

  it("disabled rules are ignored", () => {
    insertRule(db, { skill_id: "review-pr", dispatch_target: "mcp:github", enabled: 0 });
    const result = router.resolve({ skillId: "review-pr", skillArgs: {} });
    expect(result.matched).toBe(false);
  });

  // --- Block mode ---

  it("block mode is returned correctly", () => {
    insertRule(db, { skill_id: "dangerous-skill", dispatch_target: "gen:local", dispatch_mode: "block" });
    const result = router.resolve({ skillId: "dangerous-skill", skillArgs: {} });
    expect(result.matched).toBe(true);
    expect(result.mode).toBe("block");
  });

  // --- Fallback target ---

  it("returns fallback_target when set", () => {
    insertRule(db, {
      skill_id: "claude-api",
      dispatch_target: "rudalo:dispatch",
      fallback_target: "gen:local",
    });
    const result = router.resolve({ skillId: "claude-api", skillArgs: {} });
    expect(result.fallback).toBe("gen:local");
  });

  // --- Capability tags ---

  it("returns capabilityTags from the matched rule", () => {
    insertRule(db, {
      skill_id: "nsfw-prompts",
      dispatch_target: "mcp:comfyui",
      capability_tags: ["nsfw", "requiresCode"],
    });
    const result = router.resolve({ skillId: "nsfw-prompts", skillArgs: {} });
    expect(result.capabilityTags).toEqual(["nsfw", "requiresCode"]);
  });

  // --- Session cache ---

  it("second resolve with same sessionId uses session cache (appends [session-cached])", () => {
    insertRule(db, { skill_id: "review-pr", dispatch_target: "mcp:github" });

    // First call — populates cache
    const first = router.resolve({ skillId: "review-pr", skillArgs: {}, sessionId: "sess-abc" });
    expect(first.rationale).not.toContain("[session-cached]");

    // Second call — should hit cache
    const second = router.resolve({ skillId: "review-pr", skillArgs: {}, sessionId: "sess-abc" });
    expect(second.rationale).toContain("[session-cached]");
    expect(second.target).toBe("mcp:github");
  });

  it("session cache expires after TTL (5 minutes)", () => {
    insertRule(db, { skill_id: "review-pr", dispatch_target: "mcp:github" });

    // Populate cache
    router.resolve({ skillId: "review-pr", skillArgs: {}, sessionId: "sess-ttl" });

    // Advance past 5-minute TTL
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);

    // Should NOT be session-cached any more
    const result = router.resolve({ skillId: "review-pr", skillArgs: {}, sessionId: "sess-ttl" });
    expect(result.rationale).not.toContain("[session-cached]");
  });

  it("different sessions have independent caches", () => {
    insertRule(db, { skill_id: "commit", dispatch_target: "gen:local" });
    insertRule(db, { skill_id: "review-pr", dispatch_target: "mcp:github" });

    router.resolve({ skillId: "commit", skillArgs: {}, sessionId: "sess-1" });
    router.resolve({ skillId: "review-pr", skillArgs: {}, sessionId: "sess-2" });

    const r1 = router.resolve({ skillId: "commit", skillArgs: {}, sessionId: "sess-1" });
    const r2 = router.resolve({ skillId: "review-pr", skillArgs: {}, sessionId: "sess-2" });

    expect(r1.target).toBe("gen:local");
    expect(r2.target).toBe("mcp:github");
    expect(r1.rationale).toContain("[session-cached]");
    expect(r2.rationale).toContain("[session-cached]");
  });

  // --- No session id — no caching ---

  it("resolve without sessionId does not populate cache", () => {
    insertRule(db, { skill_id: "commit", dispatch_target: "gen:local" });
    router.resolve({ skillId: "commit", skillArgs: {} });
    // Second call without sessionId should not error
    const result = router.resolve({ skillId: "commit", skillArgs: {} });
    expect(result.matched).toBe(true);
    expect(result.rationale).not.toContain("[session-cached]");
  });

  // --- evictExpired helper ---

  it("evictExpired() cleans up stale session cache entries", () => {
    insertRule(db, { skill_id: "commit", dispatch_target: "gen:local" });
    router.resolve({ skillId: "commit", skillArgs: {}, sessionId: "sess-evict" });
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);
    // Should not throw
    expect(() => router.evictExpired()).not.toThrow();
  });
});
