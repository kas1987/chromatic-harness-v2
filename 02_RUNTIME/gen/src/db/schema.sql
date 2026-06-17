-- 1. pretool_events: Log every PreToolUse event
CREATE TABLE IF NOT EXISTS pretool_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  session_id TEXT,
  machine_id TEXT,
  tool_name TEXT NOT NULL,
  tool_input TEXT NOT NULL,
  decision TEXT NOT NULL,
  routing_target TEXT,
  blocked_reason TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pretool_events_ts ON pretool_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_pretool_events_session_id ON pretool_events(session_id);
CREATE INDEX IF NOT EXISTS idx_pretool_events_tool_name ON pretool_events(tool_name);

-- 2. routing_rules: Centralized policy
CREATE TABLE IF NOT EXISTS routing_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  tool TEXT NOT NULL,
  condition_json TEXT NOT NULL,
  action TEXT NOT NULL,
  target_agent TEXT,
  priority INTEGER DEFAULT 100,
  enabled INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_routing_rules_priority ON routing_rules(priority);
CREATE INDEX IF NOT EXISTS idx_routing_rules_tool ON routing_rules(tool);

-- 3. tasks: Remote task management
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  intent TEXT,
  status TEXT DEFAULT "pending",
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  completed_at TEXT,
  scheduled_for TEXT,
  result_json TEXT,
  agent_type TEXT,
  machine_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);

-- 4. sessions: Track Claude instances
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  machine_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  user_agent TEXT,
  last_activity_ts TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_machine_id ON sessions(machine_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

-- 5. webhook_events: External event log
CREATE TABLE IF NOT EXISTS webhook_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  action TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_source ON webhook_events(source);
CREATE INDEX IF NOT EXISTS idx_webhook_events_event_type ON webhook_events(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_events_created_at ON webhook_events(created_at);

-- 6. agent_configs: Agent settings
CREATE TABLE IF NOT EXISTS agent_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  agent_type TEXT NOT NULL,
  intent TEXT NOT NULL,
  scope TEXT,
  enabled INTEGER DEFAULT 1,
  config_json TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_configs_name ON agent_configs(name);
CREATE INDEX IF NOT EXISTS idx_agent_configs_agent_type ON agent_configs(agent_type);

-- 7. learning_patterns: Adaptive routing data
CREATE TABLE IF NOT EXISTS learning_patterns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  intent TEXT NOT NULL,
  scope TEXT,
  routing_target TEXT NOT NULL,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  avg_duration_ms INTEGER,
  last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_learning_patterns_intent ON learning_patterns(intent);
CREATE INDEX IF NOT EXISTS idx_learning_patterns_routing_target ON learning_patterns(routing_target);

-- 8. budget_allocations: Per-model monthly budget tracking
CREATE TABLE IF NOT EXISTS budget_allocations (
  id TEXT PRIMARY KEY,
  model TEXT NOT NULL UNIQUE,
  pct REAL NOT NULL DEFAULT 0,
  spent_usd REAL NOT NULL DEFAULT 0,
  month TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_budget_allocations_model ON budget_allocations(model);

-- 9. model_performance: Per-model intent/scope success tracking
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

-- 10. skill_dispatch_rules: Skill-level dispatch routing parameters table
CREATE TABLE IF NOT EXISTS skill_dispatch_rules (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_id         TEXT NOT NULL,        -- exact match: "commit" | "nsfw-prompts" | "*"
  skill_glob       TEXT,                 -- prefix glob: "nsfw-*" matches any nsfw-* skill
  intent_filter    TEXT,                 -- JSON string array or NULL (NULL = match all intents)
  scope_filter     TEXT,                 -- JSON string array or NULL (NULL = match all scopes)
  dispatch_target  TEXT NOT NULL,        -- "mcp:<name>" | "skill:<id>" | "gen:local" | "rudalo:dispatch"
  dispatch_mode    TEXT NOT NULL DEFAULT 'recommend',  -- "recommend" | "inject_context" | "block"
  capability_tags  TEXT,                 -- JSON string array: ["requiresCode","nsfw","vision"]
  cost_tier        TEXT DEFAULT 'free',  -- "free" | "metered" | "local"
  fallback_target  TEXT,                 -- if dispatch_target unavailable
  priority         INTEGER DEFAULT 100,
  enabled          INTEGER DEFAULT 1,
  notes            TEXT,
  created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_dispatch_skill_id ON skill_dispatch_rules(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_dispatch_priority ON skill_dispatch_rules(priority, enabled);

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- 10. t3_approvals: T3 hard stop approval tracking
CREATE TABLE IF NOT EXISTS t3_approvals (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  trace_id TEXT,
  triggered_at TEXT NOT NULL,
  criteria TEXT NOT NULL,
  tcs REAL,
  pre_mortem_score REAL,
  status TEXT DEFAULT 'pending',
  resolved_at TEXT,
  conditions TEXT,
  reviewer_notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_t3_approvals_session ON t3_approvals(session_id);
CREATE INDEX IF NOT EXISTS idx_t3_approvals_status ON t3_approvals(status);
