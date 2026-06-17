/**
 * seed-skill-dispatch.ts
 *
 * Idempotent seed script for the `skill_dispatch_rules` table.
 * Safe to run multiple times — uses INSERT OR IGNORE on (skill_id, skill_glob, dispatch_target).
 *
 * Usage:
 *   npx ts-node gen/src/db/seed-skill-dispatch.ts
 *   # or from the gen/ directory:
 *   pnpm ts-node src/db/seed-skill-dispatch.ts
 */

import Database from "better-sqlite3";
import path from "path";
import { initializeDatabase } from "./init.js";

// ---------------------------------------------------------------------------
// Seed entries
// ---------------------------------------------------------------------------

interface SeedEntry {
  skill_id: string;
  skill_glob: string | null;
  intent_filter: string[] | null;
  scope_filter: string[] | null;
  dispatch_target: string;
  dispatch_mode: "recommend" | "inject_context" | "block";
  capability_tags: string[] | null;
  cost_tier: "free" | "metered" | "local";
  fallback_target: string | null;
  priority: number;
  notes: string;
}

const SEED_RULES: SeedEntry[] = [
  // --- NSFW / ComfyUI skills ---
  {
    skill_id: "nsfw-prompts",
    skill_glob: null,
    intent_filter: ["dispatch", "code"],
    scope_filter: null,
    dispatch_target: "mcp:comfyui",
    dispatch_mode: "recommend",
    capability_tags: ["nsfw", "requiresCode"],
    cost_tier: "free",
    fallback_target: "gen:local",
    priority: 10,
    notes: "Primary NSFW prompting skill → ComfyUI MCP",
  },
  {
    skill_id: "nsfw-pipeline",
    skill_glob: null,
    intent_filter: ["dispatch", "trigger"],
    scope_filter: null,
    dispatch_target: "rudalo:dispatch",
    dispatch_mode: "inject_context",
    capability_tags: ["nsfw"],
    cost_tier: "local",
    fallback_target: "gen:local",
    priority: 10,
    notes: "NSFW pipeline orchestration → Rudalo Dispatch",
  },
  {
    skill_id: "nsfw-checkpoints",
    skill_glob: null,
    intent_filter: ["code", "explore"],
    scope_filter: null,
    dispatch_target: "gen:local",
    dispatch_mode: "recommend",
    capability_tags: ["nsfw"],
    cost_tier: "free",
    fallback_target: null,
    priority: 20,
    notes: "Checkpoint config skill handled locally",
  },
  {
    // Catch-all for any nsfw-* skill not otherwise matched
    skill_id: "*",
    skill_glob: "nsfw-*",
    intent_filter: null,
    scope_filter: null,
    dispatch_target: "gen:local",
    dispatch_mode: "recommend",
    capability_tags: ["nsfw"],
    cost_tier: "free",
    fallback_target: null,
    priority: 90,
    notes: "Catch-all: any nsfw-* skill defaults to local handler",
  },

  // --- Git / Dev skills ---
  {
    skill_id: "commit",
    skill_glob: null,
    intent_filter: null,
    scope_filter: null,
    dispatch_target: "gen:local",
    dispatch_mode: "recommend",
    capability_tags: ["requiresCode"],
    cost_tier: "free",
    fallback_target: null,
    priority: 50,
    notes: "Git commit skill stays local",
  },
  {
    skill_id: "review-pr",
    skill_glob: null,
    intent_filter: null,
    scope_filter: null,
    dispatch_target: "mcp:github",
    dispatch_mode: "inject_context",
    capability_tags: ["requiresCode"],
    cost_tier: "free",
    fallback_target: "gen:local",
    priority: 50,
    notes: "PR review via GitHub MCP — inject dispatch target into context",
  },

  // --- AI / API skills ---
  {
    skill_id: "claude-api",
    skill_glob: null,
    intent_filter: null,
    scope_filter: null,
    dispatch_target: "rudalo:dispatch",
    dispatch_mode: "recommend",
    capability_tags: ["requiresCode"],
    cost_tier: "metered",
    fallback_target: "gen:local",
    priority: 50,
    notes: "Claude API skill routes through Rudalo for cost tracking",
  },

  // --- Scheduling / Automation skills ---
  {
    skill_id: "schedule",
    skill_glob: null,
    intent_filter: ["schedule", "trigger"],
    scope_filter: null,
    dispatch_target: "gen:local",
    dispatch_mode: "recommend",
    capability_tags: [],
    cost_tier: "free",
    fallback_target: null,
    priority: 50,
    notes: "Schedule skill: local cron/trigger management",
  },
  {
    skill_id: "loop",
    skill_glob: null,
    intent_filter: ["schedule", "trigger"],
    scope_filter: null,
    dispatch_target: "gen:local",
    dispatch_mode: "recommend",
    capability_tags: [],
    cost_tier: "free",
    fallback_target: null,
    priority: 50,
    notes: "Loop skill: local interval management",
  },

  // --- Simplify / Refactor skills ---
  {
    skill_id: "simplify",
    skill_glob: null,
    intent_filter: ["code"],
    scope_filter: null,
    dispatch_target: "gen:local",
    dispatch_mode: "recommend",
    capability_tags: ["requiresCode"],
    cost_tier: "free",
    fallback_target: null,
    priority: 50,
    notes: "Code simplify skill — local, code-capable model",
  },
];

// ---------------------------------------------------------------------------
// Seed function
// ---------------------------------------------------------------------------

function seed(db: Database.Database): void {
  const insert = db.prepare(`
    INSERT OR IGNORE INTO skill_dispatch_rules (
      skill_id, skill_glob, intent_filter, scope_filter,
      dispatch_target, dispatch_mode, capability_tags, cost_tier,
      fallback_target, priority, notes
    ) VALUES (
      @skill_id, @skill_glob, @intent_filter, @scope_filter,
      @dispatch_target, @dispatch_mode, @capability_tags, @cost_tier,
      @fallback_target, @priority, @notes
    )
  `);

  // Add a unique constraint for idempotency if it doesn't exist
  // (INSERT OR IGNORE relies on a UNIQUE index; we use the natural key: skill_id + skill_glob + dispatch_target)
  try {
    db.exec(
      `CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_dispatch_seed_key
       ON skill_dispatch_rules(skill_id, COALESCE(skill_glob, ''), dispatch_target)`,
    );
  } catch {
    // Index may already exist with different definition — ignore
  }

  const seedTx = db.transaction(() => {
    let inserted = 0;
    for (const entry of SEED_RULES) {
      const result = insert.run({
        ...entry,
        intent_filter: entry.intent_filter ? JSON.stringify(entry.intent_filter) : null,
        scope_filter: entry.scope_filter ? JSON.stringify(entry.scope_filter) : null,
        capability_tags: entry.capability_tags ? JSON.stringify(entry.capability_tags) : null,
      });
      if (result.changes > 0) inserted++;
    }
    return inserted;
  });

  const inserted = seedTx() as number;
  console.log(`[seed-skill-dispatch] Inserted ${inserted} new rules (${SEED_RULES.length} total attempted).`);
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

if (require.main === module) {
  const dbPath = process.env.GEN_DB_PATH
    ?? process.env.DATABASE_PATH
    ?? path.resolve(process.cwd(), "gen.db");

  console.log(`[seed-skill-dispatch] Using database: ${dbPath}`);
  const db = initializeDatabase(dbPath);
  seed(db);
  db.close();
  console.log("[seed-skill-dispatch] Done.");
}

export { seed };
