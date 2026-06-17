import Database from "better-sqlite3";
import { AgentContext, TaskContext } from "./context";
import { MemoryItem, MemoryACL } from "./memory-types";
import { CreatedMemoryResult, createMemoryFromStep } from "./memory-write";
import { ScoredMemory, filterAndRankMemories } from "./memory-retrieve";

export class MemoryStore {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.initSchema();
  }

  private initSchema() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memory_items (
        id TEXT PRIMARY KEY, project_id TEXT, owner_user_id TEXT, author_agent_id TEXT,
        scope TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, source_step_id INTEGER,
        task_purpose TEXT, sensitivity TEXT NOT NULL, created_at TEXT NOT NULL, last_used_at TEXT,
        expires_at TEXT, provenance_json TEXT);

      CREATE TABLE IF NOT EXISTS memory_acls (
        id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
        subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, can_read INTEGER NOT NULL, can_write INTEGER NOT NULL);

      CREATE TABLE IF NOT EXISTS memory_embeddings (
        memory_id TEXT PRIMARY KEY REFERENCES memory_items(id) ON DELETE CASCADE, embedding BLOB NOT NULL);

      CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_items(project_id);
      CREATE INDEX IF NOT EXISTS idx_memory_purpose ON memory_items(task_purpose);
      CREATE INDEX IF NOT EXISTS idx_memory_expires ON memory_items(expires_at);
      CREATE INDEX IF NOT EXISTS idx_acl_memory ON memory_acls(memory_id);
    `);
  }

  public createAndStoreMemoryFromStep(ctx: TaskContext, input: {
    text: string; kind: string; sourceStepId: number | null; sensitivity?: string; scopeOverride?: string;
    ownerUserIdOverride?: string | null; embedding?: Float32Array | null;
  }): MemoryItem {
    const { memory, acls } = createMemoryFromStep(ctx, {
      text: input.text, kind: input.kind as any, sourceStepId: input.sourceStepId,
      sensitivity: input.sensitivity as any, scopeOverride: input.scopeOverride as any,
      ownerUserIdOverride: input.ownerUserIdOverride ?? null,
    });

    const tx = this.db.transaction(() => {
      const insertMem = this.db.prepare(`INSERT INTO memory_items (id, project_id, owner_user_id, author_agent_id,
        scope, kind, text, source_step_id, task_purpose, sensitivity, created_at, last_used_at, expires_at, provenance_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`);

      insertMem.run(memory.id, memory.projectId, memory.ownerUserId, memory.authorAgentId, memory.scope, memory.kind,
        memory.text, memory.sourceStepId, memory.taskPurpose, memory.sensitivity, memory.createdAt,
        memory.lastUsedAt, memory.expiresAt, memory.provenanceJson ? JSON.stringify(memory.provenanceJson) : null);

      const insertAcl = this.db.prepare(`INSERT INTO memory_acls (memory_id, subject_type, subject_id, can_read, can_write)
        VALUES (?, ?, ?, ?, ?)`);
      for (const acl of acls) {
        insertAcl.run(memory.id, acl.subjectType, acl.subjectId, acl.canRead ? 1 : 0, acl.canWrite ? 1 : 0);
      }

      if (input.embedding) {
        const buf = Buffer.from(input.embedding.buffer, input.embedding.byteOffset, input.embedding.byteLength);
        const insertEmb = this.db.prepare(`INSERT OR REPLACE INTO memory_embeddings (memory_id, embedding) VALUES (?, ?)`);
        insertEmb.run(memory.id, buf);
      }
    });
    tx();
    return memory;
  }

  private getAclsForMemory(memoryId: string): MemoryACL[] {
    const rows = this.db.prepare(`SELECT id, memory_id, subject_type, subject_id, can_read, can_write FROM memory_acls WHERE memory_id = ?`).all(memoryId);
    return rows.map((r: any) => ({
      id: r.id, memoryId: r.memory_id, subjectType: r.subject_type, subjectId: r.subject_id,
      canRead: Boolean(r.can_read), canWrite: Boolean(r.can_write),
    }));
  }

  public filterAndRankForAgent(ctx: AgentContext, scoredCandidates: ScoredMemory[], opts?: { maxItems?: number; minScore?: number }): MemoryItem[] {
    return filterAndRankMemories(ctx, scoredCandidates, (memoryId) => this.getAclsForMemory(memoryId), opts);
  }

  public getRecentCandidatesForProject(projectId: string, purpose: string | null, limit: number): MemoryItem[] {
    const rows = this.db.prepare(`SELECT * FROM memory_items WHERE (project_id IS NULL OR project_id = ?)
      AND (task_purpose IS NULL OR task_purpose = COALESCE(?, task_purpose))
      AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP) ORDER BY created_at DESC LIMIT ?`).all(projectId, purpose, limit);

    return rows.map((r: any) => ({
      id: r.id, projectId: r.project_id, ownerUserId: r.owner_user_id, authorAgentId: r.author_agent_id,
      scope: r.scope, kind: r.kind, text: r.text, sourceStepId: r.source_step_id, taskPurpose: r.task_purpose,
      sensitivity: r.sensitivity, createdAt: r.created_at, lastUsedAt: r.last_used_at, expiresAt: r.expires_at,
      provenanceJson: r.provenance_json ? JSON.parse(r.provenance_json) : null,
    }));
  }

  public getEmbedding(memoryId: string): Float32Array | null {
    const row = this.db.prepare("SELECT embedding FROM memory_embeddings WHERE memory_id = ?").get(memoryId) as any;
    if (!row) return null;
    const buf: Buffer = row.embedding;
    // Copy to a new aligned ArrayBuffer — sliced Node.js Buffers may have non-4-byte-aligned
    // byteOffset which causes a RangeError when passed directly to Float32Array.
    const alignedBuffer = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    return new Float32Array(alignedBuffer);
  }

  public close() {
    this.db.close();
  }
}
