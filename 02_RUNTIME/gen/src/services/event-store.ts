import Database from 'better-sqlite3';
import type { PrismEvent } from '../types/prism-event';

export class EventStore {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
    this.db.pragma('journal_mode = WAL');
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS prism_events (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        received_at TEXT NOT NULL,
        subject TEXT NOT NULL,
        body_text TEXT NOT NULL,
        sender TEXT,
        thread_id TEXT,
        url TEXT,
        metadata TEXT NOT NULL DEFAULT '{}',
        classification TEXT,
        actioned INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      )
    `);
  }

  insert(event: PrismEvent, classification?: string): void {
    const stmt = this.db.prepare(`
      INSERT OR IGNORE INTO prism_events
        (id, source, received_at, subject, body_text, sender, thread_id, url, metadata, classification)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      event.id, event.source, event.received_at, event.subject, event.body_text,
      event.sender ?? null, event.thread_id ?? null, event.url ?? null,
      JSON.stringify(event.metadata ?? {}),
      classification ?? null,
    );
  }

  getByWindow(since: string, until?: string): PrismEvent[] {
    const until_ = until ?? new Date().toISOString();
    const rows = this.db.prepare(
      `SELECT * FROM prism_events WHERE received_at >= ? AND received_at <= ? AND actioned = 0 ORDER BY received_at DESC`
    ).all(since, until_) as any[];
    return rows.map(r => ({ ...r, metadata: JSON.parse(r.metadata) }));
  }

  getByClassification(classification: string, limit = 100): PrismEvent[] {
    const rows = this.db.prepare(
      `SELECT * FROM prism_events WHERE classification = ? AND actioned = 0 ORDER BY received_at DESC LIMIT ?`
    ).all(classification, limit) as any[];
    return rows.map(r => ({ ...r, metadata: JSON.parse(r.metadata) }));
  }

  markActioned(id: string): void {
    this.db.prepare(`UPDATE prism_events SET actioned = 1 WHERE id = ?`).run(id);
  }

  count(): number {
    return (this.db.prepare(`SELECT COUNT(*) as c FROM prism_events`).get() as any).c;
  }
}
