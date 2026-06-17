import Database from 'better-sqlite3';
import crypto from 'crypto';
import path from 'path';

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface Job {
  id: string;
  script_name: string;
  status: JobStatus;
  priority: number;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

export class GenerationQueueService {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS generation_queue (
        id TEXT PRIMARY KEY,
        script_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        priority INTEGER NOT NULL DEFAULT 0,
        failure_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
    `);
  }

  enqueue(script_name: string, priority = 0): string {
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    this.db.prepare(`
      INSERT INTO generation_queue (id, script_name, status, priority, created_at, updated_at)
      VALUES (?, ?, 'pending', ?, ?, ?)
    `).run(id, script_name, priority, now, now);
    return id;
  }

  get(jobId: string): Job | null {
    return (this.db.prepare(
      `SELECT * FROM generation_queue WHERE id = ?`
    ).get(jobId) as Job | undefined) ?? null;
  }

  list(status?: JobStatus, limit = 100): Job[] {
    if (status) {
      return this.db.prepare(
        `SELECT * FROM generation_queue WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT ?`
      ).all(status, limit) as Job[];
    }
    return this.db.prepare(
      `SELECT * FROM generation_queue ORDER BY priority DESC, created_at ASC LIMIT ?`
    ).all(limit) as Job[];
  }

  markRunning(jobId: string): void {
    this.db.prepare(
      `UPDATE generation_queue SET status = 'running', updated_at = ? WHERE id = ?`
    ).run(new Date().toISOString(), jobId);
  }

  markCompleted(jobId: string): void {
    this.db.prepare(
      `UPDATE generation_queue SET status = 'completed', updated_at = ? WHERE id = ?`
    ).run(new Date().toISOString(), jobId);
  }

  markFailed(jobId: string, reason: string): void {
    this.db.prepare(
      `UPDATE generation_queue SET status = 'failed', failure_reason = ?, updated_at = ? WHERE id = ?`
    ).run(reason, new Date().toISOString(), jobId);
  }

  close(): void {
    this.db.close();
  }
}

// Singleton factory — one instance per DB path
const instances = new Map<string, GenerationQueueService>();

export function getGenerationQueueService(dbPath: string): GenerationQueueService {
  const resolved = path.resolve(dbPath);
  if (!instances.has(resolved)) {
    instances.set(resolved, new GenerationQueueService(resolved));
  }
  return instances.get(resolved)!;
}
