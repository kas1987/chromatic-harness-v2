/**
 * Memory store using better-sqlite3 for persistence
 */

import Database from "better-sqlite3";
import { MemoryItem, MemoryACL } from "./memory-types";
import { MemoryId, MemoryScope, MemoryKind, SensitivityLevel, TaskPurpose } from "./ids";

export class MemoryStore {
  private db: Database.Database;

  constructor(dbPath: string = "./gen.db") {
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
    this.initializeSchema();
  }

  private initializeSchema() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memory_items (
        id TEXT PRIMARY KEY,
        projectId TEXT NOT NULL,
        ownerUserId TEXT NOT NULL,
        authorAgentId TEXT NOT NULL,
        scope TEXT NOT NULL CHECK(scope IN ('agent_private', 'team_scoped', 'user_profile', 'global')),
        kind TEXT NOT NULL CHECK(kind IN ('summary', 'preference', 'decision', 'bug_fix')),
        text TEXT NOT NULL,
        sourceStepId TEXT,
        taskPurpose TEXT CHECK(taskPurpose IN ('code', 'debug', 'test', 'deploy', 'other')),
        sensitivity TEXT NOT NULL CHECK(sensitivity IN ('public', 'internal', 'confidential')),
        createdAt TEXT NOT NULL,
        lastAccessedAt TEXT,
        provenanceJson TEXT,
        UNIQUE(id)
      );

      CREATE TABLE IF NOT EXISTS memory_acls (
        id TEXT PRIMARY KEY,
        memoryId TEXT NOT NULL,
        subjectType TEXT NOT NULL CHECK(subjectType IN ('agent_id', 'project_id', 'user_id')),
        subjectId TEXT NOT NULL,
        canRead BOOLEAN NOT NULL,
        canWrite BOOLEAN NOT NULL,
        FOREIGN KEY(memoryId) REFERENCES memory_items(id),
        UNIQUE(memoryId, subjectType, subjectId)
      );

      CREATE INDEX IF NOT EXISTS idx_memory_items_projectId ON memory_items(projectId);
      CREATE INDEX IF NOT EXISTS idx_memory_items_ownerUserId ON memory_items(ownerUserId);
      CREATE INDEX IF NOT EXISTS idx_memory_items_createdAt ON memory_items(createdAt);
      CREATE INDEX IF NOT EXISTS idx_memory_acls_memoryId ON memory_acls(memoryId);
    `);
  }

  insertMemoryItem(item: MemoryItem): void {
    const stmt = this.db.prepare(`
      INSERT INTO memory_items (id, projectId, ownerUserId, authorAgentId, scope, kind, text, sourceStepId, taskPurpose, sensitivity, createdAt, lastAccessedAt, provenanceJson)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      item.id,
      item.projectId,
      item.ownerUserId,
      item.authorAgentId,
      item.scope,
      item.kind,
      item.text,
      item.sourceStepId,
      item.taskPurpose,
      item.sensitivity,
      item.createdAt,
      item.lastAccessedAt,
      item.provenanceJson
    );
  }

  insertMemoryACL(acl: MemoryACL): void {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO memory_acls (id, memoryId, subjectType, subjectId, canRead, canWrite)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      acl.id,
      acl.memoryId,
      acl.subjectType,
      acl.subjectId,
      acl.canRead,
      acl.canWrite
    );
  }

  getMemoryItemById(id: MemoryId): MemoryItem | null {
    const stmt = this.db.prepare("SELECT * FROM memory_items WHERE id = ?");
    return (stmt.get(id) as MemoryItem) || null;
  }

  getRecentMemoriesByProject(
    projectId: string,
    limit: number = 10
  ): MemoryItem[] {
    const stmt = this.db.prepare(`
      SELECT * FROM memory_items WHERE projectId = ? ORDER BY createdAt DESC LIMIT ?
    `);
    return (stmt.all(projectId, limit) as MemoryItem[]) || [];
  }

  getACLsByMemoryId(memoryId: MemoryId): MemoryACL[] {
    const stmt = this.db.prepare(
      "SELECT * FROM memory_acls WHERE memoryId = ?"
    );
    return (stmt.all(memoryId) as MemoryACL[]) || [];
  }

  close(): void {
    this.db.close();
  }
}
