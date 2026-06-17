import Database from "better-sqlite3";
import { LlmProvider } from "../llm/llm-types.js";
import { nanoid } from "nanoid";

export interface GlobalBudgetAllocation {
  totalMonthlyBudgetUsd: number;
  allocations: Record<LlmProvider, number>; // percentage 0-100
}

const DEFAULT_ALLOCATION: GlobalBudgetAllocation = {
  totalMonthlyBudgetUsd: 50,
  allocations: {
    claude:      0,   // Max plan — no per-token cost; budget tracking skipped (getRemainingBudget returns Infinity)
    gpt:         40,
    gemini:      35,
    "lm-studio": 0,   // local server — no cost; Infinity remaining
    minimax:     0,   // cloud MoE — metered but low-volume; track separately if usage grows
    ollama:      25,
    gemma:       0,   // local Ollama Gemma — no USD cost
  },
};

// Fallback chain: must include every key in DEFAULT_ALLOCATION.allocations so ensureRows() creates
// a DB row for each provider and recordSpend() never silently no-ops.
const FALLBACK_CHAIN: LlmProvider[] = ["claude", "gpt", "gemini", "minimax", "lm-studio", "ollama", "gemma"];

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * Normalise an allocation entry that may arrive as either a bare number or an
 * object { pct: number } (the shape used by the test helpers).
 */
function resolvePct(value: number | { pct: number }): number {
  if (typeof value === "number") return value;
  return value.pct;
}

export class BudgetAllocator {
  private alloc: GlobalBudgetAllocation;

  constructor(
    private db: Database.Database,
    allocation?: Partial<{
      totalMonthlyBudgetUsd: number;
      allocations: Record<LlmProvider, number | { pct: number }>;
    }>,
  ) {
    const resolvedAllocations: Record<LlmProvider, number> = {
      ...DEFAULT_ALLOCATION.allocations,
    };
    if (allocation?.allocations) {
      for (const key of Object.keys(allocation.allocations) as LlmProvider[]) {
        resolvedAllocations[key] = resolvePct(allocation.allocations[key]);
      }
    }
    this.alloc = {
      totalMonthlyBudgetUsd:
        allocation?.totalMonthlyBudgetUsd ?? DEFAULT_ALLOCATION.totalMonthlyBudgetUsd,
      allocations: resolvedAllocations,
    };
    this.ensureTable();
    this.ensureRows();
  }

  /** Create the table if it does not exist (needed when tests pass a bare in-memory DB). */
  private ensureTable(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS budget_allocations (
        id TEXT PRIMARY KEY,
        model TEXT NOT NULL UNIQUE,
        pct REAL NOT NULL DEFAULT 0,
        spent_usd REAL NOT NULL DEFAULT 0,
        month TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_budget_alloc_model ON budget_allocations(model);
    `);
  }

  /** Ensure all provider rows exist for the current month; reset spend if month rolled. */
  private ensureRows(): void {
    const month = currentMonth();
    for (const provider of FALLBACK_CHAIN) {
      const existing = this.db
        .prepare("SELECT id, month, spent_usd FROM budget_allocations WHERE model = ?")
        .get(provider) as { id: string; month: string; spent_usd: number } | undefined;

      if (!existing) {
        this.db.prepare(
          "INSERT INTO budget_allocations (id, model, pct, spent_usd, month, updated_at) VALUES (?, ?, ?, 0, ?, ?)"
        ).run(nanoid(), provider, this.alloc.allocations[provider], month, new Date().toISOString());
      } else if (existing.month !== month) {
        // New month — reset spend
        this.db.prepare(
          "UPDATE budget_allocations SET spent_usd = 0, month = ?, updated_at = ? WHERE model = ?"
        ).run(month, new Date().toISOString(), provider);
      }
    }
  }

  getSpentUsd(model: LlmProvider): number {
    const row = this.db
      .prepare("SELECT spent_usd FROM budget_allocations WHERE model = ?")
      .get(model) as { spent_usd: number } | undefined;
    return row?.spent_usd ?? 0;
  }

  getRemainingBudget(model: LlmProvider): number {
    // Free providers: always unlimited budget
    if (model === "ollama" || model === "gemma" || model === "lm-studio" || model === "claude") return Infinity;
    const pct = this.alloc.allocations[model];
    const ceiling = (pct / 100) * this.alloc.totalMonthlyBudgetUsd;
    return Math.max(0, ceiling - this.getSpentUsd(model));
  }

  isModelBudgetExhausted(model: LlmProvider): boolean {
    if (model === "ollama" || model === "gemma" || model === "lm-studio" || model === "claude") return false;
    return this.getRemainingBudget(model) <= 0;
  }

  recordSpend(model: LlmProvider, amountUsd: number): void {
    this.db.prepare(
      "UPDATE budget_allocations SET spent_usd = spent_usd + ?, updated_at = ? WHERE model = ?"
    ).run(amountUsd, new Date().toISOString(), model);
  }

  /**
   * Returns next provider in fallback chain after `exhausted`.
   * Terminal provider maps to itself; unknown provider falls back to "ollama".
   */
  getFallbackModel(exhausted: LlmProvider): LlmProvider {
    const idx = FALLBACK_CHAIN.indexOf(exhausted);
    if (idx === -1) return "ollama";
    if (idx === FALLBACK_CHAIN.length - 1) return exhausted;
    return FALLBACK_CHAIN[idx + 1];
  }
}
