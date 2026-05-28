-- Chromatic Harness v2 — System Memory Schema
-- Persistent awareness layer for governance, learnings, and scope enforcement.

CREATE TABLE IF NOT EXISTS learnings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('security','architecture','process','debugging','testing','infrastructure')),
    confidence TEXT NOT NULL CHECK(confidence IN ('high','medium','low')),
    scope TEXT NOT NULL CHECK(scope IN ('cross-cutting','repo-specific')),
    content TEXT NOT NULL,
    source TEXT,
    epic TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS governance_rules (
    id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK(category IN ('file_scope','security','privacy','routing','hook','budget')),
    severity TEXT NOT NULL CHECK(severity IN ('critical','warning','info')),
    description TEXT NOT NULL,
    enforcement TEXT NOT NULL, -- 'block', 'warn', 'log', 'ask'
    pseudocode_fix TEXT,         -- concrete mitigation snippet
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    active BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS scope_violations (
    id TEXT PRIMARY KEY,
    mission_id TEXT,
    task_id TEXT,
    expected_scope TEXT NOT NULL,
    violated_files TEXT NOT NULL, -- JSON array of paths
    detected_by TEXT NOT NULL DEFAULT 'scope_magnet',
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    severity TEXT NOT NULL DEFAULT 'warning' CHECK(severity IN ('critical','warning','info'))
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    session_start TEXT NOT NULL DEFAULT (datetime('now')),
    session_end TEXT,
    project_context TEXT, -- JSON: repo, branch, files touched
    injected_memory TEXT, -- JSON array of learning/rule IDs injected at start
    outcome TEXT CHECK(outcome IN ('success','failure','abandoned'))
);

CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category);
CREATE INDEX IF NOT EXISTS idx_learnings_scope ON learnings(scope);
CREATE INDEX IF NOT EXISTS idx_learnings_active ON learnings(active);
CREATE INDEX IF NOT EXISTS idx_governance_category ON governance_rules(category);
CREATE INDEX IF NOT EXISTS idx_governance_active ON governance_rules(active);
CREATE INDEX IF NOT EXISTS idx_violations_mission ON scope_violations(mission_id);
CREATE INDEX IF NOT EXISTS idx_sessions_agent ON agent_sessions(agent_id);

-- Seed critical governance rules
INSERT OR IGNORE INTO governance_rules (id, rule_name, category, severity, description, enforcement, pseudocode_fix)
VALUES
    ('RULE-001', 'FILE_SCOPE_ENFORCEMENT', 'file_scope', 'critical',
     'Workers MUST NOT write, create, or modify files outside declared FILE SCOPE.',
     'block',
     'git diff --name-only HEAD~1 | grep -v "^${SCOPE}" && exit 1'),

    ('RULE-002', 'PRETOOLUSE_HOOK_ISOLATION', 'hook', 'warning',
     'Test hook logic in isolation BEFORE wiring into settings.json; hooks are live immediately.',
     'warn',
     'python hook.py < test_payload.json && cp hook.py ~/.claude/hooks/'),

    ('RULE-003', 'SUBSTRING_MATCHING_INSUFFICIENT', 'security', 'critical',
     'Deny-list hooks must not use simple substring matching; use segment-level scanning with safe-prefix exclusion.',
     'block',
     'for segment in re.split(r"[;&|]\\s*", command): if not SAFE_PREFIXES.match(segment): ...'),

    ('RULE-004', 'P3_SECRETS_BLOCKED', 'privacy', 'critical',
     'P3 secrets must never reach any LLM provider. Block at privacy gate.',
     'block',
     'if privacy_class == PrivacyClass.P3: return deny("P3 blocked")'),

    ('RULE-005', 'OPENHUMAN_DISABLED_DEFAULT', 'routing', 'warning',
     'OpenHuman is disabled by default and read-only when enabled.',
     'warn',
     'enabled: false in providers.yaml; default_mode: read_only'),

    ('RULE-006', 'LOW_CONFIDENCE_NO_EXTERNAL', 'routing', 'warning',
     'If confidence < 60, do not call OpenHuman, cloud providers, or tools with sensitive data.',
     'warn',
     'if confidence.score < 60: return block("confidence too low")'),

    ('RULE-007', 'WRITE_ISSUES_AGAINST_REALITY', 'process', 'warning',
     'Issues must describe reality ("Create X with Y") not plans ("Change line N of X").',
     'warn',
     'if not path.exists(target_file): issue.type = "create"'),

    ('RULE-008', 'PREMORTEM_PSEUDOCODE_PAYOFF', 'process', 'info',
     'Pre-mortems with pseudocode fixes have higher payoff than abstract warnings.',
     'log',
     'Include concrete code snippets alongside risk descriptions.');

-- Seed the injected learnings from the current session
INSERT OR IGNORE INTO learnings (id, title, category, confidence, scope, content, source)
VALUES
    ('L-2026-05-28-001', 'Substring Matching Insufficient for Security-Hook Deny Lists',
     'security', 'high', 'cross-cutting',
     'Using marker in command_string produces false positives in grep/echo/python. Scan at segment level with safe-prefix list and quote-balance heuristic.',
     'mc-x1bi governance hook implementation'),

    ('L-2026-05-28-002', 'PreToolUse Hooks Are Live Immediately',
     'architecture', 'high', 'cross-cutting',
     'Adding a hook to settings.json activates it for the current session immediately. Test in isolation before wiring.',
     'mc-x1bi governance hook implementation'),

    ('L-2026-05-28-003', 'Pre-Mortems With Pseudocode Fixes Have Higher Payoff',
     'process', 'high', 'cross-cutting',
     'Concrete pseudocode in pre-mortems enables zero-debugging mitigation during implementation.',
     'mc-x1bi governance hook implementation'),

    ('L-2026-05-28-004', 'FILE SCOPE Boundary Enforcement Is Safety-Critical',
     'process', 'high', 'cross-cutting',
     'A single out-of-scope worker can break previously passing test suites. Run pre-wave baselines and pytest after every wave.',
     'mc-9eex chromatic-harness-v2 Wave 3'),

    ('L-2026-05-28-005', 'LiteLLM Stateless Config Avoids Prisma Auth Bug',
     'infrastructure', 'high', 'cross-cutting',
     'LiteLLM main-latest image has Prisma/Wolfi auth bug against external Postgres. Use store_model_in_db: false and yaml-only model list for local-first harnesses.',
     'mc-a17w chromatic-stack deployment'),

    ('L-2026-05-28-006', 'Langfuse Requires 64-Hex ENCRYPTION_KEY',
     'infrastructure', 'high', 'cross-cutting',
     'Langfuse v2 needs 64-hex ENCRYPTION_KEY (openssl rand -hex 32). Also needs CLICKHOUSE_MIGRATION_URL with clickhouse:// protocol and CLICKHOUSE_CLUSTER_ENABLED=false.',
     'mc-a17w chromatic-stack deployment');
