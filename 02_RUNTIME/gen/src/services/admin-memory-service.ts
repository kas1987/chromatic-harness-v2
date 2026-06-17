import Database from "better-sqlite3";
import { MemoryItem } from "../memory/memory-types";
import { MemoryScope, MemoryKind, SensitivityLevel } from "../memory/ids";

export interface ListMemoriesFilters {
  projectId?: string;
  scope?: MemoryScope;
  sensitivity?: SensitivityLevel;
  kind?: MemoryKind;
  limit?: number;
  offset?: number;
}

export interface UpdateMemoryPatch {
  text?: string;
  sensitivity?: SensitivityLevel;
  expiresAt?: string | null;
}

function rowToMemoryItem(r: any): MemoryItem {
  return {
    id: r.id,
    projectId: r.project_id ?? null,
    ownerUserId: r.owner_user_id ?? null,
    authorAgentId: r.author_agent_id ?? null,
    scope: r.scope,
    kind: r.kind,
    text: r.text,
    sourceStepId: r.source_step_id ?? null,
    taskPurpose: r.task_purpose ?? null,
    sensitivity: r.sensitivity,
    createdAt: r.created_at,
    lastUsedAt: r.last_used_at ?? null,
    expiresAt: r.expires_at ?? null,
    provenanceJson: r.provenance_json ? JSON.parse(r.provenance_json) : null,
  };
}

export class AdminMemoryService {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.ensureAdminColumns();
  }

  private ensureAdminColumns(): void {
    // Add soft-delete columns if they don't exist yet (idempotent migration)
    const tableInfo = this.db.prepare("PRAGMA table_info(memory_items)").all() as Array<{ name: string }>;
    const cols = new Set(tableInfo.map((c) => c.name));

    if (!cols.has("deleted_at")) {
      this.db.exec("ALTER TABLE memory_items ADD COLUMN deleted_at TEXT");
    }
    if (!cols.has("deletion_reason")) {
      this.db.exec("ALTER TABLE memory_items ADD COLUMN deletion_reason TEXT");
    }
  }

  public listMemories(filters: ListMemoriesFilters): { items: MemoryItem[]; total: number } {
    const limit = filters.limit ?? 50;
    const offset = filters.offset ?? 0;

    const conditions: string[] = ["deleted_at IS NULL"];
    const params: unknown[] = [];

    if (filters.projectId !== undefined) {
      conditions.push("project_id = ?");
      params.push(filters.projectId);
    }
    if (filters.scope !== undefined) {
      conditions.push("scope = ?");
      params.push(filters.scope);
    }
    if (filters.sensitivity !== undefined) {
      conditions.push("sensitivity = ?");
      params.push(filters.sensitivity);
    }
    if (filters.kind !== undefined) {
      conditions.push("kind = ?");
      params.push(filters.kind);
    }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

    const total = (
      this.db.prepare(`SELECT COUNT(*) as cnt FROM memory_items ${where}`).get(...params) as { cnt: number }
    ).cnt;

    const rows = this.db
      .prepare(`SELECT * FROM memory_items ${where} ORDER BY created_at DESC LIMIT ? OFFSET ?`)
      .all(...params, limit, offset);

    return { items: rows.map(rowToMemoryItem), total };
  }

  public getMemory(id: string): MemoryItem | null {
    const row = this.db
      .prepare("SELECT * FROM memory_items WHERE id = ? AND deleted_at IS NULL")
      .get(id);
    return row ? rowToMemoryItem(row) : null;
  }

  public updateMemory(id: string, patch: UpdateMemoryPatch): MemoryItem {
    const existing = this.getMemory(id);
    if (!existing) {
      throw new Error(`Memory not found: ${id}`);
    }

    const setClauses: string[] = [];
    const params: unknown[] = [];

    if (patch.text !== undefined) {
      setClauses.push("text = ?");
      params.push(patch.text);
    }
    if (patch.sensitivity !== undefined) {
      setClauses.push("sensitivity = ?");
      params.push(patch.sensitivity);
    }
    if ("expiresAt" in patch) {
      setClauses.push("expires_at = ?");
      params.push(patch.expiresAt ?? null);
    }

    if (setClauses.length === 0) {
      return existing;
    }

    params.push(id);
    this.db.prepare(`UPDATE memory_items SET ${setClauses.join(", ")} WHERE id = ?`).run(...params);

    const updated = this.getMemory(id);
    if (!updated) {
      throw new Error(`Memory disappeared after update: ${id}`);
    }
    return updated;
  }

  public deleteMemory(id: string, reason: string): void {
    const existing = this.getMemory(id);
    if (!existing) {
      throw new Error(`Memory not found: ${id}`);
    }

    const now = new Date().toISOString();
    this.db
      .prepare("UPDATE memory_items SET deleted_at = ?, deletion_reason = ? WHERE id = ?")
      .run(now, reason, id);
  }

  public scanConfidential(projectId?: string): MemoryItem[] {
    const conditions: string[] = ["sensitivity = 'confidential'", "deleted_at IS NULL"];
    const params: unknown[] = [];

    if (projectId !== undefined) {
      conditions.push("project_id = ?");
      params.push(projectId);
    }

    const rows = this.db
      .prepare(`SELECT * FROM memory_items WHERE ${conditions.join(" AND ")} ORDER BY created_at DESC`)
      .all(...params);
    return rows.map(rowToMemoryItem);
  }

  public findStale(olderThanDays: number): MemoryItem[] {
    const cutoff = new Date(Date.now() - olderThanDays * 24 * 60 * 60 * 1000).toISOString();

    // Stale = last_used_at is null or before cutoff, AND created_at is before cutoff, AND not deleted
    const rows = this.db
      .prepare(
        `SELECT * FROM memory_items
         WHERE deleted_at IS NULL
           AND (last_used_at IS NULL OR last_used_at < ?)
           AND created_at < ?
         ORDER BY created_at ASC`
      )
      .all(cutoff, cutoff);
    return rows.map(rowToMemoryItem);
  }

  public close(): void {
    this.db.close();
  }
}
