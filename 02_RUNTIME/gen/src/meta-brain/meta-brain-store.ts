import Database from "better-sqlite3";
import { nanoid } from "nanoid";

export type MetaBrainSourceType = "log" | "knowledge" | "finding" | "review" | "event";

export interface MetaBrainEntry {
  id: string;
  createdAt: string;
  eventTs: string;
  sourceTeam: string;
  sourceType: MetaBrainSourceType;
  repoKey: string;
  userKey: string;
  sessionId?: string;
  title: string;
  content: string;
  confidence: number;
  tagsJson: string;
  metadataJson: string;
  sourceKey?: string;
}

export interface CreateMetaBrainEntryInput {
  sourceTeam: string;
  sourceType: MetaBrainSourceType;
  repoKey: string;
  userKey: string;
  sessionId?: string;
  title: string;
  content: string;
  confidence?: number;
  tagsJson?: string;
  metadataJson?: string;
  eventTs?: string;
  sourceKey?: string;
}

export interface MetaBrainFilters {
  repoKey?: string;
  userKey?: string;
  sourceTeam?: string;
  sourceType?: MetaBrainSourceType;
  sourceKey?: string;
  limit?: number;
  offset?: number;
}

export interface MetaBrainSummary {
  repoKey?: string;
  userKey?: string;
  total: number;
  byTeam: Array<{ sourceTeam: string; count: number }>;
  byType: Array<{ sourceType: string; count: number }>;
  topUsers: Array<{ userKey: string; count: number }>;
  topRepos: Array<{ repoKey: string; count: number }>;
  recent: MetaBrainEntry[];
}

export class MetaBrainStore {
  constructor(private db: Database.Database) {
    this.initSchema();
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS meta_brain_entries (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        event_ts TEXT NOT NULL,
        source_team TEXT NOT NULL,
        source_type TEXT NOT NULL,
        repo_key TEXT NOT NULL,
        user_key TEXT NOT NULL,
        session_id TEXT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0,
        tags_json TEXT NOT NULL DEFAULT '[]',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        source_key TEXT
      );

      CREATE UNIQUE INDEX IF NOT EXISTS idx_meta_brain_source_key
        ON meta_brain_entries(source_key)
        WHERE source_key IS NOT NULL;

      CREATE INDEX IF NOT EXISTS idx_meta_brain_event
        ON meta_brain_entries(event_ts DESC);
      CREATE INDEX IF NOT EXISTS idx_meta_brain_repo_user
        ON meta_brain_entries(repo_key, user_key, event_ts DESC);
      CREATE INDEX IF NOT EXISTS idx_meta_brain_team
        ON meta_brain_entries(source_team, event_ts DESC);
      CREATE INDEX IF NOT EXISTS idx_meta_brain_type
        ON meta_brain_entries(source_type, event_ts DESC);
    `);
  }

  createEntry(input: CreateMetaBrainEntryInput): MetaBrainEntry {
    const id = nanoid();
    const now = new Date().toISOString();
    const eventTs = input.eventTs ?? now;
    const confidence = clamp(input.confidence ?? 0, 0, 1);

    if (input.sourceKey) {
      const existing = this.db
        .prepare("SELECT id FROM meta_brain_entries WHERE source_key = ? LIMIT 1")
        .get(input.sourceKey) as { id: string } | undefined;

      if (existing) {
        this.db
          .prepare(
            `UPDATE meta_brain_entries SET
              event_ts = ?,
              source_team = ?,
              source_type = ?,
              repo_key = ?,
              user_key = ?,
              session_id = ?,
              title = ?,
              content = ?,
              confidence = ?,
              tags_json = ?,
              metadata_json = ?
             WHERE id = ?`,
          )
          .run(
            eventTs,
            input.sourceTeam,
            input.sourceType,
            input.repoKey,
            input.userKey,
            input.sessionId ?? null,
            input.title,
            input.content,
            confidence,
            input.tagsJson ?? "[]",
            input.metadataJson ?? "{}",
            existing.id,
          );

        const updated = this.db
          .prepare("SELECT * FROM meta_brain_entries WHERE id = ? LIMIT 1")
          .get(existing.id) as Record<string, unknown> | undefined;

        if (!updated) {
          throw new Error("Failed to update meta-brain entry");
        }
        return rowToEntry(updated);
      }
    }

    this.db
      .prepare(
        `INSERT INTO meta_brain_entries (
          id, created_at, event_ts, source_team, source_type, repo_key, user_key,
          session_id, title, content, confidence, tags_json, metadata_json, source_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        id,
        now,
        eventTs,
        input.sourceTeam,
        input.sourceType,
        input.repoKey,
        input.userKey,
        input.sessionId ?? null,
        input.title,
        input.content,
        confidence,
        input.tagsJson ?? "[]",
        input.metadataJson ?? "{}",
        input.sourceKey ?? null,
      );

    const entry = this.db
      .prepare("SELECT * FROM meta_brain_entries WHERE source_key = ? OR id = ? ORDER BY created_at DESC LIMIT 1")
      .get(input.sourceKey ?? null, id) as Record<string, unknown> | undefined;

    if (!entry) {
      throw new Error("Failed to create meta-brain entry");
    }
    return rowToEntry(entry);
  }

  listEntries(filters: MetaBrainFilters = {}): MetaBrainEntry[] {
    const where: string[] = [];
    const params: unknown[] = [];

    if (filters.repoKey) {
      where.push("repo_key = ?");
      params.push(filters.repoKey);
    }
    if (filters.userKey) {
      where.push("user_key = ?");
      params.push(filters.userKey);
    }
    if (filters.sourceTeam) {
      where.push("source_team = ?");
      params.push(filters.sourceTeam);
    }
    if (filters.sourceType) {
      where.push("source_type = ?");
      params.push(filters.sourceType);
    }
    if (filters.sourceKey) {
      where.push("source_key = ?");
      params.push(filters.sourceKey);
    }

    const limit = Math.max(1, Math.min(filters.limit ?? 100, 1000));
    const offset = Math.max(0, filters.offset ?? 0);

    const rows = this.db
      .prepare(
        `SELECT *
         FROM meta_brain_entries
         ${where.length > 0 ? `WHERE ${where.join(" AND ")}` : ""}
         ORDER BY event_ts DESC
         LIMIT ? OFFSET ?`,
      )
      .all(...params, limit, offset) as Array<Record<string, unknown>>;

    return rows.map(rowToEntry);
  }

  getEntryBySourceKey(sourceKey: string): MetaBrainEntry | null {
    const row = this.db
      .prepare("SELECT * FROM meta_brain_entries WHERE source_key = ? LIMIT 1")
      .get(sourceKey) as Record<string, unknown> | undefined;

    if (!row) return null;
    return rowToEntry(row);
  }

  summary(repoKey?: string, userKey?: string): MetaBrainSummary {
    const where: string[] = [];
    const params: unknown[] = [];

    if (repoKey) {
      where.push("repo_key = ?");
      params.push(repoKey);
    }
    if (userKey) {
      where.push("user_key = ?");
      params.push(userKey);
    }

    const whereSql = where.length > 0 ? `WHERE ${where.join(" AND ")}` : "";

    const total = (this.db.prepare(`SELECT COUNT(*) AS c FROM meta_brain_entries ${whereSql}`).get(...params) as { c: number }).c;

    const byTeam = this.db
      .prepare(
        `SELECT source_team, COUNT(*) AS c
         FROM meta_brain_entries
         ${whereSql}
         GROUP BY source_team
         ORDER BY c DESC`,
      )
      .all(...params) as Array<{ source_team: string; c: number }>;

    const byType = this.db
      .prepare(
        `SELECT source_type, COUNT(*) AS c
         FROM meta_brain_entries
         ${whereSql}
         GROUP BY source_type
         ORDER BY c DESC`,
      )
      .all(...params) as Array<{ source_type: string; c: number }>;

    const topUsers = this.db
      .prepare(
        `SELECT user_key, COUNT(*) AS c
         FROM meta_brain_entries
         ${whereSql}
         GROUP BY user_key
         ORDER BY c DESC
         LIMIT 10`,
      )
      .all(...params) as Array<{ user_key: string; c: number }>;

    const topRepos = this.db
      .prepare(
        `SELECT repo_key, COUNT(*) AS c
         FROM meta_brain_entries
         ${whereSql}
         GROUP BY repo_key
         ORDER BY c DESC
         LIMIT 10`,
      )
      .all(...params) as Array<{ repo_key: string; c: number }>;

    const recent = this.listEntries({ repoKey, userKey, limit: 20, offset: 0 });

    return {
      repoKey,
      userKey,
      total,
      byTeam: byTeam.map((r) => ({ sourceTeam: r.source_team, count: r.c })),
      byType: byType.map((r) => ({ sourceType: r.source_type, count: r.c })),
      topUsers: topUsers.map((r) => ({ userKey: r.user_key, count: r.c })),
      topRepos: topRepos.map((r) => ({ repoKey: r.repo_key, count: r.c })),
      recent,
    };
  }

  consolidateInternalSources(defaultRepoKey: string, defaultUserKey: string): { inserted: number } {
    let inserted = 0;

    if (this.tableExists("maintenance_records")) {
      const rows = this.db
        .prepare(
          `SELECT id, updated_at, group_key, title, summary, confidence, tags_json
           FROM maintenance_records
           ORDER BY updated_at DESC
           LIMIT 200`,
        )
        .all() as Array<Record<string, unknown>>;

      for (const row of rows) {
        this.createEntry({
          sourceTeam: String(row.group_key ?? "architecture"),
          sourceType: "finding",
          repoKey: defaultRepoKey,
          userKey: defaultUserKey,
          title: String(row.title ?? "maintenance record"),
          content: String(row.summary ?? ""),
          confidence: confidenceTo01(String(row.confidence ?? "unknown")),
          tagsJson: String(row.tags_json ?? "[]"),
          metadataJson: JSON.stringify({ source: "maintenance_records" }),
          eventTs: String(row.updated_at ?? new Date().toISOString()),
          sourceKey: `maintenance:${String(row.id ?? "")}`,
        });
        inserted += 1;
      }
    }

    if (this.tableExists("maintenance_daily_reviews")) {
      const rows = this.db
        .prepare(
          `SELECT id, review_date, group_key, reviewer_role, summary_markdown
           FROM maintenance_daily_reviews
           ORDER BY review_date DESC
           LIMIT 90`,
        )
        .all() as Array<Record<string, unknown>>;

      for (const row of rows) {
        this.createEntry({
          sourceTeam: String(row.group_key ?? "architecture"),
          sourceType: "review",
          repoKey: defaultRepoKey,
          userKey: defaultUserKey,
          title: `Daily review ${String(row.review_date ?? "")}`,
          content: String(row.summary_markdown ?? ""),
          confidence: 0.9,
          metadataJson: JSON.stringify({ reviewerRole: String(row.reviewer_role ?? "architecture_director") }),
          eventTs: `${String(row.review_date ?? "")}T00:00:00.000Z`,
          sourceKey: `daily-review:${String(row.id ?? "")}`,
        });
        inserted += 1;
      }
    }

    if (this.tableExists("task_outcomes")) {
      const rows = this.db
        .prepare(
          `SELECT id, recorded_at, agent_role, intent, succeeded, error_message
           FROM task_outcomes
           ORDER BY recorded_at DESC
           LIMIT 500`,
        )
        .all() as Array<Record<string, unknown>>;

      for (const row of rows) {
        const succeeded = Number(row.succeeded ?? 0) === 1;
        this.createEntry({
          sourceTeam: String(row.agent_role ?? "learning"),
          sourceType: "log",
          repoKey: defaultRepoKey,
          userKey: defaultUserKey,
          title: `Outcome: ${String(row.intent ?? "unknown")}`,
          content: succeeded ? "Task succeeded" : `Task failed: ${String(row.error_message ?? "unknown error")}`,
          confidence: succeeded ? 0.8 : 0.6,
          metadataJson: JSON.stringify({ succeeded }),
          eventTs: String(row.recorded_at ?? new Date().toISOString()),
          sourceKey: `task-outcome:${String(row.id ?? "")}`,
        });
        inserted += 1;
      }
    }

    return { inserted };
  }

  private tableExists(name: string): boolean {
    const row = this.db
      .prepare("SELECT COUNT(*) AS c FROM sqlite_master WHERE type = 'table' AND name = ?")
      .get(name) as { c: number };
    return row.c > 0;
  }
}

function rowToEntry(row: Record<string, unknown>): MetaBrainEntry {
  return {
    id: String(row.id ?? ""),
    createdAt: String(row.created_at ?? ""),
    eventTs: String(row.event_ts ?? ""),
    sourceTeam: String(row.source_team ?? ""),
    sourceType: String(row.source_type ?? "event") as MetaBrainSourceType,
    repoKey: String(row.repo_key ?? ""),
    userKey: String(row.user_key ?? ""),
    sessionId: (row.session_id as string | null) ?? undefined,
    title: String(row.title ?? ""),
    content: String(row.content ?? ""),
    confidence: Number(row.confidence ?? 0),
    tagsJson: String(row.tags_json ?? "[]"),
    metadataJson: String(row.metadata_json ?? "{}"),
    sourceKey: (row.source_key as string | null) ?? undefined,
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function confidenceTo01(confidence: string): number {
  if (confidence === "observed") return 1;
  if (confidence === "strong_inference") return 0.85;
  if (confidence === "weak_inference") return 0.6;
  return 0.4;
}
