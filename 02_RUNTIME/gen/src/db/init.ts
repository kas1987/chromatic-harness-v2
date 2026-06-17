import Database from "better-sqlite3";

export function initializeDatabase(dbPath: string): Database.Database {
  const db = new Database(dbPath);
  // WAL mode: allows concurrent readers + one writer without blocking.
  // Critical when Gen, MIGA, arc scripts, and Nate daemon access shared DBs.
  db.pragma("journal_mode = WAL");
  db.pragma("synchronous = NORMAL"); // safe with WAL; faster than FULL
  db.pragma("foreign_keys = ON");

  db.exec(`
    CREATE TABLE IF NOT EXISTS memory_items (
      id TEXT PRIMARY KEY, project_id TEXT, owner_user_id TEXT, author_agent_id TEXT,
      scope TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, source_step_id INTEGER,
      task_purpose TEXT, sensitivity TEXT NOT NULL, created_at TEXT NOT NULL,
      last_used_at TEXT, expires_at TEXT, provenance_json TEXT);

    CREATE TABLE IF NOT EXISTS memory_acls (
      id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
      subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, can_read INTEGER NOT NULL, can_write INTEGER NOT NULL);

    CREATE TABLE IF NOT EXISTS memory_embeddings (
      memory_id TEXT PRIMARY KEY REFERENCES memory_items(id) ON DELETE CASCADE, embedding BLOB NOT NULL);

    CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_items(project_id);
    CREATE INDEX IF NOT EXISTS idx_memory_purpose ON memory_items(task_purpose);
    CREATE INDEX IF NOT EXISTS idx_memory_expires ON memory_items(expires_at);
    CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_items(created_at);
    CREATE INDEX IF NOT EXISTS idx_acl_memory ON memory_acls(memory_id);

    CREATE TABLE IF NOT EXISTS budget_allocations (
      id TEXT PRIMARY KEY,
      model TEXT NOT NULL UNIQUE,
      pct REAL NOT NULL DEFAULT 0,
      spent_usd REAL NOT NULL DEFAULT 0,
      month TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_budget_alloc_model ON budget_allocations(model);

    CREATE TABLE IF NOT EXISTS model_performance (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model TEXT NOT NULL,
      intent TEXT NOT NULL,
      scope TEXT NOT NULL,
      success INTEGER NOT NULL DEFAULT 0,
      failure INTEGER NOT NULL DEFAULT 0,
      avg_latency_ms REAL,
      last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(model, intent, scope)
    );

    CREATE INDEX IF NOT EXISTS idx_model_perf_model ON model_performance(model);
    CREATE INDEX IF NOT EXISTS idx_model_perf_intent ON model_performance(intent);

    CREATE TABLE IF NOT EXISTS skill_dispatch_rules (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      skill_id         TEXT NOT NULL,
      skill_glob       TEXT,
      intent_filter    TEXT,
      scope_filter     TEXT,
      dispatch_target  TEXT NOT NULL,
      dispatch_mode    TEXT NOT NULL DEFAULT 'recommend',
      capability_tags  TEXT,
      cost_tier        TEXT DEFAULT 'free',
      fallback_target  TEXT,
      priority         INTEGER DEFAULT 100,
      enabled          INTEGER DEFAULT 1,
      notes            TEXT,
      created_at       TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_skill_dispatch_skill_id ON skill_dispatch_rules(skill_id);
    CREATE INDEX IF NOT EXISTS idx_skill_dispatch_priority ON skill_dispatch_rules(priority, enabled);
  `);

  return db;
}

export function closeDatabase(db: Database.Database): void {
  db.close();
}
